#!/usr/bin/env python3

import gzip
import os
import re
import sqlite3
import sys
import warnings
from concurrent.futures import ThreadPoolExecutor


PROJECTS_BASE_DIR = os.path.abspath(os.environ.get("PROJECTS_BASE_DIR", "/proj"))
SQLITE_TIMEOUT_SECONDS = 60
SQLITE_BUSY_TIMEOUT_MS = 60000
TIMING_DETAIL_TABLE = "APR_TIMING_DETAIL"
TIMING_SUMMARY_TABLE = "APR_TIMING_SUMMARY"
TIMING_SUMMARY_COLUMNS = ("Mode", "TCheck", "TCorner", "Voltage", "Pathgroup")

warnings.filterwarnings("ignore")

RE_PATH_START = re.compile(r"^\s*Path\s+\d+:\s*(MET|VIOLATED)(.+)$", re.IGNORECASE)
RE_STARTPOINT = re.compile(r"^\s*Beginpoint:\s*(.+)$", re.IGNORECASE)
RE_ENDPOINT = re.compile(r"^\s*Endpoint:\s*(.+)$", re.IGNORECASE)
RE_GROUP = re.compile(r"^\s*Path\s+Group\s*:\s*([^\s]+)$", re.IGNORECASE)
RE_SLACK = re.compile(r"Slack\s+Time\s*([+\-]?\d+\.\d+)\s+(.+)$", re.IGNORECASE)


def get_voltage_list(design_file):
    """
    Function Name: get_voltage_list
    Purpose: Discover voltage corner names from the APR design inputs that help decode timing report paths.
    Input Params: design_file (str)
    Output: voltage_list (list[str])
    """
    voltage_list = []
    try:
        if not os.path.exists(design_file):
            return voltage_list

        if os.path.isdir(design_file):
            found = []
            for root, _dirs, files in os.walk(design_file):
                for name in files:
                    try:
                        with open(os.path.join(root, name), "r", encoding="utf-8", errors="ignore") as input_file:
                            found.extend(re.findall(r"\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b", input_file.read()))
                    except Exception:
                        continue
            return sorted(set(found), key=len, reverse=True)

        with open(design_file, "r", encoding="utf-8", errors="ignore") as input_file:
            voltage_list = sorted(
                set(re.findall(r"\b(?:WCL|WC|BCH|BC|TYP)[A-Za-z0-9_.+]*\b", input_file.read())),
                key=len,
                reverse=True,
            )
    except Exception:
        voltage_list = []
    return voltage_list


def parse_timing_args(filename, voltage_list=None):
    """
    Function Name: parse_timing_args
    Purpose: Parse one APR timing report path into its job, milestone, block, stage, mode, corner, and voltage parts.
    Input Params: filename (str), voltage_list (list[str] | None)
    Output: parts (list[str])
    """
    normalized_path = os.path.abspath(filename).replace("\\", "/").strip()
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
    """
    Function Name: get_timing_report_paths
    Purpose: Find the absolute timing report files under one run directory that belong to the requested APR stage.
    Input Params: rundir (str), stage (str)
    Output: report_paths (list[str])
    """
    pattern = re.compile(rf"(NORM|SHIFT|CAP|OCC).*{re.escape(stage)}_final_.*tarpt\.gz$", re.IGNORECASE)
    report_paths = []
    for root, _dirs, files in os.walk(os.path.abspath(rundir)):
        for name in files:
            if "all" in name.lower():
                continue
            full_path = os.path.abspath(os.path.join(root, name))
            normalized_path = full_path.replace("\\", "/")
            if pattern.search(normalized_path):
                report_paths.append(normalized_path)
    return sorted(report_paths)


def parse_report(reportpath, parts=None):
    """
    Function Name: parse_report
    Purpose: Parse one compressed APR timing report into detailed timing rows and an error flag.
    Input Params: reportpath (str), parts (list[str] | None)
    Output: outputs (tuple[list[tuple], bool])
    """
    rows = []
    parts = parts or parse_timing_args(reportpath)
    mode = parts[5]
    tcheck = parts[6]
    tcorner = parts[7]
    voltage = parts[8]
    had_error = False

    try:
        with gzip.open(reportpath, "rt", encoding="utf-8", errors="ignore") as input_file:
            timing = None
            startpoint = None
            endpoint = None
            pathgroup = None
            slack = None

            for line in input_file:
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
                    rows.append(
                        (
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
                        )
                    )
                    startpoint = None
                    endpoint = None
                    pathgroup = None
                    slack = None
    except Exception as exc:
        had_error = True
        print(f"Error parsing: {reportpath}: {exc}")

    return rows, had_error


def build_report_info(reportpath, voltage_cache=None):
    """
    Function Name: build_report_info
    Purpose: Build the cached metadata bundle needed to parse one APR timing report.
    Input Params: reportpath (str), voltage_cache (dict | None)
    Output: report_info (dict)
    """
    if voltage_cache is None:
        voltage_cache = {}
    normalized_path = os.path.abspath(reportpath).replace("\\", "/").strip()
    design_file = "/".join(normalized_path.split("/")[:-4])
    if design_file not in voltage_cache:
        voltage_cache[design_file] = get_voltage_list(design_file)

    parts = parse_timing_args(normalized_path, voltage_list=voltage_cache[design_file])
    return {
        "parts": parts,
        "path": normalized_path,
    }


def get_parse_worker_count(report_count):
    """
    Function Name: get_parse_worker_count
    Purpose: Choose how many parallel workers should parse APR timing reports for the current stage.
    Input Params: report_count (int)
    Output: worker_count (int)
    """
    if report_count <= 1:
        return 1
    return max(1, os.cpu_count() or 1)


def build_scope(parts):
    """
    Function Name: build_scope
    Purpose: Convert parsed APR report parts into the scope fields used for the timing database path.
    Input Params: parts (list[str])
    Output: scope (dict)
    """
    return {
        "Block": parts[3],
        "Job": parts[0],
        "Milestone": parts[2],
        "Stage": parts[4],
    }


def get_timing_db_path(project_code, scope):
    """
    Function Name: get_timing_db_path
    Purpose: Build the absolute DashAI timing database path for one APR stage extraction.
    Input Params: project_code (str), scope (dict)
    Output: db_path (str)
    """
    return os.path.abspath(os.path.join(
        PROJECTS_BASE_DIR,
        project_code,
        "DashAI",
        "APR_RUNS",
        scope["Block"],
        scope["Milestone"],
        scope["Job"],
        f'{scope["Stage"]}_timing.db',
    ))


def delete_existing_db_files(db_file):
    """
    Function Name: delete_existing_db_files
    Purpose: Remove any existing APR timing database file and its SQLite sidecar files before rewriting the stage DB.
    Input Params: db_file (str)
    Output: outputs (None)
    """
    db_file = os.path.abspath(db_file)
    for suffix in ("", "-wal", "-shm", "-journal"):
        candidate = f"{db_file}{suffix}"
        try:
            if os.path.exists(candidate):
                os.remove(candidate)
        except OSError:
            pass


def connect_db_file(db_file):
    """
    Function Name: connect_db_file
    Purpose: Open the APR timing SQLite database with the configured timeout and WAL settings.
    Input Params: db_file (str)
    Output: conn (sqlite3.Connection)
    """
    absolute_db_file = os.path.abspath(db_file)
    os.makedirs(os.path.dirname(absolute_db_file), exist_ok=True)
    conn = sqlite3.connect(absolute_db_file, timeout=SQLITE_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def ensure_timing_tables(conn):
    """
    Function Name: ensure_timing_tables
    Purpose: Create the APR timing summary and detail tables inside the stage database if they do not exist.
    Input Params: conn (sqlite3.Connection)
    Output: outputs (None)
    """
    conn.execute(
        f"""
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
        """
    )
    conn.execute(
        f"""
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
        """
    )


def ensure_timing_schema(conn):
    """
    Function Name: ensure_timing_schema
    Purpose: Apply the APR timing database schema to the current SQLite connection.
    Input Params: conn (sqlite3.Connection)
    Output: outputs (None)
    """
    ensure_timing_tables(conn)


def insert_timing_detail(conn, timing_data):
    """
    Function Name: insert_timing_detail
    Purpose: Insert parsed APR timing detail rows into the stage timing database.
    Input Params: conn (sqlite3.Connection), timing_data (dict)
    Output: outputs (None)
    """
    timing_rows = timing_data.get("timing_rows", [])
    if not timing_rows:
        return

    conn.executemany(
        f"""
        INSERT INTO {TIMING_DETAIL_TABLE} (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "Slack", "Endpoint", "Startpoint", "Timing", "Report"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        timing_rows,
    )


def get_summary_options(report_combos):
    """
    Function Name: get_summary_options
    Purpose: Build the per-column option lists used to compute APR timing summary rollups.
    Input Params: report_combos (set[tuple])
    Output: options (dict)
    """
    options = {}
    for index, column_name in enumerate(TIMING_SUMMARY_COLUMNS):
        values = sorted({combo[index] for combo in report_combos if combo[index] is not None})
        if column_name != "TCheck" and values:
            values.append("all")
        options[column_name] = values
    return options


def build_timing_summary_rows(timing_data):
    """
    Function Name: build_timing_summary_rows
    Purpose: Compute APR timing summary rows from the parsed violated timing endpoints.
    Input Params: timing_data (dict)
    Output: summary_rows (list[tuple])
    """
    report_combos = {tuple(combo) for combo in timing_data.get("report_combos", set())}
    options = get_summary_options(report_combos)
    if not all(options.get(column_name) for column_name in TIMING_SUMMARY_COLUMNS):
        return []

    combos = [[]]
    for column_name in TIMING_SUMMARY_COLUMNS:
        next_combos = []
        for combo in combos:
            for value in options[column_name]:
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
                "Pathgroup": row[4],
                "TCheck": row[1],
                "TCorner": row[2],
                "Voltage": row[3],
            }
            if any(filters[column_name] != "all" and row_values[column_name] != filters[column_name] for column_name in TIMING_SUMMARY_COLUMNS):
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

        summary_rows.append(
            (
                filters["Mode"],
                filters["TCheck"],
                filters["TCorner"],
                filters["Voltage"],
                filters["Pathgroup"],
                wns,
                tns,
                nvp,
            )
        )

    return summary_rows


def insert_timing_summary(conn, timing_data):
    """
    Function Name: insert_timing_summary
    Purpose: Insert the derived APR timing summary rows into the stage timing database.
    Input Params: conn (sqlite3.Connection), timing_data (dict)
    Output: outputs (None)
    """
    summary_rows = build_timing_summary_rows(timing_data)
    if not summary_rows:
        return

    conn.executemany(
        f"""
        INSERT INTO {TIMING_SUMMARY_TABLE} (
            "Mode", "TCheck", "TCorner", "Voltage", "Pathgroup",
            "WNS", "TNS", "NVP"
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        summary_rows,
    )


def write_timing_stage(conn, timing_data):
    """
    Function Name: write_timing_stage
    Purpose: Write both APR timing detail rows and summary rows into the current stage database transaction.
    Input Params: conn (sqlite3.Connection), timing_data (dict)
    Output: outputs (None)
    """
    insert_timing_detail(conn, timing_data)
    insert_timing_summary(conn, timing_data)


def write_timing_stage_db(project_code, stage, rundir):
    """
    Function Name: write_timing_stage_db
    Purpose: Parse every matching APR timing report for one stage and rebuild that stage timing database from scratch.
    Input Params: project_code (str), stage (str), rundir (str)
    Output: outputs (None)
    """
    reports = get_timing_report_paths(os.path.abspath(rundir), stage)
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
        "report_combos": {
            tuple(row[:5])
            for row in timing_rows
            if all(str(value or "").strip() for value in row[:5])
        },
        "report_count": len(report_infos),
        "timing_rows": timing_rows,
    }

    db_path = get_timing_db_path(project_code, scope)
    delete_existing_db_files(db_path)
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
    """
    Function Name: timing_db_per_stage
    Purpose: Run the APR timing extraction for one stage and return a process exit code for batch execution.
    Input Params: project_code (str), stage (str), rundir (str)
    Output: exit_code (int)
    """
    try:
        write_timing_stage_db(project_code, stage, rundir)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python APR_TIMING_INNOVUS.py <project_code> <stage> <rundir>")
        sys.exit(1)

    sys.exit(timing_db_per_stage(sys.argv[1], sys.argv[2], sys.argv[3]))
