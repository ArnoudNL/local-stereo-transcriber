#!/usr/bin/env python3
"""Shared logging setup for Local Stereo Transcriber components."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

__all__ = ["setup_logging", "get_log_dir"]

_GLOBAL_CONFIGURED = False
_COMPONENTS_CONFIGURED: set[str] = set()


def _get_console_sink():
    """Return a usable console stream sink, or None when no console is attached."""
    for candidate in (sys.stderr, sys.stdout):
        if candidate is None:
            continue
        if hasattr(candidate, "write"):
            return candidate
    return None


def _add_sink_with_fallback(*, sink, level: str, enqueue: bool, **kwargs) -> bool:
    """Add a log sink, falling back to non-queued mode when queue creation fails."""
    try:
        logger.add(sink, level=level, enqueue=enqueue, **kwargs)
        return enqueue
    except OSError as exc:
        if enqueue and getattr(exc, "errno", None) == 28:
            logger.add(sink, level=level, enqueue=False, **kwargs)
            return False
        raise


def get_log_dir() -> Path:
    """Return the writable log directory for all app components."""
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/LocalStereoTranscriber/logs"
    return Path("./logs").resolve()


def setup_logging(component: str, file_name: str | None = None):
    """Configure loguru once and create a component-specific file sink."""
    global _GLOBAL_CONFIGURED

    level = os.environ.get("LST_LOG_LEVEL", "INFO").strip().upper()
    enqueue = os.environ.get("LST_LOG_ENQUEUE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    configured_enqueue = enqueue

    if not _GLOBAL_CONFIGURED:
        logger.remove()
        console_sink = _get_console_sink()
        if console_sink is not None:
            configured_enqueue = _add_sink_with_fallback(
                sink=console_sink,
                level=level,
                enqueue=enqueue,
                format=(
                    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} "
                    "| {extra[component]} | {message}"
                ),
            )
        _GLOBAL_CONFIGURED = True

    if component not in _COMPONENTS_CONFIGURED:
        log_path = log_dir / (file_name or f"{component}.log")
        _add_sink_with_fallback(
            sink=str(log_path),
            level="DEBUG",
            enqueue=configured_enqueue,
            rotation="5 MB",
            retention=5,
            encoding="utf-8",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[component]} "
                "| {name}:{function}:{line} | {message}"
            ),
            filter=lambda record, c=component: record["extra"].get("component") == c,
        )
        _COMPONENTS_CONFIGURED.add(component)

    return logger.bind(component=component)
