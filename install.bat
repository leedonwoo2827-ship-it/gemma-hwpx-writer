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
if not exist doc_mcp\hwpx_vision\.venv python -m venv doc_mcp\hwpx_vision\.venv
call doc_mcp\hwpx_vision\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r doc_mcp\hwpx_vision\requirements.txt
call deactivate

echo [4/6] Frontend npm install
pushd frontend
call npm install
popd

echo [5/6] kordoc (optional) - build if present
if exist doc_mcp\kordoc\package.json (
  pushd doc_mcp\kordoc
  call npm install
  call npm run build
  popd
) else (
  echo [INFO] doc_mcp\kordoc not found. Internal MD conversion limited to PDF. Drop HWP-derived MD files manually.
)

echo [6/6] Ollama models
ollama list 2>nul | findstr /i "qwen2.5:3b" >nul
if errorlevel 1 (
  echo [INFO] Pulling qwen2.5:3b ^(lightweight Korean text model, ~2GB^)...
  ollama pull qwen2.5:3b
  if errorlevel 1 (
    echo [WARN] qwen2.5:3b pull failed. Run manually: ollama pull qwen2.5:3b
  ) else (
    echo [OK] qwen2.5:3b ready
  )
) else (
  echo [OK] qwen2.5:3b installed
)
echo [INFO] HWPX vision relies on cloud Gemini API key ^(configure in Settings^).
echo [INFO] Optional heavier models ^(manual pull^):
echo         ollama pull qwen2.5:7b
echo         ollama pull gemma3:4b      ^(local vision option^)
echo         ollama pull gemma3n:e4b    ^(heavy multimodal^)

echo.
echo [DONE] Now run: start.bat
endlocal
