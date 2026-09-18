@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
if errorlevel 1 (echo. & echo Installation failed. See the message above. & pause & exit /b 1)
echo. & echo Done. Double-click START.bat to open Bramble ^& Grace Clay Studio.
pause
