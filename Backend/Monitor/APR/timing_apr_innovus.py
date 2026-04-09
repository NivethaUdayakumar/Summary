#!/usr/bin/env python3

import os
import sys
import time
import gzip
import sqlite3
import warnings
import traceback
import re
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

import apr_utils


warnings.filterwarnings("ignore")
now = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")

RE_PATH_START = re.compile(r'^\s*Path\s+\d+:\s*(MET|VIOLATED)(.+)$', re.IGNORECASE)
RE_STARTPOINT = re.compile(r'^\s*Beginpoint:\s*(.+)$', re.IGNORECASE)
RE_ENDPOINT = re.compile(r'^\s*Endpoint:\s*(.+)$', re.IGNORECASE)
RE_GROUP = re.compile(r'^\s*Path\s+Group\s*:\s*([^\s]+)$', re.IGNORECASE)
RE_SLACK = re.compile(r'Slack\s+Time\s*([+\-]?\d+\.\d+)\s+(.+)$', re.IGNORECASE)


def build_run_key(project_code, rundir, stage):
    return f"{project_code}|{os.path.abspath(rundir)}|{stage}"


def init_db(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_timing_detail (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL,
            project_code TEXT NOT NULL,
            rundir TEXT NOT NULL,
            stage TEXT NOT NULL,
            mode TEXT,
            check_name TEXT,
            corner TEXT,
            voltage TEXT,
            pathgroup TEXT,
            slack REAL,
            endpoint TEXT,
            startpoint TEXT,
            timing TEXT,
            report TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS APR_timing_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_key TEXT NOT NULL,
            project_code TEXT NOT NULL,
            rundir TEXT NOT NULL,
            stage TEXT NOT NULL,
            mode TEXT,
            check_name TEXT,
            corner TEXT,
            voltage TEXT,
            pathgroup TEXT,
            wns REAL,
            tns REAL,
            nvp INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_run_key ON APR_timing_detail(run_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_stage ON APR_timing_detail(stage)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_pathgroup ON APR_timing_detail(pathgroup)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_check_name ON APR_timing_detail(check_name)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_detail_endpoint ON APR_timing_detail(endpoint)")

    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_summary_run_key ON APR_timing_summary(run_key)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_summary_stage ON APR_timing_summary(stage)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_apr_timing_summary_pathgroup ON APR_timing_summary(pathgroup)")

    conn.commit()
    return conn


def clear_run_data(conn, run_key):
    cur = conn.cursor()
    cur.execute("DELETE FROM APR_timing_detail WHERE run_key = ?", (run_key,))
    cur.execute("DELETE FROM APR_timing_summary WHERE run_key = ?", (run_key,))
    conn.commit()


def parse_report(reportpath):
    rows = []
    parts = apr_utils.parse_timing_args(reportpath)

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
                        parts[7],      # mode
                        parts[8],      # check_name
                        parts[9],      # corner
                        parts[10],     # voltage
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


def insert_timing_detail(conn, project_code, rundir, stage, run_key, rows):
    if not rows:
        return

    cur = conn.cursor()
    ts = now()

    payload = []
    for r in rows:
        payload.append((
            run_key,
            project_code,
            os.path.abspath(rundir),
            stage,
            r[0],   # mode
            r[1],   # check_name
            r[2],   # corner
            r[3],   # voltage
            r[4],   # pathgroup
            r[5],   # slack
            r[6],   # endpoint
            r[7],   # startpoint
            r[8],   # timing
            r[9],   # report
            ts
        ))

    cur.executemany("""
        INSERT INTO APR_timing_detail (
            run_key, project_code, rundir, stage,
            mode, check_name, corner, voltage,
            pathgroup, slack, endpoint, startpoint,
            timing, report, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, payload)

    conn.commit()


def get_distinct_values(conn, run_key, column_name):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT {column_name}
        FROM APR_timing_detail
        WHERE run_key = ?
        ORDER BY {column_name}
    """, (run_key,))
    return [row[0] for row in cur.fetchall() if row[0] is not None]


def get_summary_options(conn, run_key):
    cols = ["mode", "check_name", "corner", "voltage", "pathgroup"]
    options = {}

    for col in cols:
        vals = get_distinct_values(conn, run_key, col)
        if col != "check_name" and vals:
            vals.append("all")
        options[col] = vals

    return cols, options


def query_violated_summary(conn, run_key, filters):
    where = ["run_key = ?", "timing = 'VIOLATED'"]
    params = [run_key]

    for col, value in filters.items():
        if value != "all":
            where.append(f"{col} = ?")
            params.append(value)

    where_sql = " AND ".join(where)

    query = f"""
        WITH ranked AS (
            SELECT
                slack,
                endpoint,
                ROW_NUMBER() OVER (
                    PARTITION BY endpoint
                    ORDER BY slack ASC, endpoint ASC
                ) AS rn
            FROM APR_timing_detail
            WHERE {where_sql}
        )
        SELECT
            MIN(slack) AS wns,
            SUM(slack) AS tns,
            COUNT(*) AS nvp
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


def insert_timing_summary(conn, project_code, rundir, stage, run_key):
    cols, options = get_summary_options(conn, run_key)

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
    ts = now()

    for combo in combos:
        filters = dict(zip(cols, combo))
        wns, tns, nvp = query_violated_summary(conn, run_key, filters)

        summary_rows.append((
            run_key,
            project_code,
            os.path.abspath(rundir),
            stage,
            filters["mode"],
            filters["check_name"],
            filters["corner"],
            filters["voltage"],
            filters["pathgroup"],
            wns,
            tns,
            nvp,
            ts
        ))

        print(f"COMBINATION {combo}")
        print(f"WNS={wns} TNS={tns} NVP={nvp}")

    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO APR_timing_summary (
            run_key, project_code, rundir, stage,
            mode, check_name, corner, voltage, pathgroup,
            wns, tns, nvp, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)

    conn.commit()


def summarize_stage_check(conn, run_key, check_name):
    query = """
        WITH ranked AS (
            SELECT
                slack,
                endpoint,
                ROW_NUMBER() OVER (
                    PARTITION BY endpoint
                    ORDER BY slack ASC, endpoint ASC
                ) AS rn
            FROM APR_timing_detail
            WHERE run_key = ? AND check_name = ?
        )
        SELECT
            MIN(slack) AS wns,
            COUNT(*) AS nvp,
            SUM(slack) AS tns
        FROM ranked
        WHERE rn = 1
    """

    cur = conn.cursor()
    cur.execute(query, (run_key, check_name))
    row = cur.fetchone()

    if not row or row[0] is None:
        return "", "", ""

    wns = round(row[0], 3)
    nvp = int(row[1]) if row[1] is not None else 0
    tns = round(row[2], 3) if row[2] is not None else 0.0
    return wns, nvp, tns


def print_stage_summary(conn, run_key):
    setup_wns, setup_nvp, setup_tns = summarize_stage_check(conn, run_key, "SETUP")
    hold_wns, hold_nvp, hold_tns = summarize_stage_check(conn, run_key, "HOLD")

    print("Stage summary")
    print({
        "setup_wns": setup_wns,
        "setup_nvp": setup_nvp,
        "setup_tns": setup_tns,
        "hold_wns": hold_wns,
        "hold_nvp": hold_nvp,
        "hold_tns": hold_tns
    })


def timing_db_per_stage(project_code, rundir, stage, db_path):
    run_key = build_run_key(project_code, rundir, stage)

    conn = init_db(db_path)

    print(f"run_key={run_key}")
    print("Deleting old rows for this run_key")
    clear_run_data(conn, run_key)

    reports = apr_utils.get_timing_report_paths(rundir, stage)
    print(f"Reports={reports}")

    if not reports:
        print("No reports found")
        conn.close()
        return

    t0 = time.time()

    print("Parsing timing reports")
    timing_rows, errors = process_timing_files(reports, max_workers=os.cpu_count())

    if timing_rows:
        print("Inserting APR_timing_detail")
        insert_timing_detail(conn, project_code, rundir, stage, run_key, timing_rows)

        print("Inserting APR_timing_summary")
        insert_timing_summary(conn, project_code, rundir, stage, run_key)

        print_stage_summary(conn, run_key)

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


def print_available_commands():
    print("Available Functions")
    print("[1] parse_report(reportpath)")
    print("[2] process_timing_files(paths, max_workers)")
    print("[3] insert_timing_detail(conn, project_code, rundir, stage, run_key, rows)")
    print("[4] insert_timing_summary(conn, project_code, rundir, stage, run_key)")
    print("[5] timing_db_per_stage(project_code, rundir, stage, db_path)")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python db_timing_innovus.py <project_code> <rundir> <stage> <db_path>")
        sys.exit(1)

    project_code = sys.argv[1]
    rundir = sys.argv[2]
    stage = sys.argv[3]
    db_path = sys.argv[4]

    timing_db_per_stage(project_code, rundir, stage, db_path)