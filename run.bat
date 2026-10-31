@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PLAYWRIGHT_BROWSERS_PATH=%~dp0.pw-browsers
start "" /b .venv\Scripts\python scripts\open_when_ready.py
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
