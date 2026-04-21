@echo off
chcp 65001 >nul
title AsterDex HFT - 启动中...
echo.
echo  ╔══════════════════════════════════════╗
echo  ║     AsterDex HFT 一键启动           ║
echo  ║     后端 + 前端 同时启动             ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d %~dp0

echo [1/2] 启动后端 (Python FastAPI)...
start "AsterDex 后端" cmd /k "python run.py"

echo [2/2] 等待后端就绪 (3秒)...
timeout /t 3 /nobreak >nul

echo [3/3] 启动前端 (React Dev Server)...
start "AsterDex 前端" cmd /k "npm start"

echo.
echo  ✅ 启动完成！
echo  后端地址: http://localhost:8000
echo  前端地址: http://localhost:3000
echo  (浏览器将自动打开前端页面)
echo.
pause
