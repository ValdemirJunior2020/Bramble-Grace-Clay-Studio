@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
if errorlevel 1 (echo. & echo Could not start the studio. Check the logs folder. & pause & exit /b 1)
