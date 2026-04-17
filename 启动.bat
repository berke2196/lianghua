@echo off
REM ============ 完整系统启动脚本 ============
chcp 65001 >nul
setlocal enabledelayedexpansion

title Hyperliquid AI Trader - 完整启动

cd /d "%~dp0"

echo.
echo ╔════════════════════════════════════════════╗
echo ║   🚀 Hyperliquid AI Trader v2            ║
echo ║   完整系统启动                            ║
echo ╚════════════════════════════════════════════╝
echo.

REM ============ 步骤1: 验证Docker ============
echo [1/5] 验证 Docker 环境...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker 未安装或无法运行
    echo 请下载: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
echo ✅ Docker 已安装
echo.

REM ============ 步骤2: 清理 ============
echo [2/5] 清理旧容器...
docker compose -p saizi down >nul 2>&1
echo ✅ 清理完成
echo.

REM ============ 步骤3: 构建 ============
echo [3/5] 构建 Docker 镜像...
docker compose -p saizi build
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 构建失败
    pause
    exit /b 1
)
echo ✅ 构建完成
echo.

REM ============ 步骤4: 启动 ============
echo [4/5] 启动容器...
docker compose -p saizi up -d
if %ERRORLEVEL% NEQ 0 (
    echo ❌ 启动失败
    pause
    exit /b 1
)
echo ✅ 容器已启动
echo.

REM ============ 步骤5: 验证 ============
echo [5/5] 等待服务启动...
timeout /t 5 /nobreak >nul

echo 检查服务状态...
for /L %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo ✅ 后端 API 已就绪
        goto :check_frontend
    )
    echo -n "."
    timeout /t 1 /nobreak >nul
)

:check_frontend
for /L %%i in (1,1,10) do (
    curl -s http://localhost:3000 >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo ✅ 前端已就绪
        goto :success
    )
    echo -n "."
    timeout /t 1 /nobreak >nul
)

:success
echo.
echo.
echo ╔════════════════════════════════════════════╗
echo ║  ✅ 系统已成功启动！                      ║
echo ╠════════════════════════════════════════════╣
echo ║  🌐 前端    : http://localhost:3000      ║
echo ║  📡 API    : http://localhost:8000       ║
echo ║  📚 文档   : http://localhost:8000/docs  ║
echo ║  💾 数据库  : localhost:5432             ║
echo ║  🔴 缓存    : localhost:6379             ║
echo ╚════════════════════════════════════════════╝
echo.

echo ✨ 系统启动完成！
echo.
echo 打开浏览器: http://localhost:3000
start http://localhost:3000

echo.
echo 🎉 启动成功！祝您交易愉快！💰
echo.

pause
