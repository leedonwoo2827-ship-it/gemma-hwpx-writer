@echo off
chcp 65001 >nul
setlocal enableextensions
cd /d "%~dp0"

echo [1/6] Checking prerequisites
call python --version >nul 2>&1
if errorlevel 1 (
  echo [ERR] Python 3.11+ required. Install: https://www.python.org
  exit /b 1
)
call node --version >nul 2>&1
if errorlevel 1 (
  echo [ERR] Node 18+ required. Install: https://nodejs.org
  exit /b 1
)
call soffice --version >nul 2>&1
if errorlevel 1 echo [WARN] LibreOffice not found. HWP rendering disabled.
call ollama --version >nul 2>&1
if errorlevel 1 echo [WARN] Ollama not found. Local LLM disabled.

echo [2/6] Backend venv
if not exist backend\.venv python -m venv backend\.venv
call backend\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r backend\requirements.txt
call deactivate

echo [3/6] MCP venv
if not exist hwp_mcp\hwpx_vision\.venv python -m venv hwp_mcp\hwpx_vision\.venv
call hwp_mcp\hwpx_vision\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r hwp_mcp\hwpx_vision\requirements.txt
call deactivate

echo [4/6] Frontend npm install
pushd frontend
call npm install
popd

echo [5/6] kordoc (optional) - build if present
if exist hwp_mcp\kordoc\package.json (
  pushd hwp_mcp\kordoc
  call npm install
  call npm run build
  popd
) else (
  echo [INFO] hwp_mcp\kordoc not found. Internal MD conversion limited to PDF. Drop HWP-derived MD files manually.
)

echo [6/6] Ollama models
ollama list 2>nul | findstr /i "gemma3n:e4b" >nul && (echo [OK] gemma3n:e4b installed) || (echo [WARN] run: ollama pull gemma3n:e4b)
ollama list 2>nul | findstr /i "gemma3n:e2b" >nul && (echo [OK] gemma3n:e2b installed) || (echo [INFO] gemma3n:e2b optional)

echo.
echo [DONE] Now run: start.bat
endlocal
