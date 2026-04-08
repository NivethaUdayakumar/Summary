import os
import re
import sys
import json
import time
import sqlite3
import signal
import subprocess
from pathlib import Path
from datetime import datetime

import psutil


ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_MONITOR_DIR = ROOT_DIR / "Backend" / "Monitor"
CONFIG_DIR = ROOT_DIR / "Configurations"
APPDATA_DIR = ROOT_DIR / "AppData"
APPDATA_DIR.mkdir(parents=True, exist_ok=True)

APP_PROJECT_JSON = CONFIG_DIR / "app.project.json"
PROJECTS_BASE_DIR = Path(os.environ.get("PROJECTS_BASE_DIR", "/proj"))
REGISTRY_DB = APPDATA_DIR / "monitor_registry.db"


class MonitorService:
    def __init__(self):
        self._init_registry()

    def _init_registry(self):
        conn = sqlite3.connect(REGISTRY_DB)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS monitor_registry (
                monitor_name TEXT PRIMARY KEY,
                project_code TEXT NOT NULL,
                template_name TEXT NOT NULL,
                script_path TEXT NOT NULL,
                pid INTEGER,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_started_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _connect_registry(self):
        conn = sqlite3.connect(REGISTRY_DB)
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _safe_name(self, value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_]+", value or ""))

    def list_projects(self):
        """
        Read project codes from:
        Configurations/app.project.json

        Example:
        {
            "project1": "Bond",
            "project2": "Clover"
        }

        Returns:
        ["project1", "project2"]
        """
        if not APP_PROJECT_JSON.exists():
            return []

        try:
            with open(APP_PROJECT_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                return sorted(list(data.keys()))

            return []
        except Exception:
            return []

    def list_templates(self):
        """
        Template names are folder names under:
        Backend/Monitor

        Example folders:
        APR
        STA

        Each template folder must contain:
        <TemplateName>.py
        Example:
        Backend/Monitor/APR/APR.py
        """
        templates = []
        if not BACKEND_MONITOR_DIR.exists():
            return templates

        for folder in BACKEND_MONITOR_DIR.iterdir():
            if not folder.is_dir():
                continue

            template_name = folder.name

            if template_name.startswith("__"):
                continue

            main_script = folder / f"{template_name}.py"
            if not main_script.exists():
                continue

            templates.append({
                "template_name": template_name,
                "script_path": str(main_script),
                "has_hide_runs": (folder / f"{template_name}_Hide_Runs.py").exists(),
                "has_update_run": (folder / f"{template_name}_Update_Run.py").exists()
            })
        return sorted(templates, key=lambda x: x["template_name"])

    def _get_template_info(self, template_name: str):
        for item in self.list_templates():
            if item["template_name"] == template_name:
                return item
        return None

    def get_project_db_path(self, project_code: str):
        return PROJECTS_BASE_DIR / project_code / "DB" / f"{project_code}_DB.db"

    def create_monitor(self, project_code: str, template_name: str):
        if not self._safe_name(project_code):
            raise ValueError("Invalid project_code")
        if not self._safe_name(template_name):
            raise ValueError("Invalid template_name")

        template_info = self._get_template_info(template_name)
        if not template_info:
            raise FileNotFoundError(f"Template not found: {template_name}")

        monitor_name = f"{project_code}_{template_name}"

        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT monitor_name FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        if cur.fetchone():
            conn.close()
            raise FileExistsError(f"Monitor already exists: {monitor_name}")

        now = self._now()
        cur.execute("""
            INSERT INTO monitor_registry (
                monitor_name, project_code, template_name, script_path,
                pid, status, created_at, updated_at, last_started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            monitor_name,
            project_code,
            template_name,
            template_info["script_path"],
            None,
            "created",
            now,
            now,
            None
        ))
        conn.commit()
        conn.close()

        return {
            "monitor_name": monitor_name,
            "project_code": project_code,
            "template_name": template_name,
            "status": "created"
        }

    def _is_pid_alive(self, pid):
        if not pid:
            return False
        try:
            proc = psutil.Process(pid)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except Exception:
            return False

    def _spawn_monitor(self, script_path: str, project_code: str):
        cmd = [sys.executable, script_path, project_code]

        kwargs = {
            "cwd": str(ROOT_DIR),
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["preexec_fn"] = os.setsid

        proc = subprocess.Popen(cmd, **kwargs)
        return proc.pid

    def start_monitor(self, monitor_name: str):
        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError("Monitor not found")

        pid = row["pid"]
        if self._is_pid_alive(pid):
            conn.close()
            return {
                "monitor_name": monitor_name,
                "pid": pid,
                "status": "running"
            }

        new_pid = self._spawn_monitor(row["script_path"], row["project_code"])
        now = self._now()

        cur.execute("""
            UPDATE monitor_registry
            SET pid = ?, status = ?, updated_at = ?, last_started_at = ?
            WHERE monitor_name = ?
        """, (new_pid, "running", now, now, monitor_name))
        conn.commit()
        conn.close()

        return {
            "monitor_name": monitor_name,
            "pid": new_pid,
            "status": "running"
        }

    def _kill_pid(self, pid: int):
        if not pid:
            return

        try:
            proc = psutil.Process(pid)
        except Exception:
            return

        try:
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.terminate()
                except Exception:
                    pass

            gone, alive = psutil.wait_procs(children, timeout=2)
            for child in alive:
                try:
                    child.kill()
                except Exception:
                    pass

            proc.terminate()
            try:
                proc.wait(timeout=3)
            except psutil.TimeoutExpired:
                proc.kill()
        except Exception:
            try:
                if os.name == "nt":
                    proc.kill()
                else:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
            except Exception:
                pass

    def stop_monitor(self, monitor_name: str):
        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError("Monitor not found")

        pid = row["pid"]
        if pid:
            self._kill_pid(pid)

        now = self._now()
        cur.execute("""
            UPDATE monitor_registry
            SET pid = NULL, status = ?, updated_at = ?
            WHERE monitor_name = ?
        """, ("stopped", now, monitor_name))
        conn.commit()
        conn.close()

        return {
            "monitor_name": monitor_name,
            "status": "stopped"
        }

    def restart_monitor(self, monitor_name: str):
        self.stop_monitor(monitor_name)
        time.sleep(0.3)
        return self.start_monitor(monitor_name)

    def terminate_monitor(self, monitor_name: str):
        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError("Monitor not found")

        pid = row["pid"]
        if pid:
            self._kill_pid(pid)

        cur.execute("DELETE FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        conn.commit()
        conn.close()

        return {
            "monitor_name": monitor_name,
            "status": "terminated"
        }

    def _get_latest_log(self, project_code: str, template_name: str):
        db_path = self.get_project_db_path(project_code)
        if not db_path.exists():
            return {"timestamp": "", "message": ""}

        table_name = f"{template_name}_LOG"

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cur.fetchone():
                conn.close()
                return {"timestamp": "", "message": ""}

            cur.execute(f'SELECT timestamp, message FROM "{table_name}" ORDER BY timestamp DESC LIMIT 1')
            row = cur.fetchone()
            conn.close()

            if not row:
                return {"timestamp": "", "message": ""}

            return {
                "timestamp": row["timestamp"] or "",
                "message": row["message"] or ""
            }
        except Exception:
            return {"timestamp": "", "message": ""}

    def _get_process_stats(self, pid):
        if not self._is_pid_alive(pid):
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "process_status": "not_running"
            }

        try:
            proc = psutil.Process(pid)
            return {
                "cpu_percent": round(proc.cpu_percent(interval=0.05), 2),
                "memory_mb": round(proc.memory_info().rss / (1024 * 1024), 2),
                "process_status": proc.status()
            }
        except Exception:
            return {
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "process_status": "unknown"
            }

    def list_monitors(self, project_code=None):
        conn = self._connect_registry()
        cur = conn.cursor()

        if project_code:
            cur.execute("SELECT * FROM monitor_registry WHERE project_code = ? ORDER BY monitor_name", (project_code,))
        else:
            cur.execute("SELECT * FROM monitor_registry ORDER BY monitor_name")

        rows = cur.fetchall()
        conn.close()

        template_map = {x["template_name"]: x for x in self.list_templates()}
        output = []

        for row in rows:
            pid = row["pid"]
            is_running = self._is_pid_alive(pid)

            effective_status = row["status"]
            if pid and is_running:
                effective_status = "running"
            elif row["status"] == "running" and not is_running:
                effective_status = "stopped"

            stats = self._get_process_stats(pid)
            latest_log = self._get_latest_log(row["project_code"], row["template_name"])
            template_info = template_map.get(row["template_name"], {})

            output.append({
                "monitor_name": row["monitor_name"],
                "project_code": row["project_code"],
                "template_name": row["template_name"],
                "pid": pid or "",
                "status": effective_status,
                "cpu_percent": stats["cpu_percent"],
                "memory_mb": stats["memory_mb"],
                "process_status": stats["process_status"],
                "last_log_timestamp": latest_log["timestamp"],
                "last_log_message": latest_log["message"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "last_started_at": row["last_started_at"] or "",
                "has_hide_runs": bool(template_info.get("has_hide_runs")),
                "has_update_run": bool(template_info.get("has_update_run"))
            })

        return output

    def get_tracker_table_data(self, project_code: str, template_name: str):
        if not self._safe_name(project_code):
            raise ValueError("Invalid project_code")
        if not self._safe_name(template_name):
            raise ValueError("Invalid template_name")

        db_path = self.get_project_db_path(project_code)
        if not db_path.exists():
            return {"columns": [], "rows": [], "primary_key": ""}

        table_name = f"{template_name}_Tracker"

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cur.fetchone():
            conn.close()
            return {"columns": [], "rows": [], "primary_key": ""}

        cur.execute(f'PRAGMA table_info("{table_name}")')
        info = cur.fetchall()
        columns = [x["name"] for x in info]

        cur.execute(f'SELECT * FROM "{table_name}"')
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()

        primary_key = ""
        for col in info:
            if col["pk"] == 1:
                primary_key = col["name"]
                break
        if not primary_key and columns:
            primary_key = columns[0]

        return {
            "columns": columns,
            "rows": rows,
            "primary_key": primary_key
        }

    def _run_script(self, script_path: Path, args):
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        cmd = [sys.executable, str(script_path)] + args
        result = subprocess.run(
            cmd,
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Script failed")

        return {
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }

    def hide_or_unhide_runs(self, project_code: str, template_name: str, run_ids, action: str):
        if action not in {"hide", "unhide"}:
            raise ValueError("Invalid action")

        script_path = BACKEND_MONITOR_DIR / template_name / f"{template_name}_Hide_Runs.py"
        return self._run_script(script_path, [project_code, action, json.dumps(run_ids)])

    def update_runs(self, project_code: str, template_name: str, run_ids):
        script_path = BACKEND_MONITOR_DIR / template_name / f"{template_name}_Update_Run.py"
        return self._run_script(script_path, [project_code, json.dumps(run_ids)])