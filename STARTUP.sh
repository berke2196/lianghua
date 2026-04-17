#!/bin/bash
# 启动脚本 - 完整启动交易系统
# Startup Script - Launch Complete Trading System

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║  🚀 Hyperliquid AI Trader v2                           ║"
echo "║  启动完整交易系统                                       ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 检查Docker
echo "✅ 检查 Docker..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装"
    exit 1
fi

echo "✅ Docker 已安装"
echo ""

# 启动Docker容器
echo "📦 启动 Docker 容器..."
cd "$(dirname "$0")"

# 检查docker-compose.yml
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ docker-compose.yml 未找到"
    exit 1
fi

# 启动服务
docker-compose up -d

echo ""
echo "✅ 容器已启动"
echo ""
echo "⏳ 等待服务启动... (约30秒)"
sleep 10

# 检查健康状态
echo ""
echo "🔍 检查服务状态..."
echo ""

# 检查后端
echo "后端 API 状态检查..."
for i in {1..30}; do
    if curl -s http://localhost:8000/health &> /dev/null; then
        echo "✅ 后端 API 已就绪: http://localhost:8000"
        break
    fi
    echo -n "."
    sleep 1
done

echo ""
echo ""

# 显示访问信息
echo "╔════════════════════════════════════════════════════════╗"
echo "║  ✅ 系统已启动                                         ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  📱 前端    : http://localhost:3000                   ║"
echo "║  📡 API    : http://localhost:8000                    ║"
echo "║  📚 文档   : http://localhost:8000/docs               ║"
echo "║  💾 数据库  : localhost:5432                          ║"
echo "║  🔴 缓存    : localhost:6379                          ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  🎯 下一步:                                            ║"
echo "║  1. 打开浏览器访问 http://localhost:3000              ║"
echo "║  2. 扫码登录 (用Hyperliquid App)                      ║"
echo "║  3. 点击"开始交易"启动引擎                            ║"
echo "║  4. 监控实时仪表板                                     ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  🔧 常用命令:                                          ║"
echo "║  docker-compose logs -f api      查看API日志          ║"
echo "║  docker-compose logs -f frontend 查看前端日志         ║"
echo "║  docker-compose stop             停止服务             ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

# 打开浏览器 (如果是Mac)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🌐 正在打开浏览器..."
    sleep 2
    open http://localhost:3000
fi

echo ""
echo "✨ 系统已就绪！祝您交易愉快！💰"
echo ""
