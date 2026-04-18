"""
AsterDex HFT Auto Trader - 后端核心
- 交易所: AsterDex Pro API V3 (fapi3.asterdex.com)
- 认证: EIP-712 结构化签名 (user + signer + nonce + 私钥)
- 行情: AsterDex WebSocket wss://fstream.asterdex.com
- 下单: POST /fapi/v3/order
- 账户: GET /fapi/v3/balance + /fapi/v3/positionRisk
"""

import asyncio
import itertools
import json
import logging
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp
import uvicorn
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Security imports
from security import secure_key_context, set_global_key, get_global_key, clear_global_key, validate_private_key_format
from config import Config


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("asterdex_trader")

# 持久化历史文件
HISTORY_FILE = Path(__file__).parent / "trade_history.json"

def _load_history() -> tuple:
    """从文件加载交易记录、绩效和symbol_settings"""
    default_perf = {"total_trades":0,"wins":0,"losses":0,"total_pnl":0.0,
                    "daily_pnl":0.0,"win_rate":0,"daily_pnl_pct":0.0,
                    "total_pnl_pct":0.0,"daily_history":{}}
    if not HISTORY_FILE.exists():
        return [], default_perf, {}
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        logs = [l for l in data.get("logs", []) if l.get("status") != "failed"]
        perf = data.get("perf", default_perf)
        sym_settings = data.get("symbol_settings", {})  # 恢复独立币种参数
        # 恢复全局settings（覆盖到state.settings，在TradingState.__init__后执行）
        global_cfg = data.get("global_settings", {})
        if global_cfg:
            # 延迟合并：通过返回值传给TradingState
            sym_settings["__global__"] = global_cfg  # 借用sym_settings传递
        # 确保新字段存在（旧文件兼容）
        for k, v in default_perf.items():
            perf.setdefault(k, v)
        # daily_pnl 只算今日，重启后若不是今天就清零
        today = datetime.now().strftime("%Y-%m-%d")
        if perf.get("_last_date", "") != today:
            perf["daily_pnl"] = 0.0
            perf["daily_pnl_pct"] = 0.0
            perf["_last_date"] = today
        logger.info(f"📂 加载历史记录 {len(logs)} 条，symbol_settings {len(sym_settings)} 个")
        return logs, perf, sym_settings
    except Exception as e:
        logger.warning(f"加载历史失败: {e}")
        return [], default_perf, {}

def _save_history(logs: list, perf: dict):
    """保存交易记录、绩效、symbol_settings和全局settings到文件"""
    try:
        # 全局settings中去掉symbol_settings（单独存），避免重复
        global_cfg = {k: v for k, v in state.settings.items() if k != "symbol_settings"}
        HISTORY_FILE.write_text(
            json.dumps({
                "logs": [l for l in logs if l.get("status") != "failed"][:500],
                "perf": perf,
                "symbol_settings": state.settings.get("symbol_settings", {}),
                "global_settings": global_cfg,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception as e:
        logger.warning(f"保存历史失败: {e}")

# ─────────────────────────────────────────────
# 全局复用 aiohttp Session（避免高频下重复建连）
# ─────────────────────────────────────────────
_http_session: Optional[aiohttp.ClientSession] = None

def _get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session

# ─────────────────────────────────────────────
# AsterDex API 常量
# ─────────────────────────────────────────────
ASTER_BASE   = Config.ASTER_BASE
ASTER_WS     = Config.ASTER_WS

# EIP-712 domain (固定)
EIP712_DOMAIN = {
    "types": {
        "EIP712Domain": [
            {"name": "name",             "type": "string"},
            {"name": "version",          "type": "string"},
            {"name": "chainId",          "type": "uint256"},
            {"name": "verifyingContract","type": "address"},
        ],
        "Message": [
            {"name": "msg", "type": "string"}
        ],
    },
    "primaryType": "Message",
    "domain": {
        "name": "AsterSignTransaction",
        "version": "1",
        "chainId": 1666,
        "verifyingContract": "0x0000000000000000000000000000000000000000",
    },
    "message": {"msg": ""},
}

app = FastAPI(title="AsterDex HFT Trader", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)

# ─────────────────────────────────────────────
# 全局状态
# ─────────────────────────────────────────────
class TradingState:
    def __init__(self):
        self.logged_in: bool = False
        self.user: str = ""        # 主账户钉包地址
        self.signer: str = ""      # API 钉包地址
        self.private_key: str = "" # API 钉包私钥

        # 账户数据
        self.balance: float = 0.0
        self.available: float = 0.0
        self.positions: List[Dict] = []
        self.open_orders: List[Dict] = []

        # 行情
        self.market_prices: Dict[str, float] = {}
        self.orderbooks: Dict[str, Dict] = {}

        # 任务
        self.auto_trading: bool = False
        self.trading_task: Optional[asyncio.Task] = None
        self.ws_task: Optional[asyncio.Task] = None
        self.account_sync_task: Optional[asyncio.Task] = None
        self.kline_task: Optional[asyncio.Task] = None
        # 交易设置
        self.settings: Dict = {
            "strategy": "multi",
            "symbol": "BTCUSDT",
            "leverage": 2,
            "trade_size_usd": 10,
            "min_confidence": 0.70,
            "stop_loss_pct": 0.012,
            "take_profit_pct": 0.028,
            "enable_long": True,
            "enable_short": True,
            "max_open_positions": 3,
            "max_daily_loss_usd": 50,
            "cancel_on_reverse": True,
            "hft_interval_ms": 500,
            "hft_mode": "balanced",  # conservative/balanced/aggressive
            # EMA
            "ema_fast": 5, "ema_slow": 20, "ema_long": 60,
            # MACD
            "macd_fast": 12, "macd_slow": 26, "macd_signal": 9,
            # RSI
            "rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70,
        }

        # 绩效
        self.perf: Dict = {
            "total_trades": 0, "wins": 0, "losses": 0,
            "total_pnl": 0.0, "daily_pnl": 0.0, "win_rate": 0,
        }
        # 从文件恢复历史（含symbol_settings）
        _logs, _perf, _sym_settings = _load_history()
        self.trade_logs: List[Dict] = _logs
        self.perf = _perf
        if _sym_settings:
            # 恢复全局settings（从__global__键提取）
            global_cfg = _sym_settings.pop("__global__", {})
            if global_cfg:
                # 只恢复运行时可能变化的字段，保留代码默认值作为兜底
                for k in ("hft_mode","cooldown_secs","leverage","trade_size_usd",
                          "min_confidence","stop_loss_pct","take_profit_pct",
                          "max_open_positions","max_daily_loss_usd","hft_interval_ms",
                          "active_symbols","symbol","enable_long","enable_short"):
                    if k in global_cfg:
                        self.settings[k] = global_cfg[k]
            self.settings["symbol_settings"] = _sym_settings

state = TradingState()

# ─────────────────────────────────────────────
# 每个币种独立的开仓锁，防止并发 gather 里两个协程同时通过持仓检查后重复开仓
# asyncio.Lock 是协程安全的（同一事件循环内），无需 threading.Lock
_sym_locks: Dict[str, asyncio.Lock] = {}

def _get_sym_lock(symbol: str) -> asyncio.Lock:
    if symbol not in _sym_locks:
        _sym_locks[symbol] = asyncio.Lock()
    return _sym_locks[symbol]

# ─────────────────────────────────────────────
# WebSocket 广播
# ─────────────────────────────────────────────
ws_clients: Set[WebSocket] = set()

async def broadcast(msg_type: str, data: Any):
    global ws_clients
    if not ws_clients:
        return
    msg = json.dumps({"type": msg_type, "data": data})
    dead = set()
    for ws in ws_clients.copy():
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    ws_clients -= dead

# ─────────────────────────────────────────────
# AsterDex Pro V3 EIP-712 签名工具
# ─────────────────────────────────────────────
_nonce_lock = threading.Lock()
_last_sec = 0
_nonce_i   = 0

def _nonce() -> int:
    global _last_sec, _nonce_i
    with _nonce_lock:
        now = int(time.time())
        if now == _last_sec:
            _nonce_i += 1
        else:
            _last_sec = now
            _nonce_i  = 0
        return now * 1_000_000 + _nonce_i

def _sign_v3(query_string: str) -> str:
    """EIP-712 结构化签名，对不含signature的query string签名，返回hex"""
    td = json.loads(json.dumps(EIP712_DOMAIN))  # deep copy
    td["message"]["msg"] = query_string
    msg = encode_typed_data(full_message=td)
    # ✅ Use secure key retrieval
    private_key = get_global_key()
    if not private_key:
        raise ValueError("Private key not available - please login first")
    signed = Account.sign_message(msg, private_key=private_key)
    return signed.signature.hex()

def _build_signed_url(base_url: str, params: dict) -> str:
    p = dict(params)
    p["user"]   = state.user
    p["signer"] = state.signer
    p["nonce"]  = str(_nonce())
    qs  = urllib.parse.urlencode(p)
    sig = "0x" + _sign_v3(qs)
    return base_url + "?" + qs + "&signature=" + sig

def _build_signed_body(params: dict) -> dict:
    p = dict(params)
    p["user"]   = state.user
    p["signer"] = state.signer
    p["nonce"]  = str(_nonce())
    qs  = urllib.parse.urlencode(p)
    p["signature"] = "0x" + _sign_v3(qs)
    return p

_HEADERS = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "PythonApp/1.0"}

async def aster_get(path: str, params: dict = None, auth: bool = False) -> Optional[dict]:
    base_url = ASTER_BASE + path
    s = _get_session()
    try:
        if auth:
            # ✅ Check secure key store instead of state.private_key
            if not get_global_key():
                logger.warning("❌ Authentication required but no valid key")
                return None
            signed_url = _build_signed_url(base_url, dict(params or {}))
            async with s.get(signed_url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                if r.status == 200:
                    return await r.json()
                txt = await r.text()
                logger.error(f"GET {path} -> {r.status}: {txt[:400]}")
                return None
        else:
            async with s.get(base_url, params=params, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    return await r.json()
                txt = await r.text()
                logger.error(f"GET {path} -> {r.status}: {txt[:400]}")
                return None
    except Exception as e:
        logger.error(f"GET {path} error: {e}")
        return None

async def aster_get_raw(path: str, params: dict = None, auth: bool = False):
    """Returns (json_or_None, raw_text) — used for login diagnostics."""
    base_url = ASTER_BASE + path
    s = _get_session()
    try:
        if auth:
            # ✅ Check secure key store
            if not get_global_key():
                return None, "not logged in"
            signed_url = _build_signed_url(base_url, dict(params or {}))
            async with s.get(signed_url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                txt = await r.text()
                if r.status == 200:
                    return json.loads(txt), txt
                logger.error(f"RAW GET {path} -> {r.status}: {txt[:500]}")
                return None, txt
        else:
            async with s.get(base_url, params=params, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                txt = await r.text()
                if r.status == 200:
                    return json.loads(txt), txt
                return None, txt
    except Exception as e:
        logger.error(f"GET {path} error: {e}")
        return None, str(e)

async def aster_post(path: str, params: dict = None) -> Optional[dict]:
    # ✅ Check secure key store
    if not get_global_key():
        logger.warning("❌ POST request attempted without valid authentication key")
        return None
    body = _build_signed_body(dict(params or {}))
    url  = ASTER_BASE + path
    s = _get_session()
    try:
        async with s.post(url, data=body, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
            result = await r.json()
            if r.status not in (200, 201):
                logger.error(f"POST {path} -> {r.status}: {result}")
            return result
    except Exception as e:
        logger.error(f"POST {path} error: {e}")
        return None

async def aster_delete(path: str, params: dict = None) -> Optional[dict]:
    # ✅ Check secure key store
    if not get_global_key():
        logger.warning("❌ DELETE request attempted without valid authentication key")
        return None
    base_url   = ASTER_BASE + path
    signed_url = _build_signed_url(base_url, dict(params or {}))
    s = _get_session()
    try:
        async with s.delete(signed_url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
            return await r.json()
    except Exception as e:
        logger.error(f"DELETE {path} error: {e}")
        return None

# ─────────────────────────────────────────────
# 账户同步
# ─────────────────────────────────────────────
async def sync_account():
    """拉取余额 + 持仓 + 挂单"""
    # 余额
    bal = await aster_get("/fapi/v3/balance", auth=True)
    if bal and isinstance(bal, list):
        for b in bal:
            if b.get("asset") == "USDT":
                state.balance = float(b.get("balance", 0))
                state.available = float(b.get("availableBalance", 0))
                break

    # 持仓
    pos = await aster_get("/fapi/v3/positionRisk", auth=True)
    if pos and isinstance(pos, list):
        active = []
        for p in pos:
            sz  = float(p.get("positionAmt", 0))
            sym = p.get("symbol", "")          # ← 修复：定义sym变量
            if abs(sz) > 1e-9:
                side = "LONG" if sz > 0 else "SHORT"
                lev  = max(int(p.get("leverage", 1)), 1)
                ep   = float(p.get("entryPrice", 0))
                tracker = pos_tracker.entries.get(sym, {})
                active.append({
                    "symbol":         sym,
                    "side":           side,
                    "size":           abs(sz),
                    "entry_price":    ep,
                    "mark_price":     float(p.get("markPrice", 0)),
                    "unrealized_pnl": float(p.get("unRealizedProfit", 0)),
                    "leverage":       lev,
                    "liq_price":      float(p.get("liquidationPrice", 0)),
                    "tp_price":       round(tracker.get("tp", 0), 4),
                    "sl_price":       round(tracker.get("sl", 0), 4),
                    "entry_usd":      round(abs(sz) * ep / lev, 2),  # ← 用abs(sz)
                    "open_time":      tracker.get("open_time", ""),
                })
        state.positions = active

    # 挂单
    orders = await aster_get("/fapi/v3/openOrders", auth=True)
    if orders and isinstance(orders, list):
        state.open_orders = [
            {
                "order_id": o.get("orderId"),
                "symbol":   o.get("symbol"),
                "side":     o.get("side"),
                "price":    float(o.get("price", 0)),
                "size":     float(o.get("origQty", 0)),
                "status":   o.get("status"),
            }
            for o in orders
        ]

async def account_sync_loop():
    logger.info("🔄 账户同步循环启动")
    while state.logged_in:
        try:
            await sync_account()
            await broadcast("account_update", {
                "logged_in":   True,
                "balance":     state.balance,
                "available":   state.available,
                "positions":   state.positions,
                "open_orders": state.open_orders,
            })
        except Exception as e:
            logger.error(f"账户同步失败: {e}")
        await asyncio.sleep(3)

# ─────────────────────────────────────────────
# AsterDex 行情 WebSocket
# ─────────────────────────────────────────────
async def market_ws_loop():
    """订阅 AsterDex 行情 WS: aggTrade + depth"""
    try:
        import websockets as ws_lib
    except ImportError:
        logger.warning("websockets 未安装，使用 REST 轮询行情")
        await market_poll_loop()
        return

    while state.logged_in:
        # 每次重连时重新读取active_symbols，支持运行中动态变更
        active = state.settings.get("active_symbols", ["BTCUSDT","ETHUSDT","SOLUSDT","ARBUSDT","AVAXUSDT"])
        syms = list({s.lower() for s in active} | {"btcusdt","ethusdt","solusdt"})
        streams = (
            [f"{s}@aggTrade"      for s in syms] +
            [f"{s}@depth5@100ms"  for s in syms] +
            [f"{s}@kline_1m"      for s in syms]
        )
        url = f"{ASTER_WS}/stream?streams=" + "/".join(streams)
        try:
            logger.info(f"📡 连接行情 WS: {url[:80]}...")
            async with ws_lib.connect(url, ping_interval=20, ping_timeout=10) as ws:
                await broadcast("ws_status", {"connected": True})
                _seen_etypes: set = set()
                async for raw in ws:
                    try:
                        outer = json.loads(raw)
                        data = outer.get("data", outer)
                        etype = data.get("e", "")
                        # 首次见到某类型事件时打印日志，帮助确认流是否正常
                        if etype and etype not in _seen_etypes:
                            _seen_etypes.add(etype)
                            logger.info(f"📡 WS首次收到事件类型: {etype} (stream={outer.get('stream','?')})")

                        if etype == "aggTrade":
                            sym = data["s"].replace("USDT", "")
                            px = float(data["p"])
                            state.market_prices[sym] = px
                            # 也存完整 symbol 供下单用
                            state.market_prices[data["s"]] = px
                            await broadcast("prices", {k: v for k, v in state.market_prices.items() if not k.endswith("USDT")})


                        elif etype == "depthUpdate":
                            sym = data["s"].replace("USDT", "")
                            state.orderbooks[sym] = {
                                "bids": data.get("b", [])[:10],
                                "asks": data.get("a", [])[:10],
                            }
                            if sym == state.settings.get("symbol", "BTC").replace("USDT",""):
                                await broadcast("orderbook", state.orderbooks[sym])

                        elif etype in ("kline", "k"):  # 兼容不同格式
                            k   = data.get("k") or data  # 有些交易所k线数据直接在data里
                            sym = data.get("s") or k.get("s", "")   # 完整 symbol，如 ETHUSDT
                            # k线字段: t,T,s,i,o,c,h,l,v,n,x(是否完成),q,V,Q,...
                            bar = [
                                k["t"], k["o"], k["h"], k["l"],
                                k["c"], k["v"], k["T"], k["q"],
                                k["n"], k["V"], k["Q"], "0",
                            ]
                            cache = kline_cache.get(sym, [])
                            if cache:
                                last_t = cache[-1][0] if isinstance(cache[-1][0], int) else int(cache[-1][0])
                                if last_t == k["t"]:
                                    cache[-1] = bar        # 更新当前未完成K线
                                elif k["t"] > last_t:
                                    cache.append(bar)      # 新K线开始
                                    cache = cache[-300:]   # 最多保留300根
                                kline_cache[sym] = cache

                    except Exception as e:
                        logger.error(f"WS 消息解析: {e}")

        except Exception as e:
            logger.error(f"行情 WS 断开: {e}")
            await broadcast("ws_status", {"connected": False})
            await asyncio.sleep(5)

async def market_poll_loop():
    """REST 轮询行情（websockets 不可用时）"""
    logger.info("📊 行情 REST 轮询启动")
    while state.logged_in:
        try:
            syms = state.settings.get("active_symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            for sym in syms:
                data = await aster_get("/fapi/v3/ticker/price", {"symbol": sym})
                if data:
                    k = sym.replace("USDT", "")
                    px = float(data.get("price", 0))
                    state.market_prices[k] = px
                    state.market_prices[sym] = px
            await broadcast("prices", {k: v for k, v in state.market_prices.items() if not k.endswith("USDT")})
        except Exception as e:
            logger.error(f"行情轮询: {e}")
        await asyncio.sleep(1)

# ─────────────────────────────────────────────
# 下单 / 撤单 / 平仓
# ─────────────────────────────────────────────
# 各币种数量精度（stepSize）
QTY_PRECISION = {
    "BTCUSDT": 3, "ETHUSDT": 3, "SOLUSDT": 0,
    "ARBUSDT": 0, "AVAXUSDT": 1, "BNBUSDT": 2,
}

def _fmt_qty(symbol: str, qty: float) -> str:
    prec = QTY_PRECISION.get(symbol.upper(), 3)
    return f"{qty:.{prec}f}"

async def place_order(symbol: str, side: str, order_type: str,
                      quantity: float, price: float = 0,
                      reduce_only: bool = False) -> Optional[dict]:
    """下单 (symbol 格式: BTCUSDT)"""
    qty_str = _fmt_qty(symbol, quantity)
    params = {
        "symbol":    symbol,
        "side":      side,
        "type":      order_type,
        "quantity":  qty_str,
        "reduceOnly": "true" if reduce_only else "false",
    }
    if order_type == "LIMIT":
        params["price"] = round(price, 2)
        params["timeInForce"] = "GTC"

    # 诊断信息
    if not get_global_key():
        logger.error(f"❌ 下单前检查: 未登录，无法下单 {symbol}")
        return None
    if quantity <= 0:
        logger.error(f"❌ 下单前检查: 手数无效 {symbol} qty={qty_str}")
        return None
    if state.available < 1.0:
        logger.error(f"❌ 下单前检查: 余额不足 {symbol} available=${state.available:.2f}")
        return None

    logger.info(f"📍 下单请求 {side} {symbol} qty={qty_str} px={price} auth={'✅' if get_global_key() else '❌'}")
    result = await aster_post("/fapi/v3/order", params)

    if result is None:
        logger.error(f"❌ 下单失败 {side} {symbol}: 无API响应")
    elif isinstance(result, dict):
        if result.get("code") and result["code"] < 0:
            logger.error(f"❌ 下单被拒 {side} {symbol}: {result.get('msg', 'unknown')}")
        elif result.get("orderId"):
            logger.info(f"✅ 下单成功 {side} {symbol} orderId={result.get('orderId')}")
        else:
            logger.warning(f"⚠️ 下单响应异常 {side} {symbol}: {result}")

    return result

async def cancel_order(symbol: str, order_id: int) -> Optional[dict]:
    return await aster_delete("/fapi/v3/order", {"symbol": symbol, "orderId": order_id})

async def cancel_all_orders(symbol: str) -> Optional[dict]:
    return await aster_delete("/fapi/v3/allOpenOrders", {"symbol": symbol})

async def close_position(symbol: str) -> Optional[dict]:
    """市价平仓（优先用交易所持仓，API延迟时从pos_tracker补充，确保及时平仓）"""
    pos = next((p for p in state.positions if p["symbol"] == symbol), None)
    if pos:
        close_side = "SELL" if pos["side"] == "LONG" else "BUY"
        sz = pos["size"]
    else:
        # API未同步时从本地tracker取方向和size
        entry = pos_tracker.entries.get(symbol)
        if not entry:
            return None
        close_side = "SELL" if entry["side"] == "BUY" else "BUY"
        sz = entry.get("sz", 0)
        if sz <= 0:
            return None
        logger.warning(f"⚡ {symbol} close_position: API未同步，使用tracker补充平仓 side={close_side} sz={sz}")
    return await place_order(symbol, close_side, "MARKET", sz, reduce_only=True)

async def set_leverage(symbol: str, leverage: int):
    await aster_post("/fapi/v3/leverage", {"symbol": symbol, "leverage": leverage})

# ─────────────────────────────────────────────
# K 线缓存（按 symbol 存储真实 OHLCV）
# ─────────────────────────────────────────────
kline_cache: Dict[str, List[list]] = {}   # symbol -> [[open_t,o,h,l,c,v,...], ...]

async def refresh_klines(symbol: str, interval: str = "1m", limit: int = 200):
    """拉取真实K线并更新缓存"""
    data = await aster_get("/fapi/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit})
    if data and isinstance(data, list):
        kline_cache[symbol] = data
        logger.debug(f"K线刷新 {symbol} {len(data)}根")
    return kline_cache.get(symbol, [])

async def kline_refresh_loop():
    """后台定时刷新所有启用币种的K线（每10秒）"""
    logger.info("📊 K线刷新循环启动")
    while state.logged_in:
        try:
            active = state.settings.get("active_symbols",
                        [state.settings.get("symbol", "BTCUSDT")])
            interval = state.settings.get("kline_interval", "1m")
            await asyncio.gather(
                *[refresh_klines(sym, interval, 200) for sym in active],
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"K线刷新失败: {e}")
        await asyncio.sleep(10)

# ─────────────────────────────────────────────
# 新 CryptoHFT 信号引擎（7维度，基于真实OHLCV K线）
# ─────────────────────────────────────────────
class CryptoHFTEngine:
    """基于真实K线OHLCV的7维度加权信号引擎"""

    WEIGHTS = {
        "supertrend": 0.22,
        "ema":        0.20,
        "macd":       0.15,
        "rsi":        0.15,
        "vwap":       0.12,
        "obi":        0.11,
        "momentum":   0.05,
    }

    # ── 指标计算 ──────────────────────────────
    @staticmethod
    def _ema(arr, n):
        if len(arr) < n: return arr[-1] if arr else 0.0
        k = 2.0 / (n + 1)
        v = sum(arr[:n]) / n
        for x in arr[n:]: v = x * k + v * (1 - k)
        return v

    @staticmethod
    def _ema_series(arr, n):
        if len(arr) < n: return []
        k = 2.0 / (n + 1)
        out = [sum(arr[:n]) / n]
        for x in arr[n:]: out.append(x * k + out[-1] * (1 - k))
        return out

    def _rsi(self, closes, n=14):
        if len(closes) < n + 1: return 50.0
        d = [closes[i] - closes[i-1] for i in range(1, len(closes))][-n:]
        g = [x for x in d if x > 0]; l_ = [-x for x in d if x < 0]
        ag = sum(g)/n if g else 0.0; al = sum(l_)/n if l_ else 1e-9
        return 100 - 100 / (1 + ag / al)

    def _macd(self, closes, fast=12, slow=26, sig=9):
        if len(closes) < slow + sig: return 0.0, 0.0, 0.0
        ef = self._ema_series(closes, fast)
        es = self._ema_series(closes, slow)
        ml = min(len(ef), len(es))
        dif = [ef[-(ml-i)] - es[-(ml-i)] for i in range(ml)]
        sv  = self._ema_series(dif, sig)
        if not sv: return 0.0, 0.0, 0.0
        return dif[-1], sv[-1], dif[-1] - sv[-1]

    def _supertrend(self, highs, lows, closes, n=10, mult=3.0):
        """价格低于下轨(hl2-mult*atr)=上升趋势up；高于上轨(hl2+mult*atr)=下降趋势down；区间内=neutral"""
        if len(closes) < n + 1: return "neutral"
        trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
               for i in range(1, len(closes))]
        atr = sum(trs[-n:]) / n
        hl2 = (highs[-1] + lows[-1]) / 2
        lower = hl2 - mult * atr  # 下轨：价格站上=多头
        upper = hl2 + mult * atr  # 上轨：价格跌破=空头
        p = closes[-1]
        if p >= lower and p <= upper: return "neutral"  # 价格在区间内
        if p < lower:  return "up"    # 价格跌破下轨，已是超卖，反转看多
        return "down"                 # 价格突破上轨，已是超买，反转看空

    def _vwap(self, highs, lows, closes, volumes):
        typical = [(h+l+c)/3 for h,l,c in zip(highs, lows, closes)]
        tv = sum(t*v for t,v in zip(typical, volumes))
        sv = sum(volumes)
        return tv / sv if sv > 0 else closes[-1]

    def _obi(self, sym_short: str):
        ob = state.orderbooks.get(sym_short, {})
        bids = ob.get("bids", []); asks = ob.get("asks", [])
        if not bids or not asks: return 0.0
        try:
            bv = sum(float(b[1]) for b in bids[:10])
            av = sum(float(a[1]) for a in asks[:10])
            return (bv - av) / (bv + av + 1e-9)
        except: return 0.0

    @staticmethod
    def _atr(highs, lows, closes, n=14):
        """ATR 真实波动幅"""
        trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
               for i in range(1, len(closes))]
        return sum(trs[-n:]) / n if len(trs) >= n else sum(trs) / max(len(trs), 1)

    @staticmethod
    def _adx(highs, lows, closes, n=14):
        """ADX 趋势强度：>25为趋势，<20为震荡"""
        if len(closes) < n * 2: return 0.0
        plus_dm, minus_dm, trs = [], [], []
        for i in range(1, len(closes)):
            h_diff = highs[i] - highs[i-1]
            l_diff = lows[i-1] - lows[i]
            plus_dm.append(h_diff if h_diff > l_diff and h_diff > 0 else 0)
            minus_dm.append(l_diff if l_diff > h_diff and l_diff > 0 else 0)
            trs.append(max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])))
        def smooth(arr, n):
            s = sum(arr[:n])
            out = [s]
            for x in arr[n:]: s = s - s/n + x; out.append(s)
            return out
        atr14 = smooth(trs, n); p14 = smooth(plus_dm, n); m14 = smooth(minus_dm, n)
        di_plus  = [100*p/a if a>0 else 0 for p,a in zip(p14, atr14)]
        di_minus = [100*m/a if a>0 else 0 for m,a in zip(m14, atr14)]
        dx = [abs(p-m)/(p+m+1e-9)*100 for p,m in zip(di_plus, di_minus)]
        adx_val = sum(dx[-n:]) / n if len(dx) >= n else sum(dx) / max(len(dx), 1)
        return round(adx_val, 2)

    def compute(self, klines: list, sym_short: str) -> tuple:
        """返回 (side, confidence, scores_dict)"""
        if len(klines) < 65:
            return "HOLD", 0.0, {}

        closes  = [float(k[4]) for k in klines]
        highs   = [float(k[2]) for k in klines]
        lows    = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        price   = closes[-1]

        scores: Dict[str, float] = {}

        # ─── 市场状态预判断：震荡市直接不开仓 ───
        adx = self._adx(highs, lows, closes)
        atr = self._atr(highs, lows, closes)
        atr_pct = atr / price  # ATR占价格百分比
        scores["_adx"] = round(adx, 2)
        scores["_atr_pct"] = round(atr_pct * 100, 4)

        # ADX < 10 = 极度无方向（平台整理），直接HOLD
        if adx < 10:
            scores["_market"] = "ranging"
            return "HOLD", 0.0, scores
        # ADX 10-22：震荡行情，保留得分但generate()里会过滤（ADX<22一律不开仓）
        scores["_market"] = "trending" if adx >= 22 else "ranging"

        # 1. Supertrend
        st = self._supertrend(highs, lows, closes)
        scores["supertrend"] = 1.0 if st=="up" else (-1.0 if st=="down" else 0.0)

        # 2. EMA 三线
        e5  = self._ema(closes, 5)
        e20 = self._ema(closes, 20)
        e60 = self._ema(closes, 60)
        if e5 > e20 > e60:   scores["ema"] = 1.0
        elif e5 < e20 < e60: scores["ema"] = -1.0
        else:                 scores["ema"] = (1.0 if e5>e20 else -1.0) * 0.4

        # 3. MACD
        macd_l, sig_l, hist = self._macd(closes)
        if   hist > 0 and macd_l > 0: scores["macd"] =  1.0
        elif hist > 0:                 scores["macd"] =  0.5
        elif hist < 0 and macd_l < 0: scores["macd"] = -1.0
        elif hist < 0:                 scores["macd"] = -0.5
        else:                          scores["macd"] =  0.0

        # 4. RSI
        rsi_v = self._rsi(closes)
        if   rsi_v < 30: scores["rsi"] =  min(1.0, (30 - rsi_v) / 30)
        elif rsi_v > 70: scores["rsi"] = -min(1.0, (rsi_v - 70) / 30)
        else:             scores["rsi"] =  0.0

        # 5. VWAP 偏离
        vwap_p = self._vwap(highs, lows, closes, volumes)
        dev    = (price - vwap_p) / (vwap_p + 1e-9)
        if   dev < -0.003: scores["vwap"] =  min(1.0, -dev / 0.01)
        elif dev >  0.003: scores["vwap"] = max(-1.0, -dev / 0.01)
        else:              scores["vwap"] =  0.0

        # 6. 订单簿不平衡 OBI
        scores["obi"] = max(-1.0, min(1.0, self._obi(sym_short)))

        # 7. 动量（5+20周期）
        mom5  = (closes[-1] - closes[-6])  / (closes[-6]  + 1e-9) if len(closes) >= 6  else 0.0
        mom20 = (closes[-1] - closes[-21]) / (closes[-21] + 1e-9) if len(closes) >= 21 else 0.0
        scores["momentum"] = max(-1.0, min(1.0, (mom5 * 0.6 + mom20 * 0.4) / 0.005))

        # ─── 硬性过滤：三个核心指标必须至少 2 个方向一致 ───
        core_bull = sum(1 for k in ("supertrend","ema","macd") if scores.get(k,0) > 0.3)
        core_bear = sum(1 for k in ("supertrend","ema","macd") if scores.get(k,0) < -0.3)
        if core_bull < 2 and core_bear < 2:
            # 核心指标没有共识，信号不可靠
            scores["_bull"] = 0.0; scores["_bear"] = 0.0
            return "HOLD", 0.0, scores

        # ── 加权合成 ──
        bull = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS if scores.get(k,0) > 0)
        bear = sum(abs(scores[k]) * self.WEIGHTS[k] for k in self.WEIGHTS if scores.get(k,0) < 0)
        total = bull + bear
        if total < 1e-6:
            return "HOLD", 0.0, scores

        bull_pct = bull / total
        bear_pct = bear / total

        # Supertrend 硬性过滤
        if scores["supertrend"] < 0 and bull_pct > bear_pct:
            bull_pct *= 0.4; bear_pct = 1 - bull_pct
        if scores["supertrend"] > 0 and bear_pct > bull_pct:
            bear_pct *= 0.4; bull_pct = 1 - bear_pct

        if   bull_pct > bear_pct: side = "BUY";  confidence = round(bull_pct, 4)
        elif bear_pct > bull_pct: side = "SELL"; confidence = round(bear_pct, 4)
        else:                      side = "HOLD"; confidence = 0.5

        scores["_bull"] = round(bull_pct, 4)
        scores["_bear"] = round(bear_pct, 4)

        return side, confidence, scores

    def generate(self, s: dict, sym_short: str, symbol: str = ""):
        """对外接口：返回 (side, conf, block_reason)，经过 min_confidence + 盈亏比校验"""
        # symbol 必须从外部传入，避免 sym_cfg 没有 symbol 字段时回退到全局 BTCUSDT
        if not symbol:
            symbol = s.get("symbol", sym_short + "USDT")
        klines   = kline_cache.get(symbol, [])
        min_conf = s.get("min_confidence", 0.70)
        sl_pct   = s.get("stop_loss_pct",  0.012)
        tp_pct   = s.get("take_profit_pct",0.028)
        side, conf, scores = self.compute(klines, sym_short)

        # 根据 hft_mode 动态调整参数
        # conservative: 精准模式，盈亏比>=1.8，震荡打折0.6
        # balanced:     平衡模式，盈亏比>=1.2，震荡打折0.8
        # aggressive:   激进模式(HFT)，盈亏比>=0.3，震荡不打折
        # hft_mode 优先读 sym_cfg（独立配置），不存在则回退全局 state.settings
        mode = s.get("hft_mode") or state.settings.get("hft_mode", "balanced")
        if mode == "conservative":
            rr_thresh, ranging_disc = 1.8, 0.6
        elif mode == "aggressive":
            rr_thresh, ranging_disc = 0.3, 1.0
        else:  # balanced
            rr_thresh, ranging_disc = 1.2, 0.8

        # ADX < 22 → HOLD：ADX在10-22之间本质是震荡市，核心指标容易被噪音满足加权条件
        adx_v = scores.get("_adx", 0)
        if adx_v < 22:
            return "HOLD", 0.0, f"ADX{adx_v:.1f}<22，震荡市不开仓"

        # 震荡行情按模式打折
        if scores.get("_market") == "ranging":
            conf = round(conf * ranging_disc, 4)

        # 盈亏比校验
        rr = round((tp_pct - 0.001) / (sl_pct + 0.001), 2)
        if rr < rr_thresh:
            return "HOLD", 0.0, f"盈亏比{rr}x<{rr_thresh}x（{mode}模式）"

        if side == "HOLD":
            return "HOLD", conf, f"综合置信{round(conf*100)}%未达阈值{round(min_conf*100)}%"

        if side == "BUY"  and not s.get("enable_long",  True): return "HOLD", conf, "做多已禁用"
        if side == "SELL" and not s.get("enable_short", True): return "HOLD", conf, "做空已禁用"

        if conf < min_conf:
            reason = f"置信{round(conf*100)}%<阈值{round(min_conf*100)}%"
            if scores.get("_market") == "ranging" and ranging_disc < 1.0:
                reason = f"震荡打折{int(ranging_disc*100)}%后{round(conf*100)}%<阈值{round(min_conf*100)}%"
            return "HOLD", conf, reason

        return side, conf, ""

# 单例
signal_engine = CryptoHFTEngine()

# ─────────────────────────────────────────────
# 仓位跟踪（止损/止盈 + 移动止损）
# ─────────────────────────────────────────────
class PositionTracker:
    def __init__(self):
        self.entries: Dict[str, dict] = {}

    def record(self, symbol, side, entry, sz, sl_pct, tp_pct, trailing=True, open_ctx=None, atr=None):
        """
        atr: 当前ATR值（绝对价格）。传入后初始止损用 max(固定%, 1.5×ATR)，
             移动止损在盈利>2×ATR后才激活，跟踪距离1×ATR。
        """
        # 初始止损：max(固定%, 1.5×ATR占价格比)
        if atr and atr > 0 and entry > 0:
            atr_sl_pct = (1.5 * atr) / entry
            eff_sl_pct = max(sl_pct, atr_sl_pct)
        else:
            eff_sl_pct = sl_pct
            atr_sl_pct = sl_pct
        sl = entry*(1-eff_sl_pct) if side=="BUY" else entry*(1+eff_sl_pct)
        tp = entry*(1+tp_pct)     if side=="BUY" else entry*(1-tp_pct)
        self.entries[symbol] = {
            "side": side, "entry": entry, "sz": sz,
            "sl": sl, "tp": tp, "sl_pct": eff_sl_pct,
            "trailing": trailing,
            "peak": entry,
            "atr": atr or 0,           # 开仓时ATR绝对值
            "atr_sl_pct": atr_sl_pct,  # ATR对应的止损比例（记录用）
            "trailing_armed": False,   # 移动止损是否已激活（盈利>2×ATR后才开启）
            "open_time": datetime.now().strftime("%H:%M:%S"),
            "open_ctx": open_ctx or {},
        }

    def should_exit(self, symbol, price):
        e = self.entries.get(symbol)
        if not e: return None
        entry = e["entry"]
        atr   = e["atr"]
        if e["side"] == "BUY":
            # 移动止损激活条件：盈利 > 2×ATR
            if e["trailing"] and atr > 0 and not e["trailing_armed"]:
                if price - entry >= 2 * atr:
                    e["trailing_armed"] = True
                    e["peak"] = price
            if e["trailing_armed"] and price > e["peak"]:
                e["peak"] = price
                # 跟踪距离：1×ATR（ATR为0时回退固定比例）
                trail_dist = atr / price if atr > 0 else e["sl_pct"]
                e["sl"] = max(e["sl"], price * (1 - trail_dist))
            if price <= e["sl"]: return "STOP_LOSS"
            if price >= e["tp"]: return "TAKE_PROFIT"
        else:
            if e["trailing"] and atr > 0 and not e["trailing_armed"]:
                if entry - price >= 2 * atr:
                    e["trailing_armed"] = True
                    e["peak"] = price
            if e["trailing_armed"] and price < e["peak"]:
                e["peak"] = price
                trail_dist = atr / price if atr > 0 else e["sl_pct"]
                e["sl"] = min(e["sl"], price * (1 + trail_dist))
            if price >= e["sl"]: return "STOP_LOSS"
            if price <= e["tp"]: return "TAKE_PROFIT"
        return None

    def clear(self, symbol): self.entries.pop(symbol, None)

pos_tracker = PositionTracker()

def rebuild_tracker_from_positions():
    """从交易所当前持仓重建 PositionTracker，防止重启后止损/止盈失效"""
    s = state.settings
    sym_settings = s.get("symbol_settings", {})
    rebuilt = 0
    for p in state.positions:
        sym = p["symbol"]
        if sym in pos_tracker.entries:
            continue  # 已有本地记录，不覆盖（保留移动止损状态）
        side_str = "BUY" if p["side"] == "LONG" else "SELL"
        ep       = p["entry_price"]
        sz       = p["size"]
        cfg      = sym_settings.get(sym, s)
        sl_pct   = cfg.get("stop_loss_pct",  s.get("stop_loss_pct",  0.012))
        tp_pct   = cfg.get("take_profit_pct", s.get("take_profit_pct", 0.028))
        trailing = cfg.get("trailing_stop",   s.get("trailing_stop",   True))
        pos_tracker.record(sym, side_str, ep, sz, sl_pct, tp_pct, trailing=trailing)
        rebuilt += 1
        logger.info(f"🔄 重建仓位跟踪 {sym} {side_str} entry={ep} sz={sz} sl={sl_pct*100:.1f}% tp={tp_pct*100:.1f}%")
    if rebuilt:
        logger.info(f"✅ 共重建 {rebuilt} 个币种的仓位跟踪记录")

# 平仓冷却期（防止反复横跳）：记录每个symbol最后平仓时间
_close_cooldown: Dict[str, float] = {}
COOLDOWN_SECS = 60  # 平仓后60秒内不开新仓

# ─────────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────────
_log_id_counter = itertools.count(int(time.time() * 1000))

def _order_ok(result) -> bool:
    if not result: return False
    return result.get("status") in ("NEW", "PARTIALLY_FILLED", "FILLED") or "orderId" in result

# AsterDex taker 手续费率（0.05%）
FEE_RATE = 0.0005

def _log_trade(symbol, side, price, sz, strategy, confidence, result, failed=False, open_ctx=None):
    status = "failed" if failed else ("filled" if _order_ok(result) else "sent")
    notional = round(float(sz) * float(price), 4)  # 名义金额
    fee      = round(notional * FEE_RATE, 6)        # 手续费
    # 计算盈亏（平仓时从 pos_tracker 算）
    pnl = 0.0
    hold_secs = 0
    ctx = open_ctx or {}
    if side == "CLOSE":  # 只有平仓才计算盈亏
        e = pos_tracker.entries.get(symbol)
        if e:
            entry_px  = e["entry"]
            real_sz   = float(e.get("sz", sz) or sz)
            open_fee  = round(real_sz * entry_px * FEE_RATE, 6)
            close_fee = round(real_sz * float(price) * FEE_RATE, 6)
            gross_pnl = (float(price) - entry_px) * real_sz if e["side"]=="BUY" else (entry_px - float(price)) * real_sz
            pnl = round(gross_pnl - open_fee - close_fee, 4)
            # 从pos_tracker取开仓上下文
            ctx = e.get("open_ctx", {})
            open_ts = ctx.get("open_ts", 0)
            hold_secs = int(time.time() - open_ts) if open_ts else 0
    _sym_cfg = state.settings.get("symbol_settings", {}).get(symbol) or state.settings
    _lev = float(_sym_cfg.get("leverage", state.settings.get("leverage", 1)))
    entry = {
        "id": next(_log_id_counter),  # 单调递增，并发安全
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "symbol": symbol, "side": side,
        "price": round(float(price), 4), "size": float(sz),
        "notional": notional,
        "fee": fee,
        "confidence": round(confidence, 3),
        "pnl": pnl,
        "hold_secs": hold_secs,      # 持仓时长（秒）
        "open_adx":  ctx.get("adx", 0),      # 开仓时ADX
        "open_conf": ctx.get("confidence", confidence),  # 开仓时置信度
        "open_sl":   ctx.get("sl_pct", 0),
        "open_tp":   ctx.get("tp_pct", 0),
        "status": status,
        "strategy": strategy,
        "result_raw": str((result or {}).get("orderId", "")),
        "leverage": _lev,
    }
    if failed:
        return  # failed订单不写历史记录，避免挤占有效成交记录
    state.trade_logs.insert(0, entry)
    state.trade_logs = state.trade_logs[:500]
    state.perf["total_trades"] += 1
    # 平仓时累加胜负笔数、盈亏、胜率、占比
    if side == "CLOSE":
        if pnl > 0:
            state.perf["wins"]   = state.perf.get("wins", 0) + 1
        elif pnl < 0:
            state.perf["losses"] = state.perf.get("losses", 0) + 1
        state.perf["total_pnl"] = round(state.perf.get("total_pnl", 0) + pnl, 4)
        w = state.perf.get("wins", 0)
        closed = w + state.perf.get("losses", 0)
        state.perf["win_rate"]  = round(w / closed * 100, 1) if closed else 0
        # 盈亏占比（相对账户余额）
        bal = state.balance if state.balance > 0 else 1.0
        state.perf["total_pnl_pct"]  = round(state.perf["total_pnl"] / bal * 100, 2)
        # 按日期记录历史，自动归零跨日 daily_pnl
        today = datetime.now().strftime("%Y-%m-%d")
        if state.perf.get("_last_date", today) != today:
            state.perf["daily_pnl"] = 0.0  # 新的一天，重置当日盈亏
        state.perf["_last_date"] = today
        state.perf["daily_pnl"] = round(state.perf.get("daily_pnl", 0) + pnl, 4)
        state.perf["daily_pnl_pct"]  = round(state.perf["daily_pnl"] / bal * 100, 2)
        dh = state.perf.setdefault("daily_history", {})
        day = dh.setdefault(today, {"pnl": 0.0, "trades": 0, "wins": 0})
        day["pnl"]    = round(day["pnl"] + pnl, 4)
        day["trades"] += 1
        if pnl > 0: day["wins"] += 1
        day["pnl_pct"] = round(day["pnl"] / bal * 100, 2)
    _save_history(state.trade_logs, state.perf)
    asyncio.create_task(broadcast("new_trade", entry))
    asyncio.create_task(broadcast("performance", state.perf))
    # 每20笔平仓自动触发参数优化
    if side == "CLOSE":
        closed_count = len([t for t in state.trade_logs if t.get("side") == "CLOSE"])
        if closed_count >= MIN_TRADES_FOR_OPT and closed_count % 20 == 0:
            asyncio.create_task(run_auto_optimize())

# ─────────────────────────────────────────────
# HFT 交易循环（多币种并发，每个币种最多1单）
# ─────────────────────────────────────────────

# 每个 symbol 的信号广播节流（避免洪泛）
_last_broadcast: Dict[str, float] = {}

async def _process_symbol(symbol: str, s: dict, daily_start_ref: list = None):
    """单币种处理：止损检查 → 信号生成 → 开平仓。每个币种最多持1单。"""
    sym_short = symbol.replace("USDT", "")
    # 优先使用该币种独立参数，否则回退全局
    sym_cfg = state.settings.get("symbol_settings", {}).get(symbol, s)
    price = state.market_prices.get(sym_short) or state.market_prices.get(symbol)
    if not price or price <= 0:
        return

    # 提前取冷却秒数（止损/止盈广播文案需要用）
    cooldown = s.get("cooldown_secs", COOLDOWN_SECS)

    # 日亏损熔断（使用已计算的daily_pnl，比余额差更准确）
    max_loss = s.get("max_daily_loss_usd", 50)
    if state.perf.get("daily_pnl", 0) < -max_loss:
        logger.warning(f"⛔ 日亏损熔断 daily_pnl={state.perf['daily_pnl']:.2f} < -{max_loss}，停止交易")
        state.auto_trading = False
        asyncio.create_task(broadcast("trading_status", {"active": False}))
        asyncio.create_task(broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"⛔ 日亏损熔断！今日亏损 ${abs(state.perf['daily_pnl']):.2f} 已超限额 ${max_loss}，自动停止"}))
        return

    # ── 止损/止盈/移动止损（优先级最高）──
    exit_reason = pos_tracker.should_exit(symbol, price)
    if exit_reason:
        logger.info(f"🔔 {exit_reason} {symbol} @ {price:.4f}")
        await cancel_all_orders(symbol)
        result = await close_position(symbol)
        tracker_sz = pos_tracker.entries.get(symbol, {}).get("sz", 0)
        _log_trade(symbol, "CLOSE", price, tracker_sz, exit_reason, 1.0, result)  # 先log再clear，盈亏计算依赖entries
        pos_tracker.clear(symbol)
        _close_cooldown[symbol] = time.time()  # 记录平仓时间，冷却开始
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"🔔 {exit_reason} {symbol} @ {price:.4f} ⏳冷却{cooldown}s"})
        return

    # ── 信号生成（先compute取scores，再由generate过滤）──
    raw_side, raw_conf, scores = signal_engine.compute(kline_cache.get(symbol, []), sym_short)
    side, confidence, block_reason = signal_engine.generate(sym_cfg, sym_short, symbol=symbol)

    existing = next((p for p in state.positions if p["symbol"] == symbol), None)
    # pos_tracker 本地记录比交易所API同步快，优先用它防止重复开仓
    has_position = existing is not None or symbol in pos_tracker.entries

    if has_position:
        # 持仓中只检查反向信号，其余静默
        # existing 可能为 None（API未同步），从 pos_tracker 取方向
        tracker_entry = pos_tracker.entries.get(symbol)
        pos_side_src = existing["side"] if existing else (tracker_entry.get("side") if tracker_entry else None)
        if pos_side_src and side != "HOLD":
            pos_side = pos_side_src if pos_side_src in ("BUY","SELL") else ("BUY" if pos_side_src=="LONG" else "SELL")
            is_reverse = (pos_side == "BUY" and side == "SELL") or \
                         (pos_side == "SELL" and side == "BUY")
            if is_reverse and confidence >= sym_cfg.get("min_confidence", s.get("min_confidence", 0.70)):
                logger.info(f"↩️ {symbol} 反向平仓 {pos_side}→{side} conf={confidence:.3f}")
                await cancel_all_orders(symbol)
                result = await close_position(symbol)
                _log_trade(symbol, "CLOSE", price, (existing["size"] if existing else (tracker_entry.get("sz",0) if tracker_entry else 0)), "reverse_signal", confidence, result)
                pos_tracker.clear(symbol)
                _close_cooldown[symbol] = time.time()
                await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                    "text": f"↩️ {symbol} 反向平仓 {pos_side} @ {price:.4f} ⏳冷却{cooldown}s"})
        return  # 持仓中不开新仓，静默

    # ── 无持仓：广播信号（节流 1s）──
    now = time.time()
    if now - _last_broadcast.get(symbol, 0) > 1.0:
        _last_broadcast[symbol] = now
        await broadcast("signal_update", {
            "symbol": symbol, "side": raw_side, "confidence": raw_conf,
            "fired": side != "HOLD",
            "current_side": side, "current_conf": confidence,
            "block_reason": block_reason,
            "scores": scores,
            "has_position": False,
        })

    if side == "HOLD":
        return  # 无信号

    # ── enable_long / enable_short 开关 ──
    if side == "BUY" and not s.get("enable_long", True):
        return
    if side == "SELL" and not s.get("enable_short", True):
        return

    # ── 冷却期检查（防止平仓后立即反复横跳）──
    last_close = _close_cooldown.get(symbol, 0)
    if time.time() - last_close < cooldown:
        remaining = int(cooldown - (time.time() - last_close))
        # 每15秒最多提示一次（防止日志洪泛）
        last_cd_log = _close_cooldown.get(f"{symbol}_log", 0)
        if time.time() - last_cd_log >= 15:
            _close_cooldown[f"{symbol}_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⏳ {symbol} 冷却中，还需 {remaining}s"})
        return

    # ── 全局仓位上限检查 ──
    open_count = len([p for p in state.positions if abs(p.get("size", 0)) > 1e-9])
    max_pos = s.get("max_open_positions", 3)
    if open_count >= max_pos:
        # 每60秒提示一次（节流，key带symbol区分每个币种）
        last_log = _close_cooldown.get(f"{symbol}_maxpos_log", 0)
        if time.time() - last_log >= 60:
            _close_cooldown[f"{symbol}_maxpos_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⚠️ 已达最大持仓数 {open_count}/{max_pos}，{symbol} 跳过"})
        return

    # ── 资金检查 ──
    trade_usd = sym_cfg.get("trade_size_usd", s.get("trade_size_usd", 10))
    leverage  = sym_cfg.get("leverage",       s.get("leverage", 2))
    if state.available < 1.0:
        # 余额极低，停止自动交易
        state.auto_trading = False
        await broadcast("trading_status", {"active": False})
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"⛔ 可用余额 ${state.available:.2f} 极低，自动停止交易！"})
        return
    if state.available < trade_usd * 0.5:
        last_log = _close_cooldown.get(f"{symbol}_bal_log", 0)
        if time.time() - last_log >= 60:
            _close_cooldown[f"{symbol}_bal_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"💸 {symbol} 可用余额不足（需 ${trade_usd*0.5:.1f}，现 ${state.available:.2f}），跳过开仓"})
        return

    sz = float(_fmt_qty(symbol, (trade_usd * leverage) / price))
    if sz <= 0:
        return

    # ── 市价开仓（加锁：双重检查 + 下单 + tracker记录 原子化）──
    async with _get_sym_lock(symbol):
        # 加锁后再次检查持仓（防止并发等待锁期间已被其他协程开仓）
        if symbol in pos_tracker.entries:
            return
        if any(p["symbol"] == symbol for p in state.positions):
            return

        result = await place_order(symbol, side, "MARKET", sz)
        if _order_ok(result):
            sl_pct_use = sym_cfg.get("stop_loss_pct",  s.get("stop_loss_pct",  0.012))
            tp_pct_use = sym_cfg.get("take_profit_pct", s.get("take_profit_pct", 0.028))
            # 记录开仓时市场上下文（用于自动迭代分析）
            klines_now = kline_cache.get(symbol, [])
            highs_now  = [float(k[2]) for k in klines_now]
            lows_now   = [float(k[3]) for k in klines_now]
            closes_now = [float(k[4]) for k in klines_now]
            adx_now = signal_engine._adx(highs_now, lows_now, closes_now) if len(klines_now) >= 30 else 0
            atr_now = signal_engine._atr(highs_now, lows_now, closes_now) if len(klines_now) >= 15 else 0
            open_ctx = {
                "adx": round(adx_now, 1),
                "atr": round(atr_now, 6),
                "confidence": round(confidence, 3),
                "sl_pct": sl_pct_use,
                "tp_pct": tp_pct_use,
                "open_ts": time.time(),
            }
            pos_tracker.record(symbol, side, price, sz,
                sl_pct_use, tp_pct_use,
                trailing=sym_cfg.get("trailing_stop", s.get("trailing_stop", True)),
                open_ctx=open_ctx,
                atr=atr_now)
            logger.info(f"✅ 开仓 {side} {symbol} sz={sz} px≈{price:.4f} conf={confidence:.3f}")
            _log_trade(symbol, side, price, sz, "crypto_hft", confidence, result, False, open_ctx=open_ctx)
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"✅ {side} {symbol} sz={sz} @ {price:.4f} conf={confidence*100:.1f}%"})
        else:
            # 解析失败原因
            err_msg = ""
            if result:
                err_msg = result.get("msg", result.get("message", str(result)))[:80]
            else:
                err_msg = "无响应/网络超时"
            logger.warning(f"⚠️ 下单失败 {symbol}: {err_msg}")
            # 失败订单不写历史记录，避免日志被刷爆
            # 余额不足时停止自动交易
            if "Margin is insufficient" in err_msg or "insufficient" in err_msg.lower():
                state.auto_trading = False
                await broadcast("trading_status", {"active": False})
                await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                    "text": f"⛔ {symbol} 保证金不足，自动停止交易！请充值后手动重启。"})
            else:
                await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                    "text": f"❌ {symbol} 下单失败({side}): {err_msg}"})


# ─────────────────────────────────────────────
# 自动迭代优化引擎
# ─────────────────────────────────────────────
MIN_TRADES_FOR_OPT = 20   # 至少20笔平仓才触发优化

# 参数搜索空间
PARAM_GRID = {
    "min_confidence": [0.58, 0.60, 0.62, 0.65, 0.68, 0.70],
    "stop_loss_pct":  [0.008, 0.010, 0.012, 0.015, 0.018],
    "take_profit_pct":[0.020, 0.025, 0.028, 0.032, 0.038],
}

# 当前优化结果（内存）
_opt_result: Dict = {}

def _run_param_backtest(closed_trades: list) -> Dict:
    """
    用历史平仓记录做参数网格搜索。
    对每组参数：过滤出"当时参数下会触发"的交易，计算胜率和期望值。
    返回最优参数组合。
    """
    if len(closed_trades) < MIN_TRADES_FOR_OPT:
        return {}

    best_score = -999.0
    best_params = {}
    results = []

    for conf_thresh in PARAM_GRID["min_confidence"]:
        for sl in PARAM_GRID["stop_loss_pct"]:
            for tp in PARAM_GRID["take_profit_pct"]:
                # 盈亏比校验：使用最宽松的阈值(0.8)，不同模式的实际阈值在generate()里控制
                rr = (tp - 0.001) / (sl + 0.001)
                if rr < 0.3:  # 使用最宽松的激进模式阈值，不同模式在generate()里控制
                    continue
                # 过滤：只统计开仓置信度 >= conf_thresh 的交易
                filtered = [t for t in closed_trades
                            if float(t.get("open_conf", 0)) >= conf_thresh]
                if len(filtered) < 10:
                    continue
                wins   = sum(1 for t in filtered if float(t.get("pnl", 0)) > 0)
                losses = sum(1 for t in filtered if float(t.get("pnl", 0)) < 0)
                total  = wins + losses
                if total == 0:
                    continue
                win_rate = wins / total
                avg_pnl  = sum(float(t.get("pnl", 0)) for t in filtered) / total
                # 综合评分 = 期望值 × 胜率加权（期望盈利 > 0 且胜率 > 50% 才有价值）
                score = avg_pnl * win_rate * 100
                results.append({
                    "min_confidence": conf_thresh,
                    "stop_loss_pct":  sl,
                    "take_profit_pct": tp,
                    "win_rate": round(win_rate * 100, 1),
                    "avg_pnl":  round(avg_pnl, 4),
                    "score":    round(score, 4),
                    "sample":   total,
                    "rr":       round(rr, 2),
                })
                if score > best_score:
                    best_score = score
                    best_params = {
                        "min_confidence": conf_thresh,
                        "stop_loss_pct":  sl,
                        "take_profit_pct": tp,
                    }

    # 按评分排序，取前5供前端展示
    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "best": best_params,
        "top5": results[:5],
        "total_closed": len(closed_trades),
        "optimized_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

async def run_auto_optimize(force=False) -> Dict:
    """异步触发优化，结果存入_opt_result并广播到前端"""
    global _opt_result
    closed = [t for t in state.trade_logs if t.get("side") == "CLOSE" and t.get("open_conf", 0) > 0]
    if not force and len(closed) < MIN_TRADES_FOR_OPT:
        return {"error": f"需要至少{MIN_TRADES_FOR_OPT}笔平仓数据，当前{len(closed)}笔"}

    logger.info(f"🔬 开始参数网格优化，共{len(closed)}笔平仓数据...")
    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
        "text": f"🔬 自动优化启动，分析{len(closed)}笔历史平仓..."})

    # CPU密集型，在线程池跑
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _run_param_backtest, closed)
    _opt_result = result

    if result.get("best"):
        best = result["best"]
        top  = result["top5"][0] if result.get("top5") else {}
        logger.info(f"✅ 优化完成：conf={best['min_confidence']} sl={best['stop_loss_pct']} tp={best['take_profit_pct']} 胜率={top.get('win_rate')}%")
        await broadcast("opt_result", result)
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"✅ 优化完成：最优 conf={best['min_confidence']} sl={best['stop_loss_pct']*100:.1f}% tp={best['take_profit_pct']*100:.1f}% 预期胜率={top.get('win_rate')}%"})
    return result

async def hft_trading_loop():
    logger.info("🚀 HFT 多币种交易循环启动")
    await broadcast("trading_status", {"active": True})
    # K线刷新统一管理
    if not state.kline_task or state.kline_task.done():
        state.kline_task = asyncio.create_task(kline_refresh_loop())

    # 启动前预拉所有启用币种的K线并按独立设置设置杠杆
    active_syms_init = state.settings.get("active_symbols", [state.settings.get("symbol","BTCUSDT")])
    sym_settings_map = state.settings.get("symbol_settings", {})
    for sym in active_syms_init:
        lev = sym_settings_map.get(sym, {}).get("leverage", state.settings.get("leverage", 2))
        await set_leverage(sym, lev)
        asyncio.create_task(refresh_klines(sym, "1m", 200))

    while state.auto_trading:
        try:
            s        = state.settings
            interval = s.get("hft_interval_ms", 500) / 1000.0

            # 获取启用的币种列表（active_symbols 或 fallback 到 symbol）
            active_syms = s.get("active_symbols", [s.get("symbol", "BTCUSDT")])
            if not active_syms:
                active_syms = [s.get("symbol", "BTCUSDT")]

            # 并发处理所有启用币种
            await asyncio.gather(
                *[_process_symbol(sym, s) for sym in active_syms],
                return_exceptions=True
            )

        except Exception as e:
            logger.error(f"HFT 主循环异常: {e}\n{traceback.format_exc()}")

        await asyncio.sleep(interval)

    await broadcast("trading_status", {"active": False})
    logger.info("⏹️ HFT 循环已停止")

# ─────────────────────────────────────────────
# FastAPI 路由
# ─────────────────────────────────────────────
@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "exchange": "AsterDex",
        "logged_in": state.logged_in,
        "auto_trading": state.auto_trading,
        "ts": datetime.now().isoformat(),
    }

class LoginRequest(BaseModel):
    user: str        # 主账户钉包地址
    signer: str      # API 钉包地址
    private_key: str # API 钉包私钥

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    user   = req.user.strip()
    signer = req.signer.strip()
    pk     = req.private_key.strip()
    if not user or not signer or not pk:
        return JSONResponse({"ok": False, "error": "三个字段均不能为空"}, status_code=400)

    # 验证私钥格式
    try:
        acct = Account.from_key(pk)
        if acct.address.lower() != signer.lower():
            return JSONResponse({"ok": False, "error": f"私钥不对应 API 钉包地址\n私钥对应: {acct.address}\n您填入: {signer}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"私钥格式错误: {e}"}, status_code=400)

    state.user        = user
    state.signer      = signer
    # ✅ Use secure key storage instead of state.private_key
    set_global_key(pk)

    bal, bal_raw = await aster_get_raw("/fapi/v3/balance", auth=True)
    if bal is None:
        # ✅ Clear secure key on login failure
        clear_global_key()
        state.user = state.signer = ""
        return JSONResponse({"ok": False, "error": f"登录失败 (AsterDex原始响应): {bal_raw}"}, status_code=401)

    usdt_balance = 0.0
    usdt_avail   = 0.0
    if isinstance(bal, list):
        for b in bal:
            if b.get("asset") == "USDT":
                usdt_balance = float(b.get("balance", 0))
                usdt_avail   = float(b.get("availableBalance", 0))
                break

    # ⚠️ 安全说明：私钥仅保存在进程内存中，不落盘、不记录日志、不广播到前端。
    # 最佳实践是由前端（MetaMask等钱包）完成签名，后端只接收signature，
    # 但当前架构需要后端代为签名（无钱包环境），请确保后端仅运行在本地可信环境。
    state.logged_in = True
    state.balance   = usdt_balance
    state.available = usdt_avail

    # 同步持仓
    await sync_account()
    # 重建本地仓位跟踪（防止重启后止损/止盈失效）
    rebuild_tracker_from_positions()

    # 启动后台任务
    if state.account_sync_task is None or state.account_sync_task.done():
        state.account_sync_task = asyncio.create_task(account_sync_loop())
    if state.ws_task is None or state.ws_task.done():
        state.ws_task = asyncio.create_task(market_ws_loop())

    # 登录后立即拉取所有启用币种的K线并启动刷新循环
    active_syms_login = state.settings.get("active_symbols",
                         [state.settings.get("symbol", "BTCUSDT")])
    for _sym in active_syms_login:
        asyncio.create_task(refresh_klines(_sym, "1m", 200))
    if not hasattr(state, 'kline_task') or state.kline_task is None or state.kline_task.done():
        state.kline_task = asyncio.create_task(kline_refresh_loop())

    # 广播
    await broadcast("account_update", {
        "logged_in":   True,
        "balance":     state.balance,
        "available":   state.available,
        "positions":   state.positions,
        "open_orders": state.open_orders,
    })

    return {
        "ok":      True,
        "balance": state.balance,
        "available": state.available,
        "wallet":  state.user,
        "message": f"登录成功 ✅ | 主钉包: {state.user[:8]}...",
    }

@app.post("/api/auth/logout")
async def logout():
    state.logged_in   = False
    state.user        = ""
    state.signer      = ""
    # ✅ Use secure key clearing
    clear_global_key()
    state.auto_trading = False
    # 清空账户数据，防止页面显示旧数据
    state.balance     = 0.0
    state.available   = 0.0
    state.positions   = []
    state.open_orders = []
    for task in [state.trading_task, state.account_sync_task, state.ws_task, state.kline_task]:
        if task and not task.done():
            task.cancel()
    state.trading_task = state.account_sync_task = state.ws_task = state.kline_task = None
    kline_cache.clear()
    await broadcast("account_update", {"logged_in": False, "balance": 0, "available": 0, "positions": [], "open_orders": []})
    logger.info("✅ User logged out successfully")
    return {"ok": True}

class TestOrderRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"

@app.post("/api/trading/test_order")
async def test_order(req: TestOrderRequest):
    if not state.logged_in:
        return JSONResponse({"ok": False, "error": "请先登录"}, status_code=401)
    symbol = req.symbol.upper()
    side   = req.side.upper()
    # 获取最新价格
    price_data = await aster_get(f"/fapi/v3/ticker/price", {"symbol": symbol})
    if not price_data:
        return JSONResponse({"ok": False, "error": "获取价格失败"}, status_code=500)
    cur_price = float(price_data.get("price", 0))
    if cur_price <= 0:
        return JSONResponse({"ok": False, "error": "价格无效"}, status_code=500)
    # 按币种设定最小手数（满足交易所最小名义价值要求）
    min_qty_map = {
        "BTCUSDT": 0.001, "ETHUSDT": 0.01, "SOLUSDT": 0.1,
        "ARBUSDT": 1.0,   "AVAXUSDT": 0.1, "BNBUSDT": 0.01,
    }
    qty = min_qty_map.get(symbol, round(6.0 / cur_price, 3)) or 0.001
    result = await aster_post("/fapi/v3/order", {
        "symbol":      symbol,
        "side":        side,
        "type":        "MARKET",
        "quantity":    str(qty),
        "reduceOnly":  "false",
    })
    if result is None:
        return JSONResponse({"ok": False, "error": "下单请求失败"}, status_code=500)
    if isinstance(result, dict) and result.get("code") and result["code"] < 0:
        return JSONResponse({"ok": False, "error": f"交易所拒绝: {result.get('msg','')}"}, status_code=400)
    logger.info(f"测试下单 {side} {symbol} qty={qty} -> {result}")
    return {"ok": True, "result": result, "qty": qty, "price": cur_price}

@app.post("/api/trading/start")
async def start_trading():
    if not state.logged_in:
        return JSONResponse({"ok": False, "error": "请先登录"}, status_code=401)
    if state.auto_trading:
        return {"ok": True, "message": "已在运行"}
    state.auto_trading = True
    state.trading_task = asyncio.create_task(hft_trading_loop())
    return {
        "ok": True,
        "message": "HFT 已启动",
        "symbol": state.settings.get("symbol", "BTCUSDT"),
    }

@app.post("/api/trading/stop")
async def stop_trading():
    state.auto_trading = False
    if state.trading_task and not state.trading_task.done():
        state.trading_task.cancel()
    return {"ok": True, "message": "已停止"}

@app.get("/api/trading/status")
async def trading_status():
    t = state.perf["total_trades"]; w = state.perf["wins"]
    return {
        "ok": True,
        "logged_in":    state.logged_in,
        "auto_trading": state.auto_trading,
        "balance":      state.balance,
        "available":    state.available,
        "positions":    state.positions,
        "performance":  {**state.perf, "win_rate": round(w/t*100,1) if t else 0},
        "settings":     state.settings,
        "market_prices": {k:v for k,v in list(state.market_prices.items())[:10]},
    }

@app.post("/api/settings")
async def save_settings(body: dict):
    old_symbol  = state.settings.get("symbol", "BTCUSDT")
    old_actives = set(state.settings.get("active_symbols", [old_symbol]))
    state.settings.update(body)
    new_symbol  = state.settings.get("symbol", "BTCUSDT")
    new_actives = set(state.settings.get("active_symbols", [new_symbol]))
    # symbol 变更时立即刷新新币种K线
    if new_symbol != old_symbol:
        asyncio.create_task(refresh_klines(new_symbol, "1m", 200))
        logger.info(f"📊 symbol切换 {old_symbol}→{new_symbol}，重新拉取K线")
    # active_symbols 新增的币种也要拉K线 + 重启WS以订阅行情
    added = new_actives - old_actives
    if added:
        for sym in added:
            asyncio.create_task(refresh_klines(sym, "1m", 200))
            logger.info(f"📊 新增币种 {sym}，拉取K线")
        # 重启行情WS以订阅新币种（取消旧task，订阅新币种）
        if state.ws_task and not state.ws_task.done():
            state.ws_task.cancel()
        state.ws_task = asyncio.create_task(market_ws_loop())
        logger.info(f"📡 active_symbols新增{added}，重启行情WS")
    # 设置变更后持久化到文件（防止重启后丢失）
    _save_history(state.trade_logs, state.perf)
    return {"ok": True}

@app.get("/api/trading/logs")
async def get_logs(limit: int = 500):
    return {"logs": state.trade_logs[:limit], "performance": state.perf}

def _compute_indicators(symbol: str) -> dict:
    """通用指标计算，支持任意symbol"""
    s         = state.settings
    # 每个币种可独立配置参数（存在 symbol_settings 里），否则用全局
    sym_cfg   = state.settings.get("symbol_settings", {}).get(symbol, s)
    sym_short = symbol.replace("USDT", "")
    klines    = kline_cache.get(symbol, [])
    min_conf  = sym_cfg.get("min_confidence", s.get("min_confidence", 0.70))
    n = len(klines)

    if n < 30:
        return {"ready": False, "bars": n, "symbol": symbol,
                "message": f"等待K线数据 ({n}/65)..."}

    closes  = [float(k[4]) for k in klines]
    highs   = [float(k[2]) for k in klines]
    lows    = [float(k[3]) for k in klines]
    volumes = [float(k[5]) for k in klines]

    rsi         = signal_engine._rsi(closes)
    m, sv, hist = signal_engine._macd(closes)
    ef          = signal_engine._ema(closes, 5)
    es_         = signal_engine._ema(closes, 20)
    el          = signal_engine._ema(closes, 60)
    st          = signal_engine._supertrend(highs, lows, closes)
    obi         = signal_engine._obi(sym_short)
    adx         = signal_engine._adx(highs, lows, closes)

    raw_side, raw_conf, scores = signal_engine.compute(klines, sym_short)
    side, conf, block_reason = signal_engine.generate(sym_cfg, sym_short, symbol=symbol)

    sl_pct       = sym_cfg.get("stop_loss_pct", s.get("stop_loss_pct", 0.012))
    tp_pct       = sym_cfg.get("take_profit_pct", s.get("take_profit_pct", 0.028))
    rr           = round((tp_pct - 0.001) / (sl_pct + 0.001), 2)
    market_state = scores.get("_market", "ranging" if adx < 10 else "trending")
    has_position = any(p["symbol"] == symbol for p in state.positions)

    return {
        "ready":        n >= 65,
        "bars":         n,
        "symbol":       symbol,
        "rsi":          round(rsi, 2),
        "macd":         {"macd": round(m,6), "signal": round(sv,6), "hist": round(hist,6)},
        "ema":          {"fast": round(ef,2), "slow": round(es_,2), "long": round(el,2)},
        "ob_imbalance": round(obi, 4),
        "supertrend":   st,
        "adx":          round(adx, 1),
        "market_state": market_state,
        "reward_risk":  rr,
        "strategy":     "crypto_hft",
        "min_confidence": min_conf,
        "has_position": has_position,
        "scores":       {k: (round(v,3) if isinstance(v,(int,float)) else v)
                         for k,v in scores.items()
                         if not k.startswith("_") or k in ("_bull","_bear","_adx","_market")},
        "raw_signal":     {"side": raw_side, "confidence": round(raw_conf, 3)},
        "current_signal": {"side": side, "confidence": conf, "block_reason": block_reason},
    }

@app.get("/api/trading/indicators")
async def get_indicators(symbol: str = ""):
    sym = symbol or state.settings.get("symbol", "BTCUSDT")
    return _compute_indicators(sym)

@app.get("/api/trading/indicators_all")
async def get_indicators_all():
    """批量返回所有启用币种的指标"""
    syms = state.settings.get("active_symbols", [state.settings.get("symbol","BTCUSDT")])
    return {"symbols": {sym: _compute_indicators(sym) for sym in syms}}

@app.post("/api/settings/symbol")
async def save_symbol_settings(body: dict):
    """保存单个币种的独立策略参数"""
    symbol = body.get("symbol")
    params = body.get("params", {})
    if not symbol:
        return {"ok": False, "error": "缺少symbol"}
    ss = state.settings.setdefault("symbol_settings", {})
    ss[symbol] = params
    _save_history(state.trade_logs, state.perf)
    return {"ok": True, "symbol": symbol, "params": ss[symbol]}

@app.post("/api/trading/close_position")
async def api_close_position(body: dict):
    symbol = body.get("symbol", state.settings.get("symbol","BTCUSDT"))
    price  = state.market_prices.get(symbol.replace("USDT","")) or state.market_prices.get(symbol) or 0
    await cancel_all_orders(symbol)  # 先撤单再平仓
    result = await close_position(symbol)
    if result:
        tracker_sz = pos_tracker.entries.get(symbol, {}).get("sz", 0)
        _log_trade(symbol, "CLOSE", price, tracker_sz, "CLOSE", 1.0, result)  # 记录手动平仓
        pos_tracker.clear(symbol)
    return {"ok": bool(result), "result": result}

@app.post("/api/optimize/run")
async def api_run_optimize():
    """手动触发参数优化"""
    result = await run_auto_optimize(force=True)
    return {"ok": True, **result}

@app.get("/api/optimize/result")
async def api_get_opt_result():
    """获取最新优化结果"""
    closed_count = len([t for t in state.trade_logs if t.get("side") == "CLOSE"])
    return {
        "ok": True,
        "result": _opt_result,
        "closed_trades": closed_count,
        "min_required": MIN_TRADES_FOR_OPT,
        "ready": closed_count >= MIN_TRADES_FOR_OPT,
    }

@app.post("/api/optimize/apply")
async def api_apply_opt():
    """将最优参数自动应用到当前策略设置"""
    if not _opt_result.get("best"):
        return {"ok": False, "error": "暂无优化结果，请先运行优化"}
    best = _opt_result["best"]
    state.settings.update(best)
    _save_history(state.trade_logs, state.perf)
    await broadcast("settings_updated", state.settings)
    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
        "text": f"🔁 已自动应用最优参数：conf={best['min_confidence']} sl={best['stop_loss_pct']*100:.1f}% tp={best['take_profit_pct']*100:.1f}%"})
    return {"ok": True, "applied": best}

@app.get("/api/strategy/recommendations")
async def api_strategy_recommendations():
    """根据当前交易数据提供策略优化建议"""
    closed = [t for t in state.trade_logs if t.get("side") == "CLOSE" and t.get("pnl") is not None]

    if len(closed) < 10:
        return {
            "ok": True,
            "recommendations": [],
            "reason": f"数据不足，需要至少10笔平仓交易，当前{len(closed)}笔"
        }

    recommendations = []

    # 分析胜率
    win_rate = state.perf.get("win_rate", 0)
    if win_rate < 45:
        recommendations.append({
            "level": "critical",
            "issue": "胜率过低",
            "current": f"{win_rate}%",
            "suggestion": "降低min_confidence阈值（如从0.70→0.65），或增加止盈目标",
            "impact": "可能提高交易频率，但需谨慎风险"
        })
    elif win_rate > 60:
        recommendations.append({
            "level": "opportunity",
            "issue": "胜率高，可以积极",
            "current": f"{win_rate}%",
            "suggestion": "提高杠杆或增加单笔下单金额来放大收益",
            "impact": "增加收益，但同时增加风险"
        })

    # 分析平均持仓时间
    avg_hold_secs = sum(t.get("hold_secs", 0) for t in closed) / len(closed) if closed else 0
    if avg_hold_secs < 60:
        recommendations.append({
            "level": "info",
            "issue": "非常短线策略",
            "current": f"平均{avg_hold_secs:.0f}秒",
            "suggestion": "这是HFT特征，确保交易所手续费支持，考虑降低最小下单金额",
            "impact": "高频率交易，需关注手续费成本"
        })

    # 分析平均单笔盈亏
    total_pnl = sum(t.get("pnl", 0) for t in closed)
    avg_pnl = total_pnl / len(closed) if closed else 0
    if avg_pnl < 0.5 and avg_pnl > 0:
        recommendations.append({
            "level": "warning",
            "issue": "平均单笔盈利过小",
            "current": f"${avg_pnl:.2f}/笔",
            "suggestion": "增加take_profit_pct目标，或降低信号过滤阈值",
            "impact": "追求更大的每笔收益"
        })

    # 分析最大回撤
    pnl_series = [t.get("pnl", 0) for t in closed]
    if pnl_series:
        cumsum = []
        cum = 0
        for p in pnl_series:
            cum += p
            cumsum.append(cum)
        max_drawdown = min(0, min(cumsum) - max(0, min(cumsum)))  # 计算最大回撤
        if max_drawdown < -100:
            recommendations.append({
                "level": "critical",
                "issue": "最大回撤过大",
                "current": f"${max_drawdown:.2f}",
                "suggestion": "增加stop_loss_pct，或降低max_open_positions",
                "impact": "提高风险控制，可能牺牲一些盈利"
            })

    return {
        "ok": True,
        "closed_trades": len(closed),
        "recommendations": recommendations,
        "current_settings": {
            "min_confidence": state.settings.get("min_confidence", 0.70),
            "stop_loss_pct": state.settings.get("stop_loss_pct", 0.012),
            "take_profit_pct": state.settings.get("take_profit_pct", 0.028),
            "leverage": state.settings.get("leverage", 2),
            "hft_mode": state.settings.get("hft_mode", "balanced"),
        }
    }

@app.post("/api/trading/cancel_orders")
async def api_cancel_orders(body: dict):
    symbol = body.get("symbol", state.settings.get("symbol","BTCUSDT"))
    result = await cancel_all_orders(symbol)
    return {"ok": True, "result": result}

@app.get("/api/market/orderbook")
async def get_orderbook(symbol: str = "BTCUSDT"):
    sym = symbol.replace("USDT","")
    return {"ok": True, "symbol": symbol, **state.orderbooks.get(sym, {"bids":[],"asks":[]})}

@app.get("/api/diagnostics")
async def api_diagnostics():
    """系统诊断接口 - 检查所有关键组件"""
    return {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "backend": {
            "logged_in": state.logged_in,
            "user": state.user[:8] + "..." if state.user else "❌ Not logged in",
            "signer": state.signer[:8] + "..." if state.signer else "❌",
            "auth_ready": "✅" if get_global_key() else "❌",
        },
        "account": {
            "balance": state.balance,
            "available": state.available,
            "positions": len(state.positions),
            "open_orders": len(state.open_orders),
        },
        "trading": {
            "auto_trading": state.auto_trading,
            "active_symbols": state.settings.get("active_symbols", ["BTCUSDT"]),
            "leverage": state.settings.get("leverage", 2),
            "trade_size_usd": state.settings.get("trade_size_usd", 10),
        },
        "market": {
            "prices_count": len(state.market_prices),
            "orderbooks_count": len(state.orderbooks),
            "klines_symbols": list(kline_cache.keys()),
        },
        "performance": state.perf,
        "recent_logs": state.trade_logs[:5],
    }

# ─────────────────────────────────────────────
# WebSocket 前端推送
# ─────────────────────────────────────────────
@app.websocket("/ws/frontend")
async def ws_frontend(ws: WebSocket):
    await ws.accept()
    ws_clients.add(ws)
    try:
        await ws.send_text(json.dumps({"type": "init", "data": {
            "logged_in":   state.logged_in,
            "balance":     state.balance,
            "available":   state.available,
            "positions":   state.positions,
            "open_orders": state.open_orders,
            "auto_trading": state.auto_trading,
        }}))
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "pong"}))
            except WebSocketDisconnect:
                break
    except Exception:
        pass
    finally:
        ws_clients.discard(ws)

# ─────────────────────────────────────────────
# 启动
# ─────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🚀 AsterDex HFT Trader 启动")
    logger.info("   API: https://fapi.asterdex.com")
    logger.info("   前端: http://localhost:3000")
    logger.info("   后端: http://localhost:8000")
    logger.info("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000,
                log_level="warning",          # 关闭 access log 刷屏
                access_log=False)             # 不输出每条请求日志
