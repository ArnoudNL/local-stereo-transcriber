#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
DMG_NAME="LocalStereoTranscriber.dmg"
DMG_PATH="$DIST_DIR/$DMG_NAME"
RW_DMG_PATH="$DIST_DIR/LocalStereoTranscriber-rw.dmg"
STAGING_DIR="$DIST_DIR/dmg-staging"
MOUNT_POINT="$DIST_DIR/dmg-mount"
ICON_PATH="$ROOT_DIR/assets/AppIcon.icns"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
DMG_ICON_RSRC="$DIST_DIR/.dmg-icon.rsrc"

mkdir -p "$DIST_DIR"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python venv not found at $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" "$ROOT_DIR/scripts/generate_app_icon.py" --output "$ICON_PATH"

if [[ ! -d "$DIST_DIR/LocalStereoTranscriberLauncher.app" ]]; then
  echo "Launcher app not found. Building it first..."
  "$ROOT_DIR/scripts/build_macos_launcher_app.sh"
fi

if [[ ! -d "$DIST_DIR/LocalStereoTranscriberDesktop.app" ]]; then
  echo "Desktop app not found. Building it first..."
  "$ROOT_DIR/scripts/build_macos_desktop_app.sh"
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$DIST_DIR/LocalStereoTranscriberLauncher.app" "$STAGING_DIR/"
cp -R "$DIST_DIR/LocalStereoTranscriberDesktop.app" "$STAGING_DIR/"

ln -s /Applications "$STAGING_DIR/Applications"
rm -f "$DMG_PATH"
rm -f "$RW_DMG_PATH"
rm -rf "$MOUNT_POINT"
mkdir -p "$MOUNT_POINT"

hdiutil create \
  -volname "LocalStereoTranscriber" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDRW \
  "$RW_DMG_PATH"

hdiutil attach "$RW_DMG_PATH" -mountpoint "$MOUNT_POINT" -nobrowse
cp -f "$ICON_PATH" "$MOUNT_POINT/.VolumeIcon.icns"

if command -v SetFile >/dev/null 2>&1; then
  SetFile -a V "$MOUNT_POINT/.VolumeIcon.icns"
  SetFile -a C "$MOUNT_POINT"
else
  echo "WARNING: SetFile not found; DMG volume custom icon flag was not set." >&2
fi

sync
hdiutil detach "$MOUNT_POINT"
hdiutil convert "$RW_DMG_PATH" -format UDZO -o "$DMG_PATH"

# Also set icon on the DMG file itself so Finder shows a branded icon pre-mount.
if command -v xcrun >/dev/null 2>&1 && xcrun --find DeRez >/dev/null 2>&1 && xcrun --find Rez >/dev/null 2>&1; then
  sips -i "$ICON_PATH" >/dev/null
  xcrun DeRez -only icns "$ICON_PATH" > "$DMG_ICON_RSRC"
  xcrun Rez -append "$DMG_ICON_RSRC" -o "$DMG_PATH"
  if command -v SetFile >/dev/null 2>&1; then
    SetFile -a C "$DMG_PATH"
  else
    echo "WARNING: SetFile not found; DMG file custom icon flag was not set." >&2
  fi
else
  echo "WARNING: DeRez/Rez tools not found; DMG file icon metadata was not embedded." >&2
fi

rm -rf "$STAGING_DIR"
rm -f "$RW_DMG_PATH"
rm -rf "$MOUNT_POINT"
rm -f "$DMG_ICON_RSRC"

echo "Built DMG: $DMG_PATH"
