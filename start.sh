#!/bin/bash
# AsterDex HFT Trader - Linux/Mac 启动脚本

set -e
cd "$(dirname "$0")"

echo "============================================"
echo "  AsterDex HFT Trader - 启动中..."
echo "============================================"

# 加载 .env
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
    echo "[OK] 已加载 .env 配置"
else
    echo "[WARN] 未找到 .env 文件"
fi

# 检查 Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] 未找到 python3"
    exit 1
fi

# 检查依赖
python3 -c "import fastapi, uvicorn, jwt, bcrypt, slowapi" 2>/dev/null || {
    echo "[INFO] 安装依赖..."
    pip3 install -r requirements.txt
}

echo "[INFO] API 前缀: /${API_PREFIX}"
echo "[INFO] 监听: http://0.0.0.0:${PORT:-8000}"
echo "============================================"

# 自动重启循环
while true; do
    python3 asterdex_backend.py
    echo "[WARN] 进程退出，5秒后重启..."
    sleep 5
done
