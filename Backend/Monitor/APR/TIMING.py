#!/usr/bin/env python3

import gzip
import os
import re
import subprocess
import sys
import warnings

import APR_DB_Operations

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


def parse_timing_args(filename):
    parts = filename.strip().split("/")
    corners = ["WCL", "WC", "BCH", "BC", "TYP"]
    voltage = ""

    design_file = "/".join(filename.strip().split("/")[:-4])
    for voltage_name in get_voltage_list(design_file):
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
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def parse_report(reportpath):
    rows = []
    parts = parse_timing_args(reportpath)
    mode = parts[5]
    tcheck = parts[6]
    tcorner = parts[7]
    voltage = parts[8]

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
        print(f"Error parsing: {reportpath}: {exc}")

    return rows


def get_report_combo(reportpath):
    parts = parse_timing_args(reportpath)
    return tuple(parts[index] for index in (5, 6, 7, 8, 9))


def get_log_mtime(rundir, stage):
    log_path = os.path.join(rundir, "logs", f"{stage}.log")
    try:
        return int(os.path.getmtime(log_path))
    except OSError:
        return None


def build_timing_payload(project_code, stage, rundir, source_mtime=None):
    reports = get_timing_report_paths(rundir, stage)
    if not reports:
        return None

    first_parts = parse_timing_args(reports[0])
    timing_rows = []
    error_count = 0

    for report in reports:
        try:
            timing_rows.extend(parse_report(report))
        except Exception:
            error_count += 1

    return {
        "error_count": error_count,
        "report_combos": {get_report_combo(report) for report in reports},
        "report_count": len(reports),
        "scope": {
            "Job": first_parts[0],
            "Milestone": first_parts[2],
            "Block": first_parts[3],
            "Stage": first_parts[4],
        },
        "source_mtime": source_mtime if source_mtime is not None else get_log_mtime(rundir, stage),
        "timing_rows": timing_rows,
    }


def timing_db_per_stage(project_code, stage, rundir):
    payload = build_timing_payload(project_code, stage, rundir)
    if payload is None:
        print("No reports found")
        return 1

    db_path = APR_DB_Operations.get_db_path(f"/proj/{project_code}/DashAI")
    result = APR_DB_Operations.write_timing_stage_file(db_path, payload)
    print(
        f"Processed {result['report_count']} reports into {db_path} "
        f"with {result['row_count']} detail rows"
    )
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python TIMING.py <project_code> <stage> <rundir>")
        sys.exit(1)

    sys.exit(timing_db_per_stage(sys.argv[1], sys.argv[2], sys.argv[3]))
