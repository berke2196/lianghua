# Hyperliquid 交易引擎集成
import asyncio
import logging
from typing import List, Optional, Callable, Dict, Any
from decimal import Decimal
from datetime import datetime

from hyperliquid_api import HyperliquidAPI, HyperliquidAPIError
from hyperliquid_websocket import HyperliquidWebSocket, HyperliquidWebSocketError
from hyperliquid_models import (
    Account,
    Candle,
    Order,
    OrderBook,
    OrderSide,
    OrderType,
    Position,
    Ticker,
    Trade,
    FundingRate,
    SubscriptionConfig,
    WebSocketMessage,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingEngineError(Exception):
    """交易引擎异常"""

    pass


class HyperliquidTradingEngine:
    """Hyperliquid交易引擎集成类"""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
    ):
        """
        初始化交易引擎

        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # 初始化API客户端
        self.api = HyperliquidAPI(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )

        # 初始化WebSocket客户端
        self.ws = HyperliquidWebSocket(testnet=testnet)

        # 缓存
        self._ticker_cache: Dict[str, Ticker] = {}
        self._position_cache: Dict[str, Position] = {}
        self._orderbook_cache: Dict[str, OrderBook] = {}

        # 事件处理器
        self._on_ticker: List[Callable] = []
        self._on_trade: List[Callable] = []
        self._on_orderbook: List[Callable] = []
        self._on_order: List[Callable] = []
        self._on_position: List[Callable] = []
        self._on_funding: List[Callable] = []

    # ========== REST API 方法 ==========

    async def get_account_info(self) -> Account:
        """获取账户信息"""
        try:
            return self.api.get_account_info()
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取账户信息失败: {str(e)}")

    async def get_positions(self) -> List[Position]:
        """获取持仓"""
        try:
            positions = self.api.get_positions()
            for pos in positions:
                self._position_cache[pos.symbol] = pos
            return positions
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取持仓失败: {str(e)}")

    async def get_ticker(self, symbol: str) -> Ticker:
        """获取行情"""
        try:
            ticker = self.api.get_ticker(symbol)
            self._ticker_cache[symbol] = ticker
            return ticker
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取行情失败: {str(e)}")

    async def get_orderbook(self, symbol: str) -> OrderBook:
        """获取委托簿"""
        try:
            orderbook = self.api.get_orderbook(symbol)
            self._orderbook_cache[symbol] = orderbook
            return orderbook
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取委托簿失败: {str(e)}")

    async def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> List[Candle]:
        """获取K线"""
        try:
            return self.api.get_candles(symbol, interval, limit)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取K线失败: {str(e)}")

    async def get_funding_rates(self, symbol: str) -> FundingRate:
        """获取资金费率"""
        try:
            return self.api.get_funding_rates(symbol)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取资金费率失败: {str(e)}")

    async def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """获取订单历史"""
        try:
            return self.api.get_order_history(symbol, limit)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取订单历史失败: {str(e)}")

    async def get_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """获取成交记录"""
        try:
            return self.api.get_trades(symbol, limit)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"获取成交记录失败: {str(e)}")

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """创建订单"""
        try:
            return self.api.create_order(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                reduce_only=reduce_only,
                post_only=post_only,
                client_order_id=client_order_id,
            )
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"创建订单失败: {str(e)}")

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        try:
            return self.api.cancel_order(symbol, order_id)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"取消订单失败: {str(e)}")

    async def modify_order(
        self,
        symbol: str,
        order_id: str,
        new_price: Optional[Decimal] = None,
        new_quantity: Optional[Decimal] = None,
    ) -> Order:
        """修改订单"""
        try:
            return self.api.modify_order(symbol, order_id, new_price, new_quantity)
        except HyperliquidAPIError as e:
            raise TradingEngineError(f"修改订单失败: {str(e)}")

    # ========== WebSocket 方法 ==========

    async def start_streaming(
        self,
        symbols: List[str],
        channels: List[str],
        auto_reconnect: bool = True,
    ) -> None:
        """
        启动实时流

        Args:
            symbols: 交易对列表
            channels: 频道列表
            auto_reconnect: 是否自动重连
        """
        config = SubscriptionConfig(
            symbols=symbols,
            channels=channels,
            auto_reconnect=auto_reconnect,
        )

        try:
            await self.ws.connect(config)
            self._setup_ws_callbacks()
            logger.info("实时流已启动")
        except HyperliquidWebSocketError as e:
            raise TradingEngineError(f"启动实时流失败: {str(e)}")

    def _setup_ws_callbacks(self) -> None:
        """设置WebSocket回调"""
        self.ws.on("ticker", self._on_ticker_event)
        self.ws.on("trade", self._on_trade_event)
        self.ws.on("orderBook", self._on_orderbook_event)
        self.ws.on("order", self._on_order_event)
        self.ws.on("position", self._on_position_event)
        self.ws.on("fundingRate", self._on_funding_event)

    async def _on_ticker_event(self, ticker: Ticker) -> None:
        """处理Ticker事件"""
        self._ticker_cache[ticker.symbol] = ticker
        for handler in self._on_ticker:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(ticker)
                else:
                    handler(ticker)
            except Exception as e:
                logger.error(f"Ticker处理器错误: {str(e)}")

    async def _on_trade_event(self, trade: Trade) -> None:
        """处理成交事件"""
        for handler in self._on_trade:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(trade)
                else:
                    handler(trade)
            except Exception as e:
                logger.error(f"成交处理器错误: {str(e)}")

    async def _on_orderbook_event(self, orderbook: OrderBook) -> None:
        """处理委托簿事件"""
        self._orderbook_cache[orderbook.symbol] = orderbook
        for handler in self._on_orderbook:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(orderbook)
                else:
                    handler(orderbook)
            except Exception as e:
                logger.error(f"委托簿处理器错误: {str(e)}")

    async def _on_order_event(self, order_data: Dict[str, Any]) -> None:
        """处理订单事件"""
        for handler in self._on_order:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(order_data)
                else:
                    handler(order_data)
            except Exception as e:
                logger.error(f"订单处理器错误: {str(e)}")

    async def _on_position_event(self, position_data: Dict[str, Any]) -> None:
        """处理持仓事件"""
        for handler in self._on_position:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(position_data)
                else:
                    handler(position_data)
            except Exception as e:
                logger.error(f"持仓处理器错误: {str(e)}")

    async def _on_funding_event(self, funding: FundingRate) -> None:
        """处理资金费率事件"""
        for handler in self._on_funding:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(funding)
                else:
                    handler(funding)
            except Exception as e:
                logger.error(f"资金费率处理器错误: {str(e)}")

    # ========== 事件处理器 ==========

    def on_ticker(self, handler: Callable) -> Callable:
        """注册Ticker处理器"""
        self._on_ticker.append(handler)
        return handler

    def on_trade(self, handler: Callable) -> Callable:
        """注册成交处理器"""
        self._on_trade.append(handler)
        return handler

    def on_orderbook(self, handler: Callable) -> Callable:
        """注册委托簿处理器"""
        self._on_orderbook.append(handler)
        return handler

    def on_order(self, handler: Callable) -> Callable:
        """注册订单处理器"""
        self._on_order.append(handler)
        return handler

    def on_position(self, handler: Callable) -> Callable:
        """注册持仓处理器"""
        self._on_position.append(handler)
        return handler

    def on_funding(self, handler: Callable) -> Callable:
        """注册资金费率处理器"""
        self._on_funding.append(handler)
        return handler

    # ========== 缓存访问 ==========

    def get_cached_ticker(self, symbol: str) -> Optional[Ticker]:
        """获取缓存的行情"""
        return self._ticker_cache.get(symbol)

    def get_cached_position(self, symbol: str) -> Optional[Position]:
        """获取缓存的持仓"""
        return self._position_cache.get(symbol)

    def get_cached_orderbook(self, symbol: str) -> Optional[OrderBook]:
        """获取缓存的委托簿"""
        return self._orderbook_cache.get(symbol)

    # ========== 辅助方法 ==========

    async def get_last_message(self, timeout: float = 5.0) -> Optional[WebSocketMessage]:
        """获取最后一条WebSocket消息"""
        return await self.ws.get_message(timeout)

    def get_all_messages(self) -> List[WebSocketMessage]:
        """获取所有待处理的WebSocket消息"""
        return self.ws.get_messages()

    async def close(self) -> None:
        """关闭引擎"""
        try:
            await self.ws.close()
            self.api.close()
            logger.info("交易引擎已关闭")
        except Exception as e:
            logger.error(f"关闭引擎失败: {str(e)}")

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.close()


# ========== 使用示例 ==========

async def example_usage():
    """使用示例"""
    api_key = "your-api-key"
    api_secret = "your-api-secret"

    # 初始化引擎
    async with HyperliquidTradingEngine(api_key, api_secret, testnet=True) as engine:
        # 1. 获取账户信息
        try:
            account = await engine.get_account_info()
            print(f"账户ID: {account.account_id}")
            print(f"总资产: {account.total_balance}")
        except TradingEngineError as e:
            print(f"错误: {e}")

        # 2. 启动实时流
        try:
            await engine.start_streaming(
                symbols=["BTC", "ETH"],
                channels=["ticker", "trade", "orderBook"],
            )

            # 3. 注册事件处理器
            @engine.on_ticker
            async def handle_ticker(ticker: Ticker):
                print(f"Ticker - {ticker.symbol}: {ticker.last_price}")

            @engine.on_trade
            async def handle_trade(trade: Trade):
                print(f"Trade - {trade.symbol}: {trade.price}")

            # 4. 运行一段时间
            await asyncio.sleep(30)

            # 5. 获取持仓
            positions = await engine.get_positions()
            for pos in positions:
                print(f"持仓 - {pos.symbol}: {pos.size}")

            # 6. 创建订单
            order = await engine.create_order(
                symbol="BTC-USD",
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=Decimal("0.1"),
                price=Decimal("50000"),
            )
            print(f"订单创建: {order.order_id}")

        except TradingEngineError as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    asyncio.run(example_usage())
