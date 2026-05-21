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
GRACEFUL_SHUTDOWN_WAIT_SECONDS = 5
APR_BATCH_TERMINATION_WAIT_SECONDS = 3
APR_TERMINATE_SHUTDOWN_BUFFER_SECONDS = 5

APP_PROJECT_JSON = CONFIG_DIR / "app.project.json"
PROJECTS_BASE_DIR = Path(os.environ.get("PROJECTS_BASE_DIR", "/proj"))
REGISTRY_DB = APPDATA_DIR / "monitor_registry.db"
TRACKER_PREVIEW_ROWS = 100
FLOW_MONITOR_SCRIPT = BACKEND_MONITOR_DIR / "FLOW" / "FLOW_MONITOR.py"


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

    def _supports_update_run(self, _template_name: str):
        """
        Function Name: _supports_update_run
        Purpose: Report whether the monitor service currently supports a manual update-runs action for one template.
        Input Params: _template_name (str)
        Output: supports_update_run (bool)
        """
        return False

    def _has_flow_modules(self, template_dir: Path, template_name: str, module_suffixes):
        """
        Function Name: _has_flow_modules
        Purpose: Check whether one flow template exposes a full required module set from either its root folder or MONITORING subfolder.
        Input Params: template_dir (Path), template_name (str), module_suffixes (list[str] | tuple[str, ...])
        Output: has_modules (bool)
        """
        for suffix in module_suffixes:
            root_path = template_dir / f"{template_name}_{suffix}.py"
            monitoring_path = template_dir / "MONITORING" / f"{template_name}_{suffix}.py"
            if not (root_path.exists() or monitoring_path.exists()):
                return False
        return True

    def _is_central_flow_template(self, template_dir: Path, template_name: str):
        module_sets = [
            (
                "FLOW_CONTEXT",
                "MONITOR_ITEMS",
                "ITEM_STATUS",
                "STATUS_ACTION",
                "UPDATE_DB",
                "SLEEP",
                "CLOSE",
            ),
            (
                "MONITOR_ITEMS",
                "ITEM_STATUS",
                "STATUS_ACTION",
                "UPDATE_TRACKER",
                "UPDATE_STATE",
                "UPDATE_LOG",
                "SLEEP",
                "CLOSE",
            ),
        ]
        return FLOW_MONITOR_SCRIPT.exists() and any(
            self._has_flow_modules(template_dir, template_name, module_suffixes)
            for module_suffixes in module_sets
        )

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
            if template_name.startswith("__") or template_name == "FLOW":
                continue

            main_script = folder / f"{template_name}.py"
            is_central_flow = self._is_central_flow_template(folder, template_name)
            if is_central_flow:
                script_path = FLOW_MONITOR_SCRIPT
                launch_mode = "flow"
            elif main_script.exists():
                script_path = main_script
                launch_mode = "legacy"
            else:
                continue

            templates.append({
                "template_name": template_name,
                "script_path": str(script_path),
                "launch_mode": launch_mode,
                "has_hide_runs": False,
                "has_update_run": self._supports_update_run(template_name)
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
        db_name = f"DashAI_{template_name}.db"
        try:
            _, defs_module = self._load_template_modules(template_name)
            db_name = getattr(defs_module, "DB_NAME", db_name) or db_name
        except Exception:
            pass
        return PROJECTS_BASE_DIR / project_code / "DashAI" / db_name

    def get_project_log_dir(self, project_code: str, template_name: str):
        log_dir_name = f"Logs{template_name}"
        try:
            _, defs_module = self._load_template_modules(template_name)
            log_dir_name = getattr(defs_module, "LOG_DIR", log_dir_name) or log_dir_name
        except Exception:
            pass
        return PROJECTS_BASE_DIR / project_code / "DashAI" / log_dir_name

    def _load_python_module(self, module_path: Path, module_name: str):
        if not module_path.exists():
            raise FileNotFoundError(f"Module not found: {module_path}")

        spec = importlib.util.spec_from_file_location(module_name, str(module_path))
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module: {module_path}")

        module = importlib.util.module_from_spec(spec)
        root_dir = str(ROOT_DIR)
        module_dir = str(module_path.parent)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)
        spec.loader.exec_module(module)
        return module

    def _load_template_modules(self, template_name: str):
        template_dir = self._get_template_dir(template_name)
        db_ops_path = template_dir / f"{template_name}_DB_ACTIONS.py"
        if not db_ops_path.exists():
            db_ops_path = template_dir / f"{template_name}_DB_Operations.py"

        defs_path = template_dir / f"{template_name}_VARS.py"
        if not defs_path.exists():
            defs_path = template_dir / f"{template_name}_Definitions.py"

        db_ops = self._load_python_module(db_ops_path, f"{template_name}_db_ops")
        defs = self._load_python_module(defs_path, f"{template_name}_defs")
        return db_ops, defs

    def _supports_graceful_shutdown(self, template_name: str):
        return self._is_central_flow_template(self._get_template_dir(template_name), template_name) or template_name == "APR"

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

    def _spawn_monitor(self, script_path: str, template_name: str, project_code: str):
        if Path(script_path).resolve() == FLOW_MONITOR_SCRIPT.resolve():
            cmd = [sys.executable, script_path, template_name, project_code]
        else:
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
                "status": row["status"] if row["status"] in {"stopping", "terminating"} else "running"
            }

        template_info = self._get_template_info(row["template_name"])
        script_path = template_info["script_path"] if template_info else row["script_path"]
        new_pid = self._spawn_monitor(script_path, row["template_name"], row["project_code"])
        now = self._now()

        cur.execute("""
            UPDATE monitor_registry
            SET pid = ?, script_path = ?, status = ?, updated_at = ?, last_started_at = ?
            WHERE monitor_name = ?
        """, (new_pid, script_path, "running", now, now, monitor_name))
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
            if os.name == "nt":
                kwargs = {
                    "check": False,
                    "stderr": subprocess.DEVNULL,
                    "stdout": subprocess.DEVNULL,
                }
                create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                if create_no_window:
                    kwargs["creationflags"] = create_no_window
                subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"], **kwargs)
                try:
                    proc.wait(timeout=3)
                    return
                except Exception:
                    pass

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

    def _snapshot_pid_family(self, pid: int):
        if not pid:
            return {}

        try:
            root_process = psutil.Process(pid)
        except Exception:
            return {}

        try:
            process_family = [root_process, *root_process.children(recursive=True)]
        except Exception:
            process_family = [root_process]

        snapshot = {}
        for process_info in process_family:
            try:
                snapshot[process_info.pid] = process_info.create_time()
            except Exception:
                pass
        return snapshot

    def _kill_pid_snapshot(self, pid_snapshot, exclude_pids=None):
        exclude_pids = set(exclude_pids or [])
        for candidate_pid, created_at in sorted(dict(pid_snapshot or {}).items(), reverse=True):
            if not candidate_pid or candidate_pid in exclude_pids:
                continue

            try:
                proc = psutil.Process(candidate_pid)
            except Exception:
                continue

            try:
                if abs(float(proc.create_time()) - float(created_at)) > 0.01:
                    continue
            except Exception:
                continue

            self._kill_pid(candidate_pid)

    def _request_pid_shutdown(self, pid: int):
        if not pid:
            return False

        try:
            proc = psutil.Process(pid)
        except Exception:
            return False

        try:
            if os.name == "nt" and hasattr(signal, "CTRL_BREAK_EVENT"):
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                proc.terminate()
            return True
        except Exception:
            return False

    def _wait_for_pid_exit(self, pid: int, timeout_seconds=None):
        if not pid:
            return True

        if timeout_seconds is None:
            while self._is_pid_alive(pid):
                time.sleep(0.2)
            return True

        deadline = time.time() + max(0.0, float(timeout_seconds))
        while time.time() < deadline:
            if not self._is_pid_alive(pid):
                return True
            time.sleep(0.2)

        return not self._is_pid_alive(pid)

    def _get_shutdown_wait_seconds(self, template_name: str, action: str):
        timeout_seconds = GRACEFUL_SHUTDOWN_WAIT_SECONDS
        if action != "terminate" or template_name != "APR":
            return timeout_seconds

        try:
            _, defs_module = self._load_template_modules(template_name)
            if hasattr(defs_module, "get_runtime_settings"):
                settings = defs_module.get_runtime_settings()
                max_parallel_batches = int(settings.get("MAX_PARALLEL_BATCHES", 1) or 1)
            else:
                max_parallel_batches = int(getattr(defs_module, "MAX_PARALLEL_BATCHES", 1) or 1)
        except Exception:
            max_parallel_batches = 1

        batch_cleanup_seconds = max(1, max_parallel_batches) * APR_BATCH_TERMINATION_WAIT_SECONDS
        return max(
            timeout_seconds,
            batch_cleanup_seconds + APR_TERMINATE_SHUTDOWN_BUFFER_SECONDS,
        )

    def stop_monitor(self, monitor_name: str):
        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError("Monitor not found")
        conn.close()

        pid = row["pid"]
        pid_snapshot = self._snapshot_pid_family(pid) if pid and self._is_pid_alive(pid) else {}
        if pid and self._supports_graceful_shutdown(row["template_name"]) and self._is_pid_alive(pid):
            shutdown_requested = self._request_pid_shutdown(pid)
            shutdown_wait_seconds = self._get_shutdown_wait_seconds(row["template_name"], "stop")
            if shutdown_requested and self._wait_for_pid_exit(pid, shutdown_wait_seconds):
                self._kill_pid_snapshot(pid_snapshot, exclude_pids={pid})
                pid = None
            else:
                self._kill_pid(pid)
                self._kill_pid_snapshot(pid_snapshot, exclude_pids={pid})
                pid = None

        if pid:
            if not pid_snapshot:
                pid_snapshot = self._snapshot_pid_family(pid)
            self._kill_pid(pid)
            self._kill_pid_snapshot(pid_snapshot, exclude_pids={pid})

        now = self._now()
        conn = self._connect_registry()
        cur = conn.cursor()
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
        stop_result = self.stop_monitor(monitor_name)
        if stop_result["status"] != "stopped":
            return stop_result
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
        conn.close()

        pid = row["pid"]
        pid_snapshot = self._snapshot_pid_family(pid) if pid and self._is_pid_alive(pid) else {}
        if pid and self._supports_graceful_shutdown(row["template_name"]) and self._is_pid_alive(pid):
            shutdown_requested = self._request_pid_shutdown(pid)
            if not shutdown_requested and self._is_pid_alive(pid):
                raise RuntimeError(f"Unable to request graceful shutdown for monitor '{monitor_name}'")

            self._wait_for_pid_exit(pid)
            self._kill_pid_snapshot(pid_snapshot, exclude_pids={pid})
            pid = None

        if pid:
            if not pid_snapshot:
                pid_snapshot = self._snapshot_pid_family(pid)
            self._kill_pid(pid)
            self._kill_pid_snapshot(pid_snapshot, exclude_pids={pid})

        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("DELETE FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        conn.commit()
        conn.close()

        return {
            "monitor_name": monitor_name,
            "status": "terminated"
        }

    def delete_monitor(self, monitor_name: str):
        conn = self._connect_registry()
        cur = conn.cursor()
        cur.execute("SELECT * FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        row = cur.fetchone()
        if not row:
            conn.close()
            raise FileNotFoundError("Monitor not found")

        pid = row["pid"]
        if pid and self._is_pid_alive(pid):
            conn.close()
            raise ValueError("Monitor is running. Terminate it before deleting.")

        cur.execute("DELETE FROM monitor_registry WHERE monitor_name = ?", (monitor_name,))
        conn.commit()
        conn.close()
        self._process_cache.pop(pid, None)

        return {
            "monitor_name": monitor_name,
            "status": "deleted"
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
        cleanup_rows = []

        for row in rows:
            pid = row["pid"]
            stats = self._get_process_snapshot(pid)
            is_running = stats["is_running"]

            effective_status = row["status"]
            if pid and is_running:
                effective_status = row["status"] if row["status"] in {"stopping", "terminating"} else "running"
            elif row["status"] == "running" and not is_running:
                effective_status = "stopped"
            elif row["status"] == "stopping" and not is_running:
                effective_status = "stopped"
            elif row["status"] == "terminating" and not is_running:
                cleanup_rows.append(row["monitor_name"])
                continue

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
                "has_hide_runs": False,
                "has_update_run": self._supports_update_run(row["template_name"])
            })

        if cleanup_rows:
            conn = self._connect_registry()
            cur = conn.cursor()
            cur.executemany(
                "DELETE FROM monitor_registry WHERE monitor_name = ?",
                [(name,) for name in cleanup_rows],
            )
            conn.commit()
            conn.close()

        return output

    def get_tracker_table_data(self, project_code: str, template_name: str, view_mode: str = "visible", limit: int = TRACKER_PREVIEW_ROWS):
        if not self._safe_name(project_code):
            raise ValueError("Invalid project_code")
        if not self._safe_name(template_name):
            raise ValueError("Invalid template_name")
        if view_mode not in {"visible", "all"}:
            raise ValueError("Invalid view_mode")

        try:
            limit = max(1, min(int(limit), TRACKER_PREVIEW_ROWS))
        except (TypeError, ValueError):
            limit = TRACKER_PREVIEW_ROWS

        db_path = self.get_project_db_path(project_code, template_name)
        defs = None
        table_name = f"{template_name}_TRACKER"

        try:
            _, defs = self._load_template_modules(template_name)
            table_name = getattr(defs, "TRACKER_TABLE", table_name) or table_name
        except Exception:
            defs = None

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
            try:
                if defs is None:
                    _, defs = self._load_template_modules(template_name)
                preferred_columns = list(getattr(defs, "TRACKER_COLUMNS", [])) + list(getattr(defs, "KPI_COLUMNS", []))
                columns = [col for col in preferred_columns if col in columns]
            except Exception:
                columns = [col for col in columns if col not in {"Project", "Hidden"}]

            cur.execute(f'SELECT * FROM "{table_name}" LIMIT ?', [limit + 1])
            fetched_rows = cur.fetchall()
            has_more = len(fetched_rows) > limit
            rows = [{col: r[col] for col in columns} for r in fetched_rows[:limit]]
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

    def hide_or_unhide_runs(self, project_code: str, template_name: str, run_rows, action: str):
        raise ValueError("Hide and unhide are not supported for this monitor")

    def update_runs(self, project_code: str, template_name: str, run_rows):
        raise ValueError("Manual update runs are not supported for this monitor. Delete the timing DB to re-extract.")
