# Architecture Rules

This document defines the single source of truth and file ownership boundaries for this repository.

## Single Source of Truth

1. Product behavior belongs in:
- `streamlit_app.py` (UI and interaction behavior)
- `transcribe_dual_channel_local.py` (core transcription behavior)

2. Runtime wrappers are host shells only:
- `packaging/desktop_runtime_wrapper.py`
- `packaging/launcher_runtime_wrapper.py`

3. Build and release scripts create artifacts only:
- `scripts/build_macos_launcher_app.sh`
- `scripts/build_macos_desktop_app.sh`
- `scripts/build_macos_dmg.sh`
- `scripts/sign_apps.sh`
- `scripts/notarize_dmg.sh`
- `scripts/release_macos.sh`

4. Generated artifacts are never edited directly:
- `build/`
- `dist/`

## Ownership Boundaries

### Core app files

- `streamlit_app.py`
  - Owns uploader rules, UI controls, settings, validation, and UX behavior.
- `transcribe_dual_channel_local.py`
  - Owns audio splitting, model loading, transcription pipeline, and transcript output.

### Wrapper files

- `packaging/desktop_runtime_wrapper.py`
  - Owns native window lifecycle, process start/stop, and startup/shutdown.
  - Must not define feature policy (for example accepted file types).
- `packaging/launcher_runtime_wrapper.py`
  - Owns browser-launch startup flow and runtime bootstrap.
  - Must not define feature policy.

### Shared infrastructure

- `app_logging.py`
  - Owns logging configuration, sink setup, and runtime-safe logging behavior.

## Change Rules

1. If behavior should be the same in Launcher and Desktop, change it in `streamlit_app.py` or `transcribe_dual_channel_local.py`.
2. Wrapper changes are only for runtime hosting concerns.
3. Avoid putting business rules behind wrapper-specific environment flags unless absolutely necessary and documented.
4. Keep old script names only as compatibility shims. Canonical names are the `build_macos_*` scripts.

## Build Chain

1. Build launcher: `scripts/build_macos_launcher_app.sh`
2. Build desktop: `scripts/build_macos_desktop_app.sh`
3. Build DMG: `scripts/build_macos_dmg.sh`
4. Sign apps: `scripts/sign_apps.sh`
5. Notarize DMG: `scripts/notarize_dmg.sh`
6. Full pipeline: `scripts/release_macos.sh`

## Validation Checklist

After behavior changes:

1. Run quality checks.
2. Build launcher and desktop.
3. Smoke test both app modes with the same input/output expectations.
4. Confirm logs are clean of new errors.
