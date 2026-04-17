@echo off
REM 打包 AsterDex 自动交易系统为 .exe 文件

echo ⭐ 打包 AsterDex 交易系统...
echo.

REM 检查PyInstaller
pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo 安装 PyInstaller...
    pip install PyInstaller -q
)

REM 清理旧的构建
if exist dist (
    rmdir /s /q dist
)
if exist build (
    rmdir /s /q build
)

echo 🔨 开始打包...
pyinstaller ^
    --name "AsterDex交易系统" ^
    --windowed ^
    --icon "C:\Users\北神大帝\Desktop\塞子\icon.ico" ^
    --add-data "C:\Users\北神大帝\Desktop\塞子\asterdex_api.py:." ^
    --add-data "C:\Users\北神大帝\Desktop\塞子\trading_engine.py:." ^
    --hidden-import=PyQt6 ^
    --hidden-import=aiohttp ^
    --hidden-import=numpy ^
    --onefile ^
    app.py

if errorlevel 1 (
    echo ❌ 打包失败
    pause
    exit /b 1
)

echo.
echo ✅ 打包完成!
echo 📍 位置: %cd%\dist\AsterDex交易系统.exe
echo.
pause
