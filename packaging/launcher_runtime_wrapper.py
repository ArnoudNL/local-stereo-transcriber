#!/usr/bin/env python3
"""Standalone launcher app that runs Streamlit and opens the local URL."""

from __future__ import annotations

import json
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from streamlit.web import cli as stcli
from wrapper_common import pick_port, resource_path, wait_until_up

from app_logging import get_log_dir, setup_logging

logger = None

IDLE_TIMEOUT_SEC = 20
IDLE_POLL_SEC = 15
STATE_FILE_NAME = "streamlit_launcher_state.json"


def _state_dir() -> Path:
    return get_log_dir().parent / "run"


def _state_file() -> Path:
    return _state_dir() / STATE_FILE_NAME


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _read_state(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _looks_like_launcher_process(pid: int) -> bool:
    if os.name != "posix":
        return True
    try:
        command = subprocess.check_output(
            ["ps", "-p", str(pid), "-o", "command="],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return False
    if not command:
        return False
    markers = ("LocalStereoTranscriberLauncher", "launcher_runtime_wrapper.py")
    return any(marker in command for marker in markers)


def _terminate_pid(pid: int, grace_sec: float = 2.0) -> bool:
    if not _pid_is_alive(pid):
        return True

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return not _pid_is_alive(pid)

    deadline = time.monotonic() + grace_sec
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.05)

    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return not _pid_is_alive(pid)

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_is_alive(pid)


def _established_connection_count(port: int) -> int:
    if sys.platform != "darwin":
        return 0
    try:
        output = subprocess.check_output(
            ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:ESTABLISHED"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return 0

    lines = [line for line in output.splitlines() if line.strip()]
    if len(lines) <= 1:
        return 0
    return len(lines) - 1


def _start_idle_watchdog(port: int, timeout_sec: int = IDLE_TIMEOUT_SEC) -> None:
    def monitor() -> None:
        last_activity_ts = time.time()

        while True:
            if _established_connection_count(port) > 0:
                last_activity_ts = time.time()

            if time.time() - last_activity_ts >= timeout_sec:
                if logger is not None:
                    logger.info(
                        "Idle timeout reached ({}s) for port {} with no active clients; exiting launcher",
                        timeout_sec,
                        port,
                    )
                _safe_unlink(_state_file())
                os._exit(0)
            time.sleep(IDLE_POLL_SEC)

    threading.Thread(target=monitor, name="launcher-idle-watchdog", daemon=True).start()


def _resolve_existing_instance(path: Path) -> bool:
    state = _read_state(path)
    if not state:
        _safe_unlink(path)
        return False

    pid = state.get("pid")
    port = state.get("port")
    if not isinstance(pid, int):
        _safe_unlink(path)
        return False

    if not _pid_is_alive(pid):
        _safe_unlink(path)
        return False

    if isinstance(port, int):
        url = f"http://127.0.0.1:{port}"
        if wait_until_up(url, timeout_sec=1.2):
            if logger is not None:
                logger.info("Reusing running launcher instance pid={} at {}", pid, url)
            _open_url(url)
            return True

    if _looks_like_launcher_process(pid):
        if logger is not None:
            logger.warning("Terminating stale launcher pid={} before relaunch", pid)
        _terminate_pid(pid)

    _safe_unlink(path)
    return False


def open_browser_when_ready(url: str) -> None:
    if wait_until_up(url):
        if logger is not None:
            logger.info("Opening browser at {}", url)
        _open_url(url)


def _open_url(url: str) -> None:
    if sys.platform == "darwin":
        # Prefer Safari explicitly to avoid LaunchServices no-op reopen behavior.
        try:
            subprocess.Popen(["open", "-a", "Safari", url])
            subprocess.Popen(["osascript", "-e", 'tell application "Safari" to activate'])
            return
        except Exception:
            if logger is not None:
                logger.warning("macOS Safari open failed for {}, falling back to default browser", url)

        try:
            subprocess.Popen(["open", url])
            return
        except Exception:
            if logger is not None:
                logger.warning("macOS default open failed for {}, falling back to webbrowser", url)

    try:
        webbrowser.open(url, new=2)
    except Exception:
        if logger is not None:
            logger.warning("Failed to open browser for {}", url)


def main() -> int:
    global logger

    # Required for frozen multiprocessing helper subprocesses.
    multiprocessing.freeze_support()

    logger = setup_logging("streamlit_launcher", "streamlit_launcher.log")

    state_file = _state_file()
    if _resolve_existing_instance(state_file):
        return 0

    app_path = resource_path("streamlit_app.py")
    if not app_path.exists():
        logger.error("Missing Streamlit app file: {}", app_path)
        print(f"ERROR: missing Streamlit app file: {app_path}", file=sys.stderr)
        return 1

    port = pick_port(8501)
    url = f"http://127.0.0.1:{port}"
    logger.info("Launcher starting Streamlit at {}", url)

    _write_state(
        state_file,
        {
            "pid": os.getpid(),
            "port": port,
            "url": url,
            "started_at": int(time.time()),
        },
    )
    _start_idle_watchdog(port)

    opener = threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True)
    opener.start()

    # Streamlit reads arguments from sys.argv.
    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode",
        "false",
        "--server.headless",
        "true",
        "--browser.gatherUsageStats",
        "false",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(port),
    ]

    try:
        return int(stcli.main())
    finally:
        _safe_unlink(state_file)


if __name__ == "__main__":
    raise SystemExit(main())
