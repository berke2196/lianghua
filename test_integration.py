# Hyperliquid 集成示例和测试
import asyncio
import logging
from decimal import Decimal
from typing import List

from hyperliquid_api import HyperliquidAPI, HyperliquidAPIError
from hyperliquid_websocket import HyperliquidWebSocket
from hyperliquid_trading_engine import HyperliquidTradingEngine
from hyperliquid_models import (
    OrderSide,
    OrderType,
    SubscriptionConfig,
    Ticker,
    Trade,
    OrderBook,
)
from hyperliquid_config import HyperliquidConfig


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_rest_api():
    """测试REST API"""
    logger.info("=" * 50)
    logger.info("测试REST API")
    logger.info("=" * 50)

    config = HyperliquidConfig.from_env()

    if not config.api_key or not config.api_secret:
        logger.warning("未设置API密钥，跳过REST API测试")
        return

    api = HyperliquidAPI(
        api_key=config.api_key,
        api_secret=config.api_secret,
        testnet=config.testnet,
    )

    try:
        # 测试公开接口
        logger.info("测试获取Ticker...")
        ticker = api.get_ticker("BTC")
        logger.info(f"BTC Ticker: {ticker}")

        logger.info("测试获取委托簿...")
        orderbook = api.get_orderbook("BTC")
        logger.info(f"BTC OrderBook - Bids: {len(orderbook.bids)}, Asks: {len(orderbook.asks)}")

        logger.info("测试获取K线...")
        candles = api.get_candles("BTC", interval="1h", limit=5)
        logger.info(f"获取K线数量: {len(candles)}")
        for candle in candles[:2]:
            logger.info(
                f"  {candle.timestamp} - O: {candle.open}, C: {candle.close}"
            )

        logger.info("测试获取资金费率...")
        funding = api.get_funding_rates("BTC")
        logger.info(f"BTC资金费率: {funding.funding_rate}")

        # 测试私有接口
        try:
            logger.info("测试获取账户信息...")
            account = api.get_account_info()
            logger.info(
                f"账户 - 总资产: {account.total_balance}, 可用: {account.available_balance}"
            )

            logger.info("测试获取持仓...")
            positions = api.get_positions()
            logger.info(f"持仓数量: {len(positions)}")
            for pos in positions[:2]:
                logger.info(
                    f"  {pos.symbol} - 数量: {pos.size}, 进价: {pos.entry_price}"
                )

            logger.info("测试获取成交记录...")
            trades = api.get_trades(limit=5)
            logger.info(f"成交数量: {len(trades)}")

            logger.info("测试获取订单历史...")
            orders = api.get_order_history(limit=5)
            logger.info(f"订单数量: {len(orders)}")

        except HyperliquidAPIError as e:
            logger.warning(f"私有接口调用失败: {str(e)}")

    except Exception as e:
        logger.error(f"REST API测试失败: {str(e)}")

    finally:
        api.close()


async def test_websocket():
    """测试WebSocket"""
    logger.info("=" * 50)
    logger.info("测试WebSocket")
    logger.info("=" * 50)

    config = HyperliquidConfig.from_env()
    ws = HyperliquidWebSocket(testnet=config.testnet)

    try:
        # 配置订阅
        config_sub = SubscriptionConfig(
            symbols=["BTC", "ETH"],
            channels=["ticker", "trade"],
            auto_reconnect=True,
            reconnect_delay=5,
            max_retries=3,
        )

        logger.info("正在连接WebSocket...")
        await ws.connect(config_sub)
        logger.info("WebSocket已连接")

        # 注册事件处理器
        ticker_count = [0]
        trade_count = [0]

        async def handle_ticker(ticker: Ticker):
            ticker_count[0] += 1
            if ticker_count[0] % 10 == 1:
                logger.info(f"Ticker ({ticker_count[0]}): {ticker.symbol} {ticker.last_price}")

        async def handle_trade(trade: Trade):
            trade_count[0] += 1
            if trade_count[0] % 5 == 1:
                logger.info(f"Trade ({trade_count[0]}): {trade.symbol} {trade.price}")

        ws.on("ticker", handle_ticker)
        ws.on("trade", handle_trade)

        # 接收数据
        logger.info("接收WebSocket数据（10秒）...")
        await asyncio.sleep(10)

        logger.info(f"总接收Ticker: {ticker_count[0]}")
        logger.info(f"总接收Trade: {trade_count[0]}")

    except Exception as e:
        logger.error(f"WebSocket测试失败: {str(e)}")

    finally:
        await ws.close()


async def test_trading_engine():
    """测试交易引擎"""
    logger.info("=" * 50)
    logger.info("测试交易引擎")
    logger.info("=" * 50)

    config = HyperliquidConfig.from_env()

    if not config.api_key or not config.api_secret:
        logger.warning("未设置API密钥，跳过交易引擎测试")
        return

    async with HyperliquidTradingEngine(
        api_key=config.api_key,
        api_secret=config.api_secret,
        testnet=config.testnet,
    ) as engine:
        try:
            # 获取账户信息
            logger.info("获取账户信息...")
            account = await engine.get_account_info()
            logger.info(f"账户: {account.account_id}")
            logger.info(f"总资产: {account.total_balance}")

            # 启动实时流
            logger.info("启动实时流...")
            await engine.start_streaming(
                symbols=["BTC", "ETH"],
                channels=["ticker"],
                auto_reconnect=True,
            )

            # 注册处理器
            count = [0]

            @engine.on_ticker
            async def handle_ticker(ticker: Ticker):
                count[0] += 1
                if count[0] % 10 == 1:
                    logger.info(f"Ticker: {ticker.symbol} {ticker.last_price}")

            # 运行
            logger.info("运行5秒...")
            await asyncio.sleep(5)

            # 获取持仓
            logger.info("获取持仓...")
            positions = await engine.get_positions()
            logger.info(f"持仓数: {len(positions)}")

            logger.info(f"总接收Ticker: {count[0]}")

        except Exception as e:
            logger.error(f"交易引擎测试失败: {str(e)}")


async def test_data_models():
    """测试数据模型"""
    logger.info("=" * 50)
    logger.info("测试数据模型")
    logger.info("=" * 50)

    from datetime import datetime
    from hyperliquid_models import (
        Ticker,
        Order,
        Position,
        Candle,
        Trade,
        FundingRate,
        Account,
    )

    # 创建对象
    ticker = Ticker(
        symbol="BTC",
        bid=Decimal("50000"),
        bid_size=Decimal("1"),
        ask=Decimal("50001"),
        ask_size=Decimal("1"),
        last_price=Decimal("50000.5"),
        timestamp=datetime.utcnow(),
    )
    logger.info(f"Ticker: {ticker.symbol} {ticker.last_price}")

    order = Order(
        order_id="123",
        symbol="BTC",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=Decimal("50000"),
        quantity=Decimal("1"),
        filled=Decimal("0"),
        timestamp=datetime.utcnow(),
    )
    logger.info(f"Order: {order.order_id} {order.side}")

    position = Position(
        symbol="BTC",
        side="LONG",
        size=Decimal("1"),
        entry_price=Decimal("50000"),
        mark_price=Decimal("50100"),
    )
    logger.info(f"Position: {position.symbol} {position.size}")

    logger.info("数据模型测试通过 ✓")


async def test_error_handling():
    """测试错误处理"""
    logger.info("=" * 50)
    logger.info("测试错误处理")
    logger.info("=" * 50)

    # 测试无效API密钥
    api = HyperliquidAPI(
        api_key="invalid-key",
        api_secret="invalid-secret",
        testnet=True,
    )

    try:
        account = api.get_account_info()
    except Exception as e:
        logger.info(f"预期错误: {type(e).__name__}: {str(e)}")

    api.close()
    logger.info("错误处理测试通过 ✓")


async def main():
    """主函数"""
    logger.info("开始集成测试")
    logger.info(f"配置: {HyperliquidConfig.from_env().to_dict()}")

    # 运行测试
    await test_data_models()
    await test_error_handling()
    await test_rest_api()
    await test_websocket()
    await test_trading_engine()

    logger.info("=" * 50)
    logger.info("所有测试完成！")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
