@echo off
rem Double-click to start pixel-pal. Creates a private Python environment on first run.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Setting up pixel-pal for the first time...
  py -3 -m venv .venv || python -m venv .venv || goto :nopython
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install --quiet -e . || goto :failed
)
start "" ".venv\Scripts\pythonw.exe" -m pixelpal
exit /b 0
:nopython
echo Python 3.10 or newer is required. Get it from https://www.python.org/downloads/
pause
exit /b 1
:failed
echo Installing dependencies failed. See the messages above.
pause
exit /b 1
