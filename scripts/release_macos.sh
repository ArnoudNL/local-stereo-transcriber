#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

has_signing_identity() {
	[[ -n "${APPLE_CODESIGN_IDENTITY:-}" ]]
}

has_notarization_credentials() {
	[[ -n "${NOTARYTOOL_PROFILE:-}" ]] || {
		[[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_PASSWORD:-}" ]]
	}
}

"$ROOT_DIR/scripts/build_macos_launcher_app.sh"
"$ROOT_DIR/scripts/build_macos_desktop_app.sh"

if has_signing_identity; then
	"$ROOT_DIR/scripts/sign_apps.sh"
else
	echo "Skipping code signing (APPLE_CODESIGN_IDENTITY is not set)."
	echo "Apps will be unsigned and intended for local/private use."
fi

"$ROOT_DIR/scripts/build_macos_dmg.sh"

if has_signing_identity && has_notarization_credentials; then
	"$ROOT_DIR/scripts/notarize_dmg.sh"
else
	echo "Skipping notarization (signing identity and/or notary credentials not configured)."
fi

echo "macOS release pipeline complete."
