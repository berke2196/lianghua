@echo off
REM 启动脚本 - 完整启动交易系统 (Windows)
REM Startup Script - Launch Complete Trading System (Windows)

setlocal enabledelayedexpansion

REM 设置编码为UTF-8
chcp 65001 >nul

cls
echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║  🚀 Hyperliquid AI Trader v2                           ║
echo ║  启动完整交易系统                                       ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM 检查Docker
echo ✅ 检查 Docker...
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker 未安装
    pause
    exit /b 1
)

where docker-compose >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Compose 未安装
    pause
    exit /b 1
)

echo ✅ Docker 已安装
echo.

REM 启动Docker容器
echo 📦 启动 Docker 容器...
cd /d "%~dp0"

if not exist "docker-compose.yml" (
    echo ❌ docker-compose.yml 未找到
    pause
    exit /b 1
)

REM 启动服务
docker-compose up -d

echo.
echo ✅ 容器已启动
echo.
echo ⏳ 等待服务启动... (约30秒)
timeout /t 10 /nobreak

REM 检查健康状态
echo.
echo 🔍 检查服务状态...
echo.

REM 检查后端
echo 后端 API 状态检查...
for /L %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo ✅ 后端 API 已就绪: http://localhost:8000
        goto :success
    )
    echo -n "."
    timeout /t 1 /nobreak >nul
)

:success
echo.
echo.

REM 显示访问信息
echo ╔════════════════════════════════════════════════════════╗
echo ║  ✅ 系统已启动                                         ║
echo ╠════════════════════════════════════════════════════════╣
echo ║  📱 前端    : http://localhost:3000                   ║
echo ║  📡 API    : http://localhost:8000                    ║
echo ║  📚 文档   : http://localhost:8000/docs               ║
echo ║  💾 数据库  : localhost:5432                          ║
echo ║  🔴 缓存    : localhost:6379                          ║
echo ╠════════════════════════════════════════════════════════╣
echo ║  🎯 下一步:                                            ║
echo ║  1. 打开浏览器访问 http://localhost:3000              ║
echo ║  2. 扫码登录 (用Hyperliquid App)                      ║
echo ║  3. 点击"开始交易"启动引擎                            ║
echo ║  4. 监控实时仪表板                                     ║
echo ╠════════════════════════════════════════════════════════╣
echo ║  🔧 常用命令:                                          ║
echo ║  docker-compose logs -f api      查看API日志          ║
echo ║  docker-compose logs -f frontend 查看前端日志         ║
echo ║  docker-compose stop             停止服务             ║
echo ╚════════════════════════════════════════════════════════╝
echo.

REM 打开浏览器
echo 🌐 正在打开浏览器...
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
echo ✨ 系统已就绪！祝您交易愉快！💰
echo.
pause
