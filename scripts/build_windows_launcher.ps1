Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $python = "python"
}

Write-Host "Using Python: $python"

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --copy-metadata streamlit `
    --collect-all streamlit `
    --hidden-import faster_whisper `
    --collect-all faster_whisper `
    --hidden-import ctranslate2 `
    --collect-all ctranslate2 `
    --hidden-import onnxruntime `
    --collect-all onnxruntime `
    --name LocalStereoTranscriberLauncher `
    --add-data "$root\assets;assets" `
    --add-data "$root\streamlit_app.py;." `
    --add-data "$root\transcribe_dual_channel_local.py;." `
    "$root\packaging\launcher_runtime_wrapper.py"

Write-Host "Built Windows launcher at: $root\dist\LocalStereoTranscriberLauncher"
