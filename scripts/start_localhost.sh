#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
APP_FILE="$ROOT_DIR/streamlit_app.py"
PORT="${1:-8501}"
URL="http://localhost:${PORT}"
LOG_DIR="$HOME/Library/Application Support/LocalStereoTranscriber/logs"
RUN_LOG="$LOG_DIR/streamlit_on_demand.log"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python environment not found at: $PYTHON_BIN"
  echo "Create it first with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$LOG_DIR"

if curl -fsS "$URL" >/dev/null 2>&1; then
  open "$URL"
  exit 0
fi

nohup "$PYTHON_BIN" -m streamlit run "$APP_FILE" --server.port "$PORT" >"$RUN_LOG" 2>&1 &

for _ in {1..60}; do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    open "$URL"
    exit 0
  fi
  sleep 0.5
done

echo "Streamlit did not become ready at $URL within 30 seconds."
echo "Check log: $RUN_LOG"
exit 1
