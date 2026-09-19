@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================================
echo  Bramble ^& Grace - Install Motionity Scene Animator
echo ============================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_optional.ps1" -Component motionity
if errorlevel 1 (
  echo.
  echo Motionity installation failed. Review the message above.
  pause
  exit /b 1
)
echo.
echo Motionity installation complete.
echo Restart Clay Studio with STOP.bat then START.bat.
pause
