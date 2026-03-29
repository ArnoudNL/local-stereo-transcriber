@echo off
setlocal EnableDelayedExpansion

set "ROOT_DIR=%~dp0.."
set "PYTHON_BIN=%ROOT_DIR%\.venv\Scripts\python.exe"
set "APP_FILE=%ROOT_DIR%\streamlit_app.py"
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8501"
set "URL=http://localhost:%PORT%"

if not exist "%PYTHON_BIN%" (
  echo Python environment not found at: %PYTHON_BIN%
  echo Create it first with:
  echo   py -m venv .venv
  echo   .venv\Scripts\activate
  echo   pip install -r requirements.txt
  exit /b 1
)

powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
  start "" "%URL%"
  exit /b 0
)

start "LocalStereoTranscriber" "%PYTHON_BIN%" -m streamlit run "%APP_FILE%" --server.port "%PORT%"

for /L %%i in (1,1,60) do (
  powershell -NoProfile -Command "try { Invoke-WebRequest -Uri '%URL%' -UseBasicParsing -TimeoutSec 1 ^| Out-Null; exit 0 } catch { exit 1 }"
  if "!ERRORLEVEL!"=="0" goto :open
  timeout /t 1 /nobreak >nul
)

echo Streamlit did not become ready at %URL% within 60 seconds.
exit /b 1

:open
start "" "%URL%"
exit /b 0
