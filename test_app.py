#!/usr/bin/env python
"""
快速测试脚本 - 验证应用是否可以启动
"""

import sys

print("正在测试应用依赖和导入...")
print()

# 测试 1: PyQt6
try:
    from PyQt6.QtWidgets import QApplication
    print("✅ PyQt6 导入成功")
except Exception as e:
    print(f"❌ PyQt6 导入失败: {e}")
    sys.exit(1)

# 测试 2: QWebEngineView
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    print("✅ QWebEngineView 导入成功")
except Exception as e:
    print(f"❌ QWebEngineView 导入失败: {e}")
    sys.exit(1)

# 测试 3: 其他导入
try:
    from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
    from PyQt6.QtGui import QFont, QColor
    print("✅ PyQt6 核心模块导入成功")
except Exception as e:
    print(f"❌ PyQt6 核心模块导入失败: {e}")
    sys.exit(1)

# 测试 4: Web3
try:
    from web3 import Web3
    print("✅ Web3 导入成功")
except Exception as e:
    print(f"❌ Web3 导入失败: {e}")
    sys.exit(1)

# 测试 5: 自定义模块
try:
    from asterdex_api import AsterDexAPI
    print("✅ AsterDex API 导入成功")
except Exception as e:
    print(f"❌ AsterDex API 导入失败: {e}")
    sys.exit(1)

try:
    from trading_engine import AutoTradingEngine
    print("✅ Trading Engine 导入成功")
except Exception as e:
    print(f"❌ Trading Engine 导入失败: {e}")
    sys.exit(1)

print()
print("=" * 50)
print("✨ 所有测试通过！")
print("=" * 50)
print()
print("现在可以启动应用:")
print("  python app.py")
print()
