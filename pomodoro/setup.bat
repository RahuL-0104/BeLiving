@echo off
cd /d "%~dp0"
echo Setting up Focus Lock...
python -m venv venv
if errorlevel 1 (
  echo.
  echo Python not found. Install it from python.org and tick "Add Python to PATH".
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q
echo.
echo Done! Now double-click run.bat
pause
