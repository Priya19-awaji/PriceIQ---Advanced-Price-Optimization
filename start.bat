@echo off
echo ============================================
echo   PriceIQ - Advanced Price Optimization
echo   Starting Backend + Frontend (No Admin)
echo ============================================
echo.

REM --- Set portable Node.js path ---
set NODE_DIR=%~dp0node-portable\node-v20.18.1-win-x64
set PATH=%NODE_DIR%;%PATH%

REM --- Activate conda priceop environment ---
call conda activate priceop

echo [1/3] Checking environment...
"%NODE_DIR%\node.exe" -e "console.log('  Node.js: ' + process.version)" 2>nul || echo  ERROR: Node.js not found!
python --version 2>nul || echo  ERROR: Python (conda priceop) not found!
echo.

echo [2/3] Starting Flask Backend on port 5001...
start "PriceIQ Backend" /MIN python "%~dp0backend.py"
timeout /t 5 /nobreak >nul

echo [3/3] Starting React Frontend on port 8080...
echo   Open http://localhost:8080 in your browser
echo.
node "%~dp0node_modules\vite\bin\vite.js" --host --port 8080
