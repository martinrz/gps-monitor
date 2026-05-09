@echo off
REM ============================================================
REM build_windows.bat — Build GPS Monitor for Windows
REM
REM Produces:
REM   dist\GPS Monitor\            — standalone directory bundle
REM   dist\GPS_Monitor_1.0_Setup.exe — Inno Setup installer
REM
REM Prerequisites:
REM   pip install pyinstaller Pillow
REM   Inno Setup 6  https://jrsoftware.org/isinfo.php  (for installer)
REM
REM Usage:
REM   cd <project root>
REM   build\build_windows.bat
REM ============================================================
setlocal EnableDelayedExpansion

set APP_NAME=GPS Monitor
set VERSION=1.0
set DIST_DIR=dist\GPS Monitor

echo === GPS Monitor - Windows build ===
echo   Python: & python --version
echo.

REM Move to project root (one level above this script)
cd /d "%~dp0.."

REM ── Step 1: Generate icons ────────────────────────────────
echo [1/3] Generating icons...
python build\make_icons.py
if errorlevel 1 (
    echo WARNING: Icon generation failed. Continuing without icons.
)

REM ── Step 2: PyInstaller ───────────────────────────────────
echo [2/3] Running PyInstaller...
pyinstaller build\gps_monitor.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

if not exist "%DIST_DIR%" (
    echo ERROR: %DIST_DIR% not found after build.
    exit /b 1
)
echo   Built: %DIST_DIR%

REM ── Step 3: Inno Setup installer ─────────────────────────
echo [3/3] Building installer...

REM Look for Inno Setup in common install locations
set ISCC=
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
)

if "!ISCC!"=="" (
    echo   Inno Setup not found. Skipping installer creation.
    echo   Install from: https://jrsoftware.org/isinfo.php
    echo   Then re-run this script or run manually:
    echo     ISCC build\installer.iss
    echo.
    echo   Alternatively, distribute the folder:  dist\GPS Monitor\
) else (
    !ISCC! build\installer.iss /DAppVersion=%VERSION%
    if errorlevel 1 (
        echo ERROR: Inno Setup failed.
        exit /b 1
    )
    echo   Installer: dist\GPS_Monitor_%VERSION%_Setup.exe
)

echo.
echo === Done ===
echo   Bundle:    %DIST_DIR%\
echo   Installer: dist\GPS_Monitor_%VERSION%_Setup.exe (if Inno Setup ran)
