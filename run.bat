@echo off
rem Launch AsciiCrawler. Double-click, or run from a terminal.
rem Works from any working directory: everything is resolved relative to this
rem file, so shortcuts and pinned launchers behave.

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo Could not find .venv\Scripts\python.exe
    echo.
    echo Create the environment first:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install pygame-ce numpy pytest
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py

rem Only hold the window open on a crash, so a normal quit closes cleanly but
rem a traceback is still readable after a double-click.
if errorlevel 1 (
    echo.
    echo AsciiCrawler exited with an error ^(code %errorlevel%^).
    pause
)
