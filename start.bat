@echo off
REM ============================================================
REM  antique - one-click launcher (Windows)
REM  First run: creates a venv, installs deps + Chromium.
REM  Later runs: just starts the server.
REM ============================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH. Install Python 3.10+ and re-run.
  pause
  exit /b 1
)

set SETUP_NEEDED=0

if not exist ".venv\Scripts\activate.bat" (
  set SETUP_NEEDED=1
) else (
  call .venv\Scripts\activate.bat
  python -c "import fastapi, playwright, typer" >nul 2>nul
  if errorlevel 1 (
    echo [info] Virtual environment exists but dependencies are missing or corrupt.
    echo [info] Triggering repair / dependency installation...
    set SETUP_NEEDED=1
  )
)

if "%SETUP_NEEDED%"=="1" (
  echo [setup] Creating or repairing virtual environment...
  if not exist ".venv\Scripts\activate.bat" (
    python -m venv .venv
  )
  call .venv\Scripts\activate.bat
  echo [setup] Upgrading pip...
  python -m pip install --upgrade pip
  echo [setup] Installing antique + dependencies...
  pip install -e .
  echo [setup] Downloading Chromium engine (one-time)...
  python -m playwright install chromium
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo   ============================================
echo    antique is starting
echo    Dashboard : http://127.0.0.1:8080/
echo    API docs  : http://127.0.0.1:8080/docs
echo   ============================================
echo.
echo   (Press Ctrl+C to stop)
echo.

python -m src.cli serve --ui-port 8080

pause
