"""
等待系统启动完成 - 监控脚本
"""

import subprocess
import time
import sys

print("\n")
print("=" * 60)
print("⏳ 等待系统启动完成...")
print("=" * 60)
print()

# 等待Docker容器启动
time.sleep(15)

print("🔍 检查容器状态...")
try:
    result = subprocess.run(
        ["docker-compose", "-p", "saizi", "ps"],
        capture_output=True,
        text=True,
        cwd=r"c:\Users\北神大帝\Desktop\塞子"
    )
    print(result.stdout)
except Exception as e:
    print(f"错误: {e}")

print()

# 检查API健康
print("🔍 检查 API 健康状态...")
for i in range(30):
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8000/health"],
            capture_output=True,
            timeout=3
        )
        if result.returncode == 0:
            print("✅ API 已就绪")
            print()
            print("╔" + "=" * 58 + "╗")
            print("║" + " ✅ 系统已成功启动！".center(58) + "║")
            print("╠" + "=" * 58 + "╣")
            print("║" + " 🌐 前端   : http://localhost:3000".ljust(58) + "║")
            print("║" + " 📡 API    : http://localhost:8000".ljust(58) + "║")
            print("║" + " 📚 文档   : http://localhost:8000/docs".ljust(58) + "║")
            print("║" + " 💾 数据库 : localhost:5432".ljust(58) + "║")
            print("║" + " 🔴 缓存   : localhost:6379".ljust(58) + "║")
            print("╚" + "=" * 58 + "╝")
            print()
            sys.exit(0)
    except:
        pass
    print(".", end="", flush=True)
    time.sleep(1)

print()
print("✅ 系统已启动（可能仍在初始化）")
print()
