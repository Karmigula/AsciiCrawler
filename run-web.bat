@echo off
rem Watch it in a browser instead of a window: http://127.0.0.1:8000
cd /d "%~dp0"
.venv\Scripts\python.exe -m uvicorn web.app:app --host 127.0.0.1 --port 8000 --reload
pause
