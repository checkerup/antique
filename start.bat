@echo off
REM ============================================================
REM  antique - one-click launcher (Windows)
REM  First run: creates a venv, installs deps + Chromium.
REM  Later runs: just starts the server.
REM ============================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo [info] Checking Python installation...
where python >nul 2>nul
if errorlevel 1 goto :no_python

python -c "import sys; sys.exit(0 if sys.version_info[0]*100+sys.version_info[1]>=310 else 1)" >nul 2>nul
if errorlevel 1 goto :python_bad

if not exist ".venv\Scripts\activate.bat" goto :setup

call .venv\Scripts\activate.bat
python -c "import fastapi, playwright, typer, multipart" >nul 2>nul
if errorlevel 1 goto :repair
if not exist ".venv\.antique-browsers-v2" goto :install_browsers

goto :start_server

:setup
echo [setup] Creating virtual environment '.venv'...
python -m venv .venv
if not exist ".venv\Scripts\activate.bat" goto :venv_fail

:repair
echo [setup] Upgrading pip...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo [setup] Installing dependencies from requirements.txt...
pip install -r requirements.txt
if errorlevel 1 goto :install_fail

echo [setup] Installing antique...
pip install -e .
if errorlevel 1 goto :install_fail

:install_browsers
echo [setup] Downloading Chromium, Firefox and WebKit engines (one-time)...
python -m playwright install chromium firefox webkit
if errorlevel 1 goto :playwright_fail

echo [setup] Preparing Camoufox deep-stealth engine (best effort)...
python -m camoufox fetch >nul 2>nul
if errorlevel 1 echo [warn] Camoufox download skipped. Chromium/Firefox/WebKit are ready.
type nul > ".venv\.antique-browsers-v2"

goto :start_server

:start_server
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
if errorlevel 1 goto :server_fail
goto :end

:no_python
echo [ERROR] Python was not found in your system PATH.
echo Please install Python 3.10+ and ensure "Add Python to PATH" is checked during setup.
echo Download from: https://www.python.org/downloads/
goto :pause_and_exit

:python_bad
echo [ERROR] Python is not installed correctly, version is too old, or it is the Windows Store shortcut.
echo Please download and install Python 3.10+ from https://www.python.org/downloads/
echo Make sure to check the box "Add Python to PATH" during installation.
goto :pause_and_exit

:venv_fail
echo [ERROR] Failed to create virtual environment '.venv'.
echo Please check folder permissions and try again.
goto :pause_and_exit

:install_fail
echo [ERROR] Failed to install dependencies.
goto :pause_and_exit

:playwright_fail
echo [ERROR] Failed to download Playwright browser engines.
goto :pause_and_exit

:server_fail
echo.
echo [ERROR] antique server exited with an error.
goto :pause_and_exit

:pause_and_exit
echo.
pause
exit /b 1

:end
pause
