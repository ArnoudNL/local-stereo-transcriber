# Local Dual-Channel Call Transcription (faster-whisper) 🎙️

Transcribe stereo call-center WAV recordings fully local on your machine.

- Left channel = Client
- Right channel = Agent
- Output = one merged chronological transcript with timestamps
- No cloud API calls ☁️❌

## Features ✨

- Fully local transcription using `faster-whisper`
- Dual-channel separation (left/right) for clean speaker labeling
- Chronological merge of both channels into one transcript
- Streamlit drag-and-drop web UI (app title: `Gesprek naar Tekst` / `Call to Text`)
- Streamlit-first workflow (no required CLI input arguments)
- Optional CLI workflow for automation/scripting
- Pause, resume, and stop controls during transcription
- Local model caching in `local_models`

## Prerequisites 🧰

- Python 3.10+
- macOS/Linux/Windows
- Stereo WAV input file (exactly 2 channels)

Developer tooling (recommended):

- ripgrep (`rg`) for fast repository-wide audits and cross-reference checks

## Quick Start 🚀

### 1) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

Runtime dependencies:

```bash
pip install -r requirements.txt
```

Development tools (lint/format/test + packaging):

```bash
pip install -r requirements-dev.txt
```

Enable pre-commit hooks (recommended):

```bash
pre-commit install
```

Note: pre-commit requires this folder to be a Git repository.

macOS developer system tools:

```bash
brew bundle
```

This installs system CLI dependencies from `Brewfile` (including `ripgrep`).

### 3) Run the Streamlit app (recommended) 🖥️

```bash
python -m streamlit run streamlit_app.py
```

Then open the local URL printed by Streamlit (typically `http://localhost:8501`), drop your stereo WAV file, and download the merged transcript.

## Streamlit UI behavior

Language behavior:

- Top toggle: interface language (`Nederlands` / `English`)
- Sidebar option: transcription language (`Auto detect`, `Dutch`, `English`)
- Default interface language: `Nederlands`
- Default transcription language: `Auto detect`

Settings behavior:

- `compute_type` is intentionally fixed to `int8` in the UI for simpler operation
- Model size options: `large-v3` (default) and `medium`
- Device options: `auto` (default), `cpu`, `cuda`
- Model cache location on macOS: `~/Library/Application Support/LocalStereoTranscriber/local_models`
- Beam size range: `1-10` (default `5`)
- Temperature range: `0.0-1.0` (default `0.0`, step `0.1`)
- Speaker labels are selectable as `Client`/`Agent` per channel
- Start button turns green when a WAV is uploaded and the worker is idle

Quick VS Code launch (favorite-style):

1. Run `Tasks: Run Task` and select `start-streamlit`
2. Run `Tasks: Run Task` and select `open-streamlit-url`

On-demand localhost starter scripts (starts only when you run it):

- macOS/Linux:

```bash
bash scripts/start_localhost.sh
```

- Windows (Command Prompt):

```bat
scripts\start_localhost.bat
```

These scripts:

1. Reuse existing Streamlit on `localhost:8501` when already running.
2. Otherwise start Streamlit and open `http://localhost:8501` once ready.

## Optional CLI usage

The first run downloads the model into `local_models`.

```bash
python3 transcribe_dual_channel_local.py \
  /path/to/call.wav \
  /path/to/output_transcript.txt \
  --model-size large-v3 \
  --model-dir ./local_models \
  --language nl \
  --device auto \
  --compute-type int8 \
  --beam-size 5 \
  --temperature 0.0
```

Notes:

- If you run the CLI script without required arguments, it prints guidance and exits (Streamlit-first behavior).
- For automatic language detection in CLI, use `--language auto`.

## Quality checks ✅

Run pylint:

```bash
pylint transcribe_dual_channel_local.py streamlit_app.py
```

Run formatting checks:

```bash
black --check .
isort --check-only .
```

Run full local quality pipeline:

```bash
isort . && black . && pylint transcribe_dual_channel_local.py streamlit_app.py && black --check . && isort --check-only .
```

Or run one VS Code task:

1. Open Command Palette
2. Run `Tasks: Run Task`
3. Select `quality`

Run all pre-commit hooks on demand:

```bash
pre-commit run --all-files
```

## Continuous Integration

GitHub Actions workflow at `.github/workflows/ci.yml` runs:

1. isort, black, and pylint quality checks
2. macOS app builds for launcher and desktop
3. Smoke tests:
  - launcher app serves on `127.0.0.1:8501`
  - desktop app backend mode serves on `127.0.0.1:8502`

## UI palette tokens 🎨

The color system is centralized in `streamlit_app.py` near the top of the file.

- Brand palette:
  - `COLOR_BRAND = #0a7ea4`
  - `COLOR_BRAND_SOFT = #e7f5fa`
  - `COLOR_SIDEBAR_HEADING = #375b6b`
- Upload surface palette:
  - `COLOR_UPLOAD_BORDER = #8ac6dd`
  - `COLOR_UPLOAD_BG = #f8fcfe`
  - `COLOR_UPLOAD_OVERLAY_TEXT = #1b4f63`
- Success/status palette:
  - `COLOR_OK = #1f9d55`
  - `COLOR_SUCCESS_BG = #edf9f0`
  - `COLOR_SUCCESS_TEXT = #1a7f43`
  - `COLOR_SUCCESS_BORDER = #caebd5`

## App packaging and distribution 📦

You can ship this project in 3 ways:

1. Standalone launcher app (`LocalStereoTranscriberLauncher.app`)
2. Native desktop window app (`LocalStereoTranscriberDesktop.app`)
3. DMG installer containing both apps

Install packaging dependencies first:

```bash
pip install -r requirements-dev.txt
```

Build standalone launcher app:

```bash
bash scripts/build_macos_launcher_app.sh
```

Build native desktop window app:

```bash
bash scripts/build_macos_desktop_app.sh
```

Build DMG installer:

```bash
bash scripts/build_macos_dmg.sh
```

Run local release gate before packaging (recommended):

```bash
bash scripts/release_gate.sh
```

This gate runs quality checks, builds launcher + desktop apps, and smoke-tests both binaries locally.
It expects ports `8501` and `8502` to be free.

You can also run these via VS Code tasks:

1. `build-launcher-app`
2. `build-desktop-app`
3. `build-dmg`
4. `release-gate`

Build outputs are created in `dist/`.

Both macOS app bundles include:

- Custom app icon generated at `assets/AppIcon.icns`
- Bundle identifiers:
  - `com.arnoudvanrooij.localstereotranscriber.launcher`
  - `com.arnoudvanrooij.localstereotranscriber.desktop`
- Version metadata (`CFBundleShortVersionString` and `CFBundleVersion`) set to `1.0.0`

### macOS code signing and notarization (recommended for sharing) 🔐

To avoid Gatekeeper warnings when sharing outside your own Mac, sign and notarize.
If you do not have an Apple Developer account, you can still build and package unsigned apps for local/private use.

1. Configure Apple credentials (see `scripts/notarization.env.example`)
2. Export the required environment variables in your shell
3. Run the full release pipeline:

```bash
bash scripts/release_macos.sh
```

Behavior of `release_macos.sh`:

- Always builds launcher + desktop apps and DMG.
- Signs apps only when `APPLE_CODESIGN_IDENTITY` is set.
- Notarizes DMG only when signing identity and notary credentials are set.

You can also run each step separately:

```bash
bash scripts/sign_apps.sh
bash scripts/notarize_dmg.sh
```

Or use VS Code tasks:

1. `sign-apps`
2. `notarize-dmg`
3. `release-macos`

## Project structure

```text
.
├── streamlit_app.py                  # Streamlit UI and job controls
├── transcribe_dual_channel_local.py  # Core transcription pipeline
├── requirements.txt                  # Runtime dependencies
├── requirements-dev.txt              # Dev + packaging dependencies
├── scripts/                          # Build, sign, notarize, release helpers
├── packaging/                        # Runtime wrappers (desktop/launcher)
└── local_models/                     # Local cached model files
```

## Architecture and naming

- Source of truth rules are documented in `ARCHITECTURE_RULES.md`.
- Canonical macOS build scripts are:
  - `scripts/build_macos_launcher_app.sh`
  - `scripts/build_macos_desktop_app.sh`
  - `scripts/build_macos_dmg.sh`
- Legacy script names (`build_launcher_app.sh`, `build_desktop_app.sh`, `build_dmg.sh`) are kept as compatibility shims.
- PyInstaller may regenerate `LocalStereoTranscriberLauncher.spec` and
  `LocalStereoTranscriberDesktop.spec` during local builds; these are build artifacts, not source-of-truth configuration.

## Output format

Each line in the transcript is chronological:

```text
[00:00:03.120 - 00:00:05.410] Client: Hello, I need help with my invoice.
[00:00:05.620 - 00:00:07.900] Agent: Sure, I can help with that.
```

## Troubleshooting 🛠️

- App does not open in browser:
  - Start manually with `python -m streamlit run streamlit_app.py`.
- Transcription seems slow:
  - Keep `compute_type=int8`, reduce `beam_size`, and use `device=auto`.
- No transcript output:
  - Verify your file is true stereo WAV (2 channels).
- UI language/transcription language confusion:
  - Top toggle controls interface language; sidebar controls transcription language.

## Release checklist ✅

Use this list before sharing a new build:

1. Update version metadata in build scripts/plists (if needed).
2. Run quality checks:

```bash
isort . && black . && pylint transcribe_dual_channel_local.py streamlit_app.py && black --check . && isort --check-only .
```

3. Build apps and DMG:

```bash
bash scripts/build_macos_launcher_app.sh
bash scripts/build_macos_desktop_app.sh
bash scripts/build_macos_dmg.sh
```

4. Sign and notarize (recommended):

```bash
bash scripts/sign_apps.sh
bash scripts/notarize_dmg.sh
```

5. Smoke-test deliverables from `dist/`:
  - Open both `.app` bundles.
  - Install and launch from the `.dmg`.
  - Run a short stereo WAV and verify transcript download.

## Notes 📝

- Input must be a stereo WAV with exactly 2 channels.
- WAV channel splitting uses Python standard library modules for Python 3.14 compatibility.
- Streamlit default transcription language is `Auto detect`.
- Add `--keep-temp` in CLI if you want to keep split-channel audio files.

## Connect 🤝

- GitHub: https://github.com/arnoudvanrooij

Feel free to open issues, start discussions, or submit pull requests.

## License 📄

This project is released under the MIT License. See `LICENSE` for details.
