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
import math
import os
import threading
import time
import traceback
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiohttp
import uvicorn
from eth_account import Account
from eth_account.messages import encode_typed_data
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse as StarletteJSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load .env FIRST before any module that reads os.getenv at import time
from dotenv import load_dotenv
load_dotenv()

# Security imports
from security import secure_key_context, set_global_key, get_global_key, clear_global_key, validate_private_key_format
from config import Config
import alerting

# Multi-user auth
from db import (
    init_db, register_user, activate_user, login_user,
    get_user_config, save_user_config, generate_license_codes,
    list_licenses, list_users, ensure_admin, log_login,
    save_trade_log, load_trade_logs, load_user_settings, save_user_settings,
    admin_change_password,
)
from auth import create_token, get_current_user, get_admin_user, revoke_token, get_client_ip


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("asterdex_trader")

_START_TIME = time.time()  # 记录启动时间

# ── 私钥加解密（Fernet，密钥由 SECRET_KEY + user_id 派生）──────────────
def _fernet_for_user(user_id: int):
    """为每个用户派生独立的 Fernet 加密密钥"""
    import base64, hashlib
    from cryptography.fernet import Fernet
    secret = os.getenv("SECRET_KEY", "changeme-please-set-secret-key")
    material = f"{secret}:uid:{user_id}".encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(material).digest())
    return Fernet(key)

def encrypt_pk(user_id: int, pk: str) -> str:
    return _fernet_for_user(user_id).encrypt(pk.encode()).decode()

def decrypt_pk(user_id: int, encrypted: str) -> str:
    return _fernet_for_user(user_id).decrypt(encrypted.encode()).decode()

# ── API 路径随机前缀（防扫描）──────────────────────────
# 优先读环境变量；未设置则生成一个并写入 .env，重启后保持一致
def _sync_prefix_to_env(p: str):
    """把 API_PREFIX 和 REACT_APP_API_PREFIX 都写入 .env（保证前后端同步）"""
    env_file = Path(__file__).parent / ".env"
    try:
        lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
        lines = [l for l in lines if not l.startswith("API_PREFIX=") and not l.startswith("REACT_APP_API_PREFIX=")]
        lines.append(f"API_PREFIX={p}")
        lines.append(f"REACT_APP_API_PREFIX={p}")
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass

def _load_or_gen_prefix() -> str:
    p = os.environ.get("API_PREFIX", "").strip().strip("/")
    if p:
        # 确保 REACT_APP_API_PREFIX 也存在（首次升级时可能没有）
        _sync_prefix_to_env(p)
        return p
    import secrets as _sec
    p = _sec.token_hex(8)          # 16位随机十六进制
    _sync_prefix_to_env(p)
    os.environ["API_PREFIX"] = p
    os.environ["REACT_APP_API_PREFIX"] = p
    return p

_PREFIX = _load_or_gen_prefix()

def R(path: str) -> str:
    """把 /api/xxx 或 /ws/xxx 替换为带随机前缀的路径"""
    return f"/{_PREFIX}{path}"

print(f"[AsterDex] API prefix: /{_PREFIX}   (e.g. http://localhost:8000/{_PREFIX}/api/health)", flush=True)

class _WSLogHandler(logging.Handler):
    """将后端日志实时推送到前端 WebSocket liveLog（携带level用于前端着色）"""
    _LEVEL_MAP = {"DEBUG": "debug", "INFO": "info", "WARNING": "warn", "ERROR": "error", "CRITICAL": "error"}
    def emit(self, record: logging.LogRecord):
        try:
            msg   = record.getMessage()
            ts    = datetime.now().strftime("%H:%M:%S")
            level = self._LEVEL_MAP.get(record.levelname, "info")
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(broadcast("log", {"ts": ts, "text": msg, "level": level}))
            )
        except Exception:
            pass

# 系统日志不再全局广播给所有用户（避免跨用户日志泄漏）
# 用户级别日志通过 broadcast("log", ..., user_id=uid) 单独推送
# _ws_log_handler = _WSLogHandler()
# logger.addHandler(_ws_log_handler)

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
    """保存交易记录、绩效、symbol_settings和全局settings到文件（原子写，防止写到一半崩溃损坏文件）"""
    try:
        clean_logs = [l for l in logs if l.get("status") != "failed"][:500]
        # 超过1MB时自动备份旧文件
        if HISTORY_FILE.exists() and HISTORY_FILE.stat().st_size > 1_000_000:
            backup = HISTORY_FILE.with_name(
                f"trade_history_bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            HISTORY_FILE.rename(backup)
            logger.info(f"📦 历史文件已备份到 {backup.name}")
            # 自动清理旧备份，只保留最近5个，防止长期运行磁盘堆满
            bak_files = sorted(HISTORY_FILE.parent.glob("trade_history_bak_*.json"))
            for old_bak in bak_files[:-5]:
                try:
                    old_bak.unlink()
                    logger.debug(f"🗑️ 清理旧备份: {old_bak.name}")
                except Exception:
                    pass
        # daily_history 只保留最近180天，防止无限累积
        dh = perf.get("daily_history", {})
        if len(dh) > 180:
            keep_keys = sorted(dh.keys())[-180:]
            perf["daily_history"] = {k: dh[k] for k in keep_keys}
        global_cfg = {}  # legacy file no longer used for per-user storage
        content = json.dumps({
            "logs": clean_logs,
            "perf": perf,
            "symbol_settings": {},
            "global_settings": global_cfg,
        }, ensure_ascii=False, indent=2)
        # 原子写：先写临时文件，再替换，防止写到一半崩溃导致文件损坏
        tmp_file = HISTORY_FILE.with_suffix(".tmp")
        tmp_file.write_text(content, encoding="utf-8")
        tmp_file.replace(HISTORY_FILE)
    except Exception as e:
        logger.warning(f"保存历史失败: {e}")

async def _save_history_async(logs: list, perf: dict):
    """异步版本：在线程池执行，不阻塞事件循环"""
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, _save_history, logs, perf)

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

from contextlib import asynccontextmanager

@asynccontextmanager
async def _lifespan(app):
    try:
        logger.info("[AsterDex] lifespan startup begin")
    except Exception:
        pass
    # ── startup ──
    logger.debug("Telegram通知为每用户独立配置，登录时各自启动")
    logger.info("[AsterDex] lifespan startup complete, yielding")
    try:
        yield
    except Exception as _le:
        logger.error(f"[AsterDex] lifespan yield exception: {_le}", exc_info=True)
        raise
    finally:
        logger.warning("[AsterDex] lifespan shutdown")

# ── slowapi 限速器 ──
limiter = Limiter(key_func=get_remote_address, default_limits=[])

app = FastAPI(title="AsterDex HFT Trader", version="6.0.0", lifespan=_lifespan)
app.state.limiter = limiter

_BUILD_DIR = Path(__file__).parent / "build"
if _BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_BUILD_DIR / "static")), name="static")

    @app.get("/xiangbei/admin", include_in_schema=False)
    async def serve_admin():
        return FileResponse(str(_BUILD_DIR / "admin.html"))

    @app.get("/xiangbei", include_in_schema=False)
    async def serve_index_alias():
        return FileResponse(str(_BUILD_DIR / "index.html"))

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(_BUILD_DIR / "index.html"))

@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return StarletteJSONResponse(
        {"ok": False, "msg": "请求过于频繁，请稍后再试"},
        status_code=429
    )

# ── HTTPS 强制重定向（生产环境：设置 FORCE_HTTPS=1）──
if os.environ.get("FORCE_HTTPS", "0") == "1":
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=Config.CORS_METHODS,
    allow_headers=Config.CORS_HEADERS,
)

# ── WS 路径守卫：在 HTTP 层面拦截无前缀 WS 升级请求 ──
# Python 3.14 + wsproto 处理 WS 握手拒绝时有 bug，
# 用 middleware 在协议升级前直接返回 HTTP 403 避免崩溃
class _WSGuardMiddleware:
    """纯 ASGI 中间件：在协议升级前拦截无前缀 WS 请求，返回 HTTP 403"""
    def __init__(self, app=None, **kwargs):
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            path = scope.get("path", "")
            if "//" in path:
                path = path.replace("//", "/")
                scope = dict(scope)
                scope["path"] = path
                # 不修改 raw_path：Python 3.14 + wsproto 处理 raw_path 时有 segfault
        await self._app(scope, receive, send)

app.add_middleware(_WSGuardMiddleware)

# ─────────────────────────────────────────────
# 全局状态
# ─────────────────────────────────────────────
class TradingState:
    def __init__(self):
        self.logged_in: bool = False
        self.user: str = ""        # 主账户钉包地址
        self.signer: str = ""      # API 钉包地址钥

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
        self.price_poll_task: Optional[asyncio.Task] = None
        self.user_data_task: Optional[asyncio.Task] = None
        # 交易设置
        self.settings: Dict = {
            "strategy": "multi",
            "symbol": "BTCUSDT",
            "leverage": 5,
            "trade_size_usd": 10,
            "min_confidence": 0.70,
            "stop_loss_pct": 0.005,
            "take_profit_pct": 0.008,
            "enable_long": True,
            "enable_short": True,
            "max_open_positions": 3,
            "max_daily_loss_usd": 50,
            "cancel_on_reverse": True,
            "hft_interval_ms": 500,
            "hft_mode": "balanced",  # conservative/balanced/aggressive/turbo
            "max_position_usd": 200,
            "cooldown_secs": 60,
            "size_mode": "fixed",    # "fixed"=固定USD / "pct"=余额百分比
            "size_pct": 20,          # size_mode=pct时：每笔下单占可用余额的百分比
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
        # 交易记录（从数据库按用户加载，见 get_user_state）
        self.trade_logs: List[Dict] = []

state = TradingState()

# ─────────────────────────────────────────────
# 每个币种独立的开仓锁，防止并发 gather 里两个协程同时通过持仓检查后重复开仓
# asyncio.Lock 是协程安全的（同一事件循环内），无需 threading.Lock
_sym_locks: Dict[int, Dict[str, asyncio.Lock]] = {}  # uid -> {symbol -> Lock}
# 全局持仓计数锁：防止多币种并发 gather 同时通过 open_count 检查，穿越 max_open_positions 限制
_open_pos_lock: Dict[int, asyncio.Lock] = {}  # uid -> Lock

def _get_sym_lock(symbol: str, uid: int = 0) -> asyncio.Lock:
    if uid not in _sym_locks:
        _sym_locks[uid] = {}
    if symbol not in _sym_locks[uid]:
        _sym_locks[uid][symbol] = asyncio.Lock()
    return _sym_locks[uid][symbol]

def _get_open_pos_lock(uid: int = 0) -> asyncio.Lock:
    if uid not in _open_pos_lock:
        _open_pos_lock[uid] = asyncio.Lock()
    return _open_pos_lock[uid]

# set_leverage 缓存：{uid: {symbol: (leverage, last_set_time)}}，30s内相同杠杆不重复调用
_leverage_cache: Dict[int, Dict[str, tuple]] = {}

def _get_leverage_cache(uid: int = 0) -> Dict[str, tuple]:
    if uid not in _leverage_cache:
        _leverage_cache[uid] = {}
    return _leverage_cache[uid]

# ─────────────────────────────────────────────
# WebSocket 广播
# ─────────────────────────────────────────────
# ws_clients: user_id -> Set[WebSocket]（0 = 未认证/公共）
ws_clients: Dict[int, Set[WebSocket]] = {}

async def broadcast(msg_type: str, data: Any, user_id: int = 0):
    """向指定用户的所有WS连接推送消息；user_id=0 表示广播给所有连接"""
    if not ws_clients:
        return
    msg = json.dumps({"type": msg_type, "data": data})
    targets = ws_clients.get(user_id, set()) if user_id else set().union(*ws_clients.values())
    dead = set()
    for ws in targets.copy():
        try:
            await ws.send_text(msg)
        except Exception:
            dead.add(ws)
    if dead:
        remaining = targets - dead
        if user_id:
            ws_clients[user_id] = remaining
        else:
            for uid, sockets in ws_clients.items():
                ws_clients[uid] = sockets - dead

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

def _sign_v3(query_string: str, user_id: int = 0) -> str:
    """EIP-712 结构化签名，对不含signature的query string签名，返回hex"""
    from security import get_user_key
    td = json.loads(json.dumps(EIP712_DOMAIN))  # deep copy
    td["message"]["msg"] = query_string
    msg = encode_typed_data(full_message=td)
    private_key = get_user_key(user_id) if user_id else get_global_key()
    if not private_key:
        raise ValueError("Private key not available - please login first")
    signed = Account.sign_message(msg, private_key=private_key)
    return signed.signature.hex()

def _build_signed_url(base_url: str, params: dict, user_id: int = 0) -> str:
    st = get_user_state(user_id) if user_id else state
    p = dict(params)
    p["user"]   = st.user
    p["signer"] = st.signer
    p["nonce"]  = str(_nonce())
    qs  = urllib.parse.urlencode(p)
    sig = "0x" + _sign_v3(qs, user_id)
    return base_url + "?" + qs + "&signature=" + sig

def _build_signed_body(params: dict, user_id: int = 0) -> dict:
    st = get_user_state(user_id) if user_id else state
    p = dict(params)
    p["user"]   = st.user
    p["signer"] = st.signer
    p["nonce"]  = str(_nonce())
    qs  = urllib.parse.urlencode(p)
    p["signature"] = "0x" + _sign_v3(qs, user_id)
    return p

_HEADERS = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "PythonApp/1.0"}

# ── HTTP熔断器：记录连续失败次数，过多时暂停请求（按 uid 隔离，防止一用户故障影响他人）──
_circuit: Dict[int, Dict[str, Dict]] = {}  # uid -> {path_prefix: {fails, open_until}}
_CIRCUIT_THRESHOLD = 5    # 连续失败5次打开熔断器
_CIRCUIT_TIMEOUT   = 30   # 熔断开启后30s自动半开

def _circuit_ok(key: str, uid: int = 0) -> bool:
    c = _circuit.get(uid, {}).get(key)
    if not c:
        return True
    if c["open_until"] and time.time() < c["open_until"]:
        return False  # 熔断中
    return True

def _circuit_record(key: str, success: bool, uid: int = 0):
    if uid not in _circuit:
        _circuit[uid] = {}
    c = _circuit[uid].setdefault(key, {"fails": 0, "open_until": 0})
    if success:
        c["fails"] = 0
        c["open_until"] = 0
    else:
        c["fails"] += 1
        if c["fails"] >= _CIRCUIT_THRESHOLD:
            c["open_until"] = time.time() + _CIRCUIT_TIMEOUT
            logger.warning(f"⚡ 熔断器开启 uid={uid}: {key}，{_CIRCUIT_TIMEOUT}s后自动重试")

async def fetch_klines_for_backtest(symbol: str, interval: str, limit: int) -> Optional[list]:
    """回测专用K线拉取：绕开熔断器，直连公开接口，超时15s"""
    url = f"{ASTER_BASE}/fapi/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    s = _get_session()
    for attempt in range(3):
        try:
            async with s.get(url, params=params, headers=_HEADERS,
                             timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    data = await r.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data
                    logger.warning(f"回测K线返回非列表: {str(data)[:200]}")
                    return None
                txt = await r.text()
                logger.warning(f"回测K线 {symbol} {interval} -> HTTP {r.status}: {txt[:200]}")
                if r.status in (429, 503) and attempt < 2:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return None
        except asyncio.TimeoutError:
            logger.warning(f"回测K线超时({attempt+1}/3) {symbol}")
            if attempt < 2:
                await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"回测K线异常({attempt+1}/3) {symbol}: {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None

async def aster_get(path: str, params: dict = None, auth: bool = False, user_id: int = 0) -> Optional[dict]:
    from security import get_user_key
    base_url = ASTER_BASE + path
    s = _get_session()
    key = path.split("?")[0]
    if not _circuit_ok(key, user_id):
        logger.warning(f"⚡ {path} 熔断中(uid={user_id})，跳过请求")
        return None
    for attempt in range(3):
        try:
            if auth:
                _key = get_user_key(user_id) if user_id else get_global_key()
                if not _key:
                    logger.warning("❌ Authentication required but no valid key")
                    return None
                signed_url = _build_signed_url(base_url, dict(params or {}), user_id)
                async with s.get(signed_url, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                    if r.status == 200:
                        _circuit_record(key, True, user_id)
                        return await r.json()
                    if r.status in (429, 503):
                        wait = 2 ** attempt
                        logger.warning(f"⏳ GET {path} 限流({r.status})，{wait}s后重试({attempt+1}/3)")
                        await asyncio.sleep(wait)
                        continue
                    txt = await r.text()
                    logger.error(f"GET {path} -> {r.status}: {txt[:400]}")
                    _circuit_record(key, False, user_id)
                    return None
            else:
                async with s.get(base_url, params=params, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    if r.status == 200:
                        _circuit_record(key, True, user_id)
                        return await r.json()
                    if r.status in (429, 503):
                        wait = 2 ** attempt
                        logger.warning(f"⏳ GET {path} 限流({r.status})，{wait}s后重试({attempt+1}/3)")
                        await asyncio.sleep(wait)
                        continue
                    txt = await r.text()
                    logger.error(f"GET {path} -> {r.status}: {txt[:400]}")
                    _circuit_record(key, False, user_id)
                    return None
        except Exception as e:
            logger.error(f"GET {path} error: {e}")
            _circuit_record(key, False, user_id)
            if attempt < 2:
                await asyncio.sleep(2 ** attempt)
    return None

async def aster_get_raw(path: str, params: dict = None, auth: bool = False, user_id: int = 0):
    """Returns (json_or_None, raw_text) — used for login diagnostics."""
    from security import get_user_key
    base_url = ASTER_BASE + path
    s = _get_session()
    try:
        if auth:
            _key = get_user_key(user_id) if user_id else get_global_key()
            if not _key:
                return None, "not logged in"
            signed_url = _build_signed_url(base_url, dict(params or {}), user_id)
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

async def aster_post(path: str, params: dict = None, user_id: int = 0) -> Optional[dict]:
    from security import get_user_key
    _key = get_user_key(user_id) if user_id else get_global_key()
    if not _key:
        logger.warning("❌ POST request attempted without valid authentication key")
        return None
    url = ASTER_BASE + path
    s = _get_session()
    key = path.split("?")[0]
    if not _circuit_ok(key, user_id):
        logger.warning(f"⚡ {path} 熔断中(uid={user_id})，跳过POST")
        return None
    is_order = "/fapi/v3/order" in path
    max_attempts = 2 if is_order else 3
    for attempt in range(max_attempts):
        body = _build_signed_body(dict(params or {}), user_id)
        try:
            if is_order:
                logger.info(f"📤 POST {path} symbol={body.get('symbol')}, side={body.get('side')}, qty={body.get('quantity')}")
            async with s.post(url, data=body, headers=_HEADERS, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                if r.status in (429, 503):
                    if is_order:
                        logger.error(f"❌ 下单接口限流({r.status})，不重试（防重复下单）")
                        _circuit_record(key, False, user_id)
                        return None
                    wait = 2 ** attempt
                    logger.warning(f"⏳ POST {path} 限流({r.status})，{wait}s后重试({attempt+1}/{max_attempts})")
                    await asyncio.sleep(wait)
                    continue
                result = await r.json()
                if is_order:
                    if r.status not in (200, 201):
                        logger.error(f"❌ POST {path} 返回 {r.status}: {result}")
                    else:
                        logger.info(f"✅ POST {path} 成功: orderId={result.get('orderId','N/A')}, status={result.get('status','N/A')}")
                _circuit_record(key, r.status in (200, 201), user_id)
                return result
        except Exception as e:
            logger.error(f"POST {path} error: {e}")
            _circuit_record(key, False, user_id)
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)
    return None

async def aster_delete(path: str, params: dict = None, user_id: int = 0) -> Optional[dict]:
    from security import get_user_key
    _key = get_user_key(user_id) if user_id else get_global_key()
    if not _key:
        logger.warning("❌ DELETE request attempted without valid authentication key")
        return None
    base_url   = ASTER_BASE + path
    signed_url = _build_signed_url(base_url, dict(params or {}), user_id)
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
async def sync_account(uid: int = 0):
    """并发拉取余额 + 持仓 + 挂单，缩短同步延迟"""
    bal, pos, orders = await asyncio.gather(
        aster_get("/fapi/v3/balance", auth=True, user_id=uid),
        aster_get("/fapi/v3/positionRisk", auth=True, user_id=uid),
        aster_get("/fapi/v3/openOrders", auth=True, user_id=uid),
        return_exceptions=True,
    )
    # 兼容 gather 返回 Exception 的情况
    if isinstance(bal, Exception): bal = None
    if isinstance(pos, Exception): pos = None
    if isinstance(orders, Exception): orders = None
    # 余额
    st = get_user_state(uid) if uid else state
    if bal is None:
        logger.warning("⚠️ sync_account: balance API返回None（网络超时/熔断/未登录）")
    elif isinstance(bal, list):
        found = False
        for b in bal:
            if b.get("asset") == "USDT":
                new_bal = float(b.get("balance", 0))
                new_avail = float(b.get("availableBalance", 0))
                if abs(new_bal - st.balance) > 0.01:
                    logger.info(f"💰 余额变化: {st.balance:.4f}→{new_bal:.4f} (可用:{new_avail:.2f})")
                st.balance = new_bal
                st.available = new_avail
                found = True
                break
        if not found:
            logger.warning(f"⚠️ sync_account: balance list中无USDT资产，共{len(bal)}条: {[b.get('asset') for b in bal[:5]]}")
    elif isinstance(bal, dict):
        if bal.get("asset") == "USDT":
            st.balance = float(bal.get("balance", 0))
            st.available = float(bal.get("availableBalance", 0))
        elif "balance" in bal:
            st.balance = float(bal.get("balance", st.balance))
            st.available = float(bal.get("availableBalance", bal.get("available", st.available)))
        else:
            logger.warning(f"⚠️ sync_account: balance返回dict但无法解析: {str(bal)[:200]}")
    else:
        logger.warning(f"⚠️ sync_account: balance返回未知类型 {type(bal)}: {str(bal)[:200]}")

    # 持仓（API失败时不清空，保留上次数据；成功时含空列表都更新）
    if isinstance(pos, list):
        active = []
        for p in pos:
            sz  = float(p.get("positionAmt", 0))
            sym = p.get("symbol", "")
            if abs(sz) > 1e-9:
                side = "LONG" if sz > 0 else "SHORT"
                lev  = max(int(p.get("leverage", 1)), 1)
                ep   = float(p.get("entryPrice", 0))
                tracker = get_pos_tracker(uid if uid else 0).entries.get(sym, {})
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
                    "entry_usd":      round(abs(sz) * ep / lev, 2),
                    "open_time":      tracker.get("open_time", ""),
                })
        st.positions = active

    # 挂单（API失败或返回空列表时都强制清空，避免旧数据残留）
    if isinstance(orders, list):
        st.open_orders = [
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
    else:
        st.open_orders = []  # API失败时清空，不保留旧数据

_guardian_closing: Dict[int, set] = {}  # uid -> set of symbols

def _get_guardian_closing(uid: int = 0) -> set:
    if uid not in _guardian_closing:
        _guardian_closing[uid] = set()
    return _guardian_closing[uid]

async def _guardian_close(symbol: str, price: float, exit_reason: str, uid: int = 0):
    """HFT停止时的止损/止盈守护平仓"""
    _gc = _get_guardian_closing(uid)
    _pt = get_pos_tracker(uid)
    if symbol in _gc:
        return
    _gc.add(symbol)
    _gst = get_user_state(uid) if uid else state
    _te = dict(_pt.entries.get(symbol, {}))  # 平仓前快照，防止await期间被清除
    _cd = _get_close_cooldown(uid)
    _cd[symbol] = time.time()  # 立即预写冷却，防止并发窗口期漏掉
    # Fix-A: 守护平仓（止损/止盈）冷却固定≥60s，与反向平仓一致，防止止损后立即反手再套
    _guardian_cooldown = max(_gst.settings.get("cooldown_secs", 60), 60)
    try:
        await cancel_all_orders(symbol, user_id=uid)
        result = await close_position(symbol, user_id=uid)
        tracker_sz = _te.get("sz", 0)
        # tracker_sz为0时从持仓数量补全，确保notional/fee记录准确
        if not tracker_sz or tracker_sz <= 0:
            _pos_fb = next((p for p in _gst.positions if p["symbol"] == symbol), None)
            if _pos_fb:
                tracker_sz = _pos_fb.get("size", 0)
        _log_trade(symbol, "CLOSE", price, tracker_sz, exit_reason, 1.0, result, open_ctx=_te.get("open_ctx"), uid=uid)
        _pnl = 0.0
        if _te:
            _ep = _te.get("entry", price)
            _sz = float(_te.get("sz", tracker_sz) or tracker_sz)
            _gross = (price - _ep) * _sz if _te.get("side") == "BUY" else (_ep - price) * _sz
            _pnl = round(_gross - _sz * _ep * FEE_RATE - _sz * price * FEE_RATE, 4)
        _pt.clear(symbol)
        _cd[symbol] = time.time()  # 平仓成功后再次确认冷却起点
        _cd[f"{symbol}_reverse_cd"] = time.time()  # 同时写反向冷却标记，确保 _effective_cooldown 生效
        pnl_str = f"+${_pnl:.4f}" if _pnl >= 0 else f"-${abs(_pnl):.4f}"
        logger.info(f"🛡️ 守护平仓完成 {exit_reason} {symbol} @ {price:.4f} 盈亏:{pnl_str} ⏳冷却{_guardian_cooldown}s")
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"🛡️ {exit_reason} {symbol} @ {price:.4f} 盈亏:{pnl_str} ⏳冷却{_guardian_cooldown}s"}, user_id=uid)
        asyncio.create_task(alerting.alert_position_closed(symbol, _pnl, exit_reason, uid=uid))
    except Exception as e:
        logger.error(f"守护平仓失败 {symbol}: {e}")
    finally:
        _gc.discard(symbol)

async def account_sync_loop(uid: int = 0):
    logger.info("🔄 账户同步循环启动")
    _st = get_user_state(uid) if uid else state
    while _st.logged_in:
        try:
            await sync_account(uid)
            await broadcast("account_update", {
                "logged_in":   True,
                "balance":     _st.balance,
                "available":   _st.available,
                "positions":   _st.positions,
                "open_orders": _st.open_orders,
            }, user_id=uid)
            _t = _st.perf["total_trades"]; _w = _st.perf["wins"]
            await broadcast("performance", {**_st.perf, "win_rate": round(_w/_t*100,1) if _t else 0}, user_id=uid)
            _pt_sync = get_pos_tracker(uid)
            for _p in list(_st.positions):
                _psym = _p["symbol"]
                if _psym not in _pt_sync.entries:
                    rebuild_tracker_from_positions(_st, uid=uid)
                    break
            _exchange_syms = {p["symbol"] for p in _st.positions}
            _gc_set = _get_guardian_closing(uid)  # Fix-C: 跳过正在守护平仓中的symbol
            for _ghost in list(_pt_sync.entries.keys()):
                if _ghost not in _exchange_syms and _ghost not in _gc_set:
                    logger.debug(f"🧹 自动清除幽灵tracker: {_ghost}（交易所已无持仓）")
                    _pt_sync.clear(_ghost)
            for _p in list(_st.positions):
                _sym = _p["symbol"]
                _price = _st.market_prices.get(_sym.replace("USDT","")) or _st.market_prices.get(_sym)
                if not _price:
                    try:
                        _td = await aster_get("/fapi/v3/ticker/price", {"symbol": _sym})
                        if _td and _td.get("price"):
                            _price = float(_td["price"])
                            _sk = _sym.replace("USDT", "")
                            _st.market_prices[_sk] = _price
                            _st.market_prices[_sym] = _price
                    except Exception:
                        pass
                if not _price:
                    continue
                _exit = _pt_sync.should_exit(_sym, _price)
                _gc_sync = _get_guardian_closing(uid)
                if _exit and _sym not in _gc_sync:
                    logger.info(f"🛡️ 守护止损兖底 {_exit} {_sym} @ {_price:.4f}")
                    asyncio.create_task(_guardian_close(_sym, _price, _exit, uid=uid))

            syms = _st.settings.get("active_symbols", [_st.settings.get("symbol","BTCUSDT")])
            for sym in syms:
                try:
                    ind = _compute_indicators(sym, _st)
                    ind["has_position"] = any(p["symbol"]==sym for p in _st.positions)
                    await broadcast("indicators_push", ind, user_id=uid)
                except Exception:
                    pass
            if _st.market_prices:
                await broadcast("prices", {k: v for k, v in _st.market_prices.items() if not k.endswith("USDT")}, user_id=uid)
            _now = time.time()
            _cd_sync = _get_close_cooldown(uid)
            if _now - _cd_sync.get("__last_gc__", 0) > 3600:
                _cd_sync["__last_gc__"] = _now
                _expired = [k for k, v in list(_cd_sync.items()) if k != "__last_gc__" and _now - v > 7200]
                for k in _expired:
                    _cd_sync.pop(k, None)
                if _expired:
                    logger.debug(f"🧹 清理过期冷却key {len(_expired)} 个")
                _lev_cache_uid = _get_leverage_cache(uid)
                _lev_expired = [k for k, (lev, ts) in list(_lev_cache_uid.items()) if _now - ts > 300]
                for k in _lev_expired:
                    _lev_cache_uid.pop(k, None)

            _today = datetime.now().strftime("%Y-%m-%d")
            if _st.perf.get("_last_gc_date", "") != _today:
                _st.perf["_last_gc_date"] = _today
                if len(_st.trade_logs) > 500:
                    _st.trade_logs = _st.trade_logs[:500]
                _dh = _st.perf.get("daily_history", {})
                if len(_dh) > 180:
                    _keep = sorted(_dh.keys())[-180:]
                    _st.perf["daily_history"] = {k: _dh[k] for k in _keep}
                _active = _st.settings.get("active_symbols", [_st.settings.get("symbol", "BTCUSDT")])
                _active_shorts = {_s.replace("USDT", "") for _s in _active}
                _active_full   = set(_active)
                _stale_px = [k for k in list(_st.market_prices.keys())
                             if k not in _active_shorts and k not in _active_full]
                for k in _stale_px:
                    _st.market_prices.pop(k, None)
                logger.info(f"♻️ 每日GC完成：logs={len(_st.trade_logs)} daily_history={len(_st.perf.get('daily_history',{}))}天 清理行情key {len(_stale_px)} 个")
        except Exception as e:
            logger.error(f"账户同步失败: {e}")
        await asyncio.sleep(1.5)

# ─────────────────────────────────────────────
# AsterDex 行情 WebSocket
# ─────────────────────────────────────────────
async def market_ws_loop(uid: int = 0):
    """订阅 AsterDex 行情 WS: aggTrade + depth"""
    try:
        import websockets as ws_lib
    except ImportError:
        logger.warning("websockets 未安装，使用 REST 轮询行情")
        await market_poll_loop(uid=uid)
        return

    while True:
        _st = get_user_state(uid) if uid else state
        active = _st.settings.get("active_symbols", ["BTCUSDT","ETHUSDT","SOLUSDT"])
        syms = list({s.lower() for s in active})
        streams = (
            [f"{s}@bookTicker"    for s in syms] +  # 最优买卖价，价格变动立即触发
            [f"{s}@aggTrade"      for s in syms] +  # 成交价兜底
            [f"{s}@depth5@100ms"  for s in syms] +
            [f"{s}@kline_1m"      for s in syms]
        )
        url = f"{ASTER_WS}/stream?streams=" + "/".join(streams)
        try:
            logger.info(f"📡 连接行情 WS: {url[:80]}...")
            async with ws_lib.connect(url, ping_interval=20, ping_timeout=10) as ws:
                await broadcast("ws_status", {"connected": True}, user_id=uid)
                # WS连接成功后立即REST拉一次全部价格，避免等aggTrade
                for _sym in active:
                    try:
                        _d = await aster_get("/fapi/v3/ticker/price", {"symbol": _sym})
                        if _d and _d.get("price"):
                            _k = _sym.replace("USDT", "")
                            _st.market_prices[_k]   = float(_d["price"])
                            _st.market_prices[_sym] = float(_d["price"])
                    except Exception:
                        pass
                if _st.market_prices:
                    await broadcast("prices", {k: v for k, v in _st.market_prices.items() if not k.endswith("USDT")}, user_id=uid)
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

                        if etype == "bookTicker":
                            # 最优买卖价事件：bid/ask价格变化时立即触发，比aggTrade更快
                            sym_full = data.get("s", "")
                            sym = sym_full.replace("USDT", "")
                            # 用中间价作为当前价格
                            bid = float(data.get("b", 0) or 0)
                            ask = float(data.get("a", 0) or 0)
                            if bid > 0 and ask > 0:
                                px = round((bid + ask) / 2, 8)
                                _st.market_prices[sym] = px
                                _st.market_prices[sym_full] = px
                                await broadcast("prices", {k: v for k, v in _st.market_prices.items() if not k.endswith("USDT")}, user_id=uid)
                                # ── 毫秒级止损/止盈检查 ──
                                _exit_r = get_pos_tracker(uid).should_exit(sym_full, px)
                                _gc_ws = _get_guardian_closing(uid)
                                if _exit_r and sym_full not in _gc_ws:
                                    asyncio.create_task(_guardian_close(sym_full, px, _exit_r, uid=uid))

                        elif etype == "aggTrade":
                            sym_full_ag = data["s"]
                            sym = sym_full_ag.replace("USDT", "")
                            px = float(data["p"])
                            _st.market_prices[sym] = px
                            _st.market_prices[sym_full_ag] = px
                            await broadcast("prices", {k: v for k, v in _st.market_prices.items() if not k.endswith("USDT")}, user_id=uid)
                            # aggTrade只更新价格，止损/止盈检查由bookTicker负责（避免重复触发）

                        elif etype == "depthUpdate":
                            sym = data["s"].replace("USDT", "")
                            _st.orderbooks[sym] = {
                                "bids": data.get("b", [])[:10],
                                "asks": data.get("a", [])[:10],
                            }
                            if sym == _st.settings.get("symbol", "BTC").replace("USDT",""):
                                await broadcast("orderbook", _st.orderbooks[sym], user_id=uid)

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
                                changed = False
                                if last_t == k["t"]:
                                    cache[-1] = bar        # 更新当前未完成K线
                                    changed = True
                                elif k["t"] > last_t:
                                    cache.append(bar)      # 新K线开始
                                    cache = cache[-300:]   # 最多保留300根
                                    changed = True
                                kline_cache[sym] = cache
                                # K线更新后立即重算指标并推送（零延迟）
                                if changed:
                                    try:
                                        ind = _compute_indicators(sym, _st)
                                        ind["has_position"] = any(p["symbol"]==sym for p in _st.positions)
                                        await broadcast("indicators_push", ind, user_id=uid)
                                    except Exception:
                                        pass

                    except Exception as e:
                        logger.error(f"WS 消息解析: {e}")

        except Exception as e:
            logger.error(f"行情 WS 断开: {e}")
            await broadcast("ws_status", {"connected": False}, user_id=uid)
            await asyncio.sleep(5)

async def user_data_stream_loop(uid: int = 0):
    """用户数据流WS：监听账户余额/持仓/成交实时变化（比REST轮询更快）"""
    try:
        import websockets as ws_lib
    except ImportError:
        return
    _st = get_user_state(uid) if uid else state
    logger.info("👤 用户数据流WS启动")
    _last_listen_key = None
    while _st.logged_in:
        ka_task = None
        try:
            if _last_listen_key:
                try:
                    await aster_delete("/fapi/v3/listenKey", {"listenKey": _last_listen_key}, user_id=uid)
                except Exception:
                    pass
                _last_listen_key = None
            lk_resp = await aster_post("/fapi/v3/listenKey", {}, user_id=uid)
            if not lk_resp or not lk_resp.get("listenKey"):
                logger.warning("⚠️ 无法获取listenKey，用户数据流10s后重试")
                await asyncio.sleep(10)
                continue
            listen_key = lk_resp["listenKey"]
            _last_listen_key = listen_key
            url = f"{ASTER_WS}/ws/{listen_key}"
            logger.info(f"👤 连接用户数据流: {url[:60]}...")

            async def _keepalive(_lk=listen_key):
                while _st.logged_in:
                    await asyncio.sleep(20 * 60)
                    try:
                        await aster_post("/fapi/v3/listenKey", {"listenKey": _lk}, user_id=uid)
                    except Exception:
                        pass

            ka_task = asyncio.create_task(_keepalive())
            try:
                async with ws_lib.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    async for raw in ws:
                        try:
                            ev = json.loads(raw)
                            etype = ev.get("e", "")
                            if etype == "ACCOUNT_UPDATE":
                                await sync_account(uid)
                                await broadcast("account_update", {
                                    "logged_in": True,
                                    "balance":   _st.balance,
                                    "available": _st.available,
                                    "positions": _st.positions,
                                    "open_orders": _st.open_orders,
                                }, user_id=uid)
                                logger.info(f"👤 账户实时更新: 余额=${_st.balance:.2f}")
                            elif etype == "ORDER_TRADE_UPDATE":
                                order_status = ev.get("o", {}).get("X", "")
                                if order_status in ("FILLED", "PARTIALLY_FILLED"):
                                    await sync_account(uid)
                                    await broadcast("account_update", {
                                        "logged_in": True,
                                        "balance":   _st.balance,
                                        "available": _st.available,
                                        "positions": _st.positions,
                                        "open_orders": _st.open_orders,
                                    }, user_id=uid)
                        except Exception as e:
                            logger.error(f"用户数据流解析: {e}")
            finally:
                if ka_task and not ka_task.done():
                    ka_task.cancel()
        except Exception as e:
            logger.error(f"用户数据流WS断开: {e}")
            await asyncio.sleep(5)

async def market_poll_loop(uid: int = 0):
    """REST 并发轮询所有币种实时价格，与WS并行运行保证实时同步"""
    logger.info("📊 价格轮询loop启动（与WS并行）")
    while True:
        try:
            _st = get_user_state(uid) if uid else state
            active_syms = _st.settings.get("active_symbols", ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
            pos_syms = [p["symbol"] for p in _st.positions]
            all_syms = list(dict.fromkeys(active_syms + pos_syms))

            async def _fetch_price(sym):
                try:
                    data = await aster_get("/fapi/v3/ticker/price", {"symbol": sym})
                    if data and data.get("price"):
                        px = float(data["price"])
                        _st.market_prices[sym.replace("USDT", "")] = px
                        _st.market_prices[sym] = px
                except Exception:
                    pass

            await asyncio.gather(*[_fetch_price(_s) for _s in all_syms])
            await broadcast("prices", {k: v for k, v in _st.market_prices.items() if not k.endswith("USDT")}, user_id=uid)
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
    "DOGEUSDT": 0, "XRPUSDT": 1, "ADAUSDT": 0,
    "DOTUSDT": 1, "LTCUSDT": 3, "LINKUSDT": 2,
    "UNIUSDT": 2, "ATOMUSDT": 2, "NEARUSDT": 1,
    "APTUSDT": 2, "SUIUSDT": 1, "OPUSDT": 1,
    "INJUSDT": 2, "TIAUSDT": 1, "SEIUSDT": 0,
    "WIFUSDT": 0, "FETUSDT": 0, "RENDERUSDT": 1,
}
# 各币种最低名义价值(USDT)，由最小下单量×价格估算，用于下单前校验
# 规则：精度N位 → 最小单位=10^-N；最低名义=最小单位×参考价，向上取整留20%余量
MIN_NOTIONAL = {
    "BTCUSDT":  80.0,   # 0.001 BTC × $75000 = $75，留余量→80
    "ETHUSDT":   5.0,   # 0.001 ETH × $3500  = $3.5 → 5
    "SOLUSDT":  90.0,   # 1 SOL × $84        = $84  → 90
    "ARBUSDT":   1.0,   # 1 ARB × $0.55      = $0.55 → 1
    "AVAXUSDT":  5.0,   # 0.1 AVAX × $28     = $2.8  → 5
    "BNBUSDT":   8.0,   # 0.01 BNB × $600    = $6    → 8
    "DOGEUSDT":  1.0,   # 1 DOGE × $0.18     = $0.18 → 1
    "XRPUSDT":   1.0,   # 0.1 XRP × $0.5     = $0.05 → 1
    "ADAUSDT":   1.0,   # 1 ADA × $0.4       = $0.4  → 1
    "DOTUSDT":   1.0,   # 0.1 DOT × $6       = $0.6  → 1
    "LTCUSDT":   1.0,   # 0.001 LTC × $80    = $0.08 → 1
    "LINKUSDT":  1.0,   # 0.01 LINK × $13    = $0.13 → 1
    "UNIUSDT":   1.0,   # 0.01 UNI × $8      = $0.08 → 1
    "ATOMUSDT":  1.0,
    "NEARUSDT":  1.0,
    "APTUSDT":   1.0,
    "SUIUSDT":   1.0,
    "OPUSDT":    1.0,
    "INJUSDT":   1.0,
    "TIAUSDT":   1.0,
    "SEIUSDT":   1.0,
    "WIFUSDT":   1.0,
    "FETUSDT":   1.0,
    "RENDERUSDT":1.0,
}

def _fmt_qty(symbol: str, qty: float) -> str:
    prec = QTY_PRECISION.get(symbol.upper(), 3)
    return f"{qty:.{prec}f}"

async def place_order(symbol: str, side: str, order_type: str,
                      quantity: float, price: float = 0,
                      reduce_only: bool = False, user_id: int = 0) -> Optional[dict]:
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

    if quantity <= 0:
        logger.error(f"❌ 下单前检查: 手数无效 {symbol} qty={qty_str}")
        return {"code": -9998, "msg": f"Invalid quantity: {qty_str}"}
    _st = get_user_state(user_id) if user_id else state
    if _st.available < 1.0:
        logger.error(f"❌ 下单前检查: 余额不足 {symbol} available=${_st.available:.2f}")
        return {"code": -9997, "msg": f"Insufficient balance: ${_st.available:.2f}"}

    logger.info(f"📍 下单请求 {side} {symbol} qty={qty_str} px={price}")
    result = await aster_post("/fapi/v3/order", params, user_id=user_id)

    if result is None:
        logger.error(f"❌ 下单失败 {side} {symbol}: 无API响应")
        return {"code": -9996, "msg": "No API response (timeout/connection error)"}
    elif isinstance(result, dict):
        if result.get("code") and result["code"] < 0:
            logger.error(f"❌ 下单被拒 {side} {symbol}: {result.get('msg', 'unknown')}")
        elif result.get("orderId"):
            logger.info(f"✅ 下单成功 {side} {symbol} orderId={result.get('orderId')}")
        else:
            logger.warning(f"⚠️ 下单响应异常 {side} {symbol}: {result}")

    return result

async def cancel_order(symbol: str, order_id: int, user_id: int = 0) -> Optional[dict]:
    return await aster_delete("/fapi/v3/order", {"symbol": symbol, "orderId": order_id}, user_id=user_id)

async def cancel_all_orders(symbol: str, user_id: int = 0) -> Optional[dict]:
    return await aster_delete("/fapi/v3/allOpenOrders", {"symbol": symbol}, user_id=user_id)

async def close_position(symbol: str, user_id: int = 0) -> Optional[dict]:
    """市价平仓（优先用交易所持仓，API延迟时从 pos_tracker 补充，确保及时平仓）"""
    _st = get_user_state(user_id) if user_id else state
    pos = next((p for p in _st.positions if p["symbol"] == symbol), None)
    if pos:
        close_side = "SELL" if pos["side"] == "LONG" else "BUY"
        sz = pos["size"]
    else:
        # API未同步时从本地tracker取方向和size
        entry = get_pos_tracker(user_id).entries.get(symbol)
        if not entry:
            return None
        close_side = "SELL" if entry["side"] == "BUY" else "BUY"
        sz = entry.get("sz", 0)
        if sz <= 0:
            return None
        logger.warning(f"⚡ {symbol} close_position: API未同步，使用tracker补充平仓 side={close_side} sz={sz}")
    return await place_order(symbol, close_side, "MARKET", sz, reduce_only=True, user_id=user_id)

async def set_leverage(symbol: str, leverage: int, user_id: int = 0):
    _lev_cache = _get_leverage_cache(user_id)
    cached = _lev_cache.get(symbol)
    if cached and cached[0] == leverage and time.time() - cached[1] < 30:
        return  # 30s内相同杠杆无需重复设置
    await aster_post("/fapi/v3/leverage", {"symbol": symbol, "leverage": leverage}, user_id=user_id)
    _lev_cache[symbol] = (leverage, time.time())

# ─────────────────────────────────────────────
# K 线缓存（按 symbol 存储真实 OHLCV）
# ─────────────────────────────────────────────
kline_cache: Dict[str, List[list]] = {}   # symbol -> [[open_t,o,h,l,c,v,...], ...]

async def refresh_klines(symbol: str, interval: str = "1m", limit: int = 200, user_id: int = 0):
    """拉取真实K线并更新缓存"""
    _st = get_user_state(user_id) if user_id else state
    data = await aster_get("/fapi/v3/klines", {"symbol": symbol, "interval": interval, "limit": limit}, user_id=user_id)
    if data and isinstance(data, list):
        kline_cache[symbol] = data
        logger.debug(f"K线刷新 {symbol} {len(data)}根")
    return kline_cache.get(symbol, [])

async def kline_refresh_loop(uid: int = 0):
    """后台定时刷新所有启用币种的K线（每10秒）"""
    logger.info("📊 K线刷新循环启动")
    while True:
        try:
            _st = get_user_state(uid) if uid else state
            active = _st.settings.get("active_symbols",
                        [_st.settings.get("symbol", "BTCUSDT")])
            interval = _st.settings.get("kline_interval", "1m")
            # 全量刷新K线，但保留WS实时更新的最新一根（未完成K线）
            for sym in active:
                try:
                    data = await aster_get("/fapi/v3/klines", {"symbol": sym, "interval": interval, "limit": 200}, user_id=uid)
                    if data and isinstance(data, list):
                        existing = kline_cache.get(sym, [])
                        # 如果WS已更新最新一根（时间戳更新），保留WS版本
                        if existing and len(data) > 0:
                            ws_last_t = existing[-1][0] if isinstance(existing[-1][0], int) else int(existing[-1][0])
                            rest_last_t = data[-1][0] if isinstance(data[-1][0], int) else int(data[-1][0])
                            if ws_last_t == rest_last_t:
                                data[-1] = existing[-1]  # 保留WS实时最新K线数据
                        kline_cache[sym] = data
                except Exception as e:
                    logger.debug(f"K线刷新 {sym}: {e}")
        except Exception as e:
            logger.error(f"K线刷新失败: {e}")
        await asyncio.sleep(3)

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
        """Wilder 平滑 RSI（与TradingView一致）"""
        if len(closes) < n + 2: return 50.0
        d = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [max(x, 0) for x in d]
        losses = [max(-x, 0) for x in d]
        avg_gain = sum(gains[:n]) / n
        avg_loss = sum(losses[:n]) / n
        for i in range(n, len(gains)):
            avg_gain = (avg_gain * (n - 1) + gains[i]) / n
            avg_loss = (avg_loss * (n - 1) + losses[i]) / n
        if avg_loss < 1e-10: return 100.0
        rs = avg_gain / avg_loss
        return round(100 - 100 / (1 + rs), 2)

    def _macd(self, closes, fast=12, slow=26, sig=9):
        if len(closes) < slow + sig: return 0.0, 0.0, 0.0
        ef = self._ema_series(closes, fast)
        es = self._ema_series(closes, slow)
        # 对齐：ef比es多 (slow-fast) 个，取末尾 min(len) 个做差
        ml = min(len(ef), len(es))
        dif = [ef[-ml + i] - es[-ml + i] for i in range(ml)]
        sv  = self._ema_series(dif, sig)
        if not sv: return 0.0, 0.0, 0.0
        return dif[-1], sv[-1], dif[-1] - sv[-1]

    def _supertrend(self, highs, lows, closes, n=10, mult=3.0):
        """标准动态翻转 Supertrend（与TradingView一致）
        price > supertrend_line → 多头 up
        price < supertrend_line → 空头 down
        """
        if len(closes) < n + 2: return "neutral"
        trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
               for i in range(1, len(closes))]
        # ATR 序列（简单移动平均）
        atrs = []
        for i in range(len(trs)):
            if i < n - 1:
                atrs.append(None)
            else:
                atrs.append(sum(trs[i-n+1:i+1]) / n)
        # 计算上下轨和 Supertrend
        st_direction = 1  # 1=up(多头), -1=down(空头)
        prev_upper = prev_lower = prev_st = None
        for i in range(len(atrs)):
            if atrs[i] is None:
                continue
            # i+1 是对应当前K线的索引（trs[i] = TR of K线[i+1]）
            ci = i + 1  # 当前K线索引
            if ci >= len(closes): break
            hl2 = (highs[ci] + lows[ci]) / 2
            basic_upper = hl2 + mult * atrs[i]
            basic_lower = hl2 - mult * atrs[i]
            # 上轨只能下降、下轨只能上升（防止频繁翻转）
            if prev_upper is None:
                upper = basic_upper
                lower = basic_lower
            else:
                upper = basic_upper if basic_upper < prev_upper or closes[ci-1] > prev_upper else prev_upper
                lower = basic_lower if basic_lower > prev_lower or closes[ci-1] < prev_lower else prev_lower
            # 方向翻转逻辑：用当前K线收盘判断是否穿越轨道
            if prev_st is None:
                st_val = lower if st_direction == 1 else upper
            else:
                if st_direction == 1:
                    st_val = lower
                    if closes[ci] < st_val:
                        st_direction = -1
                        st_val = upper
                else:
                    st_val = upper
                    if closes[ci] > st_val:
                        st_direction = 1
                        st_val = lower
            prev_upper = upper
            prev_lower = lower
            prev_st    = st_val
        if   st_direction == 1:  return "up"
        elif st_direction == -1: return "down"
        return "neutral"

    def _vwap(self, highs, lows, closes, volumes, window=200):
        """用最近window根K线计算VWAP，避免历史数据过多导致偏离值失真"""
        h = highs[-window:]; l = lows[-window:]; c = closes[-window:]; v = volumes[-window:]
        typical = [(hi+lo+cl)/3 for hi,lo,cl in zip(h, l, c)]
        tv = sum(t*vol for t,vol in zip(typical, v))
        sv = sum(v)
        return tv / sv if sv > 0 else closes[-1]

    def _obi(self, sym_short: str, orderbooks: dict = None):
        ob = (orderbooks or {}).get(sym_short, {})
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
        if len(dx) < n: return round(sum(dx)/max(len(dx),1), 2)
        # 标准ADX：对DX序列再做一次Wilder平滑（与TradingView一致）
        adx_val = sum(dx[:n]) / n
        for x in dx[n:]: adx_val = (adx_val * (n - 1) + x) / n
        return round(adx_val, 2)

    def compute(self, klines: list, sym_short: str, orderbooks: dict = None) -> tuple:
        """返回 (side, confidence, scores_dict)"""
        if len(klines) < 65:
            return "HOLD", 0.0, {}

        closes  = [float(k[4]) for k in klines]
        highs   = [float(k[2]) for k in klines]
        lows    = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        price   = closes[-1]

        scores: Dict[str, float] = {}

        # ─── 市场状态预判断 ───
        adx = self._adx(highs, lows, closes)
        atr = self._atr(highs, lows, closes)
        atr_pct = atr / price
        scores["_adx"]     = round(adx, 2)
        scores["_atr_pct"] = round(atr_pct * 100, 4)
        scores["_market"]  = "trending" if adx >= 18 else "ranging"

        # RSI / VWAP / OBI 先算好，均值回归逻辑需要用
        rsi_pre  = self._rsi(closes)
        vwap_pre = self._vwap(highs, lows, closes, volumes)
        dev_pre  = (price - vwap_pre) / (vwap_pre + 1e-9)
        if   rsi_pre < 30: scores["rsi"] =  min(1.0, (30 - rsi_pre) / 30)
        elif rsi_pre > 70: scores["rsi"] = -min(1.0, (rsi_pre - 70) / 30)
        else:              scores["rsi"] =  0.0
        if   dev_pre < -0.003: scores["vwap"] =  min(1.0, -dev_pre / 0.01)
        elif dev_pre >  0.003: scores["vwap"] = max(-1.0, -dev_pre / 0.01)
        else:                  scores["vwap"] =  0.0
        scores["obi"] = max(-1.0, min(1.0, self._obi(sym_short, orderbooks)))

        # ADX < 10 极度震荡 → 继续计算ST/EMA/MACD指标，供均值回归逻辑使用

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

        # 4. RSI（已在上方预计算，此处复用）

        # 5. VWAP 偏离（已在上方预计算，此处复用）

        # 6. 订单簿不平衡 OBI（已在上方预计算，此处复用）

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
        """对外接口：返回 (side, conf, block_reason)
        - 止盈/止损优先用ATR动态计算（不固定死），用户手设值作为下限参考
        - aggressive/turbo模式最大限度放宽条件，让高频真正高频
        """
        if not symbol:
            symbol = s.get("symbol", sym_short + "USDT")
        klines   = kline_cache.get(symbol, [])
        min_conf = s.get("min_confidence", 0.65)
        sl_pct   = s.get("stop_loss_pct",  0.005)
        tp_pct   = s.get("take_profit_pct", 0.008)
        side, conf, scores = self.compute(klines, sym_short)

        mode = s.get("hft_mode", "balanced") or "balanced"
        if mode == "conservative":
            rr_thresh, ranging_disc, adx_min = 1.8, 0.6, 25
        elif mode == "aggressive":
            rr_thresh, ranging_disc, adx_min = 0.2, 1.0, 15
        elif mode == "turbo":
            rr_thresh, ranging_disc, adx_min = 0.15, 1.0, 12
        else:  # balanced
            rr_thresh, ranging_disc, adx_min = 1.0, 0.85, 20

        # 严格用配置值做盈亏比校验（与实际开仓止盈止损一致）
        dyn_tp = tp_pct
        dyn_sl = sl_pct

        adx_v = scores.get("_adx", 0)
        is_ranging = adx_v < adx_min

        if is_ranging:
            if mode in ("aggressive", "turbo"):
                # ── 均值回归模式：震荡改用RSI反向+VWAP回归 ──
                rsi_v  = scores.get("rsi", 0)
                vwap_v = scores.get("vwap", 0)
                obi_v  = scores.get("obi", 0)
                # MR权重：OBI提到0.5，RSI为0.3，VWAP为0.2（震荡市OBI订单面最直接）
                mr_score = rsi_v * 0.3 + vwap_v * 0.2 + obi_v * 0.5
                mr_conf  = round(abs(mr_score), 4)
                if mr_score > 0.04:
                    mr_side = "BUY"
                elif mr_score < -0.04:
                    mr_side = "SELL"
                else:
                    return "HOLD", 0.0, f"ADX{adx_v:.1f}震荡MR不足({mr_score:.2f})"
                # 均值回归置信要求：同时满足用户设定的min_confidence和MR独立下限
                # MR独立下限：turbo=0.20, aggressive=0.25（防止阈值过高永远过滤震荡行情）
                # Fix-D: MR置信不受用户min_confidence截断（MR分数最大~0.5，远低于趋势跟踪的0.65+）
                # 使用独立下限：turbo=0.10, aggressive=0.15
                mr_floor = 0.10 if mode == "turbo" else 0.15
                if mr_conf < mr_floor:
                    return "HOLD", 0.0, f"MR置信{mr_conf:.2f}<{mr_floor:.2f}"
                if mr_side == "BUY"  and not s.get("enable_long",  True): return "HOLD", mr_conf, "做多已禁用"
                if mr_side == "SELL" and not s.get("enable_short", True): return "HOLD", mr_conf, "做空已禁用"
                return mr_side, mr_conf, f"[MR] ADX{adx_v:.1f} MR={mr_score:.2f}"
            else:
                return "HOLD", 0.0, f"ADX{adx_v:.1f}<{adx_min}，震荡不开仓({mode})"

        # 弱趋势/ADX边界：_market==ranging时按模式打折置信度，降低震荡期误判
        if scores.get("_market") == "ranging":
            conf = round(conf * ranging_disc, 4)

        # 盈亏比校验（用动态止盈止损计算，更贴近真实市场）
        net_tp = dyn_tp - 2 * FEE_RATE
        net_sl = dyn_sl + 2 * FEE_RATE
        rr = round(net_tp / net_sl, 2) if net_sl > 0 else 0
        if rr < rr_thresh:
            return "HOLD", 0.0, f"盈亏比{rr}x<{rr_thresh}x(ATR动态tp={dyn_tp*100:.2f}% sl={dyn_sl*100:.2f}%)"

        if side == "HOLD":
            return "HOLD", conf, f"置信{round(conf*100)}%<{round(min_conf*100)}%"

        if side == "BUY"  and not s.get("enable_long",  True): return "HOLD", conf, "做多已禁用"
        if side == "SELL" and not s.get("enable_short", True): return "HOLD", conf, "做空已禁用"

        if conf < min_conf:
            return "HOLD", conf, f"置信{round(conf*100)}%<阈值{round(min_conf*100)}%"

        return side, conf, f"ATR_tp={dyn_tp*100:.2f}% sl={dyn_sl*100:.2f}%"

# 单例
signal_engine = CryptoHFTEngine()

# ─────────────────────────────────────────────
# 仓位跟踪（止损/止盈 + 移动止损）
# ─────────────────────────────────────────────
class PositionTracker:
    def __init__(self):
        self.entries: Dict[str, dict] = {}

    def record(self, symbol, side, entry, sz, sl_pct, tp_pct, trailing=True, open_ctx=None, atr=None):
        """严格按配置的sl_pct/tp_pct固定止损止盈，不做任何动态调整"""
        sl = entry*(1-sl_pct) if side=="BUY" else entry*(1+sl_pct)
        tp = entry*(1+tp_pct) if side=="BUY" else entry*(1-tp_pct)
        self.entries[symbol] = {
            "side": side, "entry": entry, "sz": sz,
            "sl": sl, "tp": tp, "sl_pct": sl_pct,
            "open_time": datetime.now().strftime("%H:%M:%S"),
            "open_ctx": open_ctx or {},
        }

    def should_exit(self, symbol, price):
        e = self.entries.get(symbol)
        if not e: return None
        # sl或tp为0说明记录不完整，跳过防止误触发
        if e["sl"] <= 0 or e["tp"] <= 0:
            return None
        if e["side"] == "BUY":
            if price <= e["sl"]: return "STOP_LOSS"
            if price >= e["tp"]: return "TAKE_PROFIT"
        else:  # SELL
            if price >= e["sl"]: return "STOP_LOSS"
            if price <= e["tp"]: return "TAKE_PROFIT"
        return None

    def clear(self, symbol): self.entries.pop(symbol, None)

_pos_trackers: Dict[int, PositionTracker] = {}  # uid -> PositionTracker

def get_pos_tracker(uid: int = 0) -> PositionTracker:
    if uid not in _pos_trackers:
        _pos_trackers[uid] = PositionTracker()
    return _pos_trackers[uid]

pos_tracker = get_pos_tracker(0)  # legacy alias for uid=0

def rebuild_tracker_from_positions(_st=None, uid: int = 0):
    """从交易所当前持仓重建 PositionTracker，防止重启后止损/止盈失效"""
    _st = _st or state
    _pt = get_pos_tracker(uid)
    s = _st.settings
    sym_settings = s.get("symbol_settings", {})
    rebuilt = 0
    for p in _st.positions:
        sym = p["symbol"]
        if sym in _pt.entries:
            continue  # 已有本地记录，不覆盖（保留移动止损状态）
        side_str = "BUY" if p["side"] == "LONG" else "SELL"
        ep       = p["entry_price"]
        sz       = p["size"]
        cfg      = sym_settings.get(sym, s)
        sl_pct   = cfg.get("stop_loss_pct",  s.get("stop_loss_pct",  0.005)) or 0.005
        tp_pct   = cfg.get("take_profit_pct", s.get("take_profit_pct", 0.008)) or 0.008
        trailing = cfg.get("trailing_stop",   s.get("trailing_stop",   True))
        # 尝试从K线缓存取ATR，让移动止损能正常激活
        kl = kline_cache.get(sym, [])
        atr_val = signal_engine._atr(
            [float(k[2]) for k in kl],
            [float(k[3]) for k in kl],
            [float(k[4]) for k in kl]
        ) if len(kl) >= 15 else 0
        _pt.record(sym, side_str, ep, sz, sl_pct, tp_pct, trailing=trailing, open_ctx=None, atr=atr_val)
        rebuilt += 1
        logger.info(f"🔄 重建仓位跟踪 {sym} {side_str} entry={ep} sz={sz} sl={sl_pct*100:.1f}% tp={tp_pct*100:.1f}% atr={atr_val:.2f}")
    if rebuilt:
        logger.info(f"✅ 共重建 {rebuilt} 个币种的仓位跟踪记录")

async def reconcile_positions(uid: int = 0):
    """
    启动对账：对比本地Tracker与交易所实时持仓，检测并处理幽灵仓位。
    - Tracker有 但交易所无 → 幽灵仓位（平仓指令已发但崩溃前未确认）→ 清除Tracker并告警
    - 交易所有 但Tracker无 → 已由 rebuild_tracker_from_positions 处理
    """
    _st = get_user_state(uid) if uid else state
    exchange_syms = {p["symbol"] for p in _st.positions}
    _pt_rec = get_pos_tracker(uid)
    tracker_syms  = set(_pt_rec.entries.keys())
    ghost_syms    = tracker_syms - exchange_syms  # Tracker有但交易所没有
    if not ghost_syms:
        logger.info("✅ 持仓对账正常，无幽灵仓位")
        return
    for sym in ghost_syms:
        entry = _pt_rec.entries.get(sym, {})
        logger.warning(
            f"👻 幽灵仓位检测: {sym} Tracker记录 {entry.get('side')} @ {entry.get('entry')}"
            f" 但交易所已无持仓，清除本地记录"
        )
        _pt_rec.clear(sym)
        await broadcast("log", {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"👻 幽灵仓位已清除: {sym}（Tracker有记录但交易所无持仓，可能是崩溃前平仓未确认）",
            "level": "warn",
        }, user_id=uid)
        if alerting.is_user_enabled(uid):
            _ep = entry.get('entry')
            _ep_str = f"{_ep:.4f}" if _ep is not None else "N/A"
            asyncio.ensure_future(alerting.send_to_user(
                uid,
                f"👻 <b>[幽灵仓位] {sym}</b>\n"
                f"本地Tracker有记录({entry.get('side')}@{_ep_str})"
                f" 但交易所已无持仓，已自动清除。\n请检查该币种是否有未记录的平仓。"
            ))

# 平仓冷却期（防止反复横跳）：按 uid 隔离
_close_cooldowns: Dict[int, Dict[str, float]] = {}  # uid -> {symbol -> time}

def _get_close_cooldown(uid: int = 0) -> Dict[str, float]:
    if uid not in _close_cooldowns:
        _close_cooldowns[uid] = {}
    return _close_cooldowns[uid]

_close_cooldown = _get_close_cooldown(0)  # legacy alias

# ─────────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────────
_log_id_counter = itertools.count(int(time.time() * 1000))

def _order_ok(result) -> bool:
    if not result: return False
    return result.get("status") in ("NEW", "PARTIALLY_FILLED", "FILLED") or "orderId" in result

# AsterDex taker 手续费率（0.05%）
FEE_RATE = 0.0005

def _log_trade(symbol, side, price, sz, strategy, confidence, result, failed=False, open_ctx=None, uid: int = 0):
    status = "failed" if failed else ("filled" if _order_ok(result) else "sent")
    notional = round(float(sz) * float(price), 4)  # 名义金额
    fee      = round(notional * FEE_RATE, 6)        # 手续费
    # 计算盈亏（平仓时从 pos_tracker 算）
    pnl = 0.0
    hold_secs = 0
    ctx = open_ctx or {}
    if side == "CLOSE":  # 只有平仓才计算盈亏
        e = get_pos_tracker(uid).entries.get(symbol)
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
    _st = get_user_state(uid) if uid else state
    _sym_cfg = _st.settings.get("symbol_settings", {}).get(symbol) or _st.settings
    _lev = float(_sym_cfg.get("leverage", _st.settings.get("leverage", 1)))

    # 改进的错误捕获：存储结果信息用于诊断
    result_raw = ""
    if result:
        if isinstance(result, dict):
            if result.get("orderId"):
                result_raw = str(result.get("orderId", ""))
            elif result.get("code") and result.get("code") < 0:
                # API错误：存储错误代码和消息
                result_raw = f"CODE:{result.get('code')} MSG:{result.get('msg', '')[:40]}"
            else:
                result_raw = str(result)[:50]
        else:
            result_raw = str(result)[:50]
    else:
        result_raw = "No response"

    entry = {
        "id": next(_log_id_counter),  # 单调递增，并发安全
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "date": datetime.now().strftime("%m-%d"),
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
        "result_raw": result_raw,
        "leverage": _lev,
    }
    if failed:
        if not hasattr(_st, '_recent_failed_orders'):
            _st._recent_failed_orders = []
        _st._recent_failed_orders.insert(0, entry)
        _st._recent_failed_orders = _st._recent_failed_orders[:20]
        return

    _st.trade_logs.insert(0, entry)
    _st.trade_logs = _st.trade_logs[:500]
    _st.perf["total_trades"] += 1
    if side == "CLOSE":
        if pnl > 0:
            _st.perf["wins"]   = _st.perf.get("wins", 0) + 1
        elif pnl < 0:
            _st.perf["losses"] = _st.perf.get("losses", 0) + 1
        _st.perf["total_pnl"] = round(_st.perf.get("total_pnl", 0) + pnl, 4)
        w = _st.perf.get("wins", 0)
        _closed = w + _st.perf.get("losses", 0)
        _st.perf["win_rate"]  = round(w / _closed * 100, 1) if _closed else 0
        bal = _st.balance if _st.balance > 0 else 1.0
        _st.perf["total_pnl_pct"]  = round(_st.perf["total_pnl"] / bal * 100, 2)
        today = datetime.now().strftime("%Y-%m-%d")
        if _st.perf.get("_last_date", today) != today:
            _st.perf["daily_pnl"] = 0.0
        _st.perf["_last_date"] = today
        _st.perf["daily_pnl"] = round(_st.perf.get("daily_pnl", 0) + pnl, 4)
        _st.perf["daily_pnl_pct"]  = round(_st.perf["daily_pnl"] / bal * 100, 2)
        dh = _st.perf.setdefault("daily_history", {})
        day = dh.setdefault(today, {"pnl": 0.0, "trades": 0, "wins": 0})
        day["pnl"]    = round(day["pnl"] + pnl, 4)
        day["trades"] += 1
        if pnl > 0: day["wins"] += 1
        day["pnl_pct"] = round(day["pnl"] / bal * 100, 2)
    # DB持久化 + 广播
    save_trade_log(uid if uid else 0, entry)
    asyncio.create_task(broadcast("new_trade", entry, user_id=uid))
    asyncio.create_task(broadcast("performance", _st.perf, user_id=uid))
    if side == "CLOSE":
        closed_count = len([t for t in _st.trade_logs if t.get("side") == "CLOSE"])
        if closed_count >= MIN_TRADES_FOR_OPT and closed_count % 20 == 0:
            asyncio.create_task(run_auto_optimize(uid=uid))

# ─────────────────────────────────────────────
# HFT 交易循环（多币种并发，每个币种最多1单）
# ─────────────────────────────────────────────

# 每个 symbol 的信号广播节流（避免洪泛），按 uid 隔离
_last_broadcast: Dict[int, Dict[str, float]] = {}

def _get_last_broadcast(uid: int = 0) -> Dict[str, float]:
    if uid not in _last_broadcast:
        _last_broadcast[uid] = {}
    return _last_broadcast[uid]

async def _process_symbol(symbol: str, s: dict, daily_start_ref: list = None, uid: int = 0):
    """单币种处理：止损检查 → 信号生成 → 开平仓。每个币种最多持1单。"""
    _st = get_user_state(uid) if uid else state
    sym_short = symbol.replace("USDT", "")
    # 优先使用该币种独立参数，否则回退全局
    # 合并全局配置 + 币种独立配置（独立配置优先，缺失字段回退全局）
    _sym_override = _st.settings.get("symbol_settings", {}).get(symbol, {})
    sym_cfg = {**s, **_sym_override} if _sym_override else s
    price = _st.market_prices.get(sym_short) or _st.market_prices.get(symbol)
    if not price or price <= 0:
        return

    # 提前取冷却秒数（aggressive/turbo模式减半，高频不卡冷却）
    cooldown = sym_cfg.get("cooldown_secs", s.get("cooldown_secs", 60))  # 优先币种独立冷却
    _mode = sym_cfg.get("hft_mode") or s.get("hft_mode") or _st.settings.get("hft_mode", "balanced")
    if _mode in ("aggressive", "turbo"):
        cooldown = min(cooldown, 10)  # 激进模式最多等10s，不被用户全局冷却卡死
    # Fix1: 反向平仓专用冷却：不受 aggressive/turbo 模式缩短，固定至少60s
    # 防止震荡行情中反复触发反向平仓→开仓→再平仓的连续亏损循环
    _REVERSE_COOLDOWN = max(sym_cfg.get("cooldown_secs", s.get("cooldown_secs", 60)), 60)

    # ── 止损/止盈/移动止损（优先级最高）统一走_guardian_close防重复平仓 ──
    _pt_ps = get_pos_tracker(uid)
    _gc_ps = _get_guardian_closing(uid)
    _cd_ps = _get_close_cooldown(uid)
    exit_reason = _pt_ps.should_exit(symbol, price)
    if exit_reason:
        if symbol not in _gc_ps:
            asyncio.create_task(_guardian_close(symbol, price, exit_reason, uid=uid))
        _cd_ps[symbol] = time.time()
        return

    # ── 信号生成（先compute取scores，再由generate过滤）──
    raw_side, raw_conf, scores = signal_engine.compute(kline_cache.get(symbol, []), sym_short, _st.orderbooks)
    side, confidence, block_reason = signal_engine.generate(sym_cfg, sym_short, symbol=symbol)

    existing = next((p for p in _st.positions if p["symbol"] == symbol), None)
    # pos_tracker 本地记录比交易所API同步快，优先用它防止重复开仓
    has_position = existing is not None  # 以交易所真实持仓为准，pos_tracker仅用于开仓防重复

    # ── 实时推送完整指标（节流 0.3s，持仓/无持仓都推，0延迟）──
    now = time.time()
    _lb = _get_last_broadcast(uid)
    if now - _lb.get(symbol, 0) >= 0.3:
        _lb[symbol] = now
        ind_data = _compute_indicators(symbol, _st)
        ind_data["has_position"] = existing is not None
        await broadcast("indicators_push", ind_data, user_id=uid)

    if has_position:
        # 持仓中只检查反向信号，其余静默
        tracker_entry = _pt_ps.entries.get(symbol)
        pos_side_src = existing["side"] if existing else (tracker_entry.get("side") if tracker_entry else None)
        if pos_side_src and side != "HOLD":
            pos_side = pos_side_src if pos_side_src in ("BUY","SELL") else ("BUY" if pos_side_src=="LONG" else "SELL")
            is_reverse = (pos_side == "BUY" and side == "SELL") or \
                         (pos_side == "SELL" and side == "BUY")
            cancel_on_reverse = sym_cfg.get("cancel_on_reverse", s.get("cancel_on_reverse", False))
            if is_reverse and cancel_on_reverse and confidence >= sym_cfg.get("min_confidence", s.get("min_confidence", 0.70)):
                if symbol in _gc_ps:
                    return  # 守护平仓进行中，跳过
                logger.info(f"↩️ {symbol} 反向平仓 {pos_side}→{side} conf={confidence:.3f}")
                _gc_ps.add(symbol)
                _rev_te = dict(_pt_ps.entries.get(symbol, {}))  # 平仓前快照
                _rev_sz = existing["size"] if existing else (tracker_entry.get("sz",0) if tracker_entry else 0)
                try:
                    await cancel_all_orders(symbol, user_id=uid)
                    result = await close_position(symbol, user_id=uid)
                    _log_trade(symbol, "CLOSE", price, _rev_sz, "reverse_signal", confidence, result, open_ctx=_rev_te.get("open_ctx"), uid=uid)
                    _rev_pnl = 0.0
                    if _rev_te:
                        _ep2 = _rev_te.get("entry", price)
                        _sz2 = float(_rev_te.get("sz", _rev_sz) or _rev_sz)
                        _gross2 = (price - _ep2) * _sz2 if _rev_te.get("side") == "BUY" else (_ep2 - price) * _sz2
                        _rev_pnl = round(_gross2 - _sz2 * _ep2 * FEE_RATE - _sz2 * price * FEE_RATE, 4)
                    _pt_ps.clear(symbol)
                    # Fix1: 反向平仓写入专用冷却时间，不受 aggressive/turbo 缩短（固定≥60s）
                    _cd_ps[symbol] = time.time()
                    _cd_ps[f"{symbol}_reverse_cd"] = time.time()  # 反向平仓标记，冷却检查时使用
                    pnl_str2 = f"+${_rev_pnl:.4f}" if _rev_pnl >= 0 else f"-${abs(_rev_pnl):.4f}"
                    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                        "text": f"↩️ {symbol} 反向平仓 {pos_side} @ {price:.4f} 盈亏:{pnl_str2} ⏳冷却{_REVERSE_COOLDOWN}s"}, user_id=uid)
                    asyncio.create_task(alerting.alert_position_closed(symbol, _rev_pnl, "反向信号", uid=uid))
                finally:
                    _gc_ps.discard(symbol)
        return  # 持仓中不开新仓，静默

    if side == "HOLD":
        return  # 无信号

    # ── 最终兜底置信度校验（任何路径都不允许绕过用户设定的min_confidence）──
    _final_min_conf = sym_cfg.get("min_confidence", s.get("min_confidence", 0.65))
    if confidence < _final_min_conf:
        return

    # ── enable_long / enable_short 开关（优先币种独立配置）──
    if side == "BUY" and not sym_cfg.get("enable_long", s.get("enable_long", True)):
        return
    if side == "SELL" and not sym_cfg.get("enable_short", s.get("enable_short", True)):
        return

    # ── 日亏损限额检查 ──
    max_daily_loss = _st.settings.get("max_daily_loss_usd", 50)
    daily_pnl = _st.perf.get("daily_pnl", 0.0)
    if daily_pnl <= -abs(max_daily_loss):
        if _st.auto_trading:
            _st.auto_trading = False
            await broadcast("trading_status", {"active": False}, user_id=uid)
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⛔ 今日亏损 ${abs(daily_pnl):.2f} 已达上限 ${max_daily_loss}，自动停止交易！", "level": "error"}, user_id=uid)
            logger.warning(f"日亏损触发熔断: daily_pnl={daily_pnl:.2f} 限额={max_daily_loss}")
            asyncio.ensure_future(alerting.alert_circuit_breaker(daily_pnl, max_daily_loss, uid=uid))
        return

    # Fix1: 反向平仓后的冷却使用专用时长（不受 aggressive/turbo 模式缩短）
    _reverse_cd_ts = _cd_ps.get(f"{symbol}_reverse_cd", 0)
    _effective_cooldown = _REVERSE_COOLDOWN if (time.time() - _reverse_cd_ts < _REVERSE_COOLDOWN) else cooldown
    last_close = _cd_ps.get(symbol, 0)
    if time.time() - last_close < _effective_cooldown:
        remaining = int(_effective_cooldown - (time.time() - last_close))
        last_cd_log = _cd_ps.get(f"{symbol}_log", 0)
        if time.time() - last_cd_log >= 15:
            _cd_ps[f"{symbol}_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⏳ {symbol} 冷却中，还需 {remaining}s"}, user_id=uid)
        return

    # Fix2: max_open_positions 检查移入全局锁内（见开仓锁区域），此处仅做快速预检（无锁，可能有极小并发窗口）
    max_pos = sym_cfg.get("max_open_positions", s.get("max_open_positions", 3))
    open_count = len([p for p in _st.positions if abs(p.get("size", 0)) > 1e-9])
    if open_count >= max_pos:
        last_log = _cd_ps.get(f"{symbol}_maxpos_log", 0)
        if time.time() - last_log >= 60:
            _cd_ps[f"{symbol}_maxpos_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⚠️ 已达最大持仓数 {open_count}/{max_pos}，{symbol} 跳过"}, user_id=uid)
        return

    # 信号通过所有过滤，准备开仓（节流：5s内只打印一次）
    _sig_log_key = f"{symbol}_siglog"
    if time.time() - _cd_ps.get(_sig_log_key, 0) >= 5:
        _cd_ps[_sig_log_key] = time.time()
        logger.debug(f"🎯 {symbol} 信号通过 side={side} conf={confidence:.3f} price={price:.4f}")

    # ── 资金检查 ──
    leverage      = sym_cfg.get("leverage",          s.get("leverage",          5))
    max_pos_usd   = sym_cfg.get("max_position_usd", s.get("max_position_usd", 200))
    max_trade_usd = sym_cfg.get("max_trade_usd",    s.get("max_trade_usd",     30))  # 单笔最大USD上限

    # ── 多币种分摊：可用余额 ÷ 启用币种数，每个币只占一份 ──
    active_syms = s.get("active_symbols", [s.get("symbol", "BTCUSDT")])
    n_syms = max(len(active_syms), 1)

    size_mode = s.get("size_mode", "fixed")
    if size_mode == "pct":
        size_pct      = sym_cfg.get("size_pct", s.get("size_pct", 20)) / 100.0
        available_bal = max(_st.available, _st.balance * 0.05)
        # 分摊：总可用余额 × 百分比 ÷ 币种数
        trade_usd = (available_bal * size_pct) / n_syms
    else:
        trade_usd = sym_cfg.get("trade_size_usd", s.get("trade_size_usd", 10))

    # ── 单笔最大USD限额（保证金维度）──
    trade_usd = min(trade_usd, max_trade_usd)

    # ── 不超过 max_position_usd 名义价值 ──
    notional_usd = trade_usd * leverage
    if notional_usd > max_pos_usd:
        trade_usd    = max_pos_usd / leverage
        notional_usd = max_pos_usd

    # ── 极低余额：停止交易 ──
    if _st.available < 1.0:
        _st.auto_trading = False
        await broadcast("trading_status", {"active": False}, user_id=uid)
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"⛔ 可用余额 ${_st.available:.2f} 极低，自动停止交易！"}, user_id=uid)
        asyncio.ensure_future(alerting.alert_balance_critical(_st.available, uid=uid))
        return

    # Fix4: 余额保守系数——按当前已开仓数扣减，防止余额计算过期导致超额下单
    # 每个已持仓占用 trade_usd 额度，剩余才可用于新仓
    _occupied_usd = len(get_pos_tracker(uid).entries) * trade_usd
    _safe_available = max(_st.available - _occupied_usd * 0.1, _st.available * 0.85)
    # ── 动态余额兜底：余额不足时按实际可用缩小，不强行跳过 ──
    if _safe_available < trade_usd:
        trade_usd = _safe_available * 0.8  # 用保守可用余额的80%，留20%作手续费缓冲
        last_log = _cd_ps.get(f"{symbol}_bal_log", 0)
        if time.time() - last_log >= 60:
            _cd_ps[f"{symbol}_bal_log"] = time.time()
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"💸 余额仅 ${_st.available:.2f}，已接近下限，请注意风控", "level": "warn"}, user_id=uid)
        if trade_usd < 3.0:  # 缩减后仍不足最小下单额，跳过
            return

    # ── 名义价值校验：不足时自动提升杠杆，而不是跳过 ──
    _min_notional = MIN_NOTIONAL.get(symbol.upper(), 1.0)
    _notional = trade_usd * leverage
    _user_leverage = leverage  # 记录用户原始杠杆，用于止损/止盈比例调整
    if _notional < _min_notional:
        _need_lev = math.ceil(_min_notional / trade_usd)
        _max_auto_lev = sym_cfg.get("max_leverage", s.get("max_leverage", 20))
        if _need_lev <= _max_auto_lev:
            # 自动提升杠杆满足最小名义价值
            leverage = _need_lev
            _notional = trade_usd * leverage
            logger.info(f"📐 {symbol} 自动提升杠杆至{leverage}x 满足最小名义${_min_notional:.0f}（trade_usd={trade_usd:.1f}）")
        else:
            # 杠杆已到上限还不够，说明资金太少，跳过
            _sz0_key = f"{symbol}_sz0_log"
            if time.time() - _cd_ps.get(_sz0_key, 0) >= 60:
                _cd_ps[_sz0_key] = time.time()
                logger.warning(f"⚠️ {symbol} 资金不足：需≥${math.ceil(_min_notional/_max_auto_lev):.0f}保证金"
                               f"（当前${trade_usd:.1f}，最高{_max_auto_lev}x）")
                await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                    "text": f"⚠️ {symbol} 保证金${trade_usd:.1f}×{_max_auto_lev}x仍<最低${_min_notional:.0f}，跳过", "level": "warn"}, user_id=uid)
            return

    # leverage 可能已被名义价值检查自动提升，重新用最终值计算数量
    _notional = trade_usd * leverage
    sz = float(_fmt_qty(symbol, _notional / price))
    if sz <= 0:
        _sz0_key = f"{symbol}_sz0_log"
        if time.time() - _cd_ps.get(_sz0_key, 0) >= 60:
            _cd_ps[_sz0_key] = time.time()
            logger.warning(f"⚠️ {symbol} 精度截断后数量为0，notional={_notional:.1f} price={price:.4f}")
            await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                "text": f"⚠️ {symbol} 下单量精度截断为0，请联系开发排查精度配置", "level": "warn"}, user_id=uid)
        return

    # ── 插针保护：下单前校验实时市价与K线信号收盘价偏离不超过阈値 ──
    # price 来自 market_prices（实时），kline_close 来自 kline_cache 最新bar收盘价（信号生成依据）
    # 两者数据源不同，能真实反映"信号发出后价格是否急剧偏离"
    _SPIKE_PCT = float(sym_cfg.get("spike_protection_pct", s.get("spike_protection_pct", 2.0)))  # 默认2.0%，高频下小币波动大
    _kl_cache = kline_cache.get(symbol, [])
    _kline_close = float(_kl_cache[-1][4]) if _kl_cache else 0.0
    cur_mkt = price  # 实时市价
    if _kline_close > 0:
        _dev = abs(cur_mkt - _kline_close) / _kline_close * 100
    else:
        _dev = 0.0  # K线数据不足时跳过插针检查
    if _dev > _SPIKE_PCT:
            _spike_key = f"{symbol}_spike_log"
            _cd_spike = _get_close_cooldown(uid)
            if time.time() - _cd_spike.get(_spike_key, 0) >= 10:
                _cd_spike[_spike_key] = time.time()
                logger.warning(f"🛡️ {symbol} 插针保护触发：K线收盘={_kline_close:.4f} 实时市价={cur_mkt:.4f} 偏离={_dev:.2f}%>{_SPIKE_PCT}%，跳过")
                asyncio.ensure_future(alerting.alert_spike_protection(symbol, _kline_close, cur_mkt, _dev, uid=uid))
            return

    # ── 市价开仓（双层锁嵌套持有：全局锁 ⊃ 币种锁，两锁同时持有直到 tracker.record）──
    # 注意：必须嵌套持有，而不能先释放全局锁再等币种锁，否则两锁之间存在竞态窗口期
    async with _get_open_pos_lock(uid):   # 全局锁
        # 全局锁内重新检查持仓数（此时其他币种协程无法并发通过此检查）
        _cur_open = len([p for p in _st.positions if abs(p.get("size", 0)) > 1e-9])
        _cur_open_tracker = len(get_pos_tracker(uid).entries)
        _real_open = max(_cur_open, _cur_open_tracker)
        if _real_open >= max_pos:
            logger.debug(f"🔒 {symbol} 全局锁内持仓数 {_real_open}/{max_pos}，跳过")
            return
        async with _get_sym_lock(symbol, uid):  # 嵌套币种锁，全局锁与币种锁同时持有直到开仓完成
            _pt_open = get_pos_tracker(uid)
            if symbol in _pt_open.entries:
                logger.debug(f"🔒 {symbol} 锁内tracker已有持仓，跳过")
                return
            if any(p["symbol"] == symbol for p in _st.positions):
                logger.debug(f"🔒 {symbol} 锁内positions已有持仓，跳过")
                return

            await set_leverage(symbol, int(leverage), user_id=uid)

            logger.info(f"📤 {symbol} 准备下单 side={side} sz={sz} trade_usd={trade_usd:.2f} lev={leverage}x")
            result = await place_order(symbol, side, "MARKET", sz, user_id=uid)
            if _order_ok(result):
                sl_pct_cfg = sym_cfg.get("stop_loss_pct",  s.get("stop_loss_pct",  0.005))
                tp_pct_cfg = sym_cfg.get("take_profit_pct", s.get("take_profit_pct", 0.008))
                klines_now = kline_cache.get(symbol, [])
                highs_now  = [float(k[2]) for k in klines_now]
                lows_now   = [float(k[3]) for k in klines_now]
                closes_now = [float(k[4]) for k in klines_now]
                adx_now = signal_engine._adx(highs_now, lows_now, closes_now) if len(klines_now) >= 30 else 0
                atr_now = signal_engine._atr(highs_now, lows_now, closes_now) if len(klines_now) >= 15 else 0
                if leverage > _user_leverage and _user_leverage > 0:
                    _lev_ratio = _user_leverage / leverage
                    sl_pct_use = round(sl_pct_cfg * _lev_ratio, 6)
                    tp_pct_use = tp_pct_cfg
                    logger.info(f"📐 {symbol} 杠杆提升{_user_leverage}x→{leverage}x，sl缩小保持保证金风险恒定，tp价格距离不变: "
                                f"sl {sl_pct_cfg*100:.2f}%→{sl_pct_use*100:.2f}% tp {tp_pct_cfg*100:.2f}%（不变）")
                else:
                    sl_pct_use = sl_pct_cfg
                    tp_pct_use = tp_pct_cfg
                open_ctx = {
                    "adx": round(adx_now, 1),
                    "atr": round(atr_now, 6),
                    "confidence": round(confidence, 3),
                    "sl_pct": round(sl_pct_use, 5),
                    "tp_pct": round(tp_pct_use, 5),
                    "open_ts": time.time(),
                }
                _pt_open.record(symbol, side, price, sz,
                    sl_pct_use, tp_pct_use,
                    trailing=sym_cfg.get("trailing_stop", s.get("trailing_stop", True)),
                    open_ctx=open_ctx,
                    atr=atr_now)
                logger.info(f"✅ 开仓 {side} {symbol} sz={sz} px≈{price:.4f} conf={confidence:.3f}")
                _log_trade(symbol, side, price, sz, "crypto_hft", confidence, result, False, open_ctx=open_ctx, uid=uid)
                await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                    "text": f"✅ {side} {symbol} sz={sz} @ {price:.4f} conf={confidence*100:.1f}%"}, user_id=uid)
                asyncio.create_task(alerting.alert_position_opened(symbol, side, price, sz, confidence, uid=uid))
            else:
                err_msg = ""
                if result:
                    err_msg = result.get("msg", result.get("message", str(result)))[:80]
                else:
                    err_msg = "无响应/网络超时"
                logger.warning(f"⚠️ 下单失败 {symbol}: {err_msg}")
                if "Margin is insufficient" in err_msg or "insufficient" in err_msg.lower():
                    _st.auto_trading = False
                    await broadcast("trading_status", {"active": False}, user_id=uid)
                    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                        "text": f"⛔ {symbol} 保证金不足，自动停止交易！请充值后手动重启。"}, user_id=uid)
                else:
                    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
                        "text": f"❌ {symbol} 下单失败({side}): {err_msg}"}, user_id=uid)

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

# 当前优化结果（内存）—— per-user dict
_opt_result: Dict[int, Dict] = {}

def _eval_params(trades: list, conf_thresh: float, sl: float, tp: float):
    """在给定数据集上评估一组参数，返回 (score, win_rate, avg_pnl, total)"""
    net_tp = tp - 2 * FEE_RATE
    net_sl = sl + 2 * FEE_RATE
    rr = net_tp / net_sl if net_sl > 0 else 0
    filtered = [t for t in trades if float(t.get("open_conf", 0)) >= conf_thresh]
    if not filtered:
        return None
    closed_filtered = [t for t in filtered if float(t.get("pnl", 0)) != 0]
    total = len(closed_filtered)
    if total == 0:
        return None
    wins  = sum(1 for t in closed_filtered if float(t.get("pnl", 0)) > 0)
    win_rate = wins / total
    avg_pnl  = sum(float(t.get("pnl", 0)) for t in closed_filtered) / total
    score    = avg_pnl * win_rate * 100
    return {"score": score, "win_rate": win_rate, "avg_pnl": avg_pnl, "total": total, "rr": rr}

def _run_param_backtest(closed_trades: list) -> Dict:
    """
    参数网格搜索 + 样本外验证。
    - 训练集：前80%数据，用于网格搜索找最优参数
    - 验证集：最近20%数据，用于验证参数泛化能力，防止过拟合小样本
    """
    if len(closed_trades) < MIN_TRADES_FOR_OPT:
        return {}

    # 按时间排序（id单调递增代表时间顺序）
    sorted_trades = sorted(closed_trades, key=lambda t: t.get("id", 0))
    split = max(int(len(sorted_trades) * 0.8), MIN_TRADES_FOR_OPT - 5)
    train_set = sorted_trades[:split]
    val_set   = sorted_trades[split:]

    best_score = -999.0
    best_params = {}
    results = []

    for conf_thresh in PARAM_GRID["min_confidence"]:
        for sl in PARAM_GRID["stop_loss_pct"]:
            for tp in PARAM_GRID["take_profit_pct"]:
                net_tp = tp - 2 * FEE_RATE
                net_sl = sl + 2 * FEE_RATE
                rr = round(net_tp / net_sl, 2) if net_sl > 0 else 0
                if rr < 0.3:
                    continue

                train = _eval_params(train_set, conf_thresh, sl, tp)
                if not train or train["total"] < 8:
                    continue

                # 验证集评估（样本不足时标注"验证集不足"）
                val = _eval_params(val_set, conf_thresh, sl, tp) if len(val_set) >= 3 else None
                val_score    = round(val["score"], 4)    if val else None
                val_win_rate = round(val["win_rate"] * 100, 1) if val else None
                val_avg_pnl  = round(val["avg_pnl"], 4)  if val else None

                # 综合评分：训练集70% + 验证集30%（验证集存在时）
                if val:
                    final_score = train["score"] * 0.7 + val["score"] * 0.3
                else:
                    final_score = train["score"]

                results.append({
                    "min_confidence":  conf_thresh,
                    "stop_loss_pct":   sl,
                    "take_profit_pct": tp,
                    "win_rate":        round(train["win_rate"] * 100, 1),
                    "avg_pnl":         round(train["avg_pnl"], 4),
                    "score":           round(final_score, 4),
                    "train_score":     round(train["score"], 4),
                    "val_score":       val_score,
                    "val_win_rate":    val_win_rate,
                    "val_avg_pnl":     val_avg_pnl,
                    "sample":          train["total"],
                    "val_sample":      val["total"] if val else 0,
                    "rr":              rr,
                })
                if final_score > best_score:
                    best_score = final_score
                    best_params = {
                        "min_confidence": conf_thresh,
                        "stop_loss_pct":  sl,
                        "take_profit_pct": tp,
                    }

    results.sort(key=lambda x: x["score"], reverse=True)
    return {
        "best":          best_params,
        "top5":          results[:5],
        "total_closed":  len(closed_trades),
        "train_size":    len(train_set),
        "val_size":      len(val_set),
        "optimized_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

async def run_auto_optimize(force=False, uid: int = 0) -> Dict:
    """异步触发优化，结果存入_opt_result[uid]并广播到前端"""
    st = get_user_state(uid) if uid else state
    closed = [t for t in st.trade_logs if t.get("side") == "CLOSE" and t.get("open_conf", 0) > 0]
    if not force and len(closed) < MIN_TRADES_FOR_OPT:
        return {"error": f"需要至少{MIN_TRADES_FOR_OPT}笔平仓数据，当前{len(closed)}笔"}

    logger.info(f"🔬 开始参数网格优化，共{len(closed)}笔平仓数据...")
    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
        "text": f"🔬 自动优化启动，分析{len(closed)}笔历史平仓..."}, user_id=uid)

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_param_backtest, closed)
    _opt_result[uid] = result

    if result.get("best"):
        best = result["best"]
        top  = result["top5"][0] if result.get("top5") else {}
        logger.info(f"✅ 优化完成：conf={best['min_confidence']} sl={best['stop_loss_pct']} tp={best['take_profit_pct']} 胜率={top.get('win_rate')}%")
        await broadcast("opt_result", result, user_id=uid)
        await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
            "text": f"✅ 优化完成：最优 conf={best['min_confidence']} sl={best['stop_loss_pct']*100:.1f}% tp={best['take_profit_pct']*100:.1f}% 预期胜率={top.get('win_rate')}%"}, user_id=uid)
    return result

async def hft_trading_loop(uid: int = 0):
    st = get_user_state(uid) if uid else state
    logger.info("🚀 HFT 多币种交易循环启动")
    await broadcast("trading_status", {"active": True}, user_id=uid)
    if not st.kline_task or st.kline_task.done():
        st.kline_task = asyncio.create_task(kline_refresh_loop(uid))

    active_syms_init = st.settings.get("active_symbols", [st.settings.get("symbol","BTCUSDT")])
    sym_settings_map = st.settings.get("symbol_settings", {})
    for sym in active_syms_init:
        lev = sym_settings_map.get(sym, {}).get("leverage", st.settings.get("leverage", 2))
        await set_leverage(sym, lev, user_id=uid)
        asyncio.create_task(refresh_klines(sym, "1m", 200, user_id=uid))

    while st.auto_trading:
        try:
            s        = st.settings
            interval = s.get("hft_interval_ms", 500) / 1000.0
            active_syms = s.get("active_symbols", [s.get("symbol", "BTCUSDT")])
            if not active_syms:
                active_syms = [s.get("symbol", "BTCUSDT")]
            await asyncio.gather(
                *[_process_symbol(sym, s, uid=uid) for sym in active_syms],
                return_exceptions=True
            )
        except Exception as e:
            logger.error(f"HFT 主循环异常: {e}\n{traceback.format_exc()}")
        await asyncio.sleep(interval)

    await broadcast("trading_status", {"active": False}, user_id=uid)
    logger.info("⏹️ HFT 循环已停止")

# ─────────────────────────────────────────────
# 数据库初始化 & 多用户 state
# ─────────────────────────────────────────────
init_db()
ensure_admin(os.environ.get("ADMIN_PASSWORD", "admin123"))

_user_states: Dict[int, Any] = {}

def get_user_state(user_id: int):
    if user_id not in _user_states:
        st = TradingState()
        # 从数据库加载该用户的 settings/perf/trade_logs（完全隔离）
        try:
            _saved_settings, _saved_perf = load_user_settings(user_id)
            if _saved_settings:
                for k, v in _saved_settings.items():
                    st.settings[k] = v
            if _saved_perf:
                st.perf.update(_saved_perf)
            st.trade_logs = load_trade_logs(user_id, limit=500)
        except Exception as _e:
            logger.warning(f"加载用户 {user_id} 数据失败: {_e}")
        _user_states[user_id] = st
    return _user_states[user_id]

# ─────────────────────────────────────────────
# FastAPI 路由
# ─────────────────────────────────────────────

# 唯一公开的固定路径：前端启动时调用获取真实前缀
# 此路径不包含任何业务信息，扫描器也无法从中获益
@app.get("/cfg")
async def get_cfg():
    return {"p": _PREFIX}

@app.get(R("/api/health"))
async def health():
    uptime_secs = int(time.time() - _START_TIME)
    h, r = divmod(uptime_secs, 3600); m, s = divmod(r, 60)
    tasks = {
        "trading":   state.auto_trading and bool(state.trading_task) and not state.trading_task.done(),
        "ws":        bool(state.ws_task and not state.ws_task.done()),
        "account":   bool(state.account_sync_task and not state.account_sync_task.done()),
        "kline":     bool(state.kline_task and not state.kline_task.done()),
        "price_poll": bool(state.price_poll_task and not state.price_poll_task.done()),
        "user_data": bool(state.user_data_task and not state.user_data_task.done()),
    }
    return {
        "status": "ok",
        "version": "6.0.0",
        "exchange": "AsterDex",
        "logged_in": state.logged_in,
        "auto_trading": state.auto_trading,
        "uptime": f"{h:02d}:{m:02d}:{s:02d}",
        "uptime_secs": uptime_secs,
        "tasks": tasks,
        "ws_clients": sum(len(v) for v in ws_clients.values()),
        "market_prices": len(state.market_prices),
        "klines_ready": list(kline_cache.keys()),
        "ts": datetime.now().isoformat(),
    }

# ─────────────────────────────────────────────
# 多用户认证路由
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str
    email:    str
    password: str

class ActivateRequest(BaseModel):
    username:     str
    license_code: str

class PasswordLoginRequest(BaseModel):
    username: str
    password: str

class GenLicenseRequest(BaseModel):
    count: int = 1
    days:  int = 30

# ─── 注册：10分钟内最多 3 次 ───
@app.post(R("/api/auth/register"))
@limiter.limit("3/10minute")
async def auth_register(request: Request, req: RegisterRequest):
    ip = get_client_ip(request)
    # 长度防护
    if len(req.username) > 64 or len(req.email) > 256 or len(req.password) > 128:
        return JSONResponse({"ok": False, "msg": "输入过长"}, status_code=400)
    res = register_user(req.username.strip(), req.email.strip(), req.password)
    log_login(req.username, ip, res["ok"], res.get("msg", ""))
    return JSONResponse(res, status_code=200 if res["ok"] else 400)

# ─── 激活：10分钟内最多 5 次 ───
@app.post(R("/api/auth/activate"))
@limiter.limit("5/10minute")
async def auth_activate(request: Request, req: ActivateRequest):
    if len(req.username) > 64 or len(req.license_code) > 32:
        return JSONResponse({"ok": False, "msg": "输入无效"}, status_code=400)
    res = activate_user(req.username.strip(), req.license_code.strip().upper())
    return JSONResponse(res, status_code=200 if res["ok"] else 400)

# ─── 登录：1分钟内最多 5 次（防爆破核心）───
@app.post(R("/api/auth/password-login"))
@limiter.limit("5/minute")
async def auth_password_login(request: Request, req: PasswordLoginRequest):
    ip = get_client_ip(request)
    if len(req.username) > 64 or len(req.password) > 128:
        log_login(req.username, ip, False, "输入过长")
        return JSONResponse({"ok": False, "msg": "参数无效"}, status_code=400)
    res = login_user(req.username.strip(), req.password)
    log_login(req.username, ip, res["ok"], res.get("msg", ""))
    if not res["ok"]:
        return JSONResponse(res, status_code=401)
    uid = res["user_id"]
    # ── 单设备登录：踢掉该用户所有旧 WS 连接 ──
    old_sockets = list(ws_clients.get(uid, []))
    if old_sockets:
        kick_msg = json.dumps({"type": "kicked", "data": {"reason": "账号在其他设备登录，您已被踢下线"}})
        for old_ws in old_sockets:
            try:
                await old_ws.send_text(kick_msg)
                await old_ws.close(1000)
            except Exception:
                pass
        ws_clients.pop(uid, None)
    token = create_token(uid, res["username"], res["is_admin"])
    return {"ok": True, "token": token, "username": res["username"],
            "is_admin": res["is_admin"], "expires_at": res["expires_at"]}

@app.get(R("/api/auth/me"))
async def auth_me(user=Depends(get_current_user)):
    return {"user_id": user["sub"], "username": user["username"], "is_admin": user.get("admin", False)}

# ─── 登出：JWT token列入黑名单 + 清理交易状态 ───
@app.post(R("/api/auth/logout"))
async def auth_logout(request: Request, user=Depends(get_current_user)):
    uid = int(user["sub"])
    creds = request.headers.get("Authorization", "")
    if creds.startswith("Bearer "):
        revoke_token(creds[7:])
    # 同时清理交易状态
    st = get_user_state(uid)
    st.logged_in   = False
    st.user        = ""
    st.signer      = ""
    clear_global_key()
    st.auto_trading = False
    st.balance     = 0.0
    st.available   = 0.0
    st.positions   = []
    st.open_orders = []
    for task in [st.trading_task, st.account_sync_task, st.ws_task,
                 st.kline_task, st.price_poll_task, st.user_data_task,
                 getattr(st, '_heartbeat_task', None),
                 getattr(st, '_command_task', None)]:
        if task and not task.done():
            task.cancel()
    st.trading_task = st.account_sync_task = st.ws_task = None
    st.kline_task = st.price_poll_task = st.user_data_task = None
    # 不清除全局kline_cache（共享公共行情数据）
    # 清理该用户的全部内存占用（防止长期运营内存无限增长）
    _user_states.pop(uid, None)
    _circuit.pop(uid, None)
    _sym_locks.pop(uid, None)
    _open_pos_lock.pop(uid, None)
    _leverage_cache.pop(uid, None)
    _guardian_closing.pop(uid, None)
    _close_cooldowns.pop(uid, None)
    _pos_trackers.pop(uid, None)
    _opt_result.pop(uid, None)
    if uid in ws_clients and not ws_clients[uid]:
        ws_clients.pop(uid, None)
    return {"ok": True}

# ── 管理员接口 ──
@app.post(R("/api/admin/generate-license"))
async def admin_gen_license(req: GenLicenseRequest, user=Depends(get_admin_user)):
    if req.count < 1 or req.count > 100:
        return JSONResponse({"ok": False, "msg": "count 范围 1-100"}, status_code=400)
    codes = generate_license_codes(req.count, req.days)
    return {"ok": True, "codes": codes, "count": len(codes), "days": req.days}

@app.get(R("/api/admin/licenses"))
async def admin_licenses(page: int = 1, user=Depends(get_admin_user)):
    return {"ok": True, "data": list_licenses(page)}

@app.get(R("/api/admin/users"))
async def admin_users(page: int = 1, user=Depends(get_admin_user)):
    return {"ok": True, "data": list_users(page)}

@app.post(R("/api/admin/change-password"))
async def admin_change_pwd(body: dict, user=Depends(get_admin_user)):
    username = body.get("username", "").strip()
    new_password = body.get("new_password", "").strip()
    return admin_change_password(username, new_password)

@app.get(R("/api/admin/login-log"))
async def admin_login_log(user=Depends(get_admin_user)):
    from db import _conn
    with _conn() as c:
        rows = c.execute("SELECT * FROM login_log ORDER BY id DESC LIMIT 500").fetchall()
    return {"ok": True, "data": [dict(r) for r in rows]}

@app.get(R("/api/admin/stats"))
async def admin_stats(user=Depends(get_admin_user)):
    """全局统计：用户数、在线数、全平台盈亏、交易笔数（SQL聚合，离线用户不读全量日志）"""
    from db import _conn
    import json as _json
    with _conn() as c:
        users = c.execute(
            "SELECT id, username, is_active, is_admin, expires_at, last_login_at FROM users ORDER BY id"
        ).fetchall()
        # SQL 聚合：每用户的平仓总数、盈利数、总盈亏
        agg_rows = c.execute("""
            SELECT user_id,
                   COUNT(*) AS trades,
                   SUM(CASE WHEN json_extract(log_json,'$.pnl') > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CAST(json_extract(log_json,'$.pnl') AS REAL)) AS total_pnl
            FROM trade_logs
            WHERE json_extract(log_json,'$.side') = 'CLOSE'
            GROUP BY user_id
        """).fetchall()
    db_agg = {r["user_id"]: r for r in agg_rows}
    now = datetime.utcnow()
    online_count = len([uid for uid, clients in ws_clients.items() if uid and clients])
    user_summaries = []
    total_pnl = 0.0; total_trades = 0; total_wins = 0
    for u in users:
        uid = u["id"]
        st = _user_states.get(uid)
        if st and st.logged_in:
            pnl    = st.perf.get("total_pnl", 0.0)
            trades = st.perf.get("total_trades", 0)
            wins   = st.perf.get("wins", 0)
            is_trading = bool(st.auto_trading)
            logged_in  = True
        else:
            ag = db_agg.get(uid)
            pnl    = round(ag["total_pnl"] or 0, 4) if ag else 0.0
            trades = ag["trades"] if ag else 0
            wins   = ag["wins"]   if ag else 0
            is_trading = False
            logged_in  = bool(ws_clients.get(uid))
        total_pnl    += pnl
        total_trades += trades
        total_wins   += wins
        expired = bool(u["expires_at"] and datetime.fromisoformat(u["expires_at"]) < now)
        user_summaries.append({
            "id": uid, "username": u["username"],
            "is_active": bool(u["is_active"]), "is_admin": bool(u["is_admin"]),
            "expires_at": u["expires_at"], "last_login_at": u["last_login_at"],
            "expired": expired, "logged_in": logged_in, "is_trading": is_trading,
            "total_pnl": round(pnl, 4), "total_trades": trades, "wins": wins,
            "win_rate": round(wins / trades * 100, 1) if trades else 0,
        })
    return {
        "ok": True,
        "global": {
            "total_users":   len(users),
            "active_users":  sum(1 for u in users if u["is_active"]),
            "online_count":  online_count,
            "trading_count": sum(1 for s in user_summaries if s["is_trading"]),
            "total_pnl":     round(total_pnl, 4),
            "total_trades":  total_trades,
            "total_wins":    total_wins,
            "win_rate":      round(total_wins / total_trades * 100, 1) if total_trades else 0,
        },
        "users": user_summaries,
    }

@app.get(R("/api/admin/user-detail/{uid}"))
async def admin_user_detail(uid: int, user=Depends(get_admin_user)):
    """单用户详细交易数据"""
    from db import load_trade_logs
    logs = load_trade_logs(uid, limit=2000)
    closes = [l for l in logs if l.get("side") == "CLOSE"]
    pnl_list = [l.get("pnl", 0) for l in closes]
    total_pnl = round(sum(pnl_list), 4)
    wins = sum(1 for p in pnl_list if p > 0)
    losses = sum(1 for p in pnl_list if p <= 0)
    st = _user_states.get(uid)
    daily_pnl = st.perf.get("daily_pnl", 0.0) if st else 0.0
    return {
        "ok": True,
        "uid": uid,
        "total_trades": len(closes),
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / len(closes) * 100, 1) if closes else 0,
        "total_pnl": total_pnl,
        "daily_pnl": round(daily_pnl, 4),
        "best_trade":  round(max(pnl_list), 4) if pnl_list else 0,
        "worst_trade": round(min(pnl_list), 4) if pnl_list else 0,
        "avg_pnl":     round(total_pnl / len(closes), 4) if closes else 0,
        "recent_logs": closes[:50],
    }

@app.post(R("/api/admin/extend-license"))
async def admin_extend(body: dict, user=Depends(get_admin_user)):
    """延长用户到期时间"""
    from db import _conn
    username = body.get("username", "").strip()
    try:
        days = int(body.get("days", 30))
    except (TypeError, ValueError):
        return JSONResponse({"ok": False, "msg": "days 必须为整数"}, status_code=400)
    if not username or days < 1 or days > 3650:
        return JSONResponse({"ok": False, "msg": "参数无效（days 范围 1-3650）"}, status_code=400)
    with _conn() as c:
        u = c.execute("SELECT id, expires_at FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            return JSONResponse({"ok": False, "msg": "用户不存在"}, status_code=404)
        base = u["expires_at"]
        if base and datetime.fromisoformat(base) > datetime.utcnow():
            new_exp = (datetime.fromisoformat(base) + timedelta(days=days)).isoformat()
        else:
            new_exp = (datetime.utcnow() + timedelta(days=days)).isoformat()
        c.execute("UPDATE users SET expires_at=?, is_active=1 WHERE id=?", (new_exp, u["id"]))
    return {"ok": True, "msg": f"用户 {username} 已延期至 {new_exp[:10]}"}

@app.post(R("/api/admin/toggle-user"))
async def admin_toggle_user(body: dict, user=Depends(get_admin_user)):
    """禁用或启用用户账号"""
    from db import _conn
    username = body.get("username", "").strip()
    if not username:
        return JSONResponse({"ok": False, "msg": "参数无效"}, status_code=400)
    with _conn() as c:
        u = c.execute("SELECT id, is_active FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            return JSONResponse({"ok": False, "msg": "用户不存在"}, status_code=404)
        new_state = 0 if u["is_active"] else 1
        c.execute("UPDATE users SET is_active=? WHERE id=?", (new_state, u["id"]))
    action = "启用" if new_state else "禁用"
    return {"ok": True, "msg": f"用户 {username} 已{action}", "is_active": bool(new_state)}

@app.post(R("/api/admin/kick-user"))
async def admin_kick_user(body: dict, user=Depends(get_admin_user)):
    """强制踢下线用户（关闭其所有 WebSocket 连接）"""
    from db import _conn
    username = body.get("username", "").strip()
    if not username:
        return JSONResponse({"ok": False, "msg": "参数无效"}, status_code=400)
    with _conn() as c:
        u = c.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not u:
            return JSONResponse({"ok": False, "msg": "用户不存在"}, status_code=404)
        uid = u["id"]
    closed = 0
    for ws in list(ws_clients.get(uid, [])):
        try:
            await ws.close()
            closed += 1
        except Exception:
            pass
    st = _user_states.get(uid)
    if st:
        st.logged_in   = False
        st.auto_trading = False
        for _task in [st.trading_task, st.account_sync_task, st.ws_task,
                      st.kline_task, st.price_poll_task, st.user_data_task,
                      getattr(st, '_heartbeat_task', None),
                      getattr(st, '_command_task', None)]:
            if _task and not _task.done():
                _task.cancel()
        st.trading_task = st.account_sync_task = st.ws_task = None
        st.kline_task = st.price_poll_task = st.user_data_task = None
    _user_states.pop(uid, None)
    _circuit.pop(uid, None)
    _sym_locks.pop(uid, None)
    _open_pos_lock.pop(uid, None)
    _leverage_cache.pop(uid, None)
    _guardian_closing.pop(uid, None)
    _close_cooldowns.pop(uid, None)
    _pos_trackers.pop(uid, None)
    _opt_result.pop(uid, None)
    if uid in ws_clients and not ws_clients[uid]:
        ws_clients.pop(uid, None)
    return {"ok": True, "msg": f"用户 {username} 已踢下线，关闭 {closed} 个连接"}

@app.delete(R("/api/admin/delete-license/{code}"))
async def admin_delete_license(code: str, user=Depends(get_admin_user)):
    """删除未使用的授权码"""
    from db import _conn
    with _conn() as c:
        row = c.execute("SELECT used_by FROM licenses WHERE code=?", (code,)).fetchone()
        if not row:
            return JSONResponse({"ok": False, "msg": "授权码不存在"}, status_code=404)
        if row["used_by"]:
            return JSONResponse({"ok": False, "msg": "授权码已被使用，无法删除"}, status_code=400)
        c.execute("DELETE FROM licenses WHERE code=?", (code,))
    return {"ok": True, "msg": f"授权码 {code} 已删除"}

# ─────────────────────────────────────────────
# 旧版私钥登录（改为需要 JWT，私钥绑定到用户账号）
# ─────────────────────────────────────────────
class LoginRequest(BaseModel):
    user: str        # 主账户钉包地址
    signer: str      # API 钉包地址
    private_key: str # API 钉包私钥

@app.post(R("/api/auth/login"))
async def login(req: LoginRequest, user=Depends(get_current_user)):
    uid  = int(user["sub"])
    st   = get_user_state(uid)
    _user   = req.user.strip()
    signer = req.signer.strip()
    pk     = req.private_key.strip()
    if not _user or not signer or not pk:
        return JSONResponse({"ok": False, "error": "三个字段均不能为空"}, status_code=400)

    try:
        acct = Account.from_key(pk)
        if acct.address.lower() != signer.lower():
            return JSONResponse({"ok": False, "error": f"私钥不对应 API 钉包地址\n私钥对应: {acct.address}\n您填入: {signer}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"私钥格式错误: {e}"}, status_code=400)

    from security import set_user_key, clear_user_key
    st.user   = _user
    st.signer = signer
    set_user_key(uid, pk)

    bal, bal_raw = await aster_get_raw("/fapi/v3/balance", auth=True, user_id=uid)
    if bal is None:
        clear_user_key(uid)
        st.user = st.signer = ""
        return JSONResponse({"ok": False, "error": f"登录失败 (AsterDex原始响应): {bal_raw}"}, status_code=401)

    usdt_balance = 0.0
    usdt_avail   = 0.0
    if isinstance(bal, list):
        for b in bal:
            if b.get("asset") == "USDT":
                usdt_balance = float(b.get("balance", 0))
                usdt_avail   = float(b.get("availableBalance", 0))
                break

    st.logged_in = True
    st.balance   = usdt_balance
    st.available = usdt_avail

    await sync_account(uid)
    rebuild_tracker_from_positions(st, uid=uid)
    await reconcile_positions(uid)

    # 启动该用户的后台任务
    if st.account_sync_task is None or st.account_sync_task.done():
        st.account_sync_task = asyncio.create_task(account_sync_loop(uid))
    if st.ws_task is None or st.ws_task.done():
        st.ws_task = asyncio.create_task(market_ws_loop(uid))
    if st.price_poll_task is None or st.price_poll_task.done():
        st.price_poll_task = asyncio.create_task(market_poll_loop(uid))
    if st.user_data_task is None or st.user_data_task.done():
        st.user_data_task = asyncio.create_task(user_data_stream_loop(uid))
    if alerting.is_user_enabled(uid):
        _hb_task = getattr(st, '_heartbeat_task', None)
        if _hb_task is None or _hb_task.done():
            st._heartbeat_task = asyncio.create_task(alerting.heartbeat_loop(lambda: {
                "logged_in": st.logged_in,
                "balance": st.balance,
                "positions": st.positions,
                "daily_pnl": st.perf.get("daily_pnl", 0),
            }, uid=uid))
        _cmd_task = getattr(st, '_command_task', None)
        if _cmd_task is None or _cmd_task.done():
            async def _set_trading(active: bool, _uid=uid, _st=st):
                _st.auto_trading = active
                if active and (not _st.trading_task or _st.trading_task.done()):
                    _st.trading_task = asyncio.create_task(hft_trading_loop(_uid))
                elif not active and _st.trading_task and not _st.trading_task.done():
                    _st.trading_task.cancel()
            st._command_task = asyncio.create_task(alerting.command_loop(lambda: {
                "logged_in": st.logged_in,
                "balance": st.balance,
                "available": st.available,
                "positions": st.positions,
                "daily_pnl": st.perf.get("daily_pnl", 0),
                "total_pnl": st.perf.get("total_pnl", 0),
                "wins": st.perf.get("wins", 0),
                "total_trades": st.perf.get("total_trades", 0),
                "auto_trading": st.auto_trading,
            }, _set_trading, uid=uid))

    active_syms_login = st.settings.get("active_symbols",
                         [st.settings.get("symbol", "BTCUSDT")])
    for _sym in active_syms_login:
        asyncio.create_task(refresh_klines(_sym, "1m", 200))
    if st.kline_task is None or st.kline_task.done():
        st.kline_task = asyncio.create_task(kline_refresh_loop(uid))

    async def _delayed_status():
        await asyncio.sleep(2)
        await broadcast("trading_status", {"active": st.auto_trading}, user_id=uid)
    asyncio.create_task(_delayed_status())

    await broadcast("account_update", {
        "logged_in":   True,
        "balance":     st.balance,
        "available":   st.available,
        "positions":   st.positions,
        "open_orders": st.open_orders,
    }, user_id=uid)

    # 保存 wallet/signer/加密私钥 到 user_configs，下次登录自动填入
    try:
        _epk = encrypt_pk(uid, pk)
        save_user_config(uid, wallet_address=_user, signer_address=signer, encrypted_pk=_epk)
    except Exception as _e:
        logger.warning(f"保存凭据失败: {_e}")

    return {
        "ok":      True,
        "balance": st.balance,
        "available": st.available,
        "wallet":  st.user,
        "message": f"登录成功 ✅ | 主钉包: {st.user[:8]}...",
    }

@app.get(R("/api/auth/saved-credentials"))
async def get_saved_credentials(user=Depends(get_current_user)):
    """返回该账号上次登录时保存的全部凭据（私钥解密后返回）"""
    uid = int(user["sub"])
    try:
        cfg = get_user_config(uid)
        if cfg.get("wallet_address"):
            pk_plain = ""
            if cfg.get("encrypted_pk"):
                try:
                    pk_plain = decrypt_pk(uid, cfg["encrypted_pk"])
                except Exception:
                    pass
            return {
                "ok": True,
                "user": cfg["wallet_address"],
                "signer": cfg.get("signer_address") or "",
                "private_key": pk_plain,
            }
    except Exception as _e:
        logger.warning(f"读取凭据失败: {_e}")
    return {"ok": False}

# (trading logout merged into /api/auth/logout above)

class TestOrderRequest(BaseModel):
    symbol: str = "BTCUSDT"
    side: str = "BUY"

@app.post(R("/api/trading/test_order"))
async def test_order(req: TestOrderRequest, user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    if not st.logged_in:
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
    }, user_id=uid)
    if result is None:
        return JSONResponse({"ok": False, "error": "下单请求失败"}, status_code=500)
    if isinstance(result, dict) and result.get("code") and result["code"] < 0:
        return JSONResponse({"ok": False, "error": f"交易所拒绝: {result.get('msg','')}"}, status_code=400)
    logger.info(f"测试下单 {side} {symbol} qty={qty} -> {result}")
    return {"ok": True, "result": result, "qty": qty, "price": cur_price}

@app.post(R("/api/trading/start"))
async def start_trading(user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    if not st.logged_in:
        return JSONResponse({"ok": False, "error": "请先登录"}, status_code=401)
    if st.auto_trading:
        return {"ok": True, "message": "已在运行"}
    st.auto_trading = True
    st.trading_task = asyncio.create_task(hft_trading_loop(uid))
    return {
        "ok": True,
        "message": "HFT 已启动",
        "symbol": st.settings.get("symbol", "BTCUSDT"),
    }

@app.post(R("/api/trading/reset_daily"))
async def reset_daily_pnl(user=Depends(get_current_user)):
    """手动重置今日亏损计数，解除日亏损熔断"""
    uid = int(user["sub"]); st = get_user_state(uid)
    old = st.perf.get("daily_pnl", 0)
    st.perf["daily_pnl"] = 0.0
    st.perf["daily_pnl_pct"] = 0.0
    st.perf["_last_date"] = datetime.now().strftime("%Y-%m-%d")
    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
        "text": f"🔄 日亏损已手动重置（原值 ${abs(old):.2f}），熔断解除", "level": "warn"}, user_id=uid)
    await broadcast("performance", {**st.perf,
        "win_rate": round(st.perf["wins"]/st.perf["total_trades"]*100,1) if st.perf["total_trades"] else 0}, user_id=uid)
    logger.info(f"手动重置日亏损: {old:.2f} -> 0")
    return {"ok": True, "message": f"日亏损已重置（原 ${abs(old):.2f}）"}

@app.post(R("/api/trading/stop"))
async def stop_trading(user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    st.auto_trading = False
    if st.trading_task and not st.trading_task.done():
        st.trading_task.cancel()
    _t = st.perf["total_trades"]; _w = st.perf["wins"]
    await broadcast("performance", {**st.perf, "win_rate": round(_w/_t*100,1) if _t else 0}, user_id=uid)
    await broadcast("trading_status", {"active": False}, user_id=uid)
    return {"ok": True, "message": "已停止"}

@app.get(R("/api/trading/status"))
async def trading_status(user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    t = st.perf["total_trades"]; w = st.perf["wins"]
    kline_ready = {sym: len(kline_cache.get(sym,[])) for sym in st.settings.get("active_symbols",[st.settings.get("symbol","BTCUSDT")])}
    return {
        "ok": True,
        "logged_in":      st.logged_in,
        "auto_trading":   st.auto_trading,
        "balance":        st.balance,
        "available":      st.available,
        "positions":      st.positions,
        "open_orders":    st.open_orders,
        "performance":    {**st.perf, "win_rate": round(w/t*100,1) if t else 0},
        "settings":       st.settings,
        "symbol_settings": st.settings.get("symbol_settings", {}),
        "market_prices":  {k:v for k,v in st.market_prices.items() if not k.endswith("USDT")},
        "kline_ready":    kline_ready,
        "ws_clients":     sum(len(v) for v in ws_clients.values()),
        "uptime_secs":    int(time.time() - _START_TIME),
    }

@app.post(R("/api/settings"))
async def save_settings(body: dict, user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    old_symbol  = st.settings.get("symbol", "BTCUSDT")
    old_actives = set(st.settings.get("active_symbols", [old_symbol]))
    _ALLOWED_SETTINGS = {
        "strategy", "symbol", "leverage", "trade_size_usd", "min_confidence",
        "stop_loss_pct", "take_profit_pct", "enable_long", "enable_short",
        "max_open_positions", "max_daily_loss_usd", "cancel_on_reverse",
        "hft_interval_ms", "hft_mode", "max_position_usd", "cooldown_secs",
        "size_mode", "size_pct", "active_symbols", "kline_interval",
        "ema_fast", "ema_slow", "ema_long",
        "macd_fast", "macd_slow", "macd_signal",
        "rsi_period", "rsi_oversold", "rsi_overbought",
        "trailing_stop", "symbol_settings",
    }
    filtered = {k: v for k, v in body.items() if k in _ALLOWED_SETTINGS}
    st.settings.update(filtered)
    new_symbol  = st.settings.get("symbol", "BTCUSDT")
    new_actives = set(st.settings.get("active_symbols", [new_symbol]))
    if new_symbol != old_symbol:
        asyncio.create_task(refresh_klines(new_symbol, "1m", 200))
        logger.info(f"📊 symbol切换 {old_symbol}→{new_symbol}，重新拉取K线")
    added = new_actives - old_actives
    if added:
        for sym in added:
            asyncio.create_task(refresh_klines(sym, "1m", 200))
            logger.info(f"📊 新增币种 {sym}，拉取K线")
        if st.ws_task and not st.ws_task.done():
            st.ws_task.cancel()
        st.ws_task = asyncio.create_task(market_ws_loop(uid))
        if st.price_poll_task and not st.price_poll_task.done():
            st.price_poll_task.cancel()
        st.price_poll_task = asyncio.create_task(market_poll_loop(uid))
        logger.info(f"📡 active_symbols新增{added}，重启行情WS+价格轮询")
    save_user_settings(uid, st.settings, st.perf)
    return {"ok": True}

@app.get(R("/api/trading/logs"))
async def get_logs(limit: int = 500, user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    return {"logs": st.trade_logs[:limit], "performance": st.perf}

def _compute_indicators(symbol: str, _st=None) -> dict:
    """通用指标计算，支持任意symbol"""
    _st = _st or state
    s         = _st.settings
    _sym_override2 = s.get("symbol_settings", {}).get(symbol, {})
    sym_cfg   = {**s, **_sym_override2} if _sym_override2 else s
    sym_short = symbol.replace("USDT", "")
    klines    = kline_cache.get(symbol, [])
    min_conf  = sym_cfg.get("min_confidence", s.get("min_confidence", 0.70))
    n = len(klines)

    if n < 65:
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
    obi         = signal_engine._obi(sym_short, _st.orderbooks)
    adx         = signal_engine._adx(highs, lows, closes)

    raw_side, raw_conf, scores = signal_engine.compute(klines, sym_short, _st.orderbooks)
    side, conf, block_reason = signal_engine.generate(sym_cfg, sym_short, symbol=symbol)

    sl_pct       = sym_cfg.get("stop_loss_pct", s.get("stop_loss_pct", 0.005))
    tp_pct       = sym_cfg.get("take_profit_pct", s.get("take_profit_pct", 0.008))
    rr           = round((tp_pct - 0.001) / (sl_pct + 0.001), 2)
    market_state = scores.get("_market", "ranging" if adx < 10 else "trending")
    has_position = any(p["symbol"] == symbol for p in _st.positions)
    _supertrend = signal_engine._supertrend(highs, lows, closes)

    return {
        "ready":        n >= 65,
        "bars":         n,
        "symbol":       symbol,
        "rsi":          round(rsi, 2),
        "macd":         {"macd": round(m,6), "signal": round(sv,6), "hist": round(hist,6)},
        "ema":          {"fast": round(ef,2), "slow": round(es_,2), "long": round(el,2)},
        "ob_imbalance": round(obi, 4),
        "supertrend":   _supertrend,
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

@app.get(R("/api/trading/indicators"))
async def get_indicators(symbol: str = "", user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    sym = symbol or st.settings.get("symbol", "BTCUSDT")
    return _compute_indicators(sym, st)

@app.get(R("/api/trading/indicators_all"))
async def get_indicators_all(user=Depends(get_current_user)):
    """批量返回所有启用币种的指标"""
    uid = int(user["sub"]); st = get_user_state(uid)
    syms = st.settings.get("active_symbols", [st.settings.get("symbol","BTCUSDT")])
    return {"symbols": {sym: _compute_indicators(sym, st) for sym in syms}}

@app.post(R("/api/settings/symbol"))
async def save_symbol_settings(body: dict, user=Depends(get_current_user)):
    """保存单个币种的独立策略参数"""
    uid = int(user["sub"]); st = get_user_state(uid)
    symbol = body.get("symbol")
    params = body.get("params", {})
    if not symbol:
        return {"ok": False, "error": "缺少symbol"}
    ss = st.settings.setdefault("symbol_settings", {})
    ss[symbol] = params
    save_user_settings(uid, st.settings, st.perf)
    return {"ok": True, "symbol": symbol, "params": ss[symbol]}

# ─────────────────────────────────────────────
# 回测接口
# ─────────────────────────────────────────────
class BacktestRequest(BaseModel):
    symbol:        str   = "BTCUSDT"
    interval:      str   = "1m"
    limit:         int   = 1000          # 最多拉取多少根K线
    min_confidence: float = 0.65
    stop_loss_pct:  float = 0.005
    take_profit_pct: float = 0.008
    hft_mode:      str   = "balanced"
    enable_long:   bool  = True
    enable_short:  bool  = True
    trade_size_usd: float = 10.0
    leverage:      int   = 5

@app.post(R("/api/backtest"))
async def run_backtest(req: BacktestRequest, user=Depends(get_current_user)):
    """
    历史回测：拉取历史K线 → 逐根跑信号引擎 → 模拟开平仓 → 返回报告
    """
    uid = int(user["sub"])

    # 拉取历史K线（最多3000根，防止超时）
    limit = min(int(req.limit), 3000)
    data = await fetch_klines_for_backtest(req.symbol, req.interval, limit)
    if not data or len(data) < 65:
        return JSONResponse({"ok": False, "error": f"K线数据获取失败或不足: {len(data) if data else 0}根，需要≥65根。请检查交易对是否正确。"}, status_code=400)

    sym_short = req.symbol.replace("USDT", "")
    sim_cfg = {
        "min_confidence":  req.min_confidence,
        "stop_loss_pct":   req.stop_loss_pct,
        "take_profit_pct": req.take_profit_pct,
        "hft_mode":        req.hft_mode,
        "enable_long":     req.enable_long,
        "enable_short":    req.enable_short,
    }
    FEE = 0.0005  # 单边手续费

    def _do_backtest():
        """CPU密集循环，通过run_in_executor卸到线程池"""
        # 预计算全量信号，避免每根K线重复计算所有指标（O(N²)→O(N)）
        _signals = _precompute_signals(data, sym_short)
        trades       = []
        equity_curve = []
        equity       = 0.0
        position     = None
        max_equity   = None
        max_drawdown = 0.0

        for i in range(65, len(data)):
            candle = data[i]
            hi     = float(candle[2])
            lo     = float(candle[3])
            close  = float(candle[4])
            ts_str = datetime.utcfromtimestamp(int(candle[0]) / 1000).strftime("%m-%d %H:%M")

            # ── 持仓中检查止盈止损 ──
            if position:
                exit_price = exit_reason = None
                if position["side"] == "BUY":
                    if lo <= position["sl"]:   exit_price = position["sl"];  exit_reason = "止损"
                    elif hi >= position["tp"]: exit_price = position["tp"]; exit_reason = "止盈"
                else:
                    if hi >= position["sl"]:   exit_price = position["sl"];  exit_reason = "止损"
                    elif lo <= position["tp"]: exit_price = position["tp"]; exit_reason = "止盈"
                if exit_price:
                    sz = position["sz"]; entry = position["entry"]
                    gross = (exit_price - entry) * sz if position["side"] == "BUY" else (entry - exit_price) * sz
                    pnl = round(gross - sz * entry * FEE - sz * exit_price * FEE, 4)
                    equity = round(equity + pnl, 4)
                    trades.append({"open_ts": position["open_ts"], "close_ts": ts_str,
                                   "side": position["side"], "entry": round(entry, 4),
                                   "exit": round(exit_price, 4), "pnl": pnl,
                                   "reason": exit_reason, "equity": equity})
                    if max_equity is not None:
                        max_drawdown = max(max_drawdown, max_equity - equity)
                    if max_equity is None or equity > max_equity: max_equity = equity
                    equity_curve.append({"ts": ts_str, "equity": equity})
                    position = None
                else:
                    # 持仓浮亏也计入max_drawdown
                    if position["side"] == "BUY":
                        float_pnl = (close - position["entry"]) * position["sz"]
                    else:
                        float_pnl = (position["entry"] - close) * position["sz"]
                    float_equity = equity + float_pnl
                    if max_equity is not None:
                        max_drawdown = max(max_drawdown, max_equity - float_equity)
                    equity_curve.append({"ts": ts_str, "equity": equity})
                continue

            # ── 无持仓：查预计算信号 ──
            side, conf = _signals[i]
            if side == "HOLD" or conf < sim_cfg["min_confidence"]:
                equity_curve.append({"ts": ts_str, "equity": equity}); continue
            if side == "BUY"  and not sim_cfg.get("enable_long",  True):
                equity_curve.append({"ts": ts_str, "equity": equity}); continue
            if side == "SELL" and not sim_cfg.get("enable_short", True):
                equity_curve.append({"ts": ts_str, "equity": equity}); continue
            net_tp = sim_cfg["take_profit_pct"] - 2 * FEE
            net_sl = sim_cfg["stop_loss_pct"]   + 2 * FEE
            rr_needed = {"conservative": 1.8, "balanced": 1.0, "aggressive": 0.2, "turbo": 0.15}.get(sim_cfg["hft_mode"], 1.0)
            if net_sl > 0 and (net_tp / net_sl) < rr_needed:
                equity_curve.append({"ts": ts_str, "equity": equity}); continue
            sz = req.trade_size_usd * req.leverage / close
            sl = close * (1 - req.stop_loss_pct)  if side == "BUY" else close * (1 + req.stop_loss_pct)
            tp = close * (1 + req.take_profit_pct) if side == "BUY" else close * (1 - req.take_profit_pct)
            position = {"side": side, "entry": close, "sz": sz, "sl": sl, "tp": tp, "open_ts": ts_str}
            equity_curve.append({"ts": ts_str, "equity": equity})
            continue  # 开仓当根不再检查止损，下一根才有效

        # 强平剩余持仓
        if position:
            last = float(data[-1][4]); sz = position["sz"]; entry = position["entry"]
            gross = (last - entry) * sz if position["side"] == "BUY" else (entry - last) * sz
            pnl = round(gross - sz * entry * FEE - sz * last * FEE, 4)
            equity = round(equity + pnl, 4)
            trades.append({"open_ts": position["open_ts"], "close_ts": "回测结束",
                           "side": position["side"], "entry": round(entry, 4),
                           "exit": round(last, 4), "pnl": pnl, "reason": "强平", "equity": equity})

        return trades, equity_curve, max_drawdown

    loop = asyncio.get_running_loop()
    trades, equity_curve, max_drawdown = await loop.run_in_executor(None, _do_backtest)

    total        = len(trades)
    wins         = sum(1 for t in trades if t["pnl"] > 0)
    losses       = total - wins
    win_rate     = round(wins / total * 100, 1) if total > 0 else 0
    total_pnl    = round(sum(t["pnl"] for t in trades), 4)
    win_pnl_sum  = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    loss_pnl_sum = abs(sum(t["pnl"] for t in trades if t["pnl"] <= 0))
    avg_win      = round(win_pnl_sum  / wins   if wins   > 0 else 0, 4)
    avg_loss     = round(loss_pnl_sum / losses if losses > 0 else 0, 4)
    profit_factor = round(win_pnl_sum / loss_pnl_sum, 2) if loss_pnl_sum > 0 else (99.0 if wins > 0 else 0.0)

    step = max(1, len(equity_curve) // 200)
    return {
        "ok": True,
        "symbol":        req.symbol,
        "interval":      req.interval,
        "bars":          len(data),
        "total_trades":  total,
        "wins":          wins,
        "losses":        losses,
        "win_rate":      win_rate,
        "total_pnl":     total_pnl,
        "avg_win":       avg_win,
        "avg_loss":      avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown":  round(max_drawdown, 4),
        "trades":        trades[-50:],
        "equity_curve":  equity_curve[::step],
    }

# ─────────────────────────────────────────────
# 回测核心计算（可复用）
# ─────────────────────────────────────────────
def _precompute_signals(data: list, sym_short: str) -> list:
    """
    预计算全量信号数组，每个 bar 只算一次，供所有参数组合复用。
    返回 list[(side, conf)]，长度 == len(data)，前 65 个为 ("HOLD", 0.0)。
    把回测信号计算从 O(N²) 降为 O(N)。
    """
    signals = [("HOLD", 0.0)] * len(data)
    for i in range(65, len(data)):
        side, conf, _ = signal_engine.compute(data[:i+1], sym_short)
        signals[i] = (side, conf)
    return signals


def _run_bt_core(data: list, sym_short: str, cfg: dict, trade_size_usd: float, leverage: int,
                 signals: list = None) -> dict:
    """对给定K线数据和参数跑一次回测，返回统计摘要（不含equity_curve/trades详情）。
    signals: 预计算的信号数组（由 _precompute_signals 生成），传入时直接查表跳过重复计算。
    """
    FEE = 0.0005
    sl_pct  = cfg["stop_loss_pct"]
    tp_pct  = cfg["take_profit_pct"]
    trades       = []
    equity       = 0.0
    position     = None
    max_equity   = None
    max_drawdown = 0.0
    rr_needed = {"conservative":1.8,"balanced":1.0,"aggressive":0.2,"turbo":0.15}.get(cfg.get("hft_mode","balanced"),1.0)
    net_tp = tp_pct - 2*FEE; net_sl = sl_pct + 2*FEE
    rr_ok = net_sl <= 0 or (net_tp / net_sl) >= rr_needed  # 盈亏比预判，不满足则整组跳过

    for i in range(65, len(data)):
        candle = data[i]
        hi     = float(candle[2]); lo = float(candle[3]); close = float(candle[4])

        if position:
            exit_price = exit_reason = None
            if position["side"] == "BUY":
                if lo <= position["sl"]:  exit_price=position["sl"];  exit_reason="止损"
                elif hi >= position["tp"]: exit_price=position["tp"]; exit_reason="止盈"
            else:
                if hi >= position["sl"]:  exit_price=position["sl"];  exit_reason="止损"
                elif lo <= position["tp"]: exit_price=position["tp"]; exit_reason="止盈"
            if exit_price:
                sz=position["sz"]; entry=position["entry"]
                gross=(exit_price-entry)*sz if position["side"]=="BUY" else (entry-exit_price)*sz
                fee=sz*entry*FEE+sz*exit_price*FEE
                pnl=round(gross-fee,4)
                equity=round(equity+pnl,4)
                trades.append(pnl)
                if max_equity is not None:
                    dd=max_equity-equity; max_drawdown=max(max_drawdown,dd)
                if max_equity is None or equity>max_equity: max_equity=equity
                position=None
            else:
                float_pnl=(close-position["entry"])*position["sz"] if position["side"]=="BUY" else (position["entry"]-close)*position["sz"]
                float_eq=equity+float_pnl
                if max_equity is not None: max_drawdown=max(max_drawdown,max_equity-float_eq)
            continue

        if not rr_ok: continue  # 整组参数盈亏比不达标，跳过开仓
        # 优先使用预计算信号，没有时降级实时计算（兼容普通回测路径）
        if signals is not None:
            side, conf = signals[i]
        else:
            side, conf, _ = signal_engine.compute(data[:i+1], sym_short)
        if side=="HOLD" or conf<cfg["min_confidence"]: continue
        if side=="BUY"  and not cfg.get("enable_long",  True): continue
        if side=="SELL" and not cfg.get("enable_short", True): continue
        sz=trade_size_usd*leverage/close
        sl=close*(1-sl_pct) if side=="BUY" else close*(1+sl_pct)
        tp=close*(1+tp_pct) if side=="BUY" else close*(1-tp_pct)
        position={"side":side,"entry":close,"sz":sz,"sl":sl,"tp":tp}
        continue

    if position:
        last=float(data[-1][4]); sz=position["sz"]; entry=position["entry"]
        gross=(last-entry)*sz if position["side"]=="BUY" else (entry-last)*sz
        fee=sz*entry*FEE+sz*last*FEE
        _pnl=round(gross-fee,4)
        trades.append(_pnl)
        equity=round(equity+_pnl,4)

    total=len(trades); wins=sum(1 for p in trades if p>0); losses=total-wins
    win_pnl=sum(p for p in trades if p>0); loss_pnl=abs(sum(p for p in trades if p<=0))
    profit_factor=round(win_pnl/loss_pnl,2) if loss_pnl>0 else (99.0 if wins>0 else 0.0)
    score = profit_factor * (wins/total if total>0 else 0) - max_drawdown * 0.1
    total_pnl = round(sum(trades),4)
    avg_pnl   = round(total_pnl / total, 4) if total > 0 else 0.0
    avg_win   = round(win_pnl  / wins,   4) if wins   > 0 else 0.0
    avg_loss  = round(loss_pnl / losses, 4) if losses > 0 else 0.0
    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins/total*100,1) if total>0 else 0,
        "total_pnl": total_pnl,
        "avg_pnl":   avg_pnl,
        "avg_win":   avg_win,
        "avg_loss":  avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown": round(max_drawdown,4),
        "score": round(score,4),
    }

@app.post(R("/api/backtest/optimize"))
async def run_backtest_optimize(req: BacktestRequest, user=Depends(get_current_user)):
    """
    参数网格搜索：对多组 stop_loss / take_profit / min_confidence / hft_mode 组合跑回测，
    找出综合评分最高的参数组合并返回推荐，支持一键应用。
    """
    uid = int(user["sub"])
    limit = min(int(req.limit), 3000)
    data = await fetch_klines_for_backtest(req.symbol, req.interval, limit)
    if not data or len(data) < 65:
        return JSONResponse({"ok":False,"error":f"K线数据获取失败或不足: {len(data) if data else 0}根。请检查交易对是否正确。"}, status_code=400)

    sym_short = req.symbol.replace("USDT","")

    # 搜索空间（4×4×3×2 = 96 种组合）
    sl_list   = [0.003, 0.005, 0.008, 0.012]
    tp_list   = [0.006, 0.010, 0.015, 0.020]
    conf_list = [0.60,  0.65,  0.70]
    mode_list = ["balanced", "aggressive"]

    # 构建所有参数组合
    combos = [
        {"stop_loss_pct": sl, "take_profit_pct": tp, "min_confidence": conf,
         "hft_mode": mode, "enable_long": req.enable_long, "enable_short": req.enable_short}
        for sl in sl_list for tp in tp_list if tp > sl
        for conf in conf_list for mode in mode_list
    ]

    # 当前参数配置（用于对比）
    current_cfg = {
        "stop_loss_pct":   req.stop_loss_pct,
        "take_profit_pct": req.take_profit_pct,
        "min_confidence":  req.min_confidence,
        "hft_mode":        req.hft_mode,
        "enable_long":     req.enable_long,
        "enable_short":    req.enable_short,
    }

    # 所有计算全部卸到线程池，避免阻塞事件循环
    def _grid_search():
        # 预计算一次全量信号数组，96组参数复用，O(N²)→O(N+96N)
        precomp = _precompute_signals(data, sym_short)
        out = []
        for cfg in combos:
            stats = _run_bt_core(data, sym_short, cfg, req.trade_size_usd, req.leverage, signals=precomp)
            if stats["total_trades"] >= 3:
                out.append({**cfg, **stats})
        cur_stats = _run_bt_core(data, sym_short, current_cfg, req.trade_size_usd, req.leverage, signals=precomp)
        return out, cur_stats

    loop = asyncio.get_running_loop()
    results, current_stats = await loop.run_in_executor(None, _grid_search)

    if not results:
        return {"ok":False,"error":"所有参数组合交易次数不足（<3笔），请切换更短周期或更多K线数量"}

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "ok":            True,
        "symbol":        req.symbol,
        "interval":      req.interval,
        "bars":          len(data),
        "tested":        len(results),
        "best":          results[0],
        "top3":          results[:3],
        "current_stats": {**current_cfg, **current_stats},
    }

@app.post(R("/api/backtest/apply"))
async def backtest_apply_params(body: dict, user=Depends(get_current_user)):
    """将回测推荐参数直接写入用户策略设置"""
    uid = int(user["sub"]); st = get_user_state(uid)
    apply_keys = [
        "stop_loss_pct", "take_profit_pct", "min_confidence", "hft_mode",
        "trade_size_usd", "leverage",
        "enable_long", "enable_short", "trade_direction",
    ]
    updated = {}
    for k in apply_keys:
        if k in body:
            st.settings[k] = body[k]
            updated[k] = body[k]
    if not updated:
        return {"ok":False,"error":"无有效参数"}
    save_user_settings(uid, st.settings, st.perf)
    await broadcast("settings_updated", st.settings, user_id=uid)
    return {"ok":True,"applied":updated}

@app.post(R("/api/trading/close_position"))
async def api_close_position(body: dict, user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    symbol = body.get("symbol", st.settings.get("symbol","BTCUSDT"))
    _gc_man = _get_guardian_closing(uid)
    _pt_man = get_pos_tracker(uid)
    if symbol in _gc_man:
        return {"ok": False, "result": None, "error": "平仓进行中，请勿重复操作"}
    _gc_man.add(symbol)
    _te2 = dict(_pt_man.entries.get(symbol, {}))  # 平仓前快照
    price  = st.market_prices.get(symbol.replace("USDT","")) or st.market_prices.get(symbol) or 0
    # price为0时从持仓mark_price或entry_price补全（避免用0价格导致盈亏计算错乱）
    if not price or price <= 0:
        _pos_info = next((p for p in st.positions if p["symbol"] == symbol), None)
        if _pos_info:
            price = _pos_info.get("mark_price") or _pos_info.get("entry_price") or 0
    if not price or price <= 0:
        # 最后兜底：REST实时拉取
        try:
            _td = await aster_get("/fapi/v3/ticker/price", {"symbol": symbol})
            if _td and _td.get("price"):
                price = float(_td["price"])
        except Exception:
            pass
    try:
        await cancel_all_orders(symbol, user_id=uid)  # 先撤单再平仓
        result = await close_position(symbol, user_id=uid)
        if result:
            tracker_sz = _te2.get("sz", 0)
            # tracker_sz为0时从持仓数量补全
            if not tracker_sz or tracker_sz <= 0:
                _pos_info2 = next((p for p in st.positions if p["symbol"] == symbol), None)
                if _pos_info2:
                    tracker_sz = _pos_info2.get("size", 0)
            _log_trade(symbol, "CLOSE", price, tracker_sz, "手动平仓", 1.0, result, open_ctx=_te2.get("open_ctx"), uid=uid)
            _pt_man.clear(symbol)
        return {"ok": bool(result), "result": result}
    finally:
        _gc_man.discard(symbol)

@app.post(R("/api/optimize/run"))
async def api_run_optimize(user=Depends(get_current_user)):
    """手动触发参数优化"""
    uid = int(user["sub"]); st = get_user_state(uid)
    result = await run_auto_optimize(force=True, uid=uid)
    return {"ok": True, **result}

@app.get(R("/api/optimize/result"))
async def api_get_opt_result(user=Depends(get_current_user)):
    """获取最新优化结果"""
    uid = int(user["sub"]); st = get_user_state(uid)
    closed_count = len([t for t in st.trade_logs if t.get("side") == "CLOSE"])
    opt = _opt_result.get(uid, {})
    return {
        "ok": True,
        "result": opt,
        "closed_trades": closed_count,
        "min_required": MIN_TRADES_FOR_OPT,
        "ready": closed_count >= MIN_TRADES_FOR_OPT,
    }

@app.post(R("/api/optimize/apply"))
async def api_apply_opt(user=Depends(get_current_user)):
    """将最优参数自动应用到当前策略设置"""
    uid = int(user["sub"]); st = get_user_state(uid)
    opt = _opt_result.get(uid, {})
    if not opt.get("best"):
        return {"ok": False, "error": "暂无优化结果，请先运行优化"}
    best = opt["best"]
    st.settings.update(best)
    save_user_settings(uid, st.settings, st.perf)
    await broadcast("settings_updated", st.settings, user_id=uid)
    await broadcast("log", {"ts": datetime.now().strftime("%H:%M:%S"),
        "text": f"🔁 已自动应用最优参数：conf={best['min_confidence']} sl={best['stop_loss_pct']*100:.1f}% tp={best['take_profit_pct']*100:.1f}%"}, user_id=uid)
    return {"ok": True, "applied": best}

@app.get(R("/api/strategy/recommendations"))
async def api_strategy_recommendations(user=Depends(get_current_user)):
    """根据当前交易数据提供策略优化建议"""
    uid = int(user["sub"]); st = get_user_state(uid)
    closed = [t for t in st.trade_logs if t.get("side") == "CLOSE" and t.get("pnl") is not None]

    if len(closed) < 10:
        return {
            "ok": True,
            "recommendations": [],
            "reason": f"数据不足，需要至少10笔平仓交易，当前{len(closed)}笔"
        }

    recommendations = []

    win_rate = st.perf.get("win_rate", 0)
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
        peak = 0
        max_drawdown = 0
        for v in cumsum:
            if v > peak:
                peak = v
            dd = v - peak
            if dd < max_drawdown:
                max_drawdown = dd  # 最大回撤（负数）
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
            "min_confidence": st.settings.get("min_confidence", 0.70),
            "stop_loss_pct": st.settings.get("stop_loss_pct", 0.005),
            "take_profit_pct": st.settings.get("take_profit_pct", 0.008),
            "leverage": st.settings.get("leverage", 2),
            "hft_mode": st.settings.get("hft_mode", "balanced"),
        }
    }

@app.get(R("/api/account/summary"))
async def account_summary(user=Depends(get_current_user)):
    """仪表盘聚合接口：一次返回账户+绩效+最近交易+行情"""
    uid = int(user["sub"]); st = get_user_state(uid)
    t = st.perf["total_trades"]; w = st.perf["wins"]
    active_syms = st.settings.get("active_symbols", [st.settings.get("symbol","BTCUSDT")])
    return {
        "ok": True,
        "account": {
            "logged_in":  st.logged_in,
            "balance":    st.balance,
            "available":  st.available,
            "used_margin": round(st.balance - st.available, 4),
            "positions":  st.positions,
            "open_orders": st.open_orders,
            "user":       st.user[:12] + "..." if len(st.user) > 12 else st.user,
        },
        "trading": {
            "active": st.auto_trading,
            "active_symbols": active_syms,
            "hft_mode": st.settings.get("hft_mode", "balanced"),
            "leverage": st.settings.get("leverage", 2),
            "trade_size_usd": st.settings.get("trade_size_usd", 10),
        },
        "performance": {**st.perf, "win_rate": round(w/t*100,1) if t else 0},
        "recent_trades": st.trade_logs[:20],
        "market_prices": {k: v for k, v in st.market_prices.items() if any(k in sym for sym in active_syms)},
        "kline_bars": {sym: len(kline_cache.get(sym, [])) for sym in active_syms},
        "uptime_secs": int(time.time() - _START_TIME),
    }

@app.post(R("/api/trading/cancel_orders"))
async def api_cancel_orders(body: dict, user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    symbol = body.get("symbol", st.settings.get("symbol","BTCUSDT"))
    result = await cancel_all_orders(symbol, user_id=uid)
    return {"ok": True, "result": result}

_ENV_FILE = Path(__file__).parent / ".env"

def _read_env_file() -> dict:
    """读取.env文件为字典"""
    env = {}
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

def _write_env_file(env: dict):
    """将字典写回.env文件"""
    lines = []
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k not in env:
                    lines.append(line)
            else:
                lines.append(line)
    for k, v in env.items():
        lines.append(f"{k}={v}")
    _ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

@app.get(R("/api/telegram/config"))
async def get_telegram_config(user=Depends(get_current_user)):
    """获取当前用户的 Telegram 配置（token 脱敏）"""
    uid = int(user["sub"])
    cfg = get_user_config(uid)
    token   = cfg.get("tg_token", "") or ""
    chat_id = cfg.get("tg_chat_id", "") or ""
    return {
        "ok": True,
        "token": token[:10] + "..." + token[-4:] if len(token) > 14 else ("已配置" if token else ""),
        "token_set": bool(token),
        "chat_id": chat_id,
        "enabled": bool(token and chat_id),
    }

@app.post(R("/api/telegram/config"))
async def save_telegram_config(body: dict, user=Depends(get_current_user)):
    """保存当前用户的 Telegram 配置到数据库"""
    uid = int(user["sub"])
    token   = body.get("token", "").strip()
    chat_id = body.get("chat_id", "").strip()
    if not token or not chat_id:
        return JSONResponse({"ok": False, "error": "token和chat_id均不能为空"}, status_code=400)
    if len(token) > 128 or len(chat_id) > 32:
        return JSONResponse({"ok": False, "error": "token或chat_id格式不正确（长度超限）"}, status_code=400)
    save_user_config(uid, tg_token=token, tg_chat_id=chat_id)
    logger.info(f"✅ uid={uid} Telegram配置已保存")
    return {"ok": True, "message": "Telegram配置已保存"}

@app.post(R("/api/telegram/test"))
async def test_telegram(user=Depends(get_current_user)):
    """向当前用户自己的 bot 发送测试消息"""
    uid = int(user["sub"])
    ok = await alerting.send_to_user(uid, "🔔 <b>AsterDex HFT 测试消息</b>\nTelegram通知配置成功 ✅")
    if ok:
        return {"ok": True, "message": "测试消息已发送，请查看Telegram"}
    return JSONResponse({"ok": False, "error": "发送失败，请先在设置页填写正确的 token 和 chat_id"}, status_code=400)

@app.get(R("/api/market/orderbook"))
async def get_orderbook(symbol: str = "BTCUSDT", user=Depends(get_current_user)):
    uid = int(user["sub"]); st = get_user_state(uid)
    sym = symbol.replace("USDT","")
    return {"ok": True, "symbol": symbol, **st.orderbooks.get(sym, {"bids":[],"asks":[]})}

@app.get(R("/api/diagnostics"))
async def api_diagnostics(user=Depends(get_current_user)):
    """系统诊断接口 - 检查所有关键组件"""
    uid = int(user["sub"]); st = get_user_state(uid)
    recent_failed = getattr(st, '_recent_failed_orders', [])
    trade_status = "🔴 未交易" if len(st.trade_logs) == 0 else "🟡 全失败" if all(t.get("status")=="failed" for t in st.trade_logs) else "🟢 正常"
    return {
        "ok": True,
        "timestamp": datetime.now().isoformat(),
        "health": {
            "trading_status": trade_status,
            "auth": "✅" if st.logged_in else "❌",
            "market_feed": "✅" if len(st.market_prices) > 0 else "❌",
            "websocket": "✅" if ws_clients.get(uid) else "❌",
        },
        "backend": {
            "logged_in": st.logged_in,
        },
        "account": {
            "balance": st.balance,
            "available": st.available,
            "positions": len(st.positions),
            "open_orders": len(st.open_orders),
        },
        "trading": {
            "auto_trading": st.auto_trading,
            "active_symbols": st.settings.get("active_symbols", ["BTCUSDT"]),
            "leverage": st.settings.get("leverage", 2),
            "trade_size_usd": st.settings.get("trade_size_usd", 10),
        },
        "market": {
            "prices_count": len(st.market_prices),
            "orderbooks_count": len(st.orderbooks),
            "klines_symbols": list(kline_cache.keys()),
        },
        "performance": st.perf,
        "trading_diagnostics": {
            "total_attempts": len(st.trade_logs) + len(recent_failed),
            "successful": len([t for t in st.trade_logs if t.get("status") != "failed"]),
            "failed_recent": len(recent_failed),
            "recent_failures": [
                {
                    "time": t.get("time"),
                    "symbol": t.get("symbol"),
                    "side": t.get("side"),
                    "reason": t.get("result_raw", "unknown")
                } for t in recent_failed[:10]
            ]
        },
        "recommendations": [
            ("✅ 系统正常" if st.logged_in else "❌ 需要登录"),
            ("✅ 行情连接" if len(st.market_prices) > 0 else "⚠️ 行情未连接"),
            (f"✅ 交易正常: {len([t for t in st.trade_logs if t.get('status') != 'failed'])}成功，{len(recent_failed)}失败"
             if len(recent_failed) == 0 else f"⚠️ 订单失败: 检查recent_failures"),
            ("✅ 账户有持仓" if len(st.positions) > 0 else "ℹ️ 暂无持仓"),
        ]
    }

# ─────────────────────────────────────────────
# WebSocket 前端推送
# ─────────────────────────────────────────────

# 兼容旧路径：accept后立即发redirect消息然后关闭
# 避免uvicorn在Python3.14上因WS 403抛出未捕获异常崩溃
@app.websocket("/ws/frontend")
async def _ws_old_path(ws: WebSocket):
    try:
        await ws.accept()
        await ws.send_text('{"type":"redirect","msg":"wrong_prefix"}')
        await ws.close(1008)
    except Exception:
        pass

_WS_MAX_CLIENTS = 200  # 总连接上限（多用户场景适当放大）

@app.websocket(R("/ws/frontend"))
async def ws_frontend(ws: WebSocket, token: str = ""):
    await ws.accept()
    # 解析 token 获取 user_id（未登录用0）
    uid = 0
    if token:
        try:
            from auth import decode_token
            payload = decode_token(token)
            uid = int(payload.get("sub", 0))
        except Exception:
            uid = 0

    total = sum(len(v) for v in ws_clients.values())
    if total >= _WS_MAX_CLIENTS:
        try:
            await ws.close(1013)
        except Exception:
            pass
        return

    ws_clients.setdefault(uid, set()).add(ws)
    st = get_user_state(uid) if uid else state
    try:
        _t = st.perf["total_trades"]; _w = st.perf["wins"]
        init_payload = json.dumps({"type": "init", "data": {
            "logged_in":    st.logged_in,
            "balance":      st.balance,
            "available":    st.available,
            "positions":    st.positions,
            "open_orders":  st.open_orders,
            "auto_trading": st.auto_trading,
            "performance":  {**st.perf, "win_rate": round(_w/_t*100,1) if _t else 0},
            "settings":     st.settings,
            "trade_logs":   st.trade_logs[:200],
            "market_prices": {k: v for k, v in st.market_prices.items() if not k.endswith("USDT")},
        }})
        await ws.send_text(init_payload)
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=30)
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                try:
                    await ws.send_text(json.dumps({"type": "pong"}))
                except Exception:
                    break
            except WebSocketDisconnect:
                break
            except Exception:
                break
    except asyncio.CancelledError:
        pass
    except Exception:
        pass
    finally:
        if uid in ws_clients:
            ws_clients[uid].discard(ws)
            if not ws_clients[uid]:
                del ws_clients[uid]

# ─────────────────────────────────────────────
# 启动
# ─────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", os.environ.get("PORT", 8000)))
    host = os.environ.get("BACKEND_HOST", "0.0.0.0")
    print(f"[AsterDex] Starting on http://{host}:{port}", flush=True)
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        ws_ping_interval=20,
        ws_ping_timeout=30,
        timeout_keep_alive=75,
    )
