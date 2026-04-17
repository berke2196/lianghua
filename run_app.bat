@echo off
REM AsterDex 自动交易系统 - 桌面应用启动脚本

echo ⭐ AsterDex 自动交易系统启动中...
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未安装Python
    pause
    exit /b 1
)

REM 检查依赖
echo 检查依赖...
pip show PyQt6 >nul 2>&1
if errorlevel 1 (
    echo 安装 PyQt6...
    pip install PyQt6 -q
)

pip show aiohttp >nul 2>&1
if errorlevel 1 (
    echo 安装 aiohttp...
    pip install aiohttp -q
)

pip show numpy >nul 2>&1
if errorlevel 1 (
    echo 安装 numpy...
    pip install numpy -q
)

echo.
echo ✅ 依赖检查完成
echo 🚀 启动应用...
echo.

python app.py

if errorlevel 1 (
    echo.
    echo ❌ 应用启动失败
    pause
    exit /b 1
)
