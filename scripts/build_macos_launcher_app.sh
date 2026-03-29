#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
ICON_PATH="$ROOT_DIR/assets/AppIcon.icns"
APP_PATH="$ROOT_DIR/dist/LocalStereoTranscriberLauncher.app"
PLIST_PATH="$APP_PATH/Contents/Info.plist"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python venv not found at $PYTHON_BIN" >&2
  exit 1
fi

set_plist_value() {
  local plist_path="$1"
  local key="$2"
  local value="$3"

  if /usr/libexec/PlistBuddy -c "Print :$key" "$plist_path" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist_path"
  else
    /usr/libexec/PlistBuddy -c "Add :$key string $value" "$plist_path"
  fi
}

"$PYTHON_BIN" "$ROOT_DIR/scripts/generate_app_icon.py" --output "$ICON_PATH"

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --copy-metadata streamlit \
  --collect-all streamlit \
  --hidden-import faster_whisper \
  --collect-all faster_whisper \
  --hidden-import ctranslate2 \
  --collect-all ctranslate2 \
  --hidden-import onnxruntime \
  --collect-all onnxruntime \
  --icon "$ICON_PATH" \
  --osx-bundle-identifier "com.arnoudvanrooij.localstereotranscriber.launcher" \
  --name "LocalStereoTranscriberLauncher" \
  --add-data "$ROOT_DIR/assets:assets" \
  --add-data "$ROOT_DIR/streamlit_app.py:." \
  --add-data "$ROOT_DIR/transcribe_dual_channel_local.py:." \
  "$ROOT_DIR/packaging/launcher_runtime_wrapper.py"

set_plist_value "$PLIST_PATH" "CFBundleDisplayName" "Local Stereo Transcriber Launcher"
set_plist_value "$PLIST_PATH" "CFBundleShortVersionString" "1.0.0"
set_plist_value "$PLIST_PATH" "CFBundleVersion" "1.0.0"

echo "Built app: $ROOT_DIR/dist/LocalStereoTranscriberLauncher.app"
