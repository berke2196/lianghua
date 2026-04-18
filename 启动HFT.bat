@echo off
chcp 65001 >nul
title AsterDex HFT Trader

echo.
echo ============================================================
echo   AsterDex HFT Trader v5.0
echo ============================================================
echo.

:: Kill old processes on port 8000 and 3000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.11+
    pause & exit /b 1
)

:: Check Node
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+
    pause & exit /b 1
)

:: Install Python deps
echo [1/3] Installing Python dependencies...
pip install fastapi uvicorn aiohttp websockets python-dotenv -q
echo Done.
echo.

:: Install frontend deps if needed
if not exist "node_modules" (
    echo [2/3] Installing npm packages...
    npm install -q
) else (
    echo [2/3] npm packages already installed.
)
echo.

:: Start backend
echo [3/3] Starting backend on port 8000...
start "AsterDex-Backend" cmd /k "python asterdex_backend.py"
timeout /t 3 /nobreak >nul

:: Start frontend
echo Starting frontend on port 3000...
start "AsterDex-Frontend" cmd /k "npm start"

echo.
echo ============================================================
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:3000
echo.
echo   Login with your AsterDex API Key + Secret Key
echo ============================================================
echo.
pause