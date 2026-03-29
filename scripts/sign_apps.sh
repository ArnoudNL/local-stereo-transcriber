#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

IDENTITY="${APPLE_CODESIGN_IDENTITY:-}"
if [[ -z "$IDENTITY" ]]; then
  echo "ERROR: APPLE_CODESIGN_IDENTITY is not set." >&2
  echo "Example: export APPLE_CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'" >&2
  exit 1
fi

apps=(
  "$DIST_DIR/LocalStereoTranscriberLauncher.app"
  "$DIST_DIR/LocalStereoTranscriberDesktop.app"
)

for app in "${apps[@]}"; do
  if [[ ! -d "$app" ]]; then
    echo "ERROR: app not found: $app" >&2
    echo "Build apps first with scripts/build_macos_launcher_app.sh and scripts/build_macos_desktop_app.sh" >&2
    exit 1
  fi

  echo "Signing $app"
  codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$app"

  echo "Verifying signature for $app"
  codesign --verify --deep --strict --verbose=2 "$app"
done

echo "Code signing complete."
