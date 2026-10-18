@echo off
setlocal

set "PID_FILE=%~dp0runtime\waky.pid"

if not exist "%PID_FILE%" (
  echo PID file not found. Open Task Manager and end pythonw.exe from the Waky .venv folder.
  pause
  exit /b 1
)

set /p WAKY_PID=<"%PID_FILE%"

if "%WAKY_PID%"=="" (
  echo PID file is empty. Open Task Manager and end pythonw.exe from the Waky .venv folder.
  del "%PID_FILE%" >nul 2>&1
  pause
  exit /b 1
)

echo Stopping Waky process %WAKY_PID%...
taskkill /PID %WAKY_PID% /F
if errorlevel 1 (
  echo Could not stop process %WAKY_PID%.
  echo Open Task Manager and end pythonw.exe from the Waky .venv folder.
  pause
  exit /b 1
)

del "%PID_FILE%" >nul 2>&1
echo Waky stopped.
endlocal
