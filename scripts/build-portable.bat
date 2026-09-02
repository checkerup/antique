@echo off
REM ============================================================
REM  antique - Portable Windows build script
REM  Creates a self-contained portable directory using PyInstaller.
REM
REM  Usage:  scripts\build-portable.bat
REM  Output: dist\antique-portable\antique\antique.exe
REM
REM  No code signing is performed. The resulting .exe will show
REM  SmartScreen warnings on first run. See docs/packaging/SIGNING.md.
REM ============================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0\.."

echo [build] === antique portable build ===

REM --- Check Python ---
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found on PATH. Install Python 3.10+.
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info[0]*100+sys.version_info[1]>=310 else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python 3.10+ required.
    exit /b 1
)

REM --- Activate or create venv ---
if not exist ".venv\Scripts\activate.bat" (
    echo [build] Creating .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] venv creation failed.
        exit /b 1
    )
)

call .venv\Scripts\activate.bat

REM --- Install build dependencies ---
echo [build] Installing PyInstaller + project deps ...
pip install -q pyinstaller>=6.0
pip install -q -e .
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    exit /b 1
)

REM --- Clean previous builds ---
if exist "dist\antique-portable" rmdir /s /q "dist\antique-portable"
if exist "build\antique" rmdir /s /q "build\antique"

REM --- Run PyInstaller ---
echo [build] Building portable executable ...
pyinstaller packaging\antique.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    exit /b 1
)

REM --- Rename output to dist\antique-portable ---
if exist "dist\antique" (
    ren "dist\antique" "antique-portable" 2>nul
    if not exist "dist\antique-portable" move "dist\antique" "dist\antique-portable" >nul
)

REM --- Copy portable launcher ---
copy /y "scripts\start-portable.bat" "dist\antique-portable\start.bat" >nul 2>nul

REM --- Verify output ---
if not exist "dist\antique-portable\antique\antique.exe" (
    echo [ERROR] Expected output not found: dist\antique-portable\antique\antique.exe
    echo [build] Contents of dist:
    dir /b dist\ 2>nul
    exit /b 1
)

echo.
echo   ============================================
echo    Build complete!
echo    Output: dist\antique-portable\antique\antique.exe
echo    Run:    dist\antique-portable\start.bat
echo   ============================================
echo.
echo   NOTE: No code signing applied. Windows SmartScreen
echo   may warn on first run. See docs\packaging\SIGNING.md
echo.

exit /b 0
