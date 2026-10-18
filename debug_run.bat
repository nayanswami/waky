@echo off
setlocal
cd /d "%~dp0"

set QT_ENABLE_HIGHDPI_SCALING=0
set QT_AUTO_SCREEN_SCALE_FACTOR=0
set QT_SCALE_FACTOR_ROUNDING_POLICY=Round
set QT_LOGGING_RULES=qt.qpa.window.warning=false
set WAKY_DEBUG=1

echo Starting Waky in debug mode...
echo Logs path: %CD%\logs
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo Virtual environment missing. Run setup from README first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python main.py
echo.
echo Waky exited with code %ERRORLEVEL%.
pause
