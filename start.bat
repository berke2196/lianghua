@echo off
setlocal enabledelayedexpansion
title AsterDex Backend

echo ============================================
echo   AsterDex HFT Trader Backend - Starting...
echo ============================================

if exist .env (
    for /f "usebackq eol=# tokens=1,* delims==" %%A in (".env") do (
        if not "%%A"=="" if not "%%B"=="" (
            set "%%A=%%B"
        )
    )
    echo [OK] .env loaded
) else (
    echo [WARN] .env not found, using defaults
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo [INFO] Backend port: %BACKEND_PORT%
echo [INFO] Press Ctrl+C to stop
echo ============================================

:RESTART
python run.py
echo [WARN] Process exited. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto RESTART