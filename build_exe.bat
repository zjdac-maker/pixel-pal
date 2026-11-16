@echo off
rem Builds a standalone dist\pixel-pal.exe with PyInstaller (no Python needed to run it).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" ( py -3 -m venv .venv || python -m venv .venv || exit /b 1 )
".venv\Scripts\python.exe" -m pip install --quiet -e .[build] || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name pixel-pal ^
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick ^
  packaging\entry.py || exit /b 1
echo.
echo Built dist\pixel-pal.exe
