@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title Push BeLiving to GitHub
echo.
echo  === Push BeLiving to GitHub ===
echo.
where git >nul 2>nul
if errorlevel 1 (
  echo  Git is not installed. Get it from https://git-scm.com/download/win then run this again.
  pause & exit /b 1
)

rem --- safety check: never upload key files ---
for /r %%F in (.env keys.env) do if exist "%%F" (
  echo  STOP: found a key file: %%F
  echo  Move it out of this folder first. Keys must never go to GitHub.
  pause & exit /b 1
)

if not exist ".git" (
  git init -b main >nul
  git config user.name >nul 2>nul || git config user.name "Rakshita Kumar"
  git config user.email >nul 2>nul || git config user.email "dr.doomlord46@gmail.com"
  git add -A
  git commit -m "BeLiving: sample app (new calorie tracker), beat the clock, chatbot, voice journal, games, box breathing, pomodoro, food scan API" >nul
  echo  Local repo created and committed.
)

git remote get-url origin >nul 2>nul
if errorlevel 1 (
  where gh >nul 2>nul
  if not errorlevel 1 (
    echo  Creating private GitHub repo "BeLiving" with GitHub CLI...
    gh repo create BeLiving --private --source . --remote origin --push && goto done
  )
  echo  1. A browser tab will open on github.com/new
  echo  2. Repository name: BeLiving   ^|  leave README / .gitignore / license UNTICKED
  echo  3. Click "Create repository" and copy the URL it shows ^(ends in .git^)
  start "" "https://github.com/new?name=BeLiving"
  echo.
  set /p URL= Paste the repo URL here and press Enter: 
  git remote add origin "!URL!"
)

git push -u origin main
if errorlevel 1 (
  echo.
  echo  Push failed. If a GitHub sign-in window appeared, finish signing in and run this again.
  pause & exit /b 1
)

:done
echo.
echo  Done. BeLiving is on GitHub.
pause
