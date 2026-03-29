#!/usr/bin/env python3
"""Native desktop wrapper that hosts Streamlit in a pywebview window."""

from __future__ import annotations

import argparse
import atexit
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import webview
from streamlit.web import cli as stcli
from wrapper_common import pick_port, resource_path, wait_until_up

from app_logging import setup_logging

LOADING_HTML = """
<!doctype html>
<html>
    <head>
        <meta charset=\"utf-8\" />
        <title>Local Stereo Transcriber</title>
        <style>
            body {
                margin: 0;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: #e7f5fa;
                color: #23424f;
                display: grid;
                place-items: center;
                min-height: 100vh;
            }
            .card {
                background: rgba(255, 255, 255, 0.85);
                border: 1px solid #b8dbe8;
                border-radius: 14px;
                padding: 18px 20px;
                box-shadow: 0 6px 18px rgba(26, 57, 72, 0.12);
            }
        </style>
    </head>
    <body>
        <div class=\"card\">Starting Local Stereo Transcriber...</div>
    </body>
</html>
"""

CHILD_PROCESS: Optional[subprocess.Popen] = None
_SHUTDOWN_STARTED = False
logger = setup_logging("desktop_wrapper", "desktop_wrapper.log")


def stop_child_process(
    child: Optional[subprocess.Popen], terminate_wait_sec: float = 1.0, kill_wait_sec: float = 1.0
) -> None:
    """Stop child process and its process group."""
    if child is None or child.poll() is not None:
        return

    logger.info("Stopping child process pid={}", child.pid)

    try:
        os.killpg(child.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + terminate_wait_sec
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return
        time.sleep(0.05)

    try:
        os.killpg(child.pid, signal.SIGKILL)
    except ProcessLookupError:
        return

    deadline = time.monotonic() + kill_wait_sec
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return
        time.sleep(0.05)

    logger.warning(
        "Child pid={} did not exit after SIGKILL window; continuing shutdown without blocking",
        child.pid,
    )


def run_streamlit_server(port: int) -> int:
    app_path = resource_path("streamlit_app.py")
    if not app_path.exists():
        logger.error("Missing Streamlit app file: {}", app_path)
        print(f"ERROR: missing Streamlit app file: {app_path}", file=sys.stderr)
        return 1

    logger.info("Starting embedded Streamlit server on port {}", port)

    # Set flag so Streamlit knows we're in embedded Desktop mode
    os.environ["LST_EMBEDDED_DESKTOP"] = "1"

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
    return int(stcli.main())


def on_window_closed() -> None:
    global CHILD_PROCESS, _SHUTDOWN_STARTED

    if _SHUTDOWN_STARTED:
        return
    _SHUTDOWN_STARTED = True

    logger.info("Desktop window closing")
    child = CHILD_PROCESS
    CHILD_PROCESS = None

    # Avoid Python finalization waits on child cleanup by exiting hard after signals.
    if child is not None and child.poll() is None:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        time.sleep(0.15)
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    logger.info("Desktop shutdown complete, forcing process exit")
    logger.complete()
    os._exit(0)


def _on_termination_signal(_signum, _frame) -> None:
    on_window_closed()
    raise SystemExit(0)


def register_shutdown_hooks() -> None:
    atexit.register(on_window_closed)
    signal.signal(signal.SIGTERM, _on_termination_signal)
    signal.signal(signal.SIGINT, _on_termination_signal)


def start_backend_and_load(window: webview.Window, url: str, port: int) -> None:
    global CHILD_PROCESS

    logger.info("Preparing backend process for {}", url)

    stop_child_process(CHILD_PROCESS)
    CHILD_PROCESS = None

    if hasattr(sys, "_MEIPASS"):
        # In frozen app mode, re-launch this executable in internal server mode.
        command = [sys.executable, "--serve", "--port", str(port)]
    else:
        # In source mode, launch a separate server process.
        command = [sys.executable, str(Path(__file__).resolve()), "--serve", "--port", str(port)]

    CHILD_PROCESS = subprocess.Popen(  # pylint: disable=consider-using-with
        command,
        start_new_session=True,
    )
    logger.info("Started backend child pid={} command={}", CHILD_PROCESS.pid, command)

    if wait_until_up(url, timeout_sec=90.0):
        logger.info("Backend ready, loading URL in native window: {}", url)
        window.load_url(url)
        return

    logger.error("Backend failed to start in time for {}", url)
    stop_child_process(CHILD_PROCESS)
    CHILD_PROCESS = None

    window.load_html("""
        <html><body style='font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; padding: 16px;'>
        <h3>Failed to start Local Stereo Transcriber</h3>
        <p>The embedded Streamlit server did not start in time.</p>
        </body></html>
        """)


def run_native_window(preferred_port: int = 8501) -> int:
    port = pick_port(preferred_port)
    url = f"http://127.0.0.1:{port}"
    logger.info("Launching native desktop window on {}", url)

    register_shutdown_hooks()

    window = webview.create_window(
        title="Local Stereo Transcriber",
        html=LOADING_HTML,
        width=1200,
        height=820,
        min_size=(900, 640),
        background_color="#e7f5fa",
    )
    window.events.closing += on_window_closed
    window.events.closed += on_window_closed

    webview.start(start_backend_and_load, args=(window, url, port), gui="cocoa", debug=False)
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Desktop wrapper for Streamlit app")
    parser.add_argument("--serve", action="store_true", help="Internal mode: run Streamlit server")
    parser.add_argument("--port", type=int, default=8501, help="Port to bind Streamlit server")
    return parser.parse_args()


def main() -> int:
    multiprocessing.freeze_support()
    args = parse_args()
    logger.info("Desktop wrapper starting with args: {}", args)
    if args.serve:
        return run_streamlit_server(args.port)
    return run_native_window(args.port)


if __name__ == "__main__":
    raise SystemExit(main())
