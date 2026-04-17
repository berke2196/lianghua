"""
完整应用启动 - 一键运行
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

root = r"c:\Users\北神大帝\Desktop\塞子"
os.chdir(root)

print("\n" + "="*70)
print("🛠️  准备 Electron 应用...")
print("="*70 + "\n")

# 1. 创建目录
print("[1/3] 创建目录结构...\n")
for d in ["src", "src/components", "src/styles", "public", "build"]:
    Path(os.path.join(root, d)).mkdir(parents=True, exist_ok=True)
    print(f"  ✅ {d}")

# 2. 复制/移动文件到正确位置
print("\n[2/3] 配置应用文件...\n")

files_to_move = [
    ("src_app.js", "src/App.js"),
    ("src_index.js", "src/index.js"),
    ("src_LeftToolbar.js", "src/components/LeftToolbar.js"),
    ("src_TradingChart.js", "src/components/TradingChart.js"),
    ("src_RightPanel.js", "src/components/RightPanel.js"),
    ("src_TopBar.js", "src/components/TopBar.js"),
]

for src, dst in files_to_move:
    src_path = Path(os.path.join(root, src))
    dst_path = Path(os.path.join(root, dst))
    
    if src_path.exists():
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, dst_path)
        print(f"  ✅ {dst}")
    else:
        print(f"  ⚠️  {src} 未找到")

# 创建 public/index.html
print("\n[3/3] 创建HTML...\n")
html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Hyperliquid AI Trading System" />
    <title>Hyperliquid AI Trader v2</title>
    <style>
      * { margin: 0; padding: 0; box-sizing: border-box; }
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #fff; }
      html, body, #root { width: 100%; height: 100%; }
    </style>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
'''

Path("public").mkdir(exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("  ✅ public/index.html")

print("\n" + "="*70)
print("✅ 应用准备完成！")
print("="*70)
print("""
运行以下命令启动应用:

  npm install
  npm start

app布局:
  - 左侧: 币种选择、算法配置、启动/停止
  - 中间: K线图表、实时行情
  - 右侧: 账户信息、下单、持仓

""")
