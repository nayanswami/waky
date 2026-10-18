@echo off
setlocal
cd /d "%~dp0"

set QT_ENABLE_HIGHDPI_SCALING=0
set QT_AUTO_SCREEN_SCALE_FACTOR=0
set QT_SCALE_FACTOR_ROUNDING_POLICY=Round
set QT_LOGGING_RULES=qt.qpa.window.warning=false

echo Starting Waky...
echo If no UI appears, check the system tray.
echo Logs path: %CD%\logs\error.log
echo.

if not exist ".venv\Scripts\activate.bat" (
  echo Waky virtual environment was not found.
  echo.
  echo Setup steps:
  echo   py -3.11 -m venv .venv
  echo   .venv\Scripts\activate
  echo   python -m pip install --upgrade pip
  echo   pip install -r requirements.txt
  echo   run.bat
  echo.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python main.py
set EXITCODE=%ERRORLEVEL%

if not "%EXITCODE%"=="0" (
  echo.
  echo Waky crashed with exit code %EXITCODE%.
  echo Check logs\error.log and logs\debug.log if debug logging is enabled.
  pause
)

exit /b %EXITCODE%
