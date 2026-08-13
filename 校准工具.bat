@echo off
cd /d "%~dp0"
if not exist ".\.venv\Scripts\pythonw.exe" (
    echo Environment missing. Please run setup first.
    pause
    exit /b 1
)
start "" ".\.venv\Scripts\pythonw.exe" src\calibrate.py
