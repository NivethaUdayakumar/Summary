from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory

from Backend.Monitor.monitor_service import MonitorService


monitor_bp = Blueprint("monitor_bp", __name__)
service = MonitorService()

ROOT_DIR = Path(__file__).resolve().parents[2]
MONITOR_FRONTEND_DIR = ROOT_DIR / "Frontend" / "Pages" / "Monitor"


@monitor_bp.route("/monitor", methods=["GET"])
def monitor_page():
    return send_from_directory(MONITOR_FRONTEND_DIR, "Monitor.html")


@monitor_bp.route("/monitor_css", methods=["GET"])
def monitor_css():
    return send_from_directory(MONITOR_FRONTEND_DIR, "Monitor.css")


@monitor_bp.route("/monitor_js", methods=["GET"])
def monitor_js():
    return send_from_directory(MONITOR_FRONTEND_DIR, "Monitor.js")


@monitor_bp.route("/api/monitor/projects", methods=["GET"])
def monitor_projects():
    return jsonify({"ok": True, "projects": service.list_projects()})


@monitor_bp.route("/api/monitor/templates", methods=["GET"])
def monitor_templates():
    return jsonify({"ok": True, "templates": service.list_templates()})


@monitor_bp.route("/api/monitor/create", methods=["POST"])
def monitor_create():
    data = request.get_json(force=True)
    project_code = (data.get("project_code") or "").strip()
    template_name = (data.get("template_name") or "").strip()

    try:
        result = service.create_monitor(project_code, template_name)
        return jsonify({"ok": True, "data": result})
    except FileExistsError as e:
        return jsonify({"ok": False, "error": str(e)}), 409
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/start", methods=["POST"])
def monitor_start():
    data = request.get_json(force=True)
    monitor_name = (data.get("monitor_name") or "").strip()

    try:
        result = service.start_monitor(monitor_name)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/restart", methods=["POST"])
def monitor_restart():
    data = request.get_json(force=True)
    monitor_name = (data.get("monitor_name") or "").strip()

    try:
        result = service.restart_monitor(monitor_name)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/terminate", methods=["POST"])
def monitor_terminate():
    data = request.get_json(force=True)
    monitor_name = (data.get("monitor_name") or "").strip()

    try:
        result = service.terminate_monitor(monitor_name)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/list", methods=["GET"])
def monitor_list():
    project_code = (request.args.get("project_code") or "").strip() or None

    try:
        rows = service.list_monitors(project_code=project_code)
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/tracker", methods=["GET"])
def monitor_tracker():
    project_code = (request.args.get("project_code") or "").strip()
    template_name = (request.args.get("template_name") or "").strip()
    limit = request.args.get("limit", type=int)

    try:
        data = service.get_tracker_table_data(project_code, template_name, view_mode="visible", limit=limit)
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@monitor_bp.route("/api/monitor/update_runs", methods=["POST"])
def monitor_update_runs():
    data = request.get_json(force=True)
    project_code = (data.get("project_code") or "").strip()
    template_name = (data.get("template_name") or "").strip()
    run_rows = data.get("run_rows") or []

    try:
        result = service.update_runs(project_code, template_name, run_rows)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
