#!/usr/bin/env python3
"""
Hyperliquid AI Trader v2 - 最小化启动版本
"""

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Hyperliquid AI Trader v2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

trading_active = False

@app.on_event("startup")
async def startup():
    logger.info("=" * 60)
    logger.info("🚀 Hyperliquid AI Trader v2 启动中...")
    logger.info("✅ 系统已初始化")
    logger.info("=" * 60)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/")
async def root():
    return {"message": "Hyperliquid AI Trader v2"}

@app.get("/api/info")
async def info():
    return {"name": "Hyperliquid AI Trader v2", "version": "2.0.0"}

@app.get("/api/status")
async def status():
    return {"active": trading_active}

@app.post("/api/trading/start")
async def start_trading():
    global trading_active
    trading_active = True
    return {"status": "started"}

@app.post("/api/trading/stop")
async def stop_trading():
    global trading_active
    trading_active = False
    return {"status": "stopped"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "ping"})
            await asyncio.sleep(5)
    except:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
