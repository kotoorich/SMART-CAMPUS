@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Campus - Setup and Run

echo.
echo ==========================================
echo       SMART CAMPUS - SETUP AND START
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python 3.11 or 3.12 was not found. Install Python and enable Add Python to PATH.
  pause
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node.js 20+ and npm were not found.
  pause
  exit /b 1
)
python -c "import sys, struct; print('Detected Python:', sys.version); raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P')*8 == 64 else 1)"
if errorlevel 1 goto unsupported_python

if not exist "backend\.env" copy "backend\.env.example" "backend\.env" >nul
if not exist "frontend\.env" copy "frontend\.env.example" "frontend\.env" >nul

rem Validate an existing environment before reusing it; moved Windows venvs can break.
if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" -c "import sys" >nul 2>nul
  if errorlevel 1 (
    echo Existing virtual environment is invalid. Rebuilding...
    rmdir /s /q "backend\.venv"
  )
)
if not exist "backend\.venv\Scripts\python.exe" (
  echo Creating backend virtual environment...
  python -m venv "backend\.venv"
  if errorlevel 1 goto failed
)

echo Installing backend dependencies...
"backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto failed
"backend\.venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Africa/Accra'))"
if errorlevel 1 goto failed

if not exist "frontend\node_modules\vite\bin\vite.js" (
  echo Installing frontend dependencies...
  pushd frontend
  call npm ci
  if errorlevel 1 (
    echo npm ci failed; trying npm install...
    call npm install
    if errorlevel 1 (
      popd
      goto failed
    )
  )
  popd
)

echo.
echo Setup complete. Starting both services...
echo Backend API: http://127.0.0.1:8000
echo API docs:    http://127.0.0.1:8000/docs
echo Frontend:    http://127.0.0.1:5173
echo.
start "Smart Campus Backend" /D "%~dp0backend" "%~dp0backend\.venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
start "Smart Campus Frontend" /D "%~dp0frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"
timeout /t 8 /nobreak >nul
start "" "http://127.0.0.1:5173"
echo Keep both server windows open while using the app.
pause
exit /b 0

:unsupported_python
echo.
echo ERROR: Install 64-bit Python 3.11 or 3.12, then run this launcher again.
pause
exit /b 1

:failed
echo.
echo SETUP FAILED. Read the first error above.
pause
exit /b 1
