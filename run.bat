@echo off
REM Hyperliquid AI Trader v2 启动脚本 (Windows)

echo 🚀 启动 Hyperliquid AI Trader v2...
echo ==================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 没有找到 Python
    echo 请先安装 Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖
echo 📦 检查依赖...
pip install -q fastapi uvicorn aiohttp numpy requests

REM 启动服务器
echo ✅ 启动服务器...
echo.
echo 🌐 访问地址: http://localhost:8000
echo.
echo 按 Ctrl+C 停止
echo.

python main.py

pause
