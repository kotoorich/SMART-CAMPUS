@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Smart Campus - Backend API

where python >nul 2>nul
if errorlevel 1 (
  echo Python 3.11 or 3.12 is required and must be on PATH.
  pause
  exit /b 1
)
python -c "import sys, struct; print('Detected Python:', sys.version); raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P')*8 == 64 else 1)"
if errorlevel 1 goto unsupported_python
if not exist ".env" copy ".env.example" ".env" >nul
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
  if errorlevel 1 rmdir /s /q ".venv"
)
if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "from zoneinfo import ZoneInfo; print(ZoneInfo('Africa/Accra'))"
if errorlevel 1 goto failed

echo Starting API at http://127.0.0.1:8000
echo Swagger docs at http://127.0.0.1:8000/docs
".venv\Scripts\python.exe" -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
exit /b %errorlevel%

:unsupported_python
echo Install 64-bit Python 3.11 or 3.12 and try again.
pause
exit /b 1

:failed
echo Backend setup failed. Read the first error above.
pause
exit /b 1
