#!/bin/bash

# ============ 高频加密货币交易系统 - 启动脚本 ============
# Hyperliquid AI Trader - Start Script
# 
# 使用方法:
#   ./start.sh          # 启动所有服务
#   ./start.sh dev      # 开发模式 (带热重载)
#   ./start.sh stop     # 停止所有服务
#   ./start.sh logs     # 显示日志

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 功能定义
print_banner() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════╗"
    echo "║  🚀 Hyperliquid AI Trader                  ║"
    echo "║  高频加密货币交易系统                       ║"
    echo "╚════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 检查系统
check_system() {
    print_info "正在检查系统环境..."
    
    # 检查 Docker
    if command -v docker &> /dev/null; then
        print_success "Docker 已安装"
    else
        print_error "Docker 未安装，请先安装 Docker"
        echo "访问: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # 检查 Docker Compose
    if command -v docker-compose &> /dev/null; then
        print_success "Docker Compose 已安装"
    else
        print_error "Docker Compose 未安装"
        exit 1
    fi
    
    # 检查 Python
    if command -v python3 &> /dev/null; then
        print_success "Python 3 已安装: $(python3 --version)"
    else
        print_warning "Python 3 未安装 (某些功能需要)"
    fi
    
    # 检查 Node.js
    if command -v node &> /dev/null; then
        print_success "Node.js 已安装: $(node --version)"
    else
        print_warning "Node.js 未安装 (某些功能需要)"
    fi
}

# 检查配置文件
check_config() {
    print_info "正在检查配置文件..."
    
    if [ ! -f ".env" ]; then
        print_warning ".env 文件不存在，正在从 .env.example 创建..."
        cp .env.example .env
        print_success ".env 文件已创建"
    else
        print_success ".env 文件已存在"
    fi
}

# 启动服务
start_services() {
    print_info "正在启动所有服务..."
    
    if [ "$1" == "dev" ]; then
        # 开发模式
        print_info "使用开发模式启动 (带热重载)"
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    else
        # 生产模式
        print_info "使用生产模式启动"
        docker-compose up -d
    fi
    
    print_success "所有服务已启动"
    
    # 等待服务启动
    print_info "等待服务启动... (约30秒)"
    sleep 5
    
    # 检查服务健康状态
    check_health
}

# 检查服务健康
check_health() {
    print_info "正在检查服务状态..."
    
    # 等待后端启动
    max_attempts=30
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            print_success "后端 API 已就绪: http://localhost:8000"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 1
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "后端 API 启动超时"
    fi
    
    # 前端
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_success "前端已就绪: http://localhost:3000"
    else
        print_warning "前端启动中... 请稍候"
    fi
}

# 显示启动完成信息
show_startup_info() {
    echo ""
    print_success "所有服务已启动!"
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║  📱 现在可以使用应用了                      ║"
    echo "╠════════════════════════════════════════════╣"
    echo "║  🌐 前端    : http://localhost:3000        ║"
    echo "║  📡 API    : http://localhost:8000         ║"
    echo "║  📊 数据库  : localhost:5432              ║"
    echo "║  💾 缓存    : localhost:6379              ║"
    echo "╠════════════════════════════════════════════╣"
    echo "║  🚀 使用方法:                              ║"
    echo "║  1. 打开浏览器访问 http://localhost:3000  ║"
    echo "║  2. 用 Hyperliquid App 扫描二维码         ║"
    echo "║  3. 完成授权后自动登录                     ║"
    echo "║  4. 开始交易!                             ║"
    echo "╠════════════════════════════════════════════╣"
    echo "║  📚 文档:                                   ║"
    echo "║  - README.md          (项目概览)          ║"
    echo "║  - QR_LOGIN_GUIDE.md  (登录指南)          ║"
    echo "║  - QUICKSTART.md      (快速开始)          ║"
    echo "║  - ARCHITECTURE.md    (系统架构)          ║"
    echo "╠════════════════════════════════════════════╣"
    echo "║  🔧 常用命令:                              ║"
    echo "║  docker-compose logs -f api    (后端日志) ║"
    echo "║  docker-compose logs -f frontend (前端日志) ║"
    echo "║  docker-compose stop            (停止服务) ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
}

# 停止服务
stop_services() {
    print_info "正在停止所有服务..."
    docker-compose down
    print_success "所有服务已停止"
}

# 显示日志
show_logs() {
    print_info "显示服务日志 (Ctrl+C 退出)..."
    docker-compose logs -f
}

# 清理
cleanup() {
    print_warning "正在清理所有容器和数据..."
    docker-compose down -v
    print_success "清理完成"
}

# 主函数
main() {
    print_banner
    
    case "${1:-start}" in
        start)
            check_system
            check_config
            start_services
            show_startup_info
            ;;
        dev)
            check_system
            check_config
            start_services "dev"
            show_startup_info
            ;;
        stop)
            stop_services
            ;;
        logs)
            show_logs
            ;;
        clean)
            cleanup
            ;;
        restart)
            stop_services
            sleep 2
            start_services
            show_startup_info
            ;;
        health)
            check_health
            ;;
        *)
            echo "用法: ./start.sh [命令]"
            echo ""
            echo "命令:"
            echo "  start      启动所有服务 (默认)"
            echo "  dev        开发模式启动 (带热重载)"
            echo "  stop       停止所有服务"
            echo "  logs       显示服务日志"
            echo "  restart    重启所有服务"
            echo "  health     检查服务健康状态"
            echo "  clean      清理所有容器和数据"
            echo ""
            echo "示例:"
            echo "  ./start.sh              # 启动应用"
            echo "  ./start.sh logs         # 显示日志"
            echo "  ./start.sh stop         # 停止应用"
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@"
