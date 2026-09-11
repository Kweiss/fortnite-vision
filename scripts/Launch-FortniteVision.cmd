@echo off
setlocal

for %%I in ("%~dp0..") do set "PROJECT_ROOT=%%~fI"
set "PYTHON=%PROJECT_ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    start "FortniteVision setup" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\scripts\Start-FortniteVision.ps1"
    exit /b
)

start "FortniteVision" /D "%PROJECT_ROOT%" "%PYTHON%" -m droid_monitor
