@echo off
cd /d "%~dp0"
set "VIEWER_PY=%~dp0..\..\work\viewer-venv\Scripts\python.exe"
if not exist "%VIEWER_PY%" (
  echo The viewer environment is missing. See README.md for setup.
  pause
  exit /b 1
)
"%VIEWER_PY%" launcher.py
if errorlevel 1 pause
