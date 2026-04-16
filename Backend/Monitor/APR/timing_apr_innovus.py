#!/usr/bin/env python3

import os
import sys
import time
import gzip
import sqlite3
import warnings
import traceback
import re
import subprocess
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

warnings.filterwarnings("ignore")
now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

RE_PATH_START = re.compile(r'^\s*Path\s+\d+:\s*(MET|VIOLATED)(.+)$', re.IGNORECASE)
RE_STARTPOINT = re.compile(r'^\s*Beginpoint:\s*(.+)$', re.IGNORECASE)
RE_ENDPOINT = re.compile(r'^\s*Endpoint:\s*(.+)$', re.IGNORECASE)
RE_GROUP = re.compile(r'^\s*Path\s+Group\s*:\s*([^\s]+)$', re.IGNORECASE)
RE_SLACK = re.compile(r'Slack\s+Time\s*([+\-]?\d+\.\d+)\s+(.+)$', re.IGNORECASE)
SUMMARY_COLUMNS = ["Mode", "TCheck", "TCorner", "Voltage", "Pathgroup"]


def get_voltage_list(design_file):
    voltage_list = []
    try:
        if not os.path.exists(design_file):
            return voltage_list

        if os.path.isdir(design_file):
            collected = []
            for root, _, files in os.walk(design_file):
                for name in files:
                    fullpath = os.path.join(root, name)
                    try:
                        with open(fullpath, 'r', encoding='utf-8', errors='ignore') as infile:
                            content = infile.read()
                        found = re.findall(r'\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b', content)
                        collected.extend(found)
                    except Exception:
                        continue
            voltage_list = sorted(set(collected), key=len, reverse=True)
            return voltage_list

        with open(design_file, 'r', encoding='utf-8', errors='ignore') as infile:
            content = infile.read()

        found = re.findall(r'\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b', content)
        voltage_list = sorted(set(found), key=len, reverse=True)
    except Exception:
        voltage_list = []

    return voltage_list


def parse_timing_args(filename):
    parts = filename.strip().split('/')
    out = []
    corners = ['WCL', 'WC', 'BCH', 'BC', 'TYP']

    project = parts[2]
    milestone = parts[4]
    block = parts[5]
    flow = parts[6]
    tool = parts[7]
    job = parts[-5]
    stage = parts[-1].replace('.tarpt.gz', '').split('_final_')[0]
    mode = parts[-2].split('_')[0]
    check = parts[-2].split('_')[-1]
    pathgroup = parts[-1].replace('.tarpt.gz', '').split('_final_')[-1]
    design_file = "/".join(filename.strip().split('/')[:-4])

    voltage_list = get_voltage_list(design_file)
    voltage = ""

    for v in voltage_list:
        if v in parts[-2]:
            voltage = v
            break

    if not voltage:
        for c in corners:
            if c in parts[-2]:
                voltage = c
                break

    corner = parts[-2].replace(mode + "_", "").replace("_" + check, "").replace(voltage, "")
    args = [job, project, milestone, block, flow, tool, stage, mode, check, corner, voltage, pathgroup]
    out.extend(args)
    return out


def get_timing_report_paths(rundir, stage):
    grep_path = rf'(NORM|SHIFT|CAP|OCC).*{re.escape(stage)}_final_.*(tarpt\.gz)'
    cmd = f"find {rundir} | grep -Ei '{grep_path}' | grep -vi all"
    print("DEBUG shell pipeline:\n", cmd, "\n")
    results = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    results_list = [line.strip() for line in results.stdout.splitlines() if line.strip()]
    return results_list


def create_tables(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_TIMING_SUMMARY (
            "Mode" TEXT,
            "TCheck" TEXT,
            "TCorner" TEXT,
            "Voltage" TEXT,
            "Pathgroup" TEXT,
            "WNS" REAL,
            "TNS" REAL,
            "NVP" INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_TIMING_DETAIL (
            "Mode" TEXT,
            "TCheck" TEXT,
            "TCorner" TEXT,
            "Voltage" TEXT,
            "Pathgroup" TEXT,
            "Slack" REAL,
            "Endpoint" TEXT,
            "Startpoint" TEXT,
            "Timing" TEXT,
            "Report" TEXT
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_filters
        ON APR_TIMING_DETAIL("Mode", "TCheck", "TCorner", "Voltage", "Pathgroup", "Timing")
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_endpoint
        ON APR_TIMING_DETAIL("Endpoint")
    """)

    conn.commit()


def init_db(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    create_tables(conn)
    return conn


def clear_existing_run_rows(conn):
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS APR_TIMING_SUMMARY")
    cur.execute("DROP TABLE IF EXISTS APR_TIMING_DETAIL")

    conn.commit()


def parse_report(reportpath):
    rows = []
    parts = parse_timing_args(reportpath)

    mode = parts[7]
    tcheck = parts[8]
    tcorner = parts[9]
    voltage = parts[10]

    try:
        with gzip.open(reportpath, 'rt', encoding='utf-8', errors='ignore') as file:
            timing = None
            startpoint = None
            endpoint = None
            pathgroup = None
            slack = None

            for line in file:
                m = RE_PATH_START.match(line)
                if m:
                    timing = m.group(1)

                m = RE_STARTPOINT.match(line)
                if m:
                    startpoint = m.group(1)

                m = RE_ENDPOINT.match(line)
                if m:
                    endpoint = m.group(1)

                m = RE_GROUP.match(line)
                if m:
                    pathgroup = m.group(1)

                m = RE_SLACK.search(line)
                if m:
                    try:
                        slack = float(m.group(1))
                    except Exception:
                        slack = None

                if startpoint and endpoint and pathgroup and slack is not None:
                    rows.append((
                        mode,
                        tcheck,
                        tcorner,
                        voltage,
                        pathgroup,
                        slack,
                        endpoint,
                        startpoint,
                        timing,
                        reportpath
                    ))
                    startpoint = None
                    endpoint = None
                    pathgroup = None
                    slack = None

    except Exception as e:
        print(f"Error parsing: {reportpath}: {e}")

    return rows


def process_timing_files(paths, max_workers=os.cpu_count()):
    paths = list(map(str, paths))
    if not paths:
        return [], []

    all_rows = []
    errors = []

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        fut2p = {ex.submit(parse_report, p): p for p in paths}

        for fut in as_completed(fut2p):
            p = fut2p[fut]
            try:
                rows = fut.result()
                if rows:
                    all_rows.extend(rows)
                    print(f"No of non empty timing rows processed so far: {len(all_rows)}")
            except Exception:
                errors.append((p, traceback.format_exc()))

    if errors:
        print(f"No of error files: {len(errors)}")

    return all_rows, errors


def insert_timing_detail(conn, rows):
    if not rows:
        return

    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO APR_TIMING_DETAIL (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "Slack", "Endpoint", "Startpoint", "Timing", "Report"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()


def get_report_combo(reportpath):
    parts = parse_timing_args(reportpath)
    return tuple(parts[idx] for idx in (7, 8, 9, 10, 11))


def get_summary_options(report_combos):
    options = {}

    for idx, col in enumerate(SUMMARY_COLUMNS):
        vals = sorted({combo[idx] for combo in report_combos if combo[idx] is not None})
        if col != "TCheck" and vals:
            vals.append("all")
        options[col] = vals

    return SUMMARY_COLUMNS, options


def query_violated_summary(conn, filters):
    where = [
        'Timing = "VIOLATED"'
    ]
    params = []

    for col, value in filters.items():
        if value != "all":
            where.append(f'"{col}" = ?')
            params.append(value)

    where_sql = " AND ".join(where)

    query = f"""
        WITH ranked AS (
            SELECT
                Slack,
                Endpoint,
                ROW_NUMBER() OVER (
                    PARTITION BY Endpoint
                    ORDER BY Slack ASC, Endpoint ASC
                ) AS rn
            FROM APR_TIMING_DETAIL
            WHERE {where_sql}
        )
        SELECT
            MIN(Slack) AS WNS,
            SUM(Slack) AS TNS,
            COUNT(*) AS NVP
        FROM ranked
        WHERE rn = 1
    """

    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()

    if not row:
        return 0.0, 0.0, 0

    wns = round(row[0], 3) if row[0] is not None else 0.0
    tns = round(row[1], 3) if row[1] is not None else 0.0
    nvp = int(row[2]) if row[2] is not None else 0

    if wns == 0.0:
        tns = 0.0

    return wns, tns, nvp


def combo_has_exact_report(combo):
    return all(value != "all" for value in combo)


def insert_timing_summary(conn, report_combos):
    cols, options = get_summary_options(report_combos)

    if not all(options.get(c) for c in cols):
        print("No data found for summary generation")
        return

    combos = [[]]
    for col in cols:
        next_combos = []
        for combo in combos:
            for value in options[col]:
                next_combos.append(combo + [value])
        combos = next_combos

    summary_rows = []

    for combo in combos:
        if combo_has_exact_report(combo) and tuple(combo) not in report_combos:
            print(f"Skipping combination without report file: {combo}")
            continue

        filters = dict(zip(cols, combo))
        wns, tns, nvp = query_violated_summary(conn, filters)

        summary_rows.append((
            filters["Mode"],
            filters["TCheck"],
            filters["TCorner"],
            filters["Voltage"],
            filters["Pathgroup"],
            wns,
            tns,
            nvp
        ))

        print(f"COMBINATION {combo}")
        print(f"WNS={wns} TNS={tns} NVP={nvp}")

    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO APR_TIMING_SUMMARY (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "WNS", "TNS", "NVP"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)
    conn.commit()


def summarize_stage_tcheck(conn, tcheck_name):
    query = """
        WITH ranked AS (
            SELECT
                Slack,
                Endpoint,
                ROW_NUMBER() OVER (
                    PARTITION BY Endpoint
                    ORDER BY Slack ASC, Endpoint ASC
                ) AS rn
            FROM APR_TIMING_DETAIL
            WHERE "TCheck" = ?
        )
        SELECT
            MIN(Slack) AS WNS,
            COUNT(*) AS NVP,
            SUM(Slack) AS TNS
        FROM ranked
        WHERE rn = 1
    """

    cur = conn.cursor()
    cur.execute(query, (tcheck_name,))
    row = cur.fetchone()

    if not row or row[0] is None:
        return "", "", ""

    wns = round(row[0], 3)
    nvp = int(row[1]) if row[1] is not None else 0
    tns = round(row[2], 3) if row[2] is not None else 0.0
    return wns, nvp, tns


def print_stage_summary(conn):
    setup_wns, setup_nvp, setup_tns = summarize_stage_tcheck(conn, "SETUP")
    hold_wns, hold_nvp, hold_tns = summarize_stage_tcheck(conn, "HOLD")

    print("Stage summary")
    print({
        "setup_wns": setup_wns,
        "setup_nvp": setup_nvp,
        "setup_tns": setup_tns,
        "hold_wns": hold_wns,
        "hold_nvp": hold_nvp,
        "hold_tns": hold_tns
    })


def timing_db_per_stage(project_code, stage, rundir):
    reports = get_timing_report_paths(rundir, stage)
    print(f"Reports={reports}")

    if not reports:
        print("No reports found")
        return

    first_parts = parse_timing_args(reports[0])
    job = first_parts[0]
    milestone = first_parts[2]
    block = first_parts[3]
    db_path = f"/proj/{project_code}/DashAI/APR_RUNS/{block}/{milestone}/{job}/DashAI_{stage}.db"
    report_combos = {get_report_combo(report) for report in reports}

    conn = init_db(db_path)

    print(f"Dropping old timing tables in {db_path}")
    clear_existing_run_rows(conn)
    create_tables(conn)

    t0 = time.time()

    print("Parsing timing reports")
    timing_rows, errors = process_timing_files(reports, max_workers=os.cpu_count())

    if timing_rows:
        print("Inserting APR_TIMING_DETAIL")
        insert_timing_detail(conn, timing_rows)

        print("Inserting APR_TIMING_SUMMARY")
        insert_timing_summary(conn, report_combos)

        print_stage_summary(conn)

        timetaken = round(time.time() - t0, 2)
        hours = int(timetaken // 3600)
        minutes = int((timetaken % 3600) // 60)
        seconds = int(timetaken % 60)

        print(f"Time Taken to Process {len(reports)} reports: {hours} hour(s) {minutes} minute(s) {seconds} second(s)")
    else:
        print("No timing rows parsed")

    if errors:
        print(f"Error files count: {len(errors)}")

    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python timing_apr_innovus.py <project_code> <stage> <rundir>")
        sys.exit(1)

    project_code = sys.argv[1]
    stage = sys.argv[2]
    rundir = sys.argv[3]

    timing_db_per_stage(project_code, stage, rundir)
