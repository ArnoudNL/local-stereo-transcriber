#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
APP_FILE="$ROOT_DIR/streamlit_app.py"
LOG_DIR="$HOME/Library/Application Support/LocalStereoTranscriber/logs"
RUN_LOG="$LOG_DIR/streamlit_on_demand.log"
PID_FILE="$LOG_DIR/streamlit_on_demand.pid"
PORT_FILE="$LOG_DIR/streamlit_on_demand.port"

ACTION="start"
PORT="8501"

if [[ $# -ge 1 ]]; then
  if [[ "$1" =~ ^[0-9]+$ ]]; then
    ACTION="start"
    PORT="$1"
  else
    ACTION="$1"
    if [[ $# -ge 2 ]]; then
      PORT="$2"
    fi
  fi
fi

URL="http://localhost:${PORT}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment not found at: $PYTHON_BIN"
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$LOG_DIR"

is_pid_running() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1
}

read_pid() {
  if [[ -f "$PID_FILE" ]]; then
    tr -dc '0-9' <"$PID_FILE"
  fi
}

cleanup_state() {
  rm -f "$PID_FILE" "$PORT_FILE"
}

start_server() {
  local current_pid
  current_pid="$(read_pid || true)"
  if [[ -n "$current_pid" ]] && is_pid_running "$current_pid"; then
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "Streamlit already running (pid=$current_pid) at $URL"
      open "$URL"
      exit 0
    fi
    echo "Found stale streamlit pid $current_pid; stopping it first"
    kill "$current_pid" >/dev/null 2>&1 || true
    sleep 0.5
    if is_pid_running "$current_pid"; then
      kill -9 "$current_pid" >/dev/null 2>&1 || true
    fi
    cleanup_state
  fi

  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "Server already reachable at $URL"
    open "$URL"
    exit 0
  fi

  nohup "$PYTHON_BIN" -m streamlit run "$APP_FILE" --server.port "$PORT" >"$RUN_LOG" 2>&1 &
  local new_pid="$!"
  echo "$new_pid" >"$PID_FILE"
  echo "$PORT" >"$PORT_FILE"

  for _ in {1..60}; do
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "Streamlit started (pid=$new_pid) at $URL"
      open "$URL"
      exit 0
    fi
    sleep 0.5
  done

  echo "Streamlit did not become ready at $URL within 30 seconds."
  echo "Check log: $RUN_LOG"
  exit 1
}

stop_server() {
  local current_pid
  current_pid="$(read_pid || true)"

  if [[ -n "$current_pid" ]] && is_pid_running "$current_pid"; then
    echo "Stopping streamlit pid=$current_pid"
    kill "$current_pid" >/dev/null 2>&1 || true
    for _ in {1..30}; do
      if ! is_pid_running "$current_pid"; then
        cleanup_state
        echo "Stopped"
        exit 0
      fi
      sleep 0.1
    done
    echo "Force-stopping streamlit pid=$current_pid"
    kill -9 "$current_pid" >/dev/null 2>&1 || true
    cleanup_state
    exit 0
  fi

  local pid_by_port
  pid_by_port="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [[ -n "$pid_by_port" ]]; then
    echo "No pid file, but found listener on $PORT (pid=$pid_by_port); stopping"
    kill "$pid_by_port" >/dev/null 2>&1 || true
    sleep 0.3
    if is_pid_running "$pid_by_port"; then
      kill -9 "$pid_by_port" >/dev/null 2>&1 || true
    fi
    cleanup_state
    exit 0
  fi

  cleanup_state
  echo "No running localhost streamlit instance found"
}

status_server() {
  local current_pid
  current_pid="$(read_pid || true)"
  if [[ -n "$current_pid" ]] && is_pid_running "$current_pid"; then
    if curl -fsS "$URL" >/dev/null 2>&1; then
      echo "running pid=$current_pid url=$URL"
      exit 0
    fi
    echo "stale pid=$current_pid (process alive, endpoint not ready)"
    exit 1
  fi

  if curl -fsS "$URL" >/dev/null 2>&1; then
    echo "running url=$URL (pid file missing)"
    exit 0
  fi

  echo "stopped"
  exit 1
}

case "$ACTION" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    "$0" stop "$PORT" || true
    "$0" start "$PORT"
    ;;
  status)
    status_server
    ;;
  *)
    echo "Usage: $0 [start|stop|status|restart] [port]"
    echo "       $0 [port]"
    exit 2
    ;;
esac
