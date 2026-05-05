import importlib
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

MonitorService = importlib.import_module("Backend.Monitor.monitor_service").MonitorService


PORT = 4002
app = Flask(__name__, template_folder="templates", static_folder="static")
service = MonitorService()


def _success(**payload):
    return jsonify({"ok": True, **payload})


def _error(message, status_code=400):
    return jsonify({"ok": False, "error": str(message)}), status_code


@app.get("/")
def index():
    return render_template("index.html", port=PORT)


@app.get("/api/projects")
def api_projects():
    return _success(projects=service.list_projects())


@app.get("/api/templates")
def api_templates():
    return _success(templates=service.list_templates())


@app.get("/api/monitors")
def api_monitors():
    project_code = (request.args.get("project_code") or "").strip() or None
    return _success(monitors=service.list_monitors(project_code=project_code))


@app.post("/api/monitors")
def api_create_monitor():
    data = request.get_json(force=True)
    project_code = (data.get("project_code") or "").strip()
    template_name = (data.get("template_name") or "").strip()

    try:
        return _success(data=service.create_monitor(project_code, template_name))
    except FileExistsError as exc:
        return _error(exc, 409)
    except Exception as exc:
        return _error(exc, 400)


@app.post("/api/monitors/<monitor_name>/start")
def api_start_monitor(monitor_name):
    try:
        return _success(data=service.start_monitor(monitor_name))
    except FileNotFoundError as exc:
        return _error(exc, 404)
    except Exception as exc:
        return _error(exc, 400)


@app.post("/api/monitors/<monitor_name>/terminate")
def api_terminate_monitor(monitor_name):
    try:
        return _success(data=service.terminate_monitor(monitor_name))
    except FileNotFoundError as exc:
        return _error(exc, 404)
    except Exception as exc:
        return _error(exc, 400)


@app.delete("/api/monitors/<monitor_name>")
def api_delete_monitor(monitor_name):
    try:
        return _success(data=service.delete_monitor(monitor_name))
    except FileNotFoundError as exc:
        return _error(exc, 404)
    except Exception as exc:
        return _error(exc, 400)


if __name__ == "__main__":
    print(f"DashAI Monitoring running at http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False, use_reloader=False)
