@echo off
REM 🚀 直接启动 Electron 应用 - 简单有效

chcp 65001 >nul
cd /d "c:\Users\北神大帝\Desktop\塞子"

echo.
echo 🚀 启动应用...
echo.

REM 检查 Node.js
where node >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js 未安装
    echo 请从 https://nodejs.org 下载安装
    pause
    exit /b 1
)

REM 创建目录
if not exist "src\components" mkdir "src\components"
if not exist "public" mkdir "public"

REM 安装依赖
if not exist "node_modules" (
    echo ⏳ 安装依赖...
    call npm install
)

REM 启动
echo.
echo 💫 启动应用（5-10秒后打开）...
echo.
call npm start
