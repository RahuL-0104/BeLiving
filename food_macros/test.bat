@echo off
cd /d "%~dp0"
if not exist .venv (
  echo Run setup.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
pip install -r requirements-dev.txt -q
python -m pytest -q
pause
