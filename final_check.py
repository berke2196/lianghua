"""
最终检查 - 确保所有文件都准备好
"""

import os
import shutil
from pathlib import Path

root = r"c:\Users\北神大帝\Desktop\塞子"
os.chdir(root)

print("\n" + "="*70)
print("✅ 最后检查 - 确保应用准备就绪")
print("="*70 + "\n")

# 1. 创建必要的目录
print("[1/3] 创建目录结构...")
for d in ["src", "src/components", "src/styles", "public", "build"]:
    Path(d).mkdir(parents=True, exist_ok=True)
print("  ✅ 完成")

# 2. 复制React文件
print("\n[2/3] 复制React文件...")
files_to_copy = [
    ("src_app.js", "src/App.js"),
    ("src_index.js", "src/index.js"),
    ("src_LeftToolbar.js", "src/components/LeftToolbar.js"),
    ("src_TradingChart.js", "src/components/TradingChart.js"),
    ("src_RightPanel.js", "src/components/RightPanel.js"),
    ("src_TopBar.js", "src/components/TopBar.js"),
]

for src, dst in files_to_copy:
    if os.path.exists(src):
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  ✅ {dst}")

# 3. 创建public/index.html
print("\n[3/3] 创建HTML文件...")
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
      body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif; -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; background: #1a1a2e; color: #fff; }
      html, body { width: 100%; height: 100%; }
      #root { width: 100%; height: 100%; }
    </style>
  </head>
  <body>
    <noscript>You need to enable JavaScript to run this app.</noscript>
    <div id="root"></div>
  </body>
</html>
'''

Path("public").mkdir(exist_ok=True)
with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(html_content)
print("  ✅ public/index.html")

print("\n" + "="*70)
print("✅ 应用已准备好!")
print("="*70)
print("\n现在运行:")
print("  npm install")
print("  npm start")
print("\n或双击: GO.bat")
print("\n" + "="*70 + "\n")
