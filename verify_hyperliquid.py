# Hyperliquid 模块验证脚本
import sys
import importlib
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def check_module(module_name: str) -> bool:
    """检查模块是否可以导入"""
    try:
        importlib.import_module(module_name)
        logger.info(f"✓ {module_name:40} 导入成功")
        return True
    except ImportError as e:
        logger.error(f"✗ {module_name:40} 导入失败: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"✗ {module_name:40} 错误: {str(e)}")
        return False


def check_classes(module_name: str, class_names: list) -> bool:
    """检查模块中的类是否存在"""
    try:
        module = importlib.import_module(module_name)
        for class_name in class_names:
            if not hasattr(module, class_name):
                logger.error(f"✗ {class_name} 不存在于 {module_name}")
                return False
        logger.info(f"✓ {module_name:40} 所有类导入成功")
        return True
    except Exception as e:
        logger.error(f"✗ {module_name:40} 检查失败: {str(e)}")
        return False


def verify_file_structure():
    """验证文件结构"""
    logger.info("=" * 60)
    logger.info("验证 Hyperliquid API 模块结构")
    logger.info("=" * 60)

    files = [
        "hyperliquid_models.py",
        "hyperliquid_api.py",
        "hyperliquid_websocket.py",
        "hyperliquid_trading_engine.py",
        "hyperliquid_config.py",
        "hyperliquid_strategies.py",
        "test_hyperliquid.py",
        "test_integration.py",
        "HYPERLIQUID_GUIDE.md",
        "HYPERLIQUID_README.md",
        ".env.hyperliquid.example",
    ]

    import os

    logger.info("\n文件检查:")
    missing_files = []
    for file in files:
        filepath = f"c:\\Users\\北神大帝\\Desktop\\塞子\\{file}"
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            logger.info(f"✓ {file:45} ({size:,} 字节)")
        else:
            logger.error(f"✗ {file:45} 不存在")
            missing_files.append(file)

    return len(missing_files) == 0


def verify_imports():
    """验证导入"""
    logger.info("\n导入检查:")

    results = []

    # 检查基础模块
    results.append(check_module("hyperliquid_models"))
    results.append(check_module("hyperliquid_api"))
    results.append(check_module("hyperliquid_websocket"))
    results.append(check_module("hyperliquid_trading_engine"))
    results.append(check_module("hyperliquid_config"))
    results.append(check_module("hyperliquid_strategies"))

    return all(results)


def verify_classes():
    """验证类定义"""
    logger.info("\n类定义检查:")

    results = []

    # 检查数据模型
    results.append(
        check_classes(
            "hyperliquid_models",
            [
                "OrderStatus",
                "OrderType",
                "OrderSide",
                "Candle",
                "Ticker",
                "OrderBook",
                "Order",
                "Position",
                "Trade",
                "FundingRate",
                "Account",
                "WebSocketMessage",
                "SubscriptionConfig",
            ],
        )
    )

    # 检查API类
    results.append(
        check_classes(
            "hyperliquid_api",
            ["HyperliquidAPI", "HyperliquidAPIError", "HyperliquidAuthError"],
        )
    )

    # 检查WebSocket类
    results.append(
        check_classes(
            "hyperliquid_websocket",
            ["HyperliquidWebSocket", "HyperliquidWebSocketError"],
        )
    )

    # 检查交易引擎
    results.append(
        check_classes(
            "hyperliquid_trading_engine",
            ["HyperliquidTradingEngine", "TradingEngineError"],
        )
    )

    # 检查策略
    results.append(
        check_classes(
            "hyperliquid_strategies",
            [
                "TradingStrategy",
                "SimpleMovingAverageStrategy",
                "MeanReversionStrategy",
                "PortfolioManager",
            ],
        )
    )

    return all(results)


def verify_config():
    """验证配置"""
    logger.info("\n配置检查:")

    try:
        from hyperliquid_config import HyperliquidConfig

        config = HyperliquidConfig.from_env()
        logger.info(f"✓ 配置加载成功")
        logger.info(f"  - Testnet: {config.testnet}")
        logger.info(f"  - Timeout: {config.timeout}s")
        logger.info(f"  - WS重连: {config.ws_reconnect}")
        logger.info(f"  - WS最大重试: {config.ws_max_retries}")
        return True
    except Exception as e:
        logger.error(f"✗ 配置加载失败: {str(e)}")
        return False


def verify_api_structure():
    """验证API结构"""
    logger.info("\n API 方法检查:")

    try:
        from hyperliquid_api import HyperliquidAPI

        methods = [
            "get_ticker",
            "get_orderbook",
            "get_candles",
            "get_funding_rates",
            "get_account_info",
            "get_positions",
            "get_order_status",
            "get_order_history",
            "get_trades",
            "create_order",
            "modify_order",
            "cancel_order",
        ]

        for method in methods:
            if hasattr(HyperliquidAPI, method):
                logger.info(f"  ✓ {method}")
            else:
                logger.error(f"  ✗ {method} 缺失")
                return False

        logger.info(f"✓ API 方法检查通过 ({len(methods)} 个方法)")
        return True
    except Exception as e:
        logger.error(f"✗ API 结构检查失败: {str(e)}")
        return False


def verify_websocket_structure():
    """验证WebSocket结构"""
    logger.info("\n WebSocket 方法检查:")

    try:
        from hyperliquid_websocket import HyperliquidWebSocket

        methods = [
            "connect",
            "subscribe",
            "unsubscribe",
            "on",
            "off",
            "get_message",
            "get_messages",
            "close",
        ]

        for method in methods:
            if hasattr(HyperliquidWebSocket, method):
                logger.info(f"  ✓ {method}")
            else:
                logger.error(f"  ✗ {method} 缺失")
                return False

        logger.info(f"✓ WebSocket 方法检查通过 ({len(methods)} 个方法)")
        return True
    except Exception as e:
        logger.error(f"✗ WebSocket 结构检查失败: {str(e)}")
        return False


def main():
    """主验证函数"""
    logger.info("\n")
    logger.info("🔍 Hyperliquid API 集成模块验证")
    logger.info("=" * 60)

    results = []

    # 运行所有检查
    results.append(("文件结构", verify_file_structure()))
    results.append(("模块导入", verify_imports()))
    results.append(("类定义", verify_classes()))
    results.append(("配置", verify_config()))
    results.append(("API结构", verify_api_structure()))
    results.append(("WebSocket结构", verify_websocket_structure()))

    # 显示总结
    logger.info("\n" + "=" * 60)
    logger.info("验证总结")
    logger.info("=" * 60)

    passed = 0
    failed = 0

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{name:30} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    logger.info("=" * 60)
    logger.info(f"总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        logger.info("✓ 所有检查通过！模块已准备就绪。")
        logger.info("\n使用示例:")
        logger.info("  python test_integration.py  # 运行集成测试")
        logger.info("  pytest test_hyperliquid.py  # 运行单元测试")
        return 0
    else:
        logger.error("✗ 部分检查失败，请查看错误信息。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
