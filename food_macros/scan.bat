@echo off
REM Usage: scan.bat path\to\photo.jpg   (or no argument to be asked for paths)
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python demo.py %*
pause
