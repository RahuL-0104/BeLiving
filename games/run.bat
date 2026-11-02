@echo off
cd /d "%~dp0"
echo Starting BeLiving Mind Gym...
start "" http://localhost:8090
python app.py
if errorlevel 1 py app.py
pause
