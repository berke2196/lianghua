"""
完整启动脚本 - 直接运行
"""

import os
import shutil
import subprocess
import time
import sys

try:
    os.chdir(r"c:\Users\北神大帝\Desktop\塞子")

    print("\n" + "="*70)
    print("🚀 启动 Hyperliquid AI Trader v2 - 完整版")
    print("="*70 + "\n")

    # 替换main.py
    print("📝 替换 main.py...")
    if os.path.exists("main.py"):
        os.remove("main.py")
    shutil.copy("main_complete.py", "main.py")
    print("✅ 完成\n")

    # 清理旧容器
    print("🧹 清理旧容器...")
    subprocess.run(["docker-compose", "-p", "saizi", "down"], 
                   capture_output=True, timeout=30)
    print("✅ 完成\n")

    # 构建
    print("🔨 构建 Docker 镜像...")
    subprocess.run(["docker-compose", "-p", "saizi", "build"], timeout=300)
    print("✅ 完成\n")

    # 启动
    print("📦 启动容器...")
    subprocess.run(["docker-compose", "-p", "saizi", "up", "-d"], timeout=60)
    print("✅ 完成\n")

    # 等待
    print("⏳ 等待服务启动...")
    time.sleep(20)

    # 检查
    print("\n✅ 系统已启动！\n")
    print("🌐 访问: http://localhost:3000")
    print("📡 API  : http://localhost:8000\n")

except Exception as e:
    print(f"❌ 错误: {e}")
    sys.exit(1)
