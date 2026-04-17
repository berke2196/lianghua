@echo off
REM 完整诊断和启动脚本
chcp 65001 >nul
setlocal enabledelayedexpansion

title Hyperliquid AI Trader - 诊断和启动

echo.
echo ╔══════════════════════════════════════════════════════╗
echo ║    🔍 系统诊断和启动                                 ║
echo ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ==================== 第1步: 检查Docker ====================
echo [1/5] 检查 Docker...
docker --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker 未安装或无法运行
    echo 解决方案: 请下载并安装 Docker Desktop
    echo 链接: https://www.docker.com/products/docker-desktop
    pause
    exit /b 1
)
for /f "tokens=*" %%A in ('docker --version') do (
    echo ✅ %%A
)
echo.

REM ==================== 第2步: 检查Docker Compose ====================
echo [2/5] 检查 Docker Compose...
docker-compose --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ Docker Compose 未安装
    pause
    exit /b 1
)
for /f "tokens=*" %%A in ('docker-compose --version') do (
    echo ✅ %%A
)
echo.

REM ==================== 第3步: 检查Dockerfile ====================
echo [3/5] 检查配置文件...
if exist "Dockerfile" (
    echo ✅ Dockerfile 存在
) else (
    echo ⚠️  Dockerfile 可能缺失
)

if exist "docker-compose.yml" (
    echo ✅ docker-compose.yml 存在
) else (
    echo ❌ docker-compose.yml 缺失！
    pause
    exit /b 1
)
echo.

REM ==================== 第4步: 停止旧容器 ====================
echo [4/5] 清理旧容器...
docker-compose down >nul 2>&1
echo ✅ 旧容器已清理
echo.

REM ==================== 第5步: 启动容器 ====================
echo [5/5] 启动容器...
echo.
docker-compose up -d

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ 启动失败！显示错误日志:
    echo.
    docker-compose logs
    pause
    exit /b 1
)

echo.
echo ✅ 容器启动命令已执行
echo.

REM ==================== 检查容器状态 ====================
echo ⏳ 等待容器初始化... (约20秒)
echo.

timeout /t 5 /nobreak >nul

echo 检查容器状态...
echo.

setlocal enabledelayedexpansion
for /f "tokens=*" %%A in ('docker-compose ps') do (
    echo %%A
)
echo.

REM ==================== 检查服务健康 ====================
echo 🔍 检查服务健康状态...
echo.

set api_ready=0
for /L %%i in (1,1,30) do (
    curl -s http://localhost:8000/health >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo ✅ 后端 API 已就绪 (http://localhost:8000)
        set api_ready=1
        goto :api_ready
    )
    echo -n "."
    timeout /t 1 /nobreak >nul
)

:api_ready
echo.
echo.

REM ==================== 显示访问信息 ====================
echo ╔══════════════════════════════════════════════════════╗
echo ║    ✅ 系统已启动！                                  ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  📱 前端    : http://localhost:3000                ║
echo ║  📡 API    : http://localhost:8000                ║
echo ║  📚 文档   : http://localhost:8000/docs            ║
echo ║  💾 数据库  : localhost:5432                        ║
echo ║  🔴 缓存    : localhost:6379                        ║
echo ║  📊 监控   : http://localhost:9090                ║
echo ║  🎯 仪表板 : http://localhost:3000                ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  🎮 后续操作:                                       ║
echo ║  1. 打开浏览器: http://localhost:3000              ║
echo ║  2. 用 Hyperliquid App 扫码                        ║
echo ║  3. 完成登录                                        ║
echo ║  4. 点击"启动交易"                                 ║
echo ╠══════════════════════════════════════════════════════╣
echo ║  🔧 常用命令:                                       ║
echo ║  查看日志: docker-compose logs -f api              ║
echo ║  停止服务: docker-compose down                     ║
echo ║  查看状态: docker-compose ps                       ║
echo ╚══════════════════════════════════════════════════════╝
echo.

REM ==================== 打开浏览器 ====================
echo 🌐 正在打开浏览器...
timeout /t 2 /nobreak >nul
start http://localhost:3000

echo.
echo ✨ 系统启动完成！请在浏览器中操作
echo.

pause
