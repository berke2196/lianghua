#!/usr/bin/env python3
# Hyperliquid API 快速开始示例

"""
快速开始脚本 - 演示如何使用Hyperliquid API
"""

import asyncio
import logging
from decimal import Decimal
from os import getenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_rest_api():
    """REST API 示例"""
    logger.info("=" * 60)
    logger.info("REST API 示例")
    logger.info("=" * 60)

    from hyperliquid_api import HyperliquidAPI

    api_key = getenv("HYPERLIQUID_API_KEY", "demo-key")
    api_secret = getenv("HYPERLIQUID_API_SECRET", "demo-secret")

    api = HyperliquidAPI(api_key, api_secret, testnet=True)

    try:
        # 获取行情
        logger.info("\n1. 获取BTC行情...")
        ticker = api.get_ticker("BTC")
        logger.info(f"   BTC价格: {ticker.last_price}")
        logger.info(f"   买价: {ticker.bid}, 卖价: {ticker.ask}")

        # 获取委托簿
        logger.info("\n2. 获取BTC委托簿...")
        orderbook = api.get_orderbook("BTC")
        logger.info(f"   最优买盘: {orderbook.bids[0]}")
        logger.info(f"   最优卖盘: {orderbook.asks[0]}")

        # 获取K线
        logger.info("\n3. 获取BTC 1小时K线 (最近5条)...")
        candles = api.get_candles("BTC", interval="1h", limit=5)
        for candle in candles[-5:]:
            logger.info(
                f"   {candle.timestamp}: "
                f"O={candle.open}, H={candle.high}, "
                f"L={candle.low}, C={candle.close}"
            )

        # 获取资金费率
        logger.info("\n4. 获取BTC资金费率...")
        funding = api.get_funding_rates("BTC")
        logger.info(f"   资金费率: {funding.funding_rate}")
        logger.info(f"   下次更新: {funding.next_funding_time}")

    except Exception as e:
        logger.error(f"REST API 示例错误: {e}")

    finally:
        api.close()
        logger.info("\nREST API 示例完成")


async def example_websocket():
    """WebSocket 示例"""
    logger.info("\n" + "=" * 60)
    logger.info("WebSocket 示例")
    logger.info("=" * 60)

    from hyperliquid_websocket import HyperliquidWebSocket
    from hyperliquid_models import SubscriptionConfig

    ws = HyperliquidWebSocket(testnet=True)

    config = SubscriptionConfig(
        symbols=["BTC", "ETH"],
        channels=["ticker"],
        auto_reconnect=True
    )

    try:
        logger.info("\n1. 连接WebSocket...")
        await ws.connect(config)
        logger.info("   已连接")

        # 计数器
        count = [0]

        logger.info("\n2. 注册行情处理器...")

        @ws.on("ticker")
        async def handle_ticker(ticker):
            count[0] += 1
            if count[0] <= 5:
                logger.info(
                    f"   [{count[0]}] {ticker.symbol}: "
                    f"{ticker.last_price} "
                    f"(买:{ticker.bid}, 卖:{ticker.ask})"
                )

        logger.info("\n3. 接收行情数据 (5秒)...")
        await asyncio.sleep(5)

        logger.info(f"\n   总接收 {count[0]} 条行情")

    except Exception as e:
        logger.error(f"WebSocket 示例错误: {e}")

    finally:
        await ws.close()
        logger.info("\nWebSocket 示例完成")


async def example_trading_engine():
    """交易引擎示例"""
    logger.info("\n" + "=" * 60)
    logger.info("交易引擎示例")
    logger.info("=" * 60)

    from hyperliquid_trading_engine import HyperliquidTradingEngine

    api_key = getenv("HYPERLIQUID_API_KEY", "demo-key")
    api_secret = getenv("HYPERLIQUID_API_SECRET", "demo-secret")

    try:
        async with HyperliquidTradingEngine(
            api_key, api_secret, testnet=True
        ) as engine:
            logger.info("\n1. 获取账户信息...")
            account = await engine.get_account_info()
            logger.info(f"   账户ID: {account.account_id}")
            logger.info(f"   总资产: {account.total_balance}")

            logger.info("\n2. 启动实时流...")
            await engine.start_streaming(
                symbols=["BTC", "ETH"],
                channels=["ticker"]
            )
            logger.info("   已启动")

            # 计数器
            count = [0]

            logger.info("\n3. 注册Ticker处理器...")

            @engine.on_ticker
            async def handle_ticker(ticker):
                count[0] += 1
                if count[0] <= 3:
                    logger.info(
                        f"   [{count[0]}] Ticker: {ticker.symbol} "
                        f"{ticker.last_price}"
                    )

            logger.info("\n4. 接收数据 (3秒)...")
            await asyncio.sleep(3)

            logger.info(f"\n   总接收 {count[0]} 条行情")

    except Exception as e:
        logger.error(f"交易引擎示例错误: {e}")

    logger.info("\n交易引擎示例完成")


async def example_config():
    """配置管理示例"""
    logger.info("\n" + "=" * 60)
    logger.info("配置管理示例")
    logger.info("=" * 60)

    from hyperliquid_config import HyperliquidConfig

    logger.info("\n1. 加载配置...")
    config = HyperliquidConfig.from_env()

    logger.info("\n2. 配置信息:")
    logger.info(f"   Testnet: {config.testnet}")
    logger.info(f"   Timeout: {config.timeout}s")
    logger.info(f"   WS重连: {config.ws_reconnect}")
    logger.info(f"   WS心跳: {config.ws_heartbeat}s")
    logger.info(f"   WS最大重试: {config.ws_max_retries}")
    logger.info(f"   日志级别: {config.log_level}")

    logger.info("\n配置管理示例完成")


async def main():
    """主函数"""
    logger.info("\n")
    logger.info("🚀 Hyperliquid API 快速开始示例")
    logger.info("=" * 60)

    # 检查API密钥
    if not getenv("HYPERLIQUID_API_KEY"):
        logger.warning(
            "\n⚠️  未设置HYPERLIQUID_API_KEY，某些示例可能无法运行"
        )
        logger.info("   请设置环境变量或编辑 .env 文件")

    # 运行示例
    try:
        # 1. 配置管理
        await example_config()

        # 2. REST API (需要API密钥)
        if getenv("HYPERLIQUID_API_KEY"):
            await example_rest_api()
        else:
            logger.info("\n⏭️  跳过REST API示例（未配置API密钥）")

        # 3. WebSocket
        await example_websocket()

        # 4. 交易引擎 (需要API密钥)
        if getenv("HYPERLIQUID_API_KEY"):
            await example_trading_engine()
        else:
            logger.info("\n⏭️  跳过交易引擎示例（未配置API密钥）")

    except Exception as e:
        logger.error(f"示例执行错误: {e}")

    logger.info("\n" + "=" * 60)
    logger.info("✅ 所有示例完成！")
    logger.info("=" * 60)
    logger.info("\n📚 更多信息请查看:")
    logger.info("   - INDEX.md - 文件索引")
    logger.info("   - HYPERLIQUID_README.md - 项目文档")
    logger.info("   - HYPERLIQUID_GUIDE.md - API文档")
    logger.info("\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n用户中断执行")
    except Exception as e:
        logger.error(f"\n\n执行错误: {e}")
