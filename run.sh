#!/bin/bash

# Hyperliquid AI Trader v2 启动脚本

echo "🚀 启动 Hyperliquid AI Trader v2..."
echo "=================================="
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 没有找到 Python 3"
    echo "请先安装 Python 3.8+"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
pip3 install -q fastapi uvicorn aiohttp numpy requests

# 启动服务器
echo "✅ 启动服务器..."
echo ""
echo "🌐 访问地址: http://localhost:8000"
echo ""
echo "按 Ctrl+C 停止"
echo ""

python3 main.py
