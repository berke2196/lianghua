"""
告警模块 - Telegram Bot 推送（多用户版）
每个用户配置各自的 bot token + chat_id，互相隔离。
支持：熔断触发、日亏损触发、进程宕机心跳、仓位异常、连接失败
"""

import asyncio
import logging
import os
import time
from typing import Optional, Tuple

import aiohttp

logger = logging.getLogger("alerting")

_THROTTLE_SECS = 60  # 同类消息最短间隔60s

# 防洪泛：按 (uid, key) 记录上次发送时间
_last_sent: dict = {}


def get_user_tg(uid: int) -> Tuple[str, str]:
    """从数据库读取指定用户的 tg_token / tg_chat_id，失败返回空串"""
    try:
        from db import get_user_config
        cfg = get_user_config(uid)
        return cfg.get("tg_token", "") or "", cfg.get("tg_chat_id", "") or ""
    except Exception:
        return "", ""


def is_user_enabled(uid: int) -> bool:
    token, chat_id = get_user_tg(uid)
    return bool(token and chat_id)


def is_enabled() -> bool:
    """向后兼容：检查全局 env 是否配置（lifespan command_loop 用）"""
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def _throttled(uid: int, key: str, secs: int = _THROTTLE_SECS) -> bool:
    """True 表示应跳过（太频繁）。按 uid 隔离，互不影响。"""
    k = (uid, key)
    now = time.time()
    if now - _last_sent.get(k, 0) < secs:
        return True
    _last_sent[k] = now
    return False


async def _send_telegram(text: str, token: str, chat_id: str, silent: bool = False) -> bool:
    """发送 Telegram 消息，失败不抛异常"""
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_notification": silent,
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    return True
                body = await r.text()
                logger.warning(f"Telegram发送失败 {r.status}: {body[:200]}")
                return False
    except Exception as e:
        logger.warning(f"Telegram发送异常: {e}")
        return False


async def send_to_user(uid: int, text: str, silent: bool = False) -> bool:
    """直接用 uid 查配置并发送，外部最常用的入口"""
    token, chat_id = get_user_tg(uid)
    return await _send_telegram(text, token, chat_id, silent)


# ─── 公开告警接口（所有函数都接受 uid 参数）───

async def alert_circuit_breaker(daily_pnl: float, limit: float, uid: int = 0):
    """日亏损熔断触发时告警"""
    if _throttled(uid, "circuit_breaker", 300):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        "🚨 <b>[熔断触发] AsterDex HFT 已停止</b>\n"
        f"今日亏损: <b>${abs(daily_pnl):.2f}</b>\n"
        f"设定上限: ${abs(limit):.2f}\n"
        "请登录仪表盘确认后手动重启。"
    )
    await _send_telegram(text, token, chat_id)
    logger.info(f"[告警] uid={uid} 熔断触发通知已发送 daily_pnl={daily_pnl:.2f}")


async def alert_balance_critical(available: float, uid: int = 0):
    """可用余额极低告警"""
    if _throttled(uid, "balance_critical", 600):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        "⚠️ <b>[余额警告] AsterDex HFT</b>\n"
        f"当前可用余额: <b>${available:.2f} USDT</b>\n"
        "余额极低，交易已自动停止，请及时充值。"
    )
    await _send_telegram(text, token, chat_id)


async def alert_order_failed(symbol: str, side: str, reason: str, uid: int = 0):
    """连续下单失败告警"""
    key = f"order_failed_{symbol}"
    if _throttled(uid, key, 120):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        f"❌ <b>[下单失败] {symbol}</b>\n"
        f"方向: {side}\n"
        f"原因: {reason}\n"
        "请检查API连接和账户状态。"
    )
    await _send_telegram(text, token, chat_id, silent=True)


async def alert_position_opened(symbol: str, side: str, price: float, size: float,
                                 confidence: float, uid: int = 0):
    """开仓通知（静默推送，不响铃）"""
    if _throttled(uid, f"pos_open_{symbol}", 10):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    dir_emoji = "📈" if side == "BUY" else "📉"
    text = (
        f"{dir_emoji} <b>[开仓] {symbol}</b>\n"
        f"方向: {'做多' if side=='BUY' else '做空'} | 价格: ${price:,.4f}\n"
        f"数量: {size} | 置信度: {confidence*100:.1f}%"
    )
    await _send_telegram(text, token, chat_id, silent=True)


async def alert_position_closed(symbol: str, pnl: float, reason: str, uid: int = 0):
    """平仓通知（盈亏告警）"""
    if _throttled(uid, f"pos_close_{symbol}", 10):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    emoji = "✅" if pnl >= 0 else "🔴"
    pnl_str = f"+${pnl:.4f}" if pnl >= 0 else f"-${abs(pnl):.4f}"
    text = (
        f"{emoji} <b>[平仓] {symbol}</b>\n"
        f"盈亏: <b>{pnl_str} USDT</b>\n"
        f"原因: {reason}"
    )
    await _send_telegram(text, token, chat_id, silent=(pnl >= 0))


async def alert_connection_lost(component: str, uid: int = 0):
    """WS/API连接断开告警"""
    if _throttled(uid, f"conn_lost_{component}", 300):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        f"📡 <b>[连接断开] {component}</b>\n"
        "系统正在尝试重连，请关注后续状态。"
    )
    await _send_telegram(text, token, chat_id, silent=True)


async def alert_process_heartbeat(balance: float, positions: int, daily_pnl: float,
                                   uid: int = 0):
    """每小时心跳（证明进程存活）"""
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        "💓 <b>[心跳] AsterDex HFT 运行中</b>\n"
        f"余额: ${balance:.2f} USDT\n"
        f"持仓数: {positions}\n"
        f"今日盈亏: {'+' if daily_pnl >= 0 else ''}{daily_pnl:.2f} USDT"
    )
    await _send_telegram(text, token, chat_id, silent=True)


async def alert_spike_protection(symbol: str, signal_price: float, market_price: float,
                                  deviation_pct: float, uid: int = 0):
    """插针保护触发告警"""
    if _throttled(uid, f"spike_{symbol}", 60):
        return
    token, chat_id = get_user_tg(uid)
    if not token:
        return
    text = (
        f"🛡️ <b>[插针保护] {symbol} 下单已拦截</b>\n"
        f"信号价格: ${signal_price:,.4f}\n"
        f"当前市价: ${market_price:,.4f}\n"
        f"偏离幅度: {deviation_pct:.2f}%（超出阈值）\n"
        "已跳过本次开仓，等待价格稳定。"
    )
    await _send_telegram(text, token, chat_id)


# ─── 心跳循环（后台任务，每用户独立）───

async def heartbeat_loop(get_state_fn, uid: int = 0):
    """每小时发送一次心跳。uid=0 时不发（无用户配置）。"""
    await asyncio.sleep(60)
    while True:
        try:
            if uid and is_user_enabled(uid):
                st = get_state_fn()
                if st.get("logged_in"):
                    await alert_process_heartbeat(
                        balance=st.get("balance", 0),
                        positions=len(st.get("positions", [])),
                        daily_pnl=st.get("daily_pnl", 0),
                        uid=uid,
                    )
        except Exception as e:
            logger.warning(f"心跳发送失败 uid={uid}: {e}")
        await asyncio.sleep(3600)


# ─── Telegram 命令接收循环（按用户独立轮询）───

_user_update_ids: dict = {}  # uid -> last_update_id


async def _get_updates_for(token: str, last_id: int) -> list:
    if not token:
        return []
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 20, "offset": last_id + 1, "allowed_updates": ["message"]}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status != 200:
                    return []
                data = await r.json()
                return data.get("result", [])
    except Exception:
        return []


async def command_loop(get_state_fn, set_trading_fn, uid: int = 0):
    """轮询指定用户的 Telegram 命令，支持 /status /pnl /stop /start /help"""
    if not uid:
        return
    logger.info(f"📲 Telegram命令监听已启动 uid={uid}")
    while True:
        try:
            token, chat_id = get_user_tg(uid)
            if not token or not chat_id:
                await asyncio.sleep(30)
                continue
            last_id = _user_update_ids.get(uid, 0)
            updates = await _get_updates_for(token, last_id)
            for upd in updates:
                _user_update_ids[uid] = upd["update_id"]
                msg = upd.get("message", {})
                text = msg.get("text", "").strip().lower().split("@")[0]
                chat_id_src = str(msg.get("chat", {}).get("id", ""))
                if chat_id_src != chat_id:
                    continue  # 只响应本用户配置的 chat_id
                if not text.startswith("/"):
                    continue

                st = get_state_fn()
                bal     = st.get("balance", 0)
                avail   = st.get("available", 0)
                pos     = st.get("positions", [])
                dpnl    = st.get("daily_pnl", 0)
                trading = st.get("auto_trading", False)

                if text == "/status":
                    pos_lines = ""
                    for p in pos:
                        sym  = p.get("symbol", "")
                        side = "多" if p.get("side", "") in ("BUY", "LONG") else "空"
                        size = p.get("size", p.get("positionAmt", 0))
                        upnl = p.get("unrealizedPnl", p.get("pnl", 0))
                        pos_lines += f"  • {sym} {side} {size} 未实现:{upnl:+.4f}\n"
                    pos_section = ("持仓明细:\n" + pos_lines) if pos else ""
                    dpnl_sign = "+" if dpnl >= 0 else ""
                    trading_str = "✅运行" if trading else "⏹停止"
                    reply = (
                        f"📊 <b>AsterDex HFT 状态</b>\n"
                        f"交易中: {trading_str}\n"
                        f"余额: ${bal:.2f} USDT（可用 ${avail:.2f}）\n"
                        f"持仓数: {len(pos)}\n"
                        f"{pos_section}"
                        f"今日盈亏: {dpnl_sign}{dpnl:.4f} USDT"
                    )
                    await _send_telegram(reply, token, chat_id)

                elif text == "/pnl":
                    total = st.get("total_pnl", 0)
                    wins  = st.get("wins", 0)
                    total_trades = st.get("total_trades", 0)
                    wr = round(wins / total_trades * 100, 1) if total_trades else 0
                    dpnl_sign = "+" if dpnl >= 0 else ""
                    total_sign = "+" if total >= 0 else ""
                    reply = (
                        f"💰 <b>盈亏统计</b>\n"
                        f"今日: {dpnl_sign}{dpnl:.4f} USDT\n"
                        f"累计: {total_sign}{total:.4f} USDT\n"
                        f"总交易: {total_trades} 次 | 胜率: {wr}%"
                    )
                    await _send_telegram(reply, token, chat_id)

                elif text == "/stop":
                    await set_trading_fn(False)
                    await _send_telegram("⏹ <b>交易已远程停止</b>", token, chat_id)

                elif text == "/start":
                    await set_trading_fn(True)
                    await _send_telegram("▶️ <b>交易已远程启动</b>", token, chat_id)

                elif text == "/help":
                    reply = (
                        "🤖 <b>AsterDex HFT 命令列表</b>\n\n"
                        "/status — 查看当前持仓与余额\n"
                        "/pnl — 查看今日及累计盈亏\n"
                        "/start — 远程启动交易\n"
                        "/stop — 远程停止交易\n"
                        "/help — 显示此帮助"
                    )
                    await _send_telegram(reply, token, chat_id)

        except Exception as e:
            logger.warning(f"命令轮询异常 uid={uid}: {e}")
        await asyncio.sleep(1)
