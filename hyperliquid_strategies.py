# Hyperliquid 高级交易策略示例
import asyncio
import logging
from decimal import Decimal
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from hyperliquid_trading_engine import HyperliquidTradingEngine
from hyperliquid_models import (
    Ticker,
    OrderSide,
    OrderType,
    Trade,
    Candle,
    Position,
    Order,
    OrderStatus,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingStrategy:
    """基础交易策略类"""

    def __init__(self, engine: HyperliquidTradingEngine, symbol: str):
        """
        初始化策略

        Args:
            engine: 交易引擎
            symbol: 交易对
        """
        self.engine = engine
        self.symbol = symbol
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []

    async def on_ticker(self, ticker: Ticker) -> None:
        """处理Ticker事件"""
        pass

    async def on_trade(self, trade: Trade) -> None:
        """处理成交事件"""
        pass

    async def on_candle(self, candle: Candle) -> None:
        """处理K线事件"""
        pass


class SimpleMovingAverageStrategy(TradingStrategy):
    """简单移动平均线策略"""

    def __init__(
        self,
        engine: HyperliquidTradingEngine,
        symbol: str,
        short_period: int = 5,
        long_period: int = 20,
        position_size: Decimal = Decimal("1.0"),
    ):
        """
        初始化SMA策略

        Args:
            engine: 交易引擎
            symbol: 交易对
            short_period: 短期MA周期
            long_period: 长期MA周期
            position_size: 持仓大小
        """
        super().__init__(engine, symbol)
        self.short_period = short_period
        self.long_period = long_period
        self.position_size = position_size
        self.candles: List[Candle] = []
        self.in_position = False

    def _calculate_sma(self, prices: List[Decimal], period: int) -> Decimal:
        """计算简单移动平均线"""
        if len(prices) < period:
            return Decimal(0)
        return sum(prices[-period:]) / period

    async def on_candle(self, candle: Candle) -> None:
        """处理K线事件"""
        self.candles.append(candle)

        # 需要至少长期周期的K线
        if len(self.candles) < self.long_period:
            return

        # 保持最近的K线
        if len(self.candles) > self.long_period:
            self.candles = self.candles[-self.long_period:]

        # 计算移动平均线
        closes = [c.close for c in self.candles]
        short_sma = self._calculate_sma(closes, self.short_period)
        long_sma = self._calculate_sma(closes, self.long_period)

        current_price = candle.close
        logger.info(
            f"{self.symbol} - 价格: {current_price}, 短MA: {short_sma}, 长MA: {long_sma}"
        )

        # 金叉信号 (买入)
        if short_sma > long_sma and not self.in_position:
            logger.info(f"{self.symbol} 触发金叉信号，准备买入")
            try:
                order = await self.engine.create_order(
                    symbol=self.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=self.position_size,
                )
                self.orders[order.order_id] = order
                self.in_position = True
                logger.info(f"买入订单已创建: {order.order_id}")
            except Exception as e:
                logger.error(f"创建买入订单失败: {str(e)}")

        # 死叉信号 (卖出)
        elif short_sma < long_sma and self.in_position:
            logger.info(f"{self.symbol} 触发死叉信号，准备卖出")
            try:
                order = await self.engine.create_order(
                    symbol=self.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=self.position_size,
                )
                self.orders[order.order_id] = order
                self.in_position = False
                logger.info(f"卖出订单已创建: {order.order_id}")
            except Exception as e:
                logger.error(f"创建卖出订单失败: {str(e)}")


class MeanReversionStrategy(TradingStrategy):
    """均值回归策略"""

    def __init__(
        self,
        engine: HyperliquidTradingEngine,
        symbol: str,
        lookback_period: int = 20,
        std_dev_threshold: float = 2.0,
        position_size: Decimal = Decimal("1.0"),
    ):
        """
        初始化均值回归策略

        Args:
            engine: 交易引擎
            symbol: 交易对
            lookback_period: 回看周期
            std_dev_threshold: 标准差阈值
            position_size: 持仓大小
        """
        super().__init__(engine, symbol)
        self.lookback_period = lookback_period
        self.std_dev_threshold = std_dev_threshold
        self.position_size = position_size
        self.prices: List[Decimal] = []

    def _calculate_mean(self, prices: List[Decimal]) -> Decimal:
        """计算均值"""
        if not prices:
            return Decimal(0)
        return sum(prices) / len(prices)

    def _calculate_std_dev(
        self, prices: List[Decimal], mean: Decimal
    ) -> Decimal:
        """计算标准差"""
        if len(prices) < 2:
            return Decimal(0)
        variance = sum(
            (p - mean) ** 2 for p in prices
        ) / len(prices)
        return variance ** Decimal("0.5")

    async def on_ticker(self, ticker: Ticker) -> None:
        """处理Ticker事件"""
        self.prices.append(ticker.last_price)

        if len(self.prices) < self.lookback_period:
            return

        # 保持最近的价格
        if len(self.prices) > self.lookback_period:
            self.prices = self.prices[-self.lookback_period:]

        # 计算统计数据
        mean = self._calculate_mean(self.prices)
        std_dev = self._calculate_std_dev(self.prices, mean)
        current_price = ticker.last_price

        # 计算Z分数
        if std_dev > 0:
            z_score = (current_price - mean) / std_dev
        else:
            z_score = 0

        logger.info(
            f"{self.symbol} - 价格: {current_price}, 均值: {mean}, Z分数: {z_score}"
        )

        # 低于-2个标准差时买入
        if z_score < -self.std_dev_threshold and not self.in_position:
            logger.info(f"{self.symbol} 价格偏离均值过低，准备买入")
            try:
                order = await self.engine.create_order(
                    symbol=self.symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    quantity=self.position_size,
                )
                self.in_position = True
                logger.info(f"买入订单已创建: {order.order_id}")
            except Exception as e:
                logger.error(f"创建买入订单失败: {str(e)}")

        # 高于+2个标准差时卖出
        elif z_score > self.std_dev_threshold and self.in_position:
            logger.info(f"{self.symbol} 价格偏离均值过高，准备卖出")
            try:
                order = await self.engine.create_order(
                    symbol=self.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.MARKET,
                    quantity=self.position_size,
                )
                self.in_position = False
                logger.info(f"卖出订单已创建: {order.order_id}")
            except Exception as e:
                logger.error(f"创建卖出订单失败: {str(e)}")


class PortfolioManager:
    """投资组合管理器"""

    def __init__(self, engine: HyperliquidTradingEngine):
        """
        初始化投资组合管理器

        Args:
            engine: 交易引擎
        """
        self.engine = engine
        self.strategies: Dict[str, TradingStrategy] = {}
        self.portfolio_value = Decimal(0)
        self.pnl = Decimal(0)
        self.pnl_percent = Decimal(0)

    def add_strategy(self, strategy: TradingStrategy) -> None:
        """添加策略"""
        self.strategies[strategy.symbol] = strategy

    async def update_portfolio(self) -> None:
        """更新投资组合信息"""
        try:
            account = await self.engine.get_account_info()
            positions = await self.engine.get_positions()

            self.portfolio_value = account.total_balance

            # 计算P&L
            total_unrealized_pnl = sum(
                pos.unrealized_pnl for pos in positions
            )
            total_realized_pnl = sum(
                pos.realized_pnl for pos in positions
            )

            self.pnl = total_unrealized_pnl + total_realized_pnl

            if account.total_balance > 0:
                self.pnl_percent = (
                    self.pnl / account.total_balance * 100
                )

            logger.info(f"投资组合价值: {self.portfolio_value}")
            logger.info(f"总盈亏: {self.pnl} ({self.pnl_percent}%)")

        except Exception as e:
            logger.error(f"更新投资组合失败: {str(e)}")

    async def get_portfolio_summary(self) -> Dict:
        """获取投资组合摘要"""
        try:
            account = await self.engine.get_account_info()
            positions = await self.engine.get_positions()

            summary = {
                "timestamp": datetime.utcnow(),
                "total_balance": account.total_balance,
                "available_balance": account.available_balance,
                "positions": len(positions),
                "total_pnl": sum(p.unrealized_pnl for p in positions),
                "positions_detail": [
                    {
                        "symbol": p.symbol,
                        "size": p.size,
                        "entry_price": p.entry_price,
                        "mark_price": p.mark_price,
                        "pnl": p.unrealized_pnl,
                    }
                    for p in positions
                ],
            }
            return summary
        except Exception as e:
            logger.error(f"获取投资组合摘要失败: {str(e)}")
            return {}


# 使用示例
async def main():
    """主函数"""
    # 初始化引擎
    async with HyperliquidTradingEngine(
        api_key="your-api-key",
        api_secret="your-api-secret",
        testnet=True,
    ) as engine:
        # 创建投资组合管理器
        portfolio = PortfolioManager(engine)

        # 创建策略
        sma_strategy = SimpleMovingAverageStrategy(
            engine=engine,
            symbol="BTC",
            short_period=5,
            long_period=20,
            position_size=Decimal("0.1"),
        )
        portfolio.add_strategy(sma_strategy)

        mean_reversion_strategy = MeanReversionStrategy(
            engine=engine,
            symbol="ETH",
            lookback_period=20,
            std_dev_threshold=2.0,
            position_size=Decimal("1.0"),
        )
        portfolio.add_strategy(mean_reversion_strategy)

        # 启动实时流
        await engine.start_streaming(
            symbols=["BTC", "ETH"],
            channels=["ticker", "candle", "trade"],
        )

        # 注册处理器
        @engine.on_candle
        async def handle_candle(candle: Candle):
            if candle.symbol in portfolio.strategies:
                strategy = portfolio.strategies[candle.symbol]
                await strategy.on_candle(candle)

        @engine.on_ticker
        async def handle_ticker(ticker: Ticker):
            if ticker.symbol in portfolio.strategies:
                strategy = portfolio.strategies[ticker.symbol]
                await strategy.on_ticker(ticker)

        # 定期更新投资组合
        async def update_loop():
            while True:
                await asyncio.sleep(60)
                await portfolio.update_portfolio()
                summary = await portfolio.get_portfolio_summary()
                logger.info(f"投资组合摘要: {summary}")

        # 运行
        try:
            await asyncio.gather(update_loop())
        except KeyboardInterrupt:
            logger.info("停止交易")


if __name__ == "__main__":
    asyncio.run(main())
