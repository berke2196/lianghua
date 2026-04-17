"""
🚀 Hyperliquid AI Trader v2 - 完整启动器
运行此脚本启动整个交易系统
"""

import subprocess
import sys
import time
import os
from pathlib import Path

root_dir = r"c:\Users\北神大帝\Desktop\塞子"
os.chdir(root_dir)

print("\n" + "="*70)
print("🚀 Hyperliquid AI Trader v2 - 启动")
print("="*70 + "\n")

# 1. 检查依赖
print("[1/5] 检查系统依赖...\n")

# 检查Node.js
try:
    result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
    print(f"  ✅ Node.js: {result.stdout.strip()}")
except:
    print("  ❌ Node.js 未安装")
    print("     请从 https://nodejs.org 下载安装")
    sys.exit(1)

# 检查Python
try:
    result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True, timeout=5)
    print(f"  ✅ Python: {result.stdout.strip()}")
except:
    print("  ❌ Python 未安装")
    sys.exit(1)

print("\n[2/5] 创建应用目录...\n")

# 创建所有必需的目录
dirs = [
    "src",
    "src/components",
    "src/styles",
    "public",
    "build"
]

for d in dirs:
    path = Path(os.path.join(root_dir, d))
    path.mkdir(parents=True, exist_ok=True)
    print(f"  ✅ {d}")

print("\n[3/5] 检查前端文件...\n")

required_files = [
    "src_app.js",
    "src_LeftToolbar.js",
    "src_TradingChart.js",
    "src_RightPanel.js",
    "src_TopBar.js",
    "electron-main.js"
]

for f in required_files:
    path = Path(os.path.join(root_dir, f))
    if path.exists():
        print(f"  ✅ {f}")
    else:
        print(f"  ❌ {f} - 缺失")

print("\n[4/5] 检查后端服务...\n")

backend_files = [
    "main_complete.py",
    "hyperliquid_api.py",
    "algorithm_framework_core.py"
]

for f in backend_files:
    path = Path(os.path.join(root_dir, f))
    if path.exists():
        print(f"  ✅ {f}")
    else:
        print(f"  ⚠️  {f}")

print("\n[5/5] 准备启动应用...\n")

print("="*70)
print("📋 接下来的步骤:")
print("="*70)
print("""
1️⃣  安装前端依赖:
    npm install

2️⃣  启动系统:
    npm start

    这会同时启动:
    - React 前端  (http://localhost:3000)
    - Electron 应用 (桌面窗口)
    - Python 后端 (http://localhost:8000)

3️⃣  使用方法:
    - 左侧: 币种选择、算法配置、启动/停止按钮
    - 中间: K线图表、实时行情
    - 右侧: 账户信息、下单面板、持仓显示

4️⃣  功能说明:
    ✅ 实时行情推送
    ✅ AI 信号生成
    ✅ 自动交易
    ✅ 风险管理
    ✅ P&L 统计

""")

print("="*70)
print("⚡ 快速启动命令:")
print("="*70)
print("\n  cd c:\\Users\\北神大帝\\Desktop\\塞子")
print("  npm install")
print("  npm start")
print("\n" + "="*70 + "\n")

input("按 Enter 键关闭此窗口...")
