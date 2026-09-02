@echo off
REM ============================================================
REM  antique - One-click Windows launcher
REM
REM  Handles: install, update, rollback, serve
REM
REM  Usage:
REM    antique-launcher.bat                    (default: serve)
REM    antique-launcher.bat install             (fresh install)
REM    antique-launcher.bat update              (update deps + package)
REM    antique-launcher.bat rollback [version]  (restore previous)
REM    antique-launcher.bat serve               (start server)
REM
REM  No code signing, no admin elevation.
REM  Backups stored in .antique-backups\
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "ACTION=%~1"
if "%ACTION%"=="" set "ACTION=serve"
set "ANTIQUE_VERSION="
set "BACKUP_DIR=%~dp0.antique-backups"

REM --- Check Python ---
where python >nul 2>nul
if errorlevel 1 goto :no_python
python -c "import sys; sys.exit(0 if sys.version_info[0]*100+sys.version_info[1]>=310 else 1)" >nul 2>nul
if errorlevel 1 goto :python_bad

REM --- Dispatch ---
if /i "%ACTION%"=="install"  goto :do_install
if /i "%ACTION%"=="update"   goto :do_update
if /i "%ACTION%"=="rollback" goto :do_rollback
if /i "%ACTION%"=="serve"    goto :check_then_serve
goto :usage

:check_then_serve
if not exist ".venv\Scripts\activate.bat" goto :do_install
call .venv\Scripts\activate.bat
python -c "import fastapi, playwright, typer" >nul 2>nul
if errorlevel 1 goto :do_install
if not exist ".venv\.antique-browsers-v2" goto :install_browsers
goto :start_server

:do_install
echo [install] Setting up antique ...
REM --- Backup current state if upgrading ---
if exist ".venv\Scripts\activate.bat" (
    echo [install] Backing up current installation ...
    for /f "tokens=2 delims==" %%v in ('python -c "from src import __version__; print(__version__)" 2^>nul') do set "ANTIQUE_VERSION=%%v"
    if "%ANTIQUE_VERSION%"=="" set "ANTIQUE_VERSION=unknown"
    set "STAMP=%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%"
    set "STAMP=!STAMP: =0!"
    set "STAMP=!STAMP::=!"
    set "BACKUP_NAME=v!ANTIQUE_VERSION!_!STAMP!"
    if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
    echo !ANTIQUE_VERSION!> "%BACKUP_DIR%\last_version.txt"
    echo [install] Recorded current version: !ANTIQUE_VERSION!
)

REM --- Create or reuse venv ---
if not exist ".venv\Scripts\activate.bat" (
    echo [install] Creating virtual environment ...
    python -m venv .venv
    if errorlevel 1 goto :venv_fail
)
call .venv\Scripts\activate.bat

echo [install] Upgrading pip ...
python -m pip install --upgrade pip -q

echo [install] Installing dependencies (pinned) ...
pip install -c packaging\requirements-lock.txt -r requirements.txt
if errorlevel 1 goto :install_fail

echo [install] Installing antique ...
pip install -e .
if errorlevel 1 goto :install_fail

:install_browsers
echo [install] Downloading Chromium engine (one-time) ...
python -m playwright install chromium
if errorlevel 1 goto :playwright_fail
type nul > ".venv\.antique-browsers-v2"

echo.
echo   ============================================
echo    Install complete! Version: see 'python -m src.cli --version'
echo   ============================================
echo.
if /i "%ACTION%"=="install" goto :end

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

:do_update
echo [update] Updating antique ...
call .venv\Scripts\activate.bat 2>nul
if errorlevel 1 goto :do_install

REM --- Record pre-update version for rollback ---
for /f "tokens=2 delims==" %%v in ('python -c "from src import __version__; print(__version__)" 2^>nul') do set "ANTIQUE_VERSION=%%v"
if "%ANTIQUE_VERSION%"=="" set "ANTIQUE_VERSION=unknown"
if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
echo !ANTIQUE_VERSION!> "%BACKUP_DIR%\last_version.txt"
echo [update] Pre-update version: !ANTIQUE_VERSION!

echo [update] Pulling latest dependencies ...
pip install --upgrade -c packaging\requirements-lock.txt -r requirements.txt
if errorlevel 1 goto :install_fail

echo [update] Reinstalling antique ...
pip install -e . --force-reinstall --no-deps
if errorlevel 1 goto :install_fail

echo.
echo   ============================================
echo    Update complete!
echo   ============================================
echo.
goto :end

:do_rollback
echo [rollback] Rolling back to previous version ...
if not exist "%BACKUP_DIR%\last_version.txt" (
    echo [ERROR] No previous version recorded. Nothing to roll back to.
    goto :pause_and_exit
)
set /p PREV_VERSION=<"%BACKUP_DIR%\last_version.txt"
echo [rollback] Previous version: !PREV_VERSION!
echo.
echo To manually roll back:
echo   1. git checkout v!PREV_VERSION!  ^(or the corresponding commit^)
echo   2. call .venv\Scripts\activate.bat
echo   3. pip install -e .
echo   4. scripts\antique-launcher.bat serve
echo.
echo [rollback] No automatic git rollback performed — check out the
echo           correct commit/tag manually and re-run install.
goto :end

:usage
echo Usage: %~nx0 [install^|update^|rollback^|serve]
echo.
echo   install   Fresh install or repair
echo   update    Update dependencies + reinstall antique
echo   rollback  Show previous version and rollback instructions
echo   serve     Start the server ^(default^)
goto :end

:no_python
echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org/downloads/
goto :pause_and_exit

:python_bad
echo [ERROR] Python 3.10+ required. Download from https://www.python.org/downloads/
goto :pause_and_exit

:venv_fail
echo [ERROR] Failed to create virtual environment.
goto :pause_and_exit

:install_fail
echo [ERROR] Dependency installation failed.
goto :pause_and_exit

:playwright_fail
echo [ERROR] Failed to download Chromium. Check network and retry.
goto :pause_and_exit

:server_fail
echo [ERROR] Server exited with an error.
goto :pause_and_exit

:pause_and_exit
echo.
pause
exit /b 1

:end
if /i "%ACTION%"=="serve" pause
exit /b 0
