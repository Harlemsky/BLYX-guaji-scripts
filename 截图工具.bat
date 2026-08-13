@echo off
cd /d "%~dp0"
title BaiLian Screenshot Tool
.\.venv\Scripts\python.exe src\capture.py
echo.
echo Tool exited. Press any key to close this window.
pause >nul
