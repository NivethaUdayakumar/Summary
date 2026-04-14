import os
import re
import sys
import json
import time
import sqlite3
import signal
import subprocess
import importlib.util
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
TRACKER_PREVIEW_ROWS = 100


class MonitorService:
    def __init__(self):
        self._log_cache = {}
        self._process_cache = {}
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
                "has_hide_runs": True,
                "has_update_run": True
            })

        return sorted(templates, key=lambda x: x["template_name"])

    def _get_template_info(self, template_name: str):
        for item in self.list_templates():
            if item["template_name"] == template_name:
                return item
        return None

    def _get_template_dir(self, template_name: str):
        return BACKEND_MONITOR_DIR / template_name

    def get_project_db_path(self, project_code: str, template_name: str):
        return PROJECTS_BASE_DIR / project_code / "DashAI" / f"DashAI_{template_name}.db"

    def get_project_log_dir(self, project_code: str, template_name: str):
        return PROJECTS_BASE_DIR / project_code / "DashAI" / f"Logs{template_name}"

    def _load_python_module(self, module_path: Path, module_name: str):
        if not module_path.exists():
            raise FileNotFoundError(f"Module not found: {module_path}")

        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module: {module_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _load_template_modules(self, template_name: str):
        template_dir = self._get_template_dir(template_name)
        db_ops_path = template_dir / f"{template_name}_DB_Operations.py"
        defs_path = template_dir / f"{template_name}_Definitions.py"

        db_ops = self._load_python_module(db_ops_path, f"{template_name}_db_ops")
        defs = self._load_python_module(defs_path, f"{template_name}_defs")
        return db_ops, defs

    def _make_state_key(self, defs_module, job: str, milestone: str, block: str, stage: str):
        if hasattr(defs_module, "make_key"):
            return defs_module.make_key(job, milestone, block, stage)
        if hasattr(defs_module, "make_state_key"):
            return defs_module.make_state_key(job, milestone, block, stage)
        return f"{job}-{milestone}-{block}-{stage}"

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

    def _get_process_snapshot(self, pid):
        if not pid:
            return {
                "is_running": False,
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "process_status": "not_running"
            }

        cache_entry = self._process_cache.get(pid)
        proc = cache_entry["proc"] if cache_entry else None
        is_new_proc = proc is None

        try:
            if proc is None:
                proc = psutil.Process(pid)

            if not proc.is_running():
                raise psutil.NoSuchProcess(pid)

            process_status = proc.status()
            if process_status == psutil.STATUS_ZOMBIE:
                raise psutil.NoSuchProcess(pid)

            if is_new_proc:
                proc.cpu_percent(interval=None)
                cpu_percent = 0.0
            else:
                cpu_percent = round(proc.cpu_percent(interval=None), 2)

            memory_mb = round(proc.memory_info().rss / (1024 * 1024), 2)
            self._process_cache[pid] = {"proc": proc}

            return {
                "is_running": True,
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "process_status": process_status
            }
        except Exception:
            self._process_cache.pop(pid, None)
            return {
                "is_running": False,
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "process_status": "not_running"
            }

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

            _, alive = psutil.wait_procs(children, timeout=2)
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
        finally:
            self._process_cache.pop(pid, None)

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
        log_dir = self.get_project_log_dir(project_code, template_name)
        if not log_dir.exists():
            self._log_cache.pop(str(log_dir), None)
            return {"timestamp": "", "message": ""}

        try:
            dir_key = str(log_dir)
            dir_stat = log_dir.stat()
            dir_mtime_ns = getattr(dir_stat, "st_mtime_ns", int(dir_stat.st_mtime * 1_000_000_000))
            cached = self._log_cache.get(dir_key)

            if cached:
                cached_file = Path(cached["file_path"]) if cached.get("file_path") else None
                if cached_file and cached_file.exists():
                    file_stat = cached_file.stat()
                    file_mtime_ns = getattr(file_stat, "st_mtime_ns", int(file_stat.st_mtime * 1_000_000_000))
                    if (
                        cached.get("dir_mtime_ns") == dir_mtime_ns
                        and cached.get("file_mtime_ns") == file_mtime_ns
                        and cached.get("file_size") == file_stat.st_size
                    ):
                        return {
                            "timestamp": cached.get("timestamp", ""),
                            "message": cached.get("message", "")
                        }

            latest_file = None
            latest_file_mtime_ns = -1

            for candidate in log_dir.glob("*.log"):
                try:
                    candidate_stat = candidate.stat()
                except OSError:
                    continue

                candidate_mtime_ns = getattr(
                    candidate_stat,
                    "st_mtime_ns",
                    int(candidate_stat.st_mtime * 1_000_000_000)
                )

                if candidate_mtime_ns > latest_file_mtime_ns:
                    latest_file = candidate
                    latest_file_mtime_ns = candidate_mtime_ns

            if latest_file is None:
                self._log_cache[dir_key] = {
                    "dir_mtime_ns": dir_mtime_ns,
                    "file_path": "",
                    "file_mtime_ns": 0,
                    "file_size": 0,
                    "timestamp": "",
                    "message": ""
                }
                return {"timestamp": "", "message": ""}

            file_stat = latest_file.stat()
            file_mtime_ns = getattr(file_stat, "st_mtime_ns", int(file_stat.st_mtime * 1_000_000_000))
            last_line = self._read_last_nonempty_line(latest_file)

            if not last_line:
                result = {"timestamp": "", "message": ""}
            else:
                parts = last_line.split("|", 1)
                if len(parts) == 2:
                    result = {
                        "timestamp": parts[0].strip(),
                        "message": parts[1].strip()
                    }
                else:
                    result = {
                        "timestamp": "",
                        "message": last_line
                    }

            self._log_cache[dir_key] = {
                "dir_mtime_ns": dir_mtime_ns,
                "file_path": str(latest_file),
                "file_mtime_ns": file_mtime_ns,
                "file_size": file_stat.st_size,
                "timestamp": result["timestamp"],
                "message": result["message"]
            }

            return result
        except Exception:
            return {"timestamp": "", "message": ""}

    def _read_last_nonempty_line(self, file_path: Path, chunk_size: int = 4096):
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            file_size = f.tell()

            if file_size == 0:
                return ""

            buffer = b""
            position = file_size

            while position > 0:
                read_size = min(chunk_size, position)
                position -= read_size
                f.seek(position)
                buffer = f.read(read_size) + buffer

                lines = buffer.splitlines()
                if position > 0 and buffer[:1] not in {b"\n", b"\r"} and lines:
                    buffer = lines[0]
                    lines = lines[1:]
                else:
                    buffer = b""

                for line in reversed(lines):
                    text = line.decode("utf-8", errors="ignore").strip()
                    if text:
                        return text

            return buffer.decode("utf-8", errors="ignore").strip()

    def list_monitors(self, project_code=None):
        conn = self._connect_registry()
        cur = conn.cursor()

        if project_code:
            cur.execute("SELECT * FROM monitor_registry WHERE project_code = ? ORDER BY monitor_name", (project_code,))
        else:
            cur.execute("SELECT * FROM monitor_registry ORDER BY monitor_name")

        rows = cur.fetchall()
        conn.close()

        output = []

        for row in rows:
            pid = row["pid"]
            stats = self._get_process_snapshot(pid)
            is_running = stats["is_running"]

            effective_status = row["status"]
            if pid and is_running:
                effective_status = "running"
            elif row["status"] == "running" and not is_running:
                effective_status = "stopped"

            latest_log = self._get_latest_log(row["project_code"], row["template_name"])

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
                "has_hide_runs": True,
                "has_update_run": True
            })

        return output

    def get_tracker_table_data(self, project_code: str, template_name: str, view_mode: str = "visible", limit: int = TRACKER_PREVIEW_ROWS):
        if not self._safe_name(project_code):
            raise ValueError("Invalid project_code")
        if not self._safe_name(template_name):
            raise ValueError("Invalid template_name")
        if view_mode not in {"visible", "hidden", "all"}:
            raise ValueError("Invalid view_mode")

        try:
            limit = max(1, min(int(limit), TRACKER_PREVIEW_ROWS))
        except (TypeError, ValueError):
            limit = TRACKER_PREVIEW_ROWS

        db_path = self.get_project_db_path(project_code, template_name)
        table_name = f"{template_name}_Tracker"

        if not db_path.exists():
            return {
                "columns": [],
                "rows": [],
                "table_name": table_name,
                "id_columns": ["Job", "Milestone", "Block", "Stage"],
                "row_limit": limit,
                "displayed_rows": 0,
                "has_more": False,
                "view_mode": view_mode
            }

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        try:
            cur = conn.cursor()

            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cur.fetchone():
                return {
                    "columns": [],
                    "rows": [],
                    "table_name": table_name,
                    "id_columns": ["Job", "Milestone", "Block", "Stage"],
                    "row_limit": limit,
                    "displayed_rows": 0,
                    "has_more": False,
                    "view_mode": view_mode
                }

            cur.execute(f'PRAGMA table_info("{table_name}")')
            info = cur.fetchall()
            columns = [x["name"] for x in info]

            has_hidden_column = "Hidden" in columns
            where_sql = ""
            params = []

            if has_hidden_column and view_mode in {"visible", "hidden"}:
                where_sql = ' WHERE COALESCE("Hidden", 0) = ?'
                params.append(1 if view_mode == "hidden" else 0)

            cur.execute(f'SELECT * FROM "{table_name}"{where_sql} LIMIT ?', params + [limit + 1])
            fetched_rows = cur.fetchall()
            has_more = len(fetched_rows) > limit
            rows = [dict(r) for r in fetched_rows[:limit]]
        finally:
            conn.close()

        return {
            "columns": columns,
            "rows": rows,
            "table_name": table_name,
            "id_columns": ["Job", "Milestone", "Block", "Stage"],
            "row_limit": limit,
            "displayed_rows": len(rows),
            "has_more": has_more,
            "view_mode": view_mode
        }

    def _queue_template_action(self, project_code: str, template_name: str, run_rows, action_name: str):
        if not self._safe_name(project_code):
            raise ValueError("Invalid project_code")
        if not self._safe_name(template_name):
            raise ValueError("Invalid template_name")

        db_ops, defs = self._load_template_modules(template_name)
        db_file = self.get_project_db_path(project_code, template_name)

        if not db_file.exists():
            raise FileNotFoundError(f"DB not found: {db_file}")

        if not hasattr(db_ops, "connect_db_file"):
            raise AttributeError(f"{template_name}_DB_Operations.py is missing connect_db_file()")

        conn = db_ops.connect_db_file(str(db_file))

        queued = 0
        try:
            for row in run_rows:
                job = str(row.get("Job", "")).strip()
                milestone = str(row.get("Milestone", "")).strip()
                block = str(row.get("Block", "")).strip()
                stage = str(row.get("Stage", "")).strip()

                if not all([job, milestone, block, stage]):
                    continue

                state_key = self._make_state_key(defs, job, milestone, block, stage)

                if action_name == "hide":
                    db_ops.request_remove(conn, state_key)
                elif action_name == "unhide":
                    db_ops.request_add_back(conn, state_key)
                elif action_name == "update":
                    db_ops.request_reupdate(conn, state_key)
                else:
                    raise ValueError("Invalid action")

                queued += 1
        finally:
            conn.close()

        return {
            "queued": queued,
            "action": action_name,
            "project_code": project_code,
            "template_name": template_name
        }

    def hide_or_unhide_runs(self, project_code: str, template_name: str, run_rows, action: str):
        if action not in {"hide", "unhide"}:
            raise ValueError("Invalid action")
        return self._queue_template_action(project_code, template_name, run_rows, action)

    def update_runs(self, project_code: str, template_name: str, run_rows):
        return self._queue_template_action(project_code, template_name, run_rows, "update")
