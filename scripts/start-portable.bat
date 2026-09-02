@echo off
REM ============================================================
REM  antique - Portable launcher (for the built portable bundle)
REM
REM  This file lives inside dist\antique-portable\ and launches
REM  the packaged antique.exe. On first run it downloads Chromium
REM  via Playwright's browser manager.
REM ============================================================
setlocal
chcp 65001 >nul 2>nul
cd /d "%~dp0"

set "ANTIQUE_EXE=%~dp0antique\antique.exe"

if not exist "%ANTIQUE_EXE%" (
    echo [ERROR] antique.exe not found at %ANTIQUE_EXE%
    echo Did you run scripts\build-portable.bat?
    pause
    exit /b 1
)

REM --- First-run: download Chromium engine ---
if not exist "%LOCALAPPDATA%\antique-portable\.browsers-ready" (
    echo [setup] Downloading Chromium engine (one-time) ...
    "%ANTIQUE_EXE%" --version >nul 2>nul
    python -m playwright install chromium 2>nul
    if exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%\antique-portable" 2>nul
    type nul > "%LOCALAPPDATA%\antique-portable\.browsers-ready"
)

echo.
echo   ============================================
echo    antique portable is starting
echo    Dashboard : http://127.0.0.1:8080/
echo    API docs  : http://127.0.0.1:8080/docs
echo   ============================================
echo.

"%ANTIQUE_EXE%" serve --ui-port 8080
set EXITCODE=%ERRORLEVEL%

if not %EXITCODE%==0 (
    echo.
    echo [ERROR] antique exited with code %EXITCODE%
    pause
    exit /b %EXITCODE%
)

exit /b 0
