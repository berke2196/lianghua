#!/bin/bash
# ============================================================
# AsterDex HFT Trader — Linux 服务器一键部署脚本
# 适用：Ubuntu 20.04+ / Debian 11+
# 用法：bash server_deploy.sh
# ============================================================
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  AsterDex HFT Trader — Server Deploy${NC}"
echo -e "${CYAN}============================================${NC}"

# ── 检查 .env ──
if [ ! -f .env ]; then
    cp .env.example .env
    warn ".env 未找到，已从模板创建。请编辑 .env 填写必要配置："
    warn "  ADMIN_PASSWORD, CORS_ORIGINS, REACT_APP_API_URL"
    warn "然后重新运行此脚本"
    exit 1
fi
source .env
ok ".env loaded"

# ── 检查 Python ──
if ! command -v python3 &>/dev/null; then
    err "Python3 未安装。运行: apt-get install python3 python3-pip python3-venv"
fi
PYTHON=$(command -v python3)
ok "Python: $($PYTHON --version)"

# ── 创建虚拟环境 ──
if [ ! -d venv ]; then
    log "创建 Python 虚拟环境..."
    $PYTHON -m venv venv
fi
source venv/bin/activate
ok "虚拟环境激活"

# ── 安装 Python 依赖 ──
log "安装 Python 依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
ok "Python 依赖安装完成"

# ── 检查 Node.js ──
if ! command -v node &>/dev/null; then
    err "Node.js 未安装。运行: apt-get install nodejs npm 或使用 nvm"
fi
ok "Node.js: $(node --version)"

# ── 安装 npm 依赖 ──
log "安装 npm 依赖..."
npm install --silent
ok "npm 依赖安装完成"

# ── 启动后端（仅用于生成 .env 中的 API_PREFIX）──
log "启动后端以生成 API 前缀..."
source venv/bin/activate
timeout 10 python3 asterdex_backend.py &>/dev/null & BGPID=$!
sleep 5
kill $BGPID 2>/dev/null || true
wait $BGPID 2>/dev/null || true

# 重新加载 .env（后端已写入 REACT_APP_API_PREFIX）
source .env
if [ -z "$REACT_APP_API_PREFIX" ]; then
    err "后端未能写入 REACT_APP_API_PREFIX 到 .env，请检查后端是否能正常启动"
fi
ok "API 前缀: $REACT_APP_API_PREFIX"

# ── Build 前端（前缀硬编码进 bundle）──
log "构建前端（prefix=$REACT_APP_API_PREFIX, api=$REACT_APP_API_URL）..."
npm run build
ok "前端构建完成 → build/"

# ── 安装 pm2（进程管理）──
if ! command -v pm2 &>/dev/null; then
    log "安装 pm2..."
    npm install -g pm2 --silent
fi
ok "pm2: $(pm2 --version)"

# ── 停止旧进程 ──
pm2 stop asterdex-backend 2>/dev/null || true
pm2 stop asterdex-frontend 2>/dev/null || true
pm2 delete asterdex-backend 2>/dev/null || true
pm2 delete asterdex-frontend 2>/dev/null || true

# ── 启动后端（pm2 托管，自动重启）──
log "通过 pm2 启动后端..."
pm2 start python3 \
    --name asterdex-backend \
    --interpreter none \
    -- asterdex_backend.py \
    --log logs/backend.log \
    --error logs/backend_err.log \
    --restart-delay 2000 \
    --max-restarts 0

# 等待后端就绪
BP="${BACKEND_PORT:-8000}"
log "等待后端响应 http://127.0.0.1:$BP/cfg ..."
for i in $(seq 1 20); do
    if curl -sf "http://127.0.0.1:$BP/cfg" &>/dev/null; then
        ok "后端就绪（${i}s）"; break
    fi
    echo -n "  ."; sleep 1
    [ $i -eq 20 ] && err "后端启动超时，查看: pm2 logs asterdex-backend"
done

# ── 启动前端静态服务（npx serve）──
log "通过 pm2 启动前端静态服务（端口 3000）..."
pm2 start npx \
    --name asterdex-frontend \
    -- serve -s build -l 3000 \
    --log logs/frontend.log

# ── pm2 开机自启 ──
pm2 save
pm2 startup 2>/dev/null | tail -1 | bash 2>/dev/null || warn "pm2 startup 需要手动执行，运行: pm2 startup"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ALL SERVICES RUNNING${NC}"
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Frontend  ->  http://YOUR_SERVER_IP:3000${NC}"
echo -e "${GREEN}  Backend   ->  http://YOUR_SERVER_IP:$BP${NC}"
echo ""
echo -e "${YELLOW}  管理命令:${NC}"
echo -e "  pm2 list                  # 查看进程状态"
echo -e "  pm2 logs asterdex-backend # 查看后端日志"
echo -e "  pm2 restart all           # 重启所有服务"
echo -e "  pm2 stop all              # 停止所有服务"
echo ""
echo -e "${YELLOW}  服务器防火墙需开放端口: 3000, $BP${NC}"
echo -e "${YELLOW}  建议用 Nginx 反代，只暴露 443/80${NC}"
echo ""
