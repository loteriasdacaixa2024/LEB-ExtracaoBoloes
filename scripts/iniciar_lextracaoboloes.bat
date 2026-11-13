@echo off
chcp 65001 >nul
cd /d "%~dp0.."

set "PYTHON=%~dp0..\LEB_venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set "PORTA=8088"
set "URL=http://127.0.0.1:%PORTA%/"
netstat -ano | findstr /C:":%PORTA% " | findstr "LISTENING" >nul
if errorlevel 1 (
  start "LEB" "%PYTHON%" -u "%~dp0..\LEB.py"
  ping 127.0.0.1 -n 3 >nul
)
start "" "%URL%"
