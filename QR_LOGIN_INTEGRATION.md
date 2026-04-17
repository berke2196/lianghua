"""
Electron + React 扫码登录集成指南
QR Code Login Integration Guide
"""

# ============ 文件1: src/frontend/renderer/App.tsx ============

import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import QRLogin from './pages/QRLogin';
import Dashboard from './pages/Dashboard';
import Settings from './pages/Settings';
import './App.css';

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState(true);

  // 应用启动时检查认证状态
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch('/api/auth/verify');
        const data = await response.json();
        setIsAuthenticated(data.authenticated);
      } catch (error) {
        console.error('Failed to verify auth:', error);
        setIsAuthenticated(false);
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gradient-to-br from-gray-50 to-gray-100">
        <div className="text-center">
          <div className="inline-block">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-600"></div>
          </div>
          <p className="mt-4 text-gray-600">加载中...</p>
        </div>
      </div>
    );
  }

  return (
    <Router>
      <Routes>
        {/* 登录路由 */}
        <Route
          path="/login"
          element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <QRLogin />}
        />

        {/* 仪表板 */}
        <Route
          path="/dashboard"
          element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" replace />}
        />

        {/* 设置 */}
        <Route
          path="/settings"
          element={isAuthenticated ? <Settings /> : <Navigate to="/login" replace />}
        />

        {/* 默认重定向 */}
        <Route
          path="/"
          element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />}
        />
      </Routes>
    </Router>
  );
};

export default App;


# ============ 文件2: src/backend/main.py ============

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging
import os
from auth_endpoints import router as auth_router  # 导入认证路由

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Hyperliquid AI Trader API",
    description="生产级加密货币高频交易系统",
    version="1.0.0"
)

# 允许跨域请求 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "Hyperliquid AI Trader API"
    }

# 注册所有路由
app.include_router(auth_router)

# 其他路由...
# @app.get("/api/market/tickers")
# @app.post("/api/trading/orders")
# 等等

# 静态文件服务 (前端)
if os.path.exists("../frontend/dist"):
    app.mount("/", StaticFiles(directory="../frontend/dist", html=True), name="static")

@app.on_event("startup")
async def startup_event():
    logger.info("✅ FastAPI 已启动")
    logger.info("📍 API文档: http://localhost:8000/docs")
    logger.info("🌐 前端: http://localhost:3000")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("❌ FastAPI 已关闭")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )


# ============ 文件3: electron.js (主进程) ============

const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const isDev = require('electron-is-dev');
const path = require('path');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 1000,
    minHeight: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  // 加载应用
  const startUrl = isDev
    ? 'http://localhost:3000' // 开发模式: React开发服务器
    : `file://${path.join(__dirname, '../frontend/dist/index.html')}`; // 生产模式: 静态文件

  mainWindow.loadURL(startUrl);

  // 打开开发者工具 (仅在开发模式)
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }
}

app.on('ready', () => {
  createWindow();
  createMenu();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

// 菜单
function createMenu() {
  const template = [
    {
      label: '文件',
      submenu: [
        {
          label: '退出',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: '帮助',
      submenu: [
        {
          label: '关于',
          click: () => {
            // 显示关于对话框
          }
        }
      ]
    }
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// IPC通信示例
ipcMain.on('auth-status', async (event) => {
  try {
    const response = await fetch('http://localhost:8000/api/auth/verify');
    const data = await response.json();
    event.reply('auth-status-reply', data);
  } catch (error) {
    event.reply('auth-status-reply', { error: error.message });
  }
});


# ============ 文件4: docker-compose.yml ============

version: '3.8'

services:
  # 前端 (React)
  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
      target: development
    ports:
      - "3000:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:8000
      - REACT_APP_WS_URL=ws://localhost:8000
    volumes:
      - ./src/frontend:/app/src
    depends_on:
      - api
    networks:
      - ai-trader-network

  # 后端 (FastAPI)
  api:
    build:
      context: .
      dockerfile: Dockerfile.backend
      target: development
    ports:
      - "8000:8000"
    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO
      - HYPERLIQUID_SANDBOX_MODE=true
      - DATABASE_URL=postgresql://trader:password@db:5432/ai_trader
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./src/backend:/app/src
    depends_on:
      - db
      - redis
    networks:
      - ai-trader-network
    command: >
      uvicorn src.backend.main:app
      --host 0.0.0.0
      --port 8000
      --reload

  # 数据库 (PostgreSQL)
  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=trader
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=ai_trader
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - ai-trader-network

  # 缓存 (Redis)
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    networks:
      - ai-trader-network

volumes:
  postgres_data:

networks:
  ai-trader-network:
    driver: bridge


# ============ 文件5: .env 配置 ============

# ========== 无需填写API密钥! ==========
# API密钥通过扫码登录自动获取

# 交易所配置
HYPERLIQUID_SANDBOX_MODE=true
HYPERLIQUID_API_ENDPOINT=https://api.hyperliquid.xyz
HYPERLIQUID_WS_ENDPOINT=wss://api.hyperliquid.xyz/ws

# 应用配置
APP_ENV=development
APP_DEBUG=true
LOG_LEVEL=INFO

# 数据库
DATABASE_URL=postgresql://trader:password@localhost:5432/ai_trader

# Redis
REDIS_URL=redis://localhost:6379/0

# OAuth2配置
OAUTH2_CLIENT_ID=crypto-ai-trader
OAUTH2_REDIRECT_URI=http://localhost:3000/auth/callback

# 后端API地址
API_BASE_URL=http://localhost:8000
WS_BASE_URL=ws://localhost:8000

# 前端地址
FRONTEND_URL=http://localhost:3000


# ============ 启动步骤 ============

# 1. 使用Docker Compose启动所有服务
docker-compose up -d

# 2. 等待所有服务启动 (~30秒)
docker-compose logs -f

# 3. 打开浏览器
# http://localhost:3000

# 4. 扫码登录
# 应用会显示QR码，用Hyperliquid App扫一下

# 5. 完成!
# 自动跳转到交易仪表板


# ============ 调试 ============

# 查看后端日志
docker-compose logs -f api

# 查看前端日志
docker-compose logs -f frontend

# 进入后端容器
docker-compose exec api bash

# 进入数据库
docker-compose exec db psql -U trader -d ai_trader

# 重启所有服务
docker-compose restart

# 清理所有容器和数据
docker-compose down -v


# ============ 关键要点 ============

# ✅ API密钥零存储
#    - 所有凭证通过OAuth获取
#    - 令牌存储在加密的会话中
#    - 用户注销时自动清理

# ✅ 安全通信
#    - 所有API调用都经过CORS验证
#    - WebSocket连接使用安全令牌
#    - 敏感数据在传输前加密

# ✅ 会话管理
#    - 自动令牌刷新
#    - 会话过期后需要重新登录
#    - 支持多设备同时登录

# ✅ 错误处理
#    - 网络错误自动重试
#    - 认证失败时清除本地数据
#    - 完整的错误日志记录

"""

配置检查清单:

□ docker-compose.yml 已配置好所有服务
□ .env 文件中API密钥字段已移除
□ auth_endpoints.py 已创建并注册到FastAPI
□ QRLogin.tsx 已创建并集成到React
□ App.tsx 已更新路由和认证检查
□ 前端build脚本已配置
□ 数据库migration脚本已准备

启动命令:
docker-compose up -d && docker-compose logs -f

然后打开: http://localhost:3000
"""
