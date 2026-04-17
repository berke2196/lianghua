# Hyperliquid API 集成测试
import asyncio
import pytest
from decimal import Decimal
from datetime import datetime

from hyperliquid_api import (
    HyperliquidAPI,
    HyperliquidAPIError,
    HyperliquidAuthError,
)
from hyperliquid_websocket import HyperliquidWebSocket, HyperliquidWebSocketError
from hyperliquid_models import (
    OrderSide,
    OrderType,
    SubscriptionConfig,
)


@pytest.fixture
def api_key():
    """获取测试API密钥"""
    return "test-api-key"


@pytest.fixture
def api_secret():
    """获取测试API密钥"""
    return "test-api-secret"


@pytest.fixture
def hyperliquid_api(api_key, api_secret):
    """创建API客户端"""
    return HyperliquidAPI(api_key, api_secret, testnet=True)


@pytest.fixture
async def hyperliquid_ws():
    """创建WebSocket客户端"""
    ws = HyperliquidWebSocket(testnet=True)
    yield ws
    await ws.close()


class TestHyperliquidAPI:
    """Hyperliquid API测试"""

    def test_api_initialization(self, hyperliquid_api):
        """测试API初始化"""
        assert hyperliquid_api.api_key == "test-api-key"
        assert hyperliquid_api.api_secret == "test-api-secret"
        assert hyperliquid_api.testnet is True

    def test_rate_limit_tracking(self, hyperliquid_api):
        """测试速率限制跟踪"""
        assert len(hyperliquid_api._request_times) == 0

    def test_get_headers(self, hyperliquid_api):
        """测试请求头生成"""
        headers = hyperliquid_api._get_headers("test-signature")
        assert "HAPI-KEY" in headers
        assert "HAPI-SIGN" in headers
        assert headers["HAPI-KEY"] == "test-api-key"

    def test_api_context_manager(self, hyperliquid_api):
        """测试上下文管理器"""
        with hyperliquid_api as api:
            assert api is not None


class TestHyperliquidWebSocket:
    """Hyperliquid WebSocket测试"""

    @pytest.mark.asyncio
    async def test_ws_initialization(self, hyperliquid_ws):
        """测试WebSocket初始化"""
        assert hyperliquid_ws.connected is False
        assert len(hyperliquid_ws.callbacks) == 0

    @pytest.mark.asyncio
    async def test_ws_event_registration(self, hyperliquid_ws):
        """测试事件注册"""

        async def handler(data):
            pass

        hyperliquid_ws.on("ticker", handler)
        assert "ticker" in hyperliquid_ws.callbacks
        assert handler in hyperliquid_ws.callbacks["ticker"]

    @pytest.mark.asyncio
    async def test_ws_event_unregistration(self, hyperliquid_ws):
        """测试事件注销"""

        async def handler(data):
            pass

        hyperliquid_ws.on("ticker", handler)
        hyperliquid_ws.off("ticker", handler)
        assert "ticker" not in hyperliquid_ws.callbacks

    @pytest.mark.asyncio
    async def test_ws_message_queue(self, hyperliquid_ws):
        """测试消息队列"""
        messages = hyperliquid_ws.get_messages()
        assert len(messages) == 0


class TestDataModels:
    """数据模型测试"""

    def test_ticker_model(self):
        """测试Ticker模型"""
        from hyperliquid_models import Ticker

        ticker = Ticker(
            symbol="BTC-USD",
            bid=Decimal("50000"),
            bid_size=Decimal("1.0"),
            ask=Decimal("50001"),
            ask_size=Decimal("1.0"),
            last_price=Decimal("50000.5"),
            timestamp=datetime.utcnow(),
        )

        assert ticker.symbol == "BTC-USD"
        assert ticker.bid == Decimal("50000")
        assert ticker.ask == Decimal("50001")

    def test_order_model(self):
        """测试Order模型"""
        from hyperliquid_models import Order, OrderStatus

        order = Order(
            order_id="123",
            symbol="BTC-USD",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=Decimal("50000"),
            quantity=Decimal("1.0"),
            filled=Decimal("0.5"),
            status=OrderStatus.OPEN,
            timestamp=datetime.utcnow(),
        )

        assert order.order_id == "123"
        assert order.status == OrderStatus.OPEN
        assert order.filled == Decimal("0.5")

    def test_position_model(self):
        """测试Position模型"""
        from hyperliquid_models import Position

        position = Position(
            symbol="BTC-USD",
            side="LONG",
            size=Decimal("1.0"),
            entry_price=Decimal("50000"),
            mark_price=Decimal("50100"),
        )

        assert position.symbol == "BTC-USD"
        assert position.side == "LONG"
        assert position.size == Decimal("1.0")

    def test_candle_model(self):
        """测试Candle模型"""
        from hyperliquid_models import Candle

        candle = Candle(
            timestamp=datetime.utcnow(),
            open=Decimal("50000"),
            high=Decimal("50500"),
            low=Decimal("49500"),
            close=Decimal("50200"),
            volume=Decimal("100"),
            quote_asset_volume=Decimal("5000000"),
            trade_count=1000,
        )

        assert candle.close == Decimal("50200")
        assert candle.trade_count == 1000


class TestErrorHandling:
    """错误处理测试"""

    def test_api_error_hierarchy(self):
        """测试API错误层次"""
        from hyperliquid_api import (
            HyperliquidAPIError,
            HyperliquidAuthError,
        )

        assert issubclass(HyperliquidAuthError, HyperliquidAPIError)

    def test_websocket_error_hierarchy(self):
        """测试WebSocket错误层次"""
        from hyperliquid_websocket import (
            HyperliquidWebSocketError,
        )

        error = HyperliquidWebSocketError("测试错误")
        assert str(error) == "测试错误"


# 集成测试
@pytest.mark.asyncio
async def test_full_workflow(api_key, api_secret):
    """测试完整工作流"""
    from hyperliquid_trading_engine import HyperliquidTradingEngine

    async with HyperliquidTradingEngine(api_key, api_secret, testnet=True) as engine:
        # 测试缓存访问
        ticker = engine.get_cached_ticker("BTC-USD")
        assert ticker is None

        position = engine.get_cached_position("BTC-USD")
        assert position is None

        messages = engine.get_all_messages()
        assert isinstance(messages, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
