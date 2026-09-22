@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3.12 run.py
) else (
  python run.py
)
if %errorlevel% neq 0 echo If Python was not found, install Python 3.12 from https://www.python.org/downloads/ and select Add Python to PATH.
pause
