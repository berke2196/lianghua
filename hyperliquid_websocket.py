# Hyperliquid WebSocket 实时数据订阅
import asyncio
import json
import logging
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
from collections import deque

import websockets
from websockets.client import WebSocketClientProtocol

from hyperliquid_models import (
    Ticker,
    OrderBook,
    Trade,
    FundingRate,
    Candle,
    WebSocketMessage,
    SubscriptionConfig,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HyperliquidWebSocketError(Exception):
    """WebSocket异常基类"""

    pass


class HyperliquidWebSocket:
    """Hyperliquid WebSocket实时数据订阅"""

    # WebSocket端点
    WS_BASE_URL = "wss://api.hyperliquid.xyz/ws"
    WS_TESTNET_URL = "wss://api-testnet.hyperliquid.xyz/ws"

    # 事件类型
    CHANNEL_TICKER = "ticker"
    CHANNEL_CANDLE = "candle"
    CHANNEL_ORDERBOOK = "orderBook"
    CHANNEL_TRADE = "trade"
    CHANNEL_FUNDING = "fundingRate"
    CHANNEL_ORDER = "order"
    CHANNEL_POSITION = "position"

    def __init__(
        self,
        testnet: bool = False,
        max_queue_size: int = 1000,
    ):
        """
        初始化WebSocket客户端

        Args:
            testnet: 是否使用测试网
            max_queue_size: 消息队列最大大小
        """
        self.testnet = testnet
        self.ws_url = self.WS_TESTNET_URL if testnet else self.WS_BASE_URL
        self.max_queue_size = max_queue_size

        # WebSocket连接
        self.ws: Optional[WebSocketClientProtocol] = None
        self.connected = False

        # 消息队列
        self.message_queue: deque = deque(maxlen=max_queue_size)

        # 订阅状态
        self.subscriptions: Dict[str, set] = {}  # symbol -> channels
        self.channels: Dict[str, set] = {}  # channel -> symbols

        # 回调处理器
        self.callbacks: Dict[str, List[Callable]] = {}  # channel -> callbacks

        # 任务管理
        self.receive_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.reconnect_task: Optional[asyncio.Task] = None

        # 连接配置
        self.config: Optional[SubscriptionConfig] = None
        self.reconnect_count = 0
        self.max_reconnect_attempts = 10

    def on(self, channel: str, callback: Callable) -> None:
        """
        注册事件回调

        Args:
            channel: 频道名称
            callback: 回调函数
        """
        if channel not in self.callbacks:
            self.callbacks[channel] = []
        self.callbacks[channel].append(callback)

    def off(self, channel: str, callback: Optional[Callable] = None) -> None:
        """
        取消注册回调

        Args:
            channel: 频道名称
            callback: 回调函数 (None则移除所有)
        """
        if channel in self.callbacks:
            if callback is None:
                del self.callbacks[channel]
            else:
                self.callbacks[channel] = [
                    cb for cb in self.callbacks[channel] if cb != callback
                ]

    async def _emit(self, channel: str, data: Any) -> None:
        """
        触发事件

        Args:
            channel: 频道名称
            data: 事件数据
        """
        if channel in self.callbacks:
            for callback in self.callbacks[channel]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(data)
                    else:
                        callback(data)
                except Exception as e:
                    logger.error(f"回调处理失败 ({channel}): {str(e)}")

    async def connect(self, config: SubscriptionConfig) -> None:
        """
        连接WebSocket并订阅

        Args:
            config: 订阅配置
        """
        self.config = config

        try:
            logger.info(f"正在连接到 {self.ws_url}...")
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=30,
                ping_timeout=10,
            )
            self.connected = True
            self.reconnect_count = 0
            logger.info("WebSocket已连接")

            # 订阅
            await self.subscribe(config.symbols, config.channels)

            # 启动接收和心跳任务
            self.receive_task = asyncio.create_task(self._receive_messages())
            self.heartbeat_task = asyncio.create_task(
                self._heartbeat(config.heartbeat_interval)
            )

        except Exception as e:
            logger.error(f"连接失败: {str(e)}")
            self.connected = False
            if config.auto_reconnect:
                await self._reconnect()
            else:
                raise HyperliquidWebSocketError(f"连接失败: {str(e)}")

    async def subscribe(
        self,
        symbols: List[str],
        channels: List[str],
    ) -> None:
        """
        订阅特定交易对和频道

        Args:
            symbols: 交易对列表
            channels: 频道列表
        """
        if not self.connected or not self.ws:
            raise HyperliquidWebSocketError("WebSocket未连接")

        for symbol in symbols:
            if symbol not in self.subscriptions:
                self.subscriptions[symbol] = set()
            self.subscriptions[symbol].update(channels)

        for channel in channels:
            if channel not in self.channels:
                self.channels[channel] = set()
            self.channels[channel].update(symbols)

            # 发送订阅请求
            sub_msg = {"method": "subscribe", "subscription": {channel: symbols}}
            try:
                await self.ws.send(json.dumps(sub_msg))
                logger.info(f"已订阅 {channel}: {symbols}")
            except Exception as e:
                logger.error(f"订阅失败 ({channel}): {str(e)}")

    async def unsubscribe(
        self,
        symbols: List[str],
        channels: List[str],
    ) -> None:
        """
        取消订阅

        Args:
            symbols: 交易对列表
            channels: 频道列表
        """
        if not self.connected or not self.ws:
            return

        for symbol in symbols:
            if symbol in self.subscriptions:
                self.subscriptions[symbol].difference_update(channels)

        for channel in channels:
            if channel in self.channels:
                self.channels[channel].difference_update(symbols)

            # 发送取消订阅请求
            unsub_msg = {
                "method": "unsubscribe",
                "subscription": {channel: symbols},
            }
            try:
                await self.ws.send(json.dumps(unsub_msg))
                logger.info(f"已取消订阅 {channel}: {symbols}")
            except Exception as e:
                logger.error(f"取消订阅失败 ({channel}): {str(e)}")

    async def _receive_messages(self) -> None:
        """接收并处理WebSocket消息"""
        try:
            while self.connected and self.ws:
                try:
                    message = await asyncio.wait_for(
                        self.ws.recv(),
                        timeout=self.config.heartbeat_interval * 2,
                    )
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    logger.warning("WebSocket接收超时")
                    await self._reconnect()
                    break
        except Exception as e:
            logger.error(f"消息接收错误: {str(e)}")
            self.connected = False
            if self.config and self.config.auto_reconnect:
                await self._reconnect()

    async def _process_message(self, raw_message: str) -> None:
        """
        处理WebSocket消息

        Args:
            raw_message: 原始消息
        """
        try:
            message = json.loads(raw_message)

            # 心跳
            if message.get("channel") == "pong":
                logger.debug("收到pong")
                return

            # 添加到队列
            ws_msg = WebSocketMessage(
                channel=message.get("channel", "unknown"),
                symbol=message.get("data", {}).get("coin", ""),
                data=message.get("data", {}),
                timestamp=datetime.utcnow(),
            )
            self.message_queue.append(ws_msg)

            # 根据频道类型处理
            channel = message.get("channel", "")
            if channel == self.CHANNEL_TICKER:
                await self._handle_ticker(message.get("data", {}))
            elif channel == self.CHANNEL_CANDLE:
                await self._handle_candle(message.get("data", {}))
            elif channel == self.CHANNEL_ORDERBOOK:
                await self._handle_orderbook(message.get("data", {}))
            elif channel == self.CHANNEL_TRADE:
                await self._handle_trade(message.get("data", {}))
            elif channel == self.CHANNEL_FUNDING:
                await self._handle_funding(message.get("data", {}))
            elif channel == self.CHANNEL_ORDER:
                await self._emit(self.CHANNEL_ORDER, message.get("data", {}))
            elif channel == self.CHANNEL_POSITION:
                await self._emit(self.CHANNEL_POSITION, message.get("data", {}))

        except json.JSONDecodeError:
            logger.error(f"消息解析失败: {raw_message}")
        except Exception as e:
            logger.error(f"消息处理失败: {str(e)}")

    async def _handle_ticker(self, data: Dict) -> None:
        """处理Ticker消息"""
        try:
            ticker = Ticker(
                symbol=data.get("coin", ""),
                bid=float(data.get("bid", 0)),
                bid_size=float(data.get("bidSz", 0)),
                ask=float(data.get("ask", 0)),
                ask_size=float(data.get("askSz", 0)),
                last_price=float(data.get("mid", 0)),
                timestamp=datetime.fromtimestamp(data.get("time", 0) / 1000),
            )
            await self._emit(self.CHANNEL_TICKER, ticker)
        except Exception as e:
            logger.error(f"处理Ticker失败: {str(e)}")

    async def _handle_candle(self, data: Dict) -> None:
        """处理K线消息"""
        try:
            candles_data = data.get("candles", [])
            for c in candles_data:
                candle = Candle(
                    timestamp=datetime.fromtimestamp(c.get("t", 0) / 1000),
                    open=float(c.get("o", 0)),
                    high=float(c.get("h", 0)),
                    low=float(c.get("l", 0)),
                    close=float(c.get("c", 0)),
                    volume=float(c.get("v", 0)),
                    quote_asset_volume=float(c.get("qv", 0)),
                    trade_count=int(c.get("n", 0)),
                )
                await self._emit(self.CHANNEL_CANDLE, candle)
        except Exception as e:
            logger.error(f"处理K线失败: {str(e)}")

    async def _handle_orderbook(self, data: Dict) -> None:
        """处理委托簿消息"""
        try:
            orderbook = OrderBook(
                symbol=data.get("coin", ""),
                bids=[
                    (float(b["px"]), float(b["sz"]))
                    for b in data.get("bids", [])
                ],
                asks=[
                    (float(a["px"]), float(a["sz"]))
                    for a in data.get("asks", [])
                ],
                timestamp=datetime.fromtimestamp(data.get("time", 0) / 1000),
            )
            await self._emit(self.CHANNEL_ORDERBOOK, orderbook)
        except Exception as e:
            logger.error(f"处理委托簿失败: {str(e)}")

    async def _handle_trade(self, data: Dict) -> None:
        """处理成交消息"""
        try:
            trade = Trade(
                trade_id=data.get("tid", ""),
                order_id=data.get("oid", ""),
                symbol=data.get("coin", ""),
                side="buy" if data.get("isBuy") else "sell",
                price=float(data.get("px", 0)),
                quantity=float(data.get("sz", 0)),
                fee=float(data.get("fee", 0)),
                fee_currency="USDC",
                timestamp=datetime.fromtimestamp(data.get("time", 0) / 1000),
                is_buyer=data.get("isBuy", False),
                is_maker=not data.get("isBuy", False),
            )
            await self._emit(self.CHANNEL_TRADE, trade)
        except Exception as e:
            logger.error(f"处理成交失败: {str(e)}")

    async def _handle_funding(self, data: Dict) -> None:
        """处理资金费率消息"""
        try:
            funding = FundingRate(
                symbol=data.get("coin", ""),
                funding_rate=float(data.get("funding_rate", 0)),
                funding_time=datetime.fromtimestamp(data.get("time", 0) / 1000),
                next_funding_time=datetime.fromtimestamp(
                    data.get("nextTime", 0) / 1000
                ),
            )
            await self._emit(self.CHANNEL_FUNDING, funding)
        except Exception as e:
            logger.error(f"处理资金费率失败: {str(e)}")

    async def _heartbeat(self, interval: int) -> None:
        """心跳保活"""
        while self.connected and self.ws:
            try:
                await asyncio.sleep(interval)
                if self.connected and self.ws:
                    ping_msg = {"method": "ping"}
                    await self.ws.send(json.dumps(ping_msg))
            except Exception as e:
                logger.error(f"心跳发送失败: {str(e)}")

    async def _reconnect(self) -> None:
        """重连机制"""
        if not self.config or not self.config.auto_reconnect:
            return

        while self.reconnect_count < self.config.max_retries:
            self.reconnect_count += 1
            wait_time = min(
                self.config.reconnect_delay * (2 ** self.reconnect_count),
                300,  # 最多等待5分钟
            )
            logger.info(f"将在 {wait_time} 秒后进行第 {self.reconnect_count} 次重连...")
            await asyncio.sleep(wait_time)

            try:
                await self.connect(self.config)
                return
            except Exception as e:
                logger.error(f"重连失败 (第 {self.reconnect_count} 次): {str(e)}")

        logger.error(f"已达最大重连次数 ({self.config.max_retries})，放弃重连")
        self.connected = False

    async def get_message(self, timeout: Optional[float] = None) -> Optional[WebSocketMessage]:
        """
        从队列获取消息

        Args:
            timeout: 超时时间

        Returns:
            WebSocketMessage或None
        """
        start_time = asyncio.get_event_loop().time()
        while True:
            if self.message_queue:
                return self.message_queue.popleft()

            if timeout:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    return None

            await asyncio.sleep(0.01)

    def get_messages(self, max_count: Optional[int] = None) -> List[WebSocketMessage]:
        """
        获取队列中的所有消息

        Args:
            max_count: 最大数量

        Returns:
            WebSocketMessage列表
        """
        messages = []
        count = 0
        while self.message_queue and (max_count is None or count < max_count):
            messages.append(self.message_queue.popleft())
            count += 1
        return messages

    async def close(self) -> None:
        """关闭连接"""
        self.connected = False

        # 取消订阅
        if self.config and self.ws:
            subscriptions_to_remove = [
                (list(syms), self.config.channels)
                for syms in self.subscriptions.values()
            ]
            for symbols, channels in subscriptions_to_remove:
                await self.unsubscribe(symbols, channels)

        # 关闭WebSocket
        if self.ws:
            try:
                await self.ws.close()
            except Exception as e:
                logger.error(f"关闭WebSocket失败: {str(e)}")

        # 取消任务
        for task in [self.receive_task, self.heartbeat_task, self.reconnect_task]:
            if task and not task.done():
                task.cancel()

        logger.info("WebSocket已关闭")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()
