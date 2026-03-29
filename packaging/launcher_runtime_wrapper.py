#!/usr/bin/env python3
"""Standalone launcher app that runs Streamlit and opens the local URL."""

from __future__ import annotations

import multiprocessing
import sys
import threading
import webbrowser

from streamlit.web import cli as stcli
from wrapper_common import pick_port, resource_path, wait_until_up

from app_logging import setup_logging

logger = None


def open_browser_when_ready(url: str) -> None:
    if wait_until_up(url):
        if logger is not None:
            logger.info("Opening browser at {}", url)
        webbrowser.open(url, new=2)


def main() -> int:
    global logger

    # Required for frozen multiprocessing helper subprocesses.
    multiprocessing.freeze_support()

    logger = setup_logging("streamlit_launcher", "streamlit_launcher.log")

    app_path = resource_path("streamlit_app.py")
    if not app_path.exists():
        logger.error("Missing Streamlit app file: {}", app_path)
        print(f"ERROR: missing Streamlit app file: {app_path}", file=sys.stderr)
        return 1

    port = pick_port(8501)
    url = f"http://127.0.0.1:{port}"
    logger.info("Launcher starting Streamlit at {}", url)

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

    return int(stcli.main())


if __name__ == "__main__":
    raise SystemExit(main())
