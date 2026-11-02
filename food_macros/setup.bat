@echo off
cd /d "%~dp0"
echo Setting up BeLiving Food Scan...
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements-dev.txt
if not exist .env copy .env.example .env
echo.
echo Done. Put your GEMINI_API_KEY in .env, then double-click run.bat
pause
