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


def init_db(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_TIMING_SUMMARY (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Mode TEXT,
            Check TEXT,
            Corner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            WNS REAL,
            TNS REAL,
            NVP INTEGER
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_TIMING_DETAIL (
            Job TEXT,
            Milestone TEXT,
            Block TEXT,
            Stage TEXT,
            Mode TEXT,
            Check TEXT,
            Corner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            Slack REAL,
            Endpoint TEXT,
            Startpoint TEXT,
            Timing TEXT,
            Report TEXT
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_summary_main
        ON APR_TIMING_SUMMARY(Job, Milestone, Block, Stage)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_main
        ON APR_TIMING_DETAIL(Job, Milestone, Block, Stage)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_endpoint
        ON APR_TIMING_DETAIL(Endpoint)
    """)

    conn.commit()
    return conn


def clear_existing_run_rows(conn, job, milestone, block, stage):
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM APR_TIMING_SUMMARY
        WHERE Job = ? AND Milestone = ? AND Block = ? AND Stage = ?
    """, (job, milestone, block, stage))

    cur.execute("""
        DELETE FROM APR_TIMING_DETAIL
        WHERE Job = ? AND Milestone = ? AND Block = ? AND Stage = ?
    """, (job, milestone, block, stage))

    conn.commit()


def parse_report(reportpath):
    rows = []
    parts = parse_timing_args(reportpath)

    job = parts[0]
    milestone = parts[2]
    block = parts[3]
    stage = parts[6]
    mode = parts[7]
    check = parts[8]
    corner = parts[9]
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
                        job,
                        milestone,
                        block,
                        stage,
                        mode,
                        check,
                        corner,
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
            Job, Milestone, Block, Stage,
            Mode, Check, Corner, Voltage, Pathgroup,
            Slack, Endpoint, Startpoint, Timing, Report
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()


def get_distinct_values(conn, job, milestone, block, stage, column_name):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT "{column_name}"
        FROM APR_TIMING_DETAIL
        WHERE Job = ? AND Milestone = ? AND Block = ? AND Stage = ?
        ORDER BY "{column_name}"
    """, (job, milestone, block, stage))
    return [row[0] for row in cur.fetchall() if row[0] is not None]


def get_summary_options(conn, job, milestone, block, stage):
    cols = ["Mode", "Check", "Corner", "Voltage", "Pathgroup"]
    options = {}

    for col in cols:
        vals = get_distinct_values(conn, job, milestone, block, stage, col)
        if col != "Check" and vals:
            vals.append("all")
        options[col] = vals

    return cols, options


def query_violated_summary(conn, job, milestone, block, stage, filters):
    where = [
        'Job = ?',
        'Milestone = ?',
        'Block = ?',
        'Stage = ?',
        'Timing = "VIOLATED"'
    ]
    params = [job, milestone, block, stage]

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


def insert_timing_summary(conn, job, milestone, block, stage):
    cols, options = get_summary_options(conn, job, milestone, block, stage)

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
        filters = dict(zip(cols, combo))
        wns, tns, nvp = query_violated_summary(conn, job, milestone, block, stage, filters)

        summary_rows.append((
            job,
            milestone,
            block,
            stage,
            filters["Mode"],
            filters["Check"],
            filters["Corner"],
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
            Job, Milestone, Block, Stage,
            Mode, Check, Corner, Voltage, Pathgroup,
            WNS, TNS, NVP
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)
    conn.commit()


def summarize_stage_check(conn, job, milestone, block, stage, check_name):
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
            WHERE Job = ? AND Milestone = ? AND Block = ? AND Stage = ? AND Check = ?
        )
        SELECT
            MIN(Slack) AS WNS,
            COUNT(*) AS NVP,
            SUM(Slack) AS TNS
        FROM ranked
        WHERE rn = 1
    """

    cur = conn.cursor()
    cur.execute(query, (job, milestone, block, stage, check_name))
    row = cur.fetchone()

    if not row or row[0] is None:
        return "", "", ""

    wns = round(row[0], 3)
    nvp = int(row[1]) if row[1] is not None else 0
    tns = round(row[2], 3) if row[2] is not None else 0.0
    return wns, nvp, tns


def print_stage_summary(conn, job, milestone, block, stage):
    setup_wns, setup_nvp, setup_tns = summarize_stage_check(conn, job, milestone, block, stage, "SETUP")
    hold_wns, hold_nvp, hold_tns = summarize_stage_check(conn, job, milestone, block, stage, "HOLD")

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
    db_path = f"/proj/{project_code}/DashAI/DashAI_APR.db"

    reports = get_timing_report_paths(rundir, stage)
    print(f"Reports={reports}")

    if not reports:
        print("No reports found")
        return

    first_parts = parse_timing_args(reports[0])
    job = first_parts[0]
    milestone = first_parts[2]
    block = first_parts[3]

    conn = init_db(db_path)

    print(f"Deleting old rows for Job={job}, Milestone={milestone}, Block={block}, Stage={stage}")
    clear_existing_run_rows(conn, job, milestone, block, stage)

    t0 = time.time()

    print("Parsing timing reports")
    timing_rows, errors = process_timing_files(reports, max_workers=os.cpu_count())

    if timing_rows:
        print("Inserting APR_TIMING_DETAIL")
        insert_timing_detail(conn, timing_rows)

        print("Inserting APR_TIMING_SUMMARY")
        insert_timing_summary(conn, job, milestone, block, stage)

        print_stage_summary(conn, job, milestone, block, stage)

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