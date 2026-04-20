@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist backend\.venv (
  echo [ERR] Run install.bat first.
  exit /b 1
)

start "hwpx-backend" cmd /k "cd /d %~dp0 && call backend\.venv\Scripts\activate && set PYTHONPATH=%~dp0 && uvicorn backend.main:app --host 0.0.0.0 --port 8765 --reload"
start "hwpx-frontend" cmd /k "cd /d %~dp0\frontend && npm run dev -- --host 0.0.0.0 --port 5173"

timeout /t 3 /nobreak >nul
start http://localhost:5173

endlocal
