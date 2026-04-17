import os
import sys

root = r"c:\Users\北神大帝\Desktop\塞子"
os.chdir(root)

# 创建目录
for d in ["src/components", "src/styles", "public"]:
    os.makedirs(os.path.join(root, d), exist_ok=True)

print("✅ 完整Electron应用已准备好！")
print("\n运行以下命令启动:")
print("  npm install")
print("  npm start")
