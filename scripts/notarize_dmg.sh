#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
DMG_PATH="$DIST_DIR/LocalStereoTranscriber.dmg"

if [[ ! -f "$DMG_PATH" ]]; then
  echo "ERROR: DMG not found: $DMG_PATH" >&2
  echo "Build it first with scripts/build_macos_dmg.sh" >&2
  exit 1
fi

if ! command -v xcrun >/dev/null 2>&1; then
  echo "ERROR: xcrun not found. Install Xcode Command Line Tools." >&2
  exit 1
fi

PROFILE="${NOTARYTOOL_PROFILE:-}"
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

submit_with_profile() {
  xcrun notarytool submit "$DMG_PATH" --keychain-profile "$PROFILE" --wait
}

submit_with_apple_id() {
  xcrun notarytool submit "$DMG_PATH" \
    --apple-id "$APPLE_ID" \
    --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --wait
}

if [[ -n "$PROFILE" ]]; then
  echo "Submitting DMG for notarization using keychain profile: $PROFILE"
  submit_with_profile
elif [[ -n "$APPLE_ID" && -n "$APPLE_TEAM_ID" && -n "$APPLE_APP_PASSWORD" ]]; then
  echo "Submitting DMG for notarization using APPLE_ID credentials"
  submit_with_apple_id
else
  echo "ERROR: notarization credentials are not configured." >&2
  echo "Use one of these options:" >&2
  echo "  1) export NOTARYTOOL_PROFILE='your-profile'" >&2
  echo "  2) export APPLE_ID='name@example.com'" >&2
  echo "     export APPLE_TEAM_ID='TEAMID'" >&2
  echo "     export APPLE_APP_PASSWORD='app-specific-password'" >&2
  exit 1
fi

echo "Stapling notarization ticket to DMG"
xcrun stapler staple "$DMG_PATH"

echo "Validating stapled DMG"
xcrun stapler validate "$DMG_PATH"

echo "Notarization complete: $DMG_PATH"
