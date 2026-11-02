@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo First run: creating virtual env and installing packages, about 1-2 minutes...
  python -m venv .venv
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
.venv\Scripts\python.exe demo.py %*
