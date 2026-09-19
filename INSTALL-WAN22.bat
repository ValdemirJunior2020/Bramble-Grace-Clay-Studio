@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================================
echo  Bramble ^& Grace - Install Wan 2.2 5B Clay Performance
echo ============================================================
echo.
echo This downloads the official local image-to-video model files.
echo The download is large and can take a while.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_optional.ps1" -Component wan22
if errorlevel 1 (
  echo.
  echo Installation failed. Review the message above.
  pause
  exit /b 1
)
echo.
echo Wan 2.2 5B installation complete.
pause
