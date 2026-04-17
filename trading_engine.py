"""
完整的自动交易引擎
支持做空做多、多种策略、风险管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"


@dataclass
class Order:
    """订单数据类"""
    order_id: str
    symbol: str
    side: OrderSide
    size: float
    price: Optional[float]
    leverage: int
    order_type: OrderType
    status: str
    created_at: datetime
    filled_size: float = 0.0
    average_price: float = 0.0


@dataclass
class Position:
    """持仓数据类"""
    symbol: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    leverage: int
    unrealized_pnl: float
    pnl_percent: float
    created_at: datetime


@dataclass
class Trade:
    """交易记录"""
    trade_id: str
    symbol: str
    side: OrderSide
    size: float
    price: float
    timestamp: datetime
    status: str
    pnl: Optional[float] = None


class TradingStrategy:
    """交易策略基类"""

    def __init__(self, symbol: str, api):
        self.symbol = symbol
        self.api = api
        self.prices = []
        self.max_history = 100

    async def analyze(self, prices: List[float]) -> Dict:
        """
        分析市场数据
        返回信号：{'action': 'BUY'/'SELL'/'HOLD', 'confidence': 0-1, 'reason': str}
        """
        raise NotImplementedError

    def calculate_sma(self, prices: List[float], period: int) -> float:
        """计算简单移动平均线"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period

    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """计算相对强弱指数 (RSI)"""
        if len(prices) < period + 1:
            return 50

        deltas = np.diff(prices[-period-1:])
        seed = deltas[:period]
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        rs = up / down if down != 0 else 0
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi

    def calculate_macd(self, prices: List[float]) -> tuple:
        """计算 MACD 指标"""
        if len(prices) < 26:
            return 0, 0, 0

        ema12 = self.calculate_ema(prices, 12)
        ema26 = self.calculate_ema(prices, 26)
        macd = ema12 - ema26

        signal_prices = prices[-26:]
        signal = self.calculate_ema(signal_prices, 9)
        histogram = macd - signal

        return macd, signal, histogram

    def calculate_ema(self, prices: List[float], period: int) -> float:
        """计算指数移动平均线"""
        if not prices:
            return 0
        if len(prices) == 1:
            return prices[0]

        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = price * multiplier + ema * (1 - multiplier)
        return ema

    def calculate_bollinger_bands(self, prices: List[float], period: int = 20, std_dev: int = 2):
        """计算布林带"""
        if len(prices) < period:
            return prices[-1], prices[-1], prices[-1]

        sma = self.calculate_sma(prices, period)
        variance = np.var(prices[-period:])
        std = np.sqrt(variance)

        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)

        return upper, sma, lower


class MomentumStrategy(TradingStrategy):
    """动量策略 - 基于 RSI 和 MACD"""

    async def analyze(self, prices: List[float]) -> Dict:
        if len(prices) < 26:
            return {'action': 'HOLD', 'confidence': 0, 'reason': '数据不足'}

        rsi = self.calculate_rsi(prices)
        macd, signal, histogram = self.calculate_macd(prices)

        # RSI 信号
        if rsi < 30:
            rsi_signal = 'BUY'
        elif rsi > 70:
            rsi_signal = 'SELL'
        else:
            rsi_signal = 'HOLD'

        # MACD 信号
        if histogram > 0 and macd > signal:
            macd_signal = 'BUY'
        elif histogram < 0 and macd < signal:
            macd_signal = 'SELL'
        else:
            macd_signal = 'HOLD'

        # 综合判断
        if rsi_signal == 'BUY' and macd_signal == 'BUY':
            action = 'BUY'
            confidence = 0.8
        elif rsi_signal == 'SELL' and macd_signal == 'SELL':
            action = 'SELL'
            confidence = 0.8
        else:
            action = 'HOLD'
            confidence = 0.5

        return {
            'action': action,
            'confidence': confidence,
            'reason': f'RSI={rsi:.2f}({rsi_signal}) MACD={macd:.4f}({macd_signal})',
            'rsi': rsi,
            'macd': macd,
            'signal': signal
        }


class MeanReversionStrategy(TradingStrategy):
    """均值回归策略 - 基于布林带"""

    async def analyze(self, prices: List[float]) -> Dict:
        if len(prices) < 20:
            return {'action': 'HOLD', 'confidence': 0, 'reason': '数据不足'}

        upper, middle, lower = self.calculate_bollinger_bands(prices)
        current_price = prices[-1]

        # 计算价格与布林带的距离
        upper_distance = (upper - current_price) / (upper - middle) if upper != middle else 0
        lower_distance = (current_price - lower) / (middle - lower) if middle != lower else 0

        if current_price < lower and lower_distance < 1:
            action = 'BUY'
            confidence = min(1.0, 0.6 + lower_distance * 0.4)
        elif current_price > upper and upper_distance < 1:
            action = 'SELL'
            confidence = min(1.0, 0.6 + upper_distance * 0.4)
        else:
            action = 'HOLD'
            confidence = 0.5

        return {
            'action': action,
            'confidence': confidence,
            'reason': f'价格={current_price:.2f} 上轨={upper:.2f} 下轨={lower:.2f}',
            'upper': upper,
            'middle': middle,
            'lower': lower
        }


class TrendFollowingStrategy(TradingStrategy):
    """趋势跟踪策略 - 基于移动平均线"""

    async def analyze(self, prices: List[float]) -> Dict:
        if len(prices) < 50:
            return {'action': 'HOLD', 'confidence': 0, 'reason': '数据不足'}

        sma_10 = self.calculate_sma(prices, 10)
        sma_20 = self.calculate_sma(prices, 20)
        sma_50 = self.calculate_sma(prices, 50)
        current_price = prices[-1]

        # 金叉死叉判断
        if sma_10 > sma_20 > sma_50:
            action = 'BUY'
            confidence = 0.75
            reason = '多头排列：快速均线 > 中期均线 > 长期均线'
        elif sma_10 < sma_20 < sma_50:
            action = 'SELL'
            confidence = 0.75
            reason = '空头排列：快速均线 < 中期均线 < 长期均线'
        else:
            action = 'HOLD'
            confidence = 0.5
            reason = '均线混乱，等待明确信号'

        return {
            'action': action,
            'confidence': confidence,
            'reason': reason,
            'sma_10': sma_10,
            'sma_20': sma_20,
            'sma_50': sma_50
        }


class AutoTradingEngine:
    """自动交易引擎"""

    def __init__(self, api, user_id: str):
        self.api = api
        self.user_id = user_id
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.trades: List[Trade] = []
        self.strategies = {
            'momentum': MomentumStrategy,
            'mean_reversion': MeanReversionStrategy,
            'trend_following': TrendFollowingStrategy
        }
        self.active_strategy = 'momentum'
        self.is_running = False
        self.max_position_size = 0.1  # 单个持仓最多占资金10%
        self.stop_loss_percent = 0.05  # 5% 止损
        self.take_profit_percent = 0.10  # 10% 止盈

    async def start_auto_trading(self, symbol: str, strategy: str = 'momentum'):
        """启动自动交易"""
        self.is_running = True
        self.active_strategy = strategy

        logger.info(f"🤖 启动自动交易 | 用户: {self.user_id} | 交易对: {symbol} | 策略: {strategy}")

        try:
            while self.is_running:
                await self.trading_cycle(symbol)
                await asyncio.sleep(30)  # 每30秒执行一次
        except Exception as e:
            logger.error(f"❌ 自动交易错误: {e}")
            self.is_running = False

    async def trading_cycle(self, symbol: str):
        """一个完整的交易周期"""
        try:
            # 1. 获取价格数据
            prices = await self.api.get_candlesticks(symbol, interval='1m', limit=100)
            if not prices:
                return

            # 2. 运行策略分析
            strategy_class = self.strategies[self.active_strategy]
            strategy = strategy_class(symbol, self.api)
            signal = await strategy.analyze(prices)

            logger.info(f"📊 {symbol} 分析信号: {signal['action']} (信度: {signal['confidence']:.2f})")

            # 3. 获取账户信息
            account = await self.api.get_account_info()
            balance = account.get('balance', 0)

            # 4. 执行交易决策
            await self.execute_trading_decision(symbol, signal, balance)

            # 5. 管理风险 - 检查止损止盈
            await self.manage_risk(symbol)

        except Exception as e:
            logger.error(f"❌ 交易周期错误: {e}")

    async def execute_trading_decision(self, symbol: str, signal: Dict, balance: float):
        """执行交易决策"""
        action = signal['action']
        confidence = signal['confidence']

        # 只在信心度足够高时执行
        if confidence < 0.6:
            return

        # 获取当前价格
        price = await self.api.get_current_price(symbol)
        if not price:
            return

        # 计算交易大小
        max_size = balance * self.max_position_size / price
        trade_size = max_size * confidence

        if action == 'BUY':
            # 检查是否已有多头持仓
            if symbol in self.positions and self.positions[symbol].side == PositionSide.LONG:
                return

            # 平掉空头
            if symbol in self.positions and self.positions[symbol].side == PositionSide.SHORT:
                await self.close_position(symbol)
                await asyncio.sleep(2)

            # 开多头
            await self.place_order(
                symbol=symbol,
                side=OrderSide.BUY,
                size=trade_size,
                price=None,
                leverage=1
            )

        elif action == 'SELL':
            # 检查是否已有空头持仓
            if symbol in self.positions and self.positions[symbol].side == PositionSide.SHORT:
                return

            # 平掉多头
            if symbol in self.positions and self.positions[symbol].side == PositionSide.LONG:
                await self.close_position(symbol)
                await asyncio.sleep(2)

            # 开空头
            await self.place_order(
                symbol=symbol,
                side=OrderSide.SELL,
                size=trade_size,
                price=None,
                leverage=1
            )

    async def manage_risk(self, symbol: str):
        """风险管理 - 止损止盈"""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        current_price = await self.api.get_current_price(symbol)
        if not current_price:
            return

        # 计算盈亏百分比
        if position.side == PositionSide.LONG:
            pnl_percent = (current_price - position.entry_price) / position.entry_price
        else:
            pnl_percent = (position.entry_price - current_price) / position.entry_price

        # 止损
        if pnl_percent < -self.stop_loss_percent:
            logger.warning(f"⚠️ {symbol} 触发止损 | 亏损: {pnl_percent:.2%}")
            await self.close_position(symbol)

        # 止盈
        elif pnl_percent > self.take_profit_percent:
            logger.info(f"✅ {symbol} 触发止盈 | 盈利: {pnl_percent:.2%}")
            await self.close_position(symbol)

    async def place_order(self, symbol: str, side: OrderSide, size: float, price: Optional[float] = None, leverage: int = 1):
        """下单"""
        try:
            order = await self.api.place_order(
                symbol=symbol,
                side=side,
                size=size,
                price=price,
                leverage=leverage
            )
            self.orders[order['order_id']] = order
            logger.info(f"✅ 订单已下单 | {symbol} {side.value} {size} @ ¥{price or '市价'}")
            return order
        except Exception as e:
            logger.error(f"❌ 下单失败: {e}")

    async def close_position(self, symbol: str):
        """平仓"""
        if symbol not in self.positions:
            return

        position = self.positions[symbol]
        close_side = OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY

        try:
            order = await self.api.place_order(
                symbol=symbol,
                side=close_side,
                size=position.size,
                price=None,
                leverage=position.leverage
            )
            logger.info(f"✅ 平仓成功 | {symbol} {position.side.value}")
            del self.positions[symbol]
            return order
        except Exception as e:
            logger.error(f"❌ 平仓失败: {e}")

    def stop_auto_trading(self):
        """停止自动交易"""
        self.is_running = False
        logger.info(f"⏹️ 已停止自动交易 | 用户: {self.user_id}")

    async def get_statistics(self) -> Dict:
        """获取交易统计"""
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl and t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl and t.pnl < 0)
        total_pnl = sum(t.pnl or 0 for t in self.trades)

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'positions': len(self.positions),
            'active_positions': [
                {
                    'symbol': p.symbol,
                    'side': p.side.value,
                    'size': p.size,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'pnl_percent': p.pnl_percent
                }
                for p in self.positions.values()
            ]
        }
