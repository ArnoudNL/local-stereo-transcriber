#!/usr/bin/env python3
"""Shared utilities for Streamlit wrapper applications (desktop and launcher)."""

from __future__ import annotations

import socket
import sys
import time
import urllib.request
from pathlib import Path

__all__ = ["resource_path", "pick_port", "wait_until_up"]


def resource_path(relative_path: str) -> Path:
    """Resolve resource path for source and PyInstaller bundled mode."""
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / relative_path
    return Path(__file__).resolve().parents[1] / relative_path


def pick_port(preferred_port: int = 8501) -> int:
    """Use preferred port when free, otherwise ask OS for an available one."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if sock.connect_ex(("127.0.0.1", preferred_port)) != 0:
            return preferred_port

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_until_up(url: str, timeout_sec: float = 90.0) -> bool:
    """Poll the local URL until Streamlit is reachable."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if int(response.status) < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False
