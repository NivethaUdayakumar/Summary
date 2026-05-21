import csv
import os
from pathlib import Path

from Backend.Monitor.APR import APR_VARS


def get_kpi_report_path(log_path):
    """
    Function Name: get_kpi_report_path
    Purpose: Build the absolute KPI report path that matches the APR stage log currently being processed.
    Input Params: log_path (str)
    Output: report_path (str)
    """
    absolute_log_path = Path(os.path.abspath(log_path))
    return str(absolute_log_path.parent.parent / "reports" / f"{absolute_log_path.stem}.final.kpi.rpt")


def read_kpi_values(report_path):
    """
    Function Name: read_kpi_values
    Purpose: Read the KPI report and return the ordered KPI values extracted from its pipe-delimited rows.
    Input Params: report_path (str)
    Output: values (list[str])
    """
    values = []
    with open(report_path, "r", encoding="utf-8") as input_file:
        reader = csv.reader(input_file, delimiter="|")
        for index, row in enumerate(reader):
            if index < 2 or len(row) <= 1:
                continue
            columns = [item.strip() for item in row[1:-1]]
            values.append(columns[-1] if columns else "")
    return values


def extract_apr_kpi(log_path):
    """
    Function Name: extract_apr_kpi
    Purpose: Map KPI values from the stage KPI report onto the configured KPI column names for tracker updates.
    Input Params: log_path (str)
    Output: kpi_values (dict)
    """
    settings = APR_VARS.get_runtime_settings()
    try:
        values = read_kpi_values(get_kpi_report_path(log_path))
        return {
            column_name: (values[index] if index < len(values) else "")
            for index, column_name in enumerate(settings["KPI_COLUMNS"])
        }
    except Exception:
        return {column_name: "" for column_name in settings["KPI_COLUMNS"]}
