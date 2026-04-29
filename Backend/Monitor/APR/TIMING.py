#!/usr/bin/env python3

import gzip
import os
import re
import sqlite3
import subprocess
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor

from APR_Definitions import (
    SQLITE_BUSY_TIMEOUT_MS,
    SQLITE_TIMEOUT_SECONDS,
    TIMING_DETAIL_TABLE,
    TIMING_SUMMARY_COLUMNS,
    TIMING_SUMMARY_TABLE,
)

warnings.filterwarnings("ignore")

RE_PATH_START = re.compile(r"^\s*Path\s+\d+:\s*(MET|VIOLATED)(.+)$", re.IGNORECASE)
RE_STARTPOINT = re.compile(r"^\s*Beginpoint:\s*(.+)$", re.IGNORECASE)
RE_ENDPOINT = re.compile(r"^\s*Endpoint:\s*(.+)$", re.IGNORECASE)
RE_GROUP = re.compile(r"^\s*Path\s+Group\s*:\s*([^\s]+)$", re.IGNORECASE)
RE_SLACK = re.compile(r"Slack\s+Time\s*([+\-]?\d+\.\d+)\s+(.+)$", re.IGNORECASE)


def get_voltage_list(design_file):
    voltage_list = []
    try:
        if not os.path.exists(design_file):
            return voltage_list

        if os.path.isdir(design_file):
            found = []
            for root, _, files in os.walk(design_file):
                for name in files:
                    try:
                        with open(os.path.join(root, name), "r", encoding="utf-8", errors="ignore") as infile:
                            found.extend(re.findall(r"\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b", infile.read()))
                    except Exception:
                        continue
            return sorted(set(found), key=len, reverse=True)

        with open(design_file, "r", encoding="utf-8", errors="ignore") as infile:
            voltage_list = sorted(
                set(re.findall(r"\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b", infile.read())),
                key=len,
                reverse=True,
            )
    except Exception:
        voltage_list = []
    return voltage_list


def parse_timing_args(filename, voltage_list=None):
    normalized_path = filename.replace("\\", "/").strip()
    parts = normalized_path.split("/")
    corners = ["WCL", "WC", "BCH", "BC", "TYP"]
    voltage = ""

    design_file = "/".join(parts[:-4])
    voltage_candidates = voltage_list if voltage_list is not None else get_voltage_list(design_file)
    for voltage_name in voltage_candidates:
        if voltage_name in parts[-2]:
            voltage = voltage_name
            break

    if not voltage:
        for corner_name in corners:
            if corner_name in parts[-2]:
                voltage = corner_name
                break

    mode = parts[-2].split("_")[0]
    check = parts[-2].split("_")[-1]
    corner = parts[-2].replace(mode + "_", "").replace("_" + check, "").replace(voltage, "")
    return [
        parts[-5],
        parts[2],
        parts[4],
        parts[5],
        parts[-1].replace(".tarpt.gz", "").split("_final_")[0],
        mode,
        check,
        corner,
        voltage,
        parts[-1].replace(".tarpt.gz", "").split("_final_")[-1],
    ]


def get_timing_report_paths(rundir, stage):
    grep_path = rf"(NORM|SHIFT|CAP|OCC).*{re.escape(stage)}_final_.*(tarpt\.gz)"
    command = f"find {rundir} | grep -Ei '{grep_path}' | grep -vi all"
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return sorted(line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip())


def parse_report(reportpath, parts=None):
    rows = []
    parts = parts or parse_timing_args(reportpath)
    mode = parts[5]
    tcheck = parts[6]
    tcorner = parts[7]
    voltage = parts[8]
    had_error = False

    try:
        with gzip.open(reportpath, "rt", encoding="utf-8", errors="ignore") as infile:
            timing = None
            startpoint = None
            endpoint = None
            pathgroup = None
            slack = None

            for line in infile:
                match = RE_PATH_START.match(line)
                if match:
                    timing = match.group(1)

                match = RE_STARTPOINT.match(line)
                if match:
                    startpoint = match.group(1)

                match = RE_ENDPOINT.match(line)
                if match:
                    endpoint = match.group(1)

                match = RE_GROUP.match(line)
                if match:
                    pathgroup = match.group(1)

                match = RE_SLACK.search(line)
                if match:
                    try:
                        slack = float(match.group(1))
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
                        reportpath,
                    ))
                    startpoint = None
                    endpoint = None
                    pathgroup = None
                    slack = None
    except Exception as exc:
        had_error = True
        print(f"Error parsing: {reportpath}: {exc}")

    return rows, had_error


def build_report_info(reportpath, voltage_cache=None):
    if voltage_cache is None:
        voltage_cache = {}
    normalized_path = reportpath.replace("\\", "/").strip()
    design_file = "/".join(normalized_path.split("/")[:-4])
    if design_file not in voltage_cache:
        voltage_cache[design_file] = get_voltage_list(design_file)

    parts = parse_timing_args(normalized_path, voltage_list=voltage_cache[design_file])
    return {
        "path": normalized_path,
        "parts": parts,
    }


def get_parse_worker_count(report_count):
    if report_count <= 1:
        return 1

    return max(1, os.cpu_count() or 1)


def build_scope(parts):
    return {
        "Job": parts[0],
        "Milestone": parts[2],
        "Block": parts[3],
        "Stage": parts[4],
    }


def get_timing_db_path(project_code, scope):
    return os.path.join(
        "/proj",
        project_code,
        "DashAI",
        "APR_RUNS",
        scope["Block"],
        scope["Milestone"],
        scope["Job"],
        f'{scope["Stage"]}.db',
    )


def connect_db_file(db_file):
    os.makedirs(os.path.dirname(os.path.abspath(db_file)), exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def ensure_columns(conn, table_name, column_defs):
    existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()}
    for column_name, column_type in column_defs:
        if column_name not in existing:
            conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}')


def ensure_timing_tables(conn):
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TIMING_SUMMARY_TABLE} (
            Mode TEXT,
            TCheck TEXT,
            TCorner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            WNS REAL,
            TNS REAL,
            NVP INTEGER
        )
    """)
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TIMING_DETAIL_TABLE} (
            Mode TEXT,
            TCheck TEXT,
            TCorner TEXT,
            Voltage TEXT,
            Pathgroup TEXT,
            Slack REAL,
            Endpoint TEXT,
            Startpoint TEXT,
            Timing TEXT,
            Report TEXT
        )
    """)

    ensure_columns(conn, TIMING_SUMMARY_TABLE, [
        ("Mode", "TEXT"),
        ("TCheck", "TEXT"),
        ("TCorner", "TEXT"),
        ("Voltage", "TEXT"),
        ("Pathgroup", "TEXT"),
        ("WNS", "REAL"),
        ("TNS", "REAL"),
        ("NVP", "INTEGER"),
    ])
    ensure_columns(conn, TIMING_DETAIL_TABLE, [
        ("Mode", "TEXT"),
        ("TCheck", "TEXT"),
        ("TCorner", "TEXT"),
        ("Voltage", "TEXT"),
        ("Pathgroup", "TEXT"),
        ("Slack", "REAL"),
        ("Endpoint", "TEXT"),
        ("Startpoint", "TEXT"),
        ("Timing", "TEXT"),
        ("Report", "TEXT"),
    ])


def ensure_timing_schema(conn):
    ensure_timing_tables(conn)


def delete_timing_stage_rows(conn):
    conn.execute(f'DELETE FROM {TIMING_DETAIL_TABLE}')
    conn.execute(f'DELETE FROM {TIMING_SUMMARY_TABLE}')


def insert_timing_detail(conn, timing_data):
    timing_rows = timing_data.get("timing_rows", [])
    if not timing_rows:
        return

    conn.executemany(f"""
        INSERT INTO {TIMING_DETAIL_TABLE} (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "Slack", "Endpoint", "Startpoint", "Timing", "Report"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, timing_rows)


def get_summary_options(report_combos):
    options = {}
    for index, column in enumerate(TIMING_SUMMARY_COLUMNS):
        values = sorted({combo[index] for combo in report_combos if combo[index] is not None})
        if column != "TCheck" and values:
            values.append("all")
        options[column] = values
    return options


def build_timing_summary_rows(timing_data):
    report_combos = {tuple(combo) for combo in timing_data.get("report_combos", set())}
    options = get_summary_options(report_combos)
    if not all(options.get(column) for column in TIMING_SUMMARY_COLUMNS):
        return []

    combos = [[]]
    for column in TIMING_SUMMARY_COLUMNS:
        next_combos = []
        for combo in combos:
            for value in options[column]:
                next_combos.append(combo + [value])
        combos = next_combos

    violated_rows = [row for row in timing_data.get("timing_rows", []) if row[8] == "VIOLATED"]
    summary_rows = []
    for combo in combos:
        combo_key = tuple(combo)
        if "all" not in combo_key and combo_key not in report_combos:
            continue

        filters = dict(zip(TIMING_SUMMARY_COLUMNS, combo))
        endpoint_slacks = {}
        for row in violated_rows:
            row_values = {
                "Mode": row[0],
                "TCheck": row[1],
                "TCorner": row[2],
                "Voltage": row[3],
                "Pathgroup": row[4],
            }
            if any(filters[column] != "all" and row_values[column] != filters[column] for column in TIMING_SUMMARY_COLUMNS):
                continue

            endpoint = row[6]
            slack = row[5]
            previous_slack = endpoint_slacks.get(endpoint)
            if previous_slack is None or slack < previous_slack:
                endpoint_slacks[endpoint] = slack

        if endpoint_slacks:
            slack_values = list(endpoint_slacks.values())
            wns = round(min(slack_values), 3)
            tns = round(sum(slack_values), 3)
            nvp = len(slack_values)
            if wns == 0.0:
                tns = 0.0
        else:
            wns, tns, nvp = 0.0, 0.0, 0

        summary_rows.append((
            filters["Mode"],
            filters["TCheck"],
            filters["TCorner"],
            filters["Voltage"],
            filters["Pathgroup"],
            wns,
            tns,
            nvp,
        ))

    return summary_rows


def insert_timing_summary(conn, timing_data):
    summary_rows = build_timing_summary_rows(timing_data)
    if not summary_rows:
        return

    conn.executemany(f"""
        INSERT INTO {TIMING_SUMMARY_TABLE} (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "WNS", "TNS", "NVP"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, summary_rows)


def write_timing_stage(conn, timing_data):
    delete_timing_stage_rows(conn)
    insert_timing_detail(conn, timing_data)
    insert_timing_summary(conn, timing_data)


def write_timing_stage_db(project_code, stage, rundir):
    reports = get_timing_report_paths(rundir, stage)
    if not reports:
        raise FileNotFoundError(f"No timing reports found for stage '{stage}' in '{rundir}'")

    voltage_cache = {}
    report_infos = []
    error_count = 0
    for report in reports:
        try:
            report_infos.append(build_report_info(report, voltage_cache=voltage_cache))
        except Exception as exc:
            error_count += 1
            print(f"Error preparing report: {report}: {exc}")

    if not report_infos:
        raise RuntimeError(f"Unable to prepare timing reports for stage '{stage}' in '{rundir}'")

    scope = build_scope(report_infos[0]["parts"])
    timing_rows = []

    worker_count = get_parse_worker_count(len(report_infos))
    if worker_count == 1:
        parsed_reports = [
            parse_report(report_info["path"], parts=report_info["parts"])
            for report_info in report_infos
        ]
    else:
        report_paths = [report_info["path"] for report_info in report_infos]
        report_parts = [report_info["parts"] for report_info in report_infos]
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="timing-report") as executor:
            parsed_reports = list(executor.map(parse_report, report_paths, report_parts))

    for rows, had_error in parsed_reports:
        timing_rows.extend(rows)
        if had_error:
            error_count += 1

    timing_data = {
        "error_count": error_count,
        "report_count": len(report_infos),
        "timing_rows": timing_rows,
        "report_combos": {
            tuple(row[:5])
            for row in timing_rows
            if all(str(value or "").strip() for value in row[:5])
        },
    }

    db_path = get_timing_db_path(project_code, scope)
    conn = connect_db_file(db_path)
    try:
        ensure_timing_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        try:
            write_timing_stage(conn, timing_data)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    finally:
        conn.close()


def timing_db_per_stage(project_code, stage, rundir):
    try:
        write_timing_stage_db(project_code, stage, rundir)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python TIMING.py <project_code> <stage> <rundir>")
        sys.exit(1)

    sys.exit(timing_db_per_stage(sys.argv[1], sys.argv[2], sys.argv[3]))
