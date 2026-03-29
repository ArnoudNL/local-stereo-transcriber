#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_BIN="$ROOT_DIR/.venv/bin"
LAUNCHER_BIN="$ROOT_DIR/dist/LocalStereoTranscriberLauncher.app/Contents/MacOS/LocalStereoTranscriberLauncher"
DESKTOP_BIN="$ROOT_DIR/dist/LocalStereoTranscriberDesktop.app/Contents/MacOS/LocalStereoTranscriberDesktop"

LAUNCHER_PORT=8501
DESKTOP_PORT=8502

LAUNCHER_PID=""
DESKTOP_PID=""

cleanup() {
  if [[ -n "$LAUNCHER_PID" ]]; then
    pkill -P "$LAUNCHER_PID" >/dev/null 2>&1 || true
    kill "$LAUNCHER_PID" >/dev/null 2>&1 || true
  fi

  if [[ -n "$DESKTOP_PID" ]]; then
    pkill -P "$DESKTOP_PID" >/dev/null 2>&1 || true
    kill "$DESKTOP_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

require_port_free() {
  local port="$1"
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "ERROR: port $port is already in use. Stop the process and retry." >&2
    lsof -nP -iTCP:"$port" -sTCP:LISTEN || true
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  local timeout_sec="$2"

  for _ in $(seq 1 "$timeout_sec"); do
    if curl -sSf "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done

  return 1
}

echo "==> Checking prerequisites"
require_cmd curl
require_cmd lsof

if [[ ! -x "$VENV_BIN/python" ]]; then
  echo "ERROR: Python venv not found at $VENV_BIN/python" >&2
  exit 1
fi

echo "==> Running quality gate"
"$VENV_BIN/isort" --check-only .
"$VENV_BIN/black" --check .
"$VENV_BIN/pylint" --jobs=1 transcribe_dual_channel_local.py streamlit_app.py

echo "==> Building launcher app"
bash "$ROOT_DIR/scripts/build_launcher_app.sh"

if [[ ! -x "$LAUNCHER_BIN" ]]; then
  echo "ERROR: launcher binary not found after build: $LAUNCHER_BIN" >&2
  exit 1
fi

echo "==> Building desktop app"
bash "$ROOT_DIR/scripts/build_desktop_app.sh"

if [[ ! -x "$DESKTOP_BIN" ]]; then
  echo "ERROR: desktop binary not found after build: $DESKTOP_BIN" >&2
  exit 1
fi

echo "==> Smoke testing launcher app on port $LAUNCHER_PORT"
require_port_free "$LAUNCHER_PORT"
BROWSER=/usr/bin/true "$LAUNCHER_BIN" >/tmp/lst_release_gate_launcher.log 2>&1 &
LAUNCHER_PID=$!

if ! wait_for_http "http://127.0.0.1:$LAUNCHER_PORT" 45; then
  echo "ERROR: launcher smoke test failed" >&2
  tail -n 80 /tmp/lst_release_gate_launcher.log || true
  exit 1
fi

echo "==> Launcher smoke test passed"
pkill -P "$LAUNCHER_PID" >/dev/null 2>&1 || true
kill "$LAUNCHER_PID" >/dev/null 2>&1 || true
LAUNCHER_PID=""

echo "==> Smoke testing desktop backend mode on port $DESKTOP_PORT"
require_port_free "$DESKTOP_PORT"
"$DESKTOP_BIN" --serve --port "$DESKTOP_PORT" >/tmp/lst_release_gate_desktop.log 2>&1 &
DESKTOP_PID=$!

if ! wait_for_http "http://127.0.0.1:$DESKTOP_PORT" 45; then
  echo "ERROR: desktop backend smoke test failed" >&2
  tail -n 80 /tmp/lst_release_gate_desktop.log || true
  exit 1
fi

echo "==> Desktop backend smoke test passed"
pkill -P "$DESKTOP_PID" >/dev/null 2>&1 || true
kill "$DESKTOP_PID" >/dev/null 2>&1 || true
DESKTOP_PID=""

echo "==> Release gate passed. Safe to package."
