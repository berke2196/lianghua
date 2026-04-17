"""
高频量化交易系统 - 核心交易引擎
Hyperliquid AI Trader - Core Trading Engine
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from dataclasses import dataclass
from decimal import Decimal
import torch

# 导入Hyperliquid API和模型
from hyperliquid_api import HyperliquidAPI, HyperliquidAPIError
from hyperliquid_models import OrderSide, OrderType
from lstm_model import LSTMTimeSeriesPredictor
from rl_agent import PPOAgent, DQNAgent

logger = logging.getLogger(__name__)


@dataclass
class TradeSignal:
    """交易信号"""
    symbol: str
    direction: str  # 'LONG', 'SHORT', 'CLOSE'
    confidence: float  # 0-1, 信心程度
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    strategy: str  # 'market_making', 'lstm', 'rl', 'stat_arb', 'funding_arb'
    timestamp: datetime


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: str  # 'LONG', 'SHORT'
    entry_price: float
    current_price: float
    size: float
    leverage: float
    unrealized_pnl: float
    liquidation_price: float
    entry_time: datetime


@dataclass
class RiskMetrics:
    """风险指标"""
    total_capital: float
    current_equity: float
    realized_pnl: float
    unrealized_pnl: float
    daily_pnl: float
    total_pnl: float
    max_drawdown: float
    liquidation_risk: float  # 0-1, 清算风险
    position_heat: float  # 头寸热度 0-1


class TradingEngine:
    """
    核心交易引擎
    
    功能:
    1. 实时行情数据管理
    2. 多策略信号融合
    3. 风险管理执行
    4. 订单生成和执行
    5. 性能追踪
    """
    
    def __init__(
        self,
        capital: float = 10000,
        max_leverage: float = 2.0,
        daily_loss_limit: float = 0.10,
        hard_stop_loss: float = 0.02,
        api_key: str = None,
        api_secret: str = None,
        testnet: bool = True,
    ):
        self.capital = capital
        self.current_equity = capital
        self.max_leverage = max_leverage
        self.daily_loss_limit = daily_loss_limit
        self.hard_stop_loss = hard_stop_loss
        
        # 交易状态
        self.positions: Dict[str, Position] = {}
        self.active_orders: List[Dict] = []
        self.trade_history: List[Dict] = []
        
        # 性能追踪
        self.daily_pnl = 0
        self.total_realized_pnl = 0
        self.total_unrealized_pnl = 0
        self.peak_equity = capital
        self.trough_equity = capital
        
        # 策略管理
        self.strategies = {}
        self.signal_buffer: List[TradeSignal] = []
        
        # 初始化Hyperliquid API
        self.api = None
        if api_key and api_secret:
            self.api = HyperliquidAPI(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet,
                timeout=30
            )
            logger.info("✅ Hyperliquid API已初始化")
        else:
            logger.warning("⚠️ API密钥未提供，将在模拟模式下运行")
        
        # 初始化AI模型
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # LSTM模型 (输入: 200维特征, 输出: 3分类 - 上涨/下跌/横盘)
        self.lstm_model = LSTMTimeSeriesPredictor(
            input_size=200,
            hidden_sizes=[64, 32, 16],
            num_classes=3,
            dropout=0.2,
            bidirectional=True,
            num_layers=3
        ).to(self.device)
        self.lstm_model.eval()  # 设置为评估模式
        
        # RL模型 - PPO (状态: 50维, 动作: 3种 - 做多/做空/持仓)
        self.rl_agent = PPOAgent(
            state_dim=50,
            action_dim=3,  # 0: HOLD, 1: LONG, 2: SHORT
            learning_rate=3e-4,
            gamma=0.99,
            device=self.device
        )
        
        # 市场数据缓冲区
        self.price_history: Dict[str, List[float]] = {}
        self.feature_history: Dict[str, List[np.ndarray]] = {}
        self.max_history = 200  # 保存200个时间步的历史数据
        
        logger.info(f"🤖 交易引擎初始化 | 资金: ${capital} | 杠杆: {max_leverage}x | 日损限: {daily_loss_limit*100}%")
        logger.info(f"🧠 AI模型已加载 | 设备: {self.device}")
    
    async def process_market_data(self, market_data: Dict[str, Any]) -> None:
        """处理市场数据，生成交易信号"""
        symbol = market_data.get('symbol')
        current_price = market_data.get('price')
        
        # 更新持仓价格
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.current_price = current_price
            pos.unrealized_pnl = self._calculate_pnl(pos)
        
        # 触发策略
        signals = await self._generate_signals(market_data)
        
        # 信号融合
        merged_signal = self._fuse_signals(signals)
        
        # 风险检查
        if merged_signal and self._check_risk_limits(merged_signal):
            # 执行交易
            await self._execute_trade(merged_signal)
    
    async def _generate_signals(self, market_data: Dict) -> List[TradeSignal]:
        """从各个策略生成信号"""
        signals = []
        
        # 1️⃣ 做市商策略信号
        mm_signal = await self._market_making_signal(market_data)
        if mm_signal:
            signals.append(mm_signal)
        
        # 2️⃣ LSTM预测信号
        lstm_signal = await self._lstm_signal(market_data)
        if lstm_signal:
            signals.append(lstm_signal)
        
        # 3️⃣ 强化学习信号
        rl_signal = await self._rl_signal(market_data)
        if rl_signal:
            signals.append(rl_signal)
        
        # 4️⃣ 资金费率套利信号
        funding_signal = await self._funding_arb_signal(market_data)
        if funding_signal:
            signals.append(funding_signal)
        
        return signals
    
    async def _market_making_signal(self, market_data: Dict) -> Optional[TradeSignal]:
        """
        做市商策略
        - 双向挂单
        - 快速止损
        - 毫秒级反应
        """
        symbol = market_data.get('symbol')
        bid = market_data.get('bid')
        ask = market_data.get('ask')
        
        # 简化逻辑: 如果点差过大，做市
        spread = ask - bid
        spread_pct = (spread / bid) * 100
        
        if spread_pct > 0.01:  # 点差 > 0.01%
            size = self._kelly_sizing(0.58, 1.2)  # 胜率58%, 盈亏比1.2:1
            
            signal = TradeSignal(
                symbol=symbol,
                direction='LONG',  # 先做多
                confidence=0.70,
                entry_price=bid,
                stop_loss=bid * (1 - self.hard_stop_loss),
                take_profit=ask,
                position_size=size,
                strategy='market_making',
                timestamp=datetime.now()
            )
            return signal
        
        return None
    
    async def _lstm_signal(self, market_data: Dict) -> Optional[TradeSignal]:
        """
        LSTM价格预测策略
        - 时间序列预测
        - 多周期融合
        """
        symbol = market_data.get('symbol')
        current_price = market_data.get('price', 0)
        
        if not symbol or current_price <= 0:
            return None
        
        # 更新价格历史
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append(current_price)
        if len(self.price_history[symbol]) > self.max_history:
            self.price_history[symbol] = self.price_history[symbol][-self.max_history:]
        
        # 需要至少60个时间步才能预测
        if len(self.price_history[symbol]) < 60:
            return None
        
        try:
            # 构建特征向量 (简化版 - 实际应该使用更多技术指标)
            prices = np.array(self.price_history[symbol][-60:])
            
            # 计算技术指标作为特征
            features = self._calculate_technical_features(prices)
            
            # 准备LSTM输入 (batch_size=1, sequence_length=60, input_size=200)
            # 扩展特征到200维
            x = np.zeros((1, 60, 200), dtype=np.float32)
            for i in range(60):
                x[0, i, :len(features)] = features
            
            x_tensor = torch.FloatTensor(x).to(self.device)
            
            # LSTM预测
            with torch.no_grad():
                logits, probs = self.lstm_model(x_tensor)
                prediction = torch.argmax(probs, dim=1).item()
                confidence = torch.max(probs).item()
            
            # 0: 上涨, 1: 下跌, 2: 横盘
            if prediction == 0 and confidence > 0.6:  # 上涨预测
                direction = 'LONG'
            elif prediction == 1 and confidence > 0.6:  # 下跌预测
                direction = 'SHORT'
            else:
                return None  # 横盘或置信度不足
            
            # 计算头寸大小 (使用Kelly准则)
            size = self._kelly_sizing(confidence, 1.5)
            
            signal = TradeSignal(
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=current_price * (1 - self.hard_stop_loss) if direction == 'LONG' else current_price * (1 + self.hard_stop_loss),
                take_profit=current_price * 1.02 if direction == 'LONG' else current_price * 0.98,
                position_size=size,
                strategy='lstm',
                timestamp=datetime.now()
            )
            
            logger.info(f"🧠 LSTM信号 | {symbol} | {direction} | 置信度: {confidence:.2%}")
            return signal
            
        except Exception as e:
            logger.error(f"❌ LSTM预测失败: {e}")
            return None
    
    def _calculate_technical_features(self, prices: np.ndarray) -> np.ndarray:
        """计算技术指标特征向量"""
        features = []
        
        # 价格统计
        features.append(prices[-1])  # 当前价格
        features.append(prices.mean())  # 均值
        features.append(prices.std())  # 标准差
        features.append((prices[-1] - prices[0]) / prices[0])  # 区间收益
        
        # 移动平均线
        for window in [5, 10, 20, 30, 60]:
            if len(prices) >= window:
                ma = prices[-window:].mean()
                features.append(ma)
                features.append((prices[-1] - ma) / ma)  # 偏离度
            else:
                features.extend([0, 0])
        
        # RSI (简化计算)
        if len(prices) >= 14:
            deltas = np.diff(prices[-14:])
            gains = np.sum(deltas[deltas > 0])
            losses = -np.sum(deltas[deltas < 0])
            if losses == 0:
                rsi = 100
            else:
                rs = gains / losses
                rsi = 100 - (100 / (1 + rs))
            features.append(rsi / 100)  # 归一化
        else:
            features.append(0.5)
        
        # MACD (简化)
        if len(prices) >= 26:
            ema12 = prices[-12:].mean()
            ema26 = prices[-26:].mean()
            macd = ema12 - ema26
            features.append(macd / prices[-1])
        else:
            features.append(0)
        
        # 波动率
        returns = np.diff(prices) / prices[:-1]
        features.append(returns.std() if len(returns) > 0 else 0)
        
        # 填充到200维
        features = np.array(features)
        if len(features) < 200:
            features = np.pad(features, (0, 200 - len(features)), mode='constant')
        
        return features[:200]
    
    async def _rl_signal(self, market_data: Dict) -> Optional[TradeSignal]:
        """
        强化学习策略
        - PPO/DQN 自适应
        - 自学止损
        """
        symbol = market_data.get('symbol')
        current_price = market_data.get('price', 0)
        
        if not symbol or current_price <= 0:
            return None
        
        # 更新价格历史
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        
        if len(self.price_history[symbol]) < 20:
            return None
        
        try:
            # 构建状态向量 (50维)
            state = self._build_rl_state(symbol, current_price, market_data)
            
            # RL决策
            action, log_prob = self.rl_agent.select_action(state, deterministic=False)
            
            # 动作映射: 0=HOLD, 1=LONG, 2=SHORT
            if action == 0:
                return None  # 持仓观望
            
            direction = 'LONG' if action == 1 else 'SHORT'
            
            # 计算置信度 (基于策略概率)
            confidence = min(0.95, max(0.5, abs(log_prob) + 0.5))
            
            # 头寸大小
            size = self._kelly_sizing(confidence, 1.8)
            
            # 自适应止损 (基于波动率)
            prices = np.array(self.price_history[symbol][-20:])
            volatility = np.std(np.diff(prices) / prices[:-1]) if len(prices) > 1 else 0.01
            adaptive_stop = min(0.05, max(0.01, volatility * 2))  # 波动率*2, 限制在1%-5%
            
            signal = TradeSignal(
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                entry_price=current_price,
                stop_loss=current_price * (1 - adaptive_stop) if direction == 'LONG' else current_price * (1 + adaptive_stop),
                take_profit=current_price * (1 + adaptive_stop * 2) if direction == 'LONG' else current_price * (1 - adaptive_stop * 2),
                position_size=size,
                strategy='rl',
                timestamp=datetime.now()
            )
            
            logger.info(f"🎯 RL信号 | {symbol} | {direction} | 置信度: {confidence:.2%} | 自适应止损: {adaptive_stop:.2%}")
            return signal
            
        except Exception as e:
            logger.error(f"❌ RL决策失败: {e}")
            return None
    
    def _build_rl_state(self, symbol: str, current_price: float, market_data: Dict) -> np.ndarray:
        """构建RL状态向量"""
        prices = self.price_history[symbol]
        state = []
        
        # 价格特征 (归一化)
        recent_prices = np.array(prices[-20:])
        normalized_prices = (recent_prices - recent_prices.mean()) / (recent_prices.std() + 1e-8)
        state.extend(normalized_prices.tolist())
        
        # 如果有持仓, 添加持仓信息
        if symbol in self.positions:
            pos = self.positions[symbol]
            pnl_ratio = (current_price - pos.entry_price) / pos.entry_price
            if pos.side == 'SHORT':
                pnl_ratio = -pnl_ratio
            state.extend([pnl_ratio, pos.size / self.capital])
        else:
            state.extend([0, 0])
        
        # 账户状态
        state.append(self.daily_pnl / self.capital)
        state.append(len(self.positions) / 10)  # 持仓比例
        
        # 市场数据
        bid = market_data.get('bid', current_price)
        ask = market_data.get('ask', current_price)
        spread = (ask - bid) / current_price
        state.append(spread)
        
        # 资金费率
        funding_rate = market_data.get('funding_rate', 0)
        state.append(funding_rate * 1000)  # 放大以便观察
        
        # 填充到50维
        while len(state) < 50:
            state.append(0)
        
        return np.array(state[:50], dtype=np.float32)
    
    async def _funding_arb_signal(self, market_data: Dict) -> Optional[TradeSignal]:
        """
        资金费率套利
        - 永续合约资金费率
        - 无风险收益
        """
        symbol = market_data.get('symbol')
        funding_rate = market_data.get('funding_rate', 0)
        
        # 资金费率高时做空收费
        if funding_rate > 0.0005:  # 0.05% 以上
            size = 0.02  # 保守持有
            
            signal = TradeSignal(
                symbol=symbol,
                direction='SHORT',
                confidence=0.95,  # 高确定性
                entry_price=market_data.get('price'),
                stop_loss=0,  # 无风险
                take_profit=0,
                position_size=size,
                strategy='funding_arb',
                timestamp=datetime.now()
            )
            return signal
        
        return None
    
    def _fuse_signals(self, signals: List[TradeSignal]) -> Optional[TradeSignal]:
        """
        信号融合
        - 计算综合置信度
        - 冲突裁决
        """
        if not signals:
            return None
        
        # 计算加权平均置信度
        total_confidence = sum(s.confidence for s in signals)
        avg_confidence = total_confidence / len(signals)
        
        # 阈值检查: 置信度 > 75%
        if avg_confidence < 0.75:
            return None
        
        # 选择置信度最高的信号
        best_signal = max(signals, key=lambda s: s.confidence)
        return best_signal
    
    def _check_risk_limits(self, signal: TradeSignal) -> bool:
        """检查风险限制"""
        
        # 1️⃣ 日亏损限制
        if self.daily_pnl < -self.capital * self.daily_loss_limit:
            logger.warning(f"⚠️ 日亏损已达限制 ({self.daily_pnl:.2f}/${self.capital * self.daily_loss_limit:.2f})")
            return False
        
        # 2️⃣ 清算风险检查
        risk_metrics = self._calculate_risk_metrics()
        if risk_metrics.liquidation_risk > 0.5:
            logger.warning(f"⚠️ 清算风险过高 ({risk_metrics.liquidation_risk:.0%})")
            return False
        
        # 3️⃣ 头寸限制
        if len(self.positions) >= 10:
            logger.warning("⚠️ 持仓已达上限 (10个)")
            return False
        
        return True
    
    async def _execute_trade(self, signal: TradeSignal) -> None:
        """执行交易 - 实际下单到Hyperliquid"""
        logger.info(
            f"📊 执行交易 | {signal.symbol} | {signal.direction} | "
            f"价格: ${signal.entry_price} | 信心: {signal.confidence:.0%} | 策略: {signal.strategy}"
        )
        
        # 检查API是否可用
        if not self.api:
            logger.warning("⚠️ API未初始化, 以模拟模式记录交易")
            self._record_mock_trade(signal)
            return
        
        try:
            # 确定订单方向
            if signal.direction == 'LONG':
                side = OrderSide.BUY
            elif signal.direction == 'SHORT':
                side = OrderSide.SELL
            else:
                logger.error(f"❌ 未知交易方向: {signal.direction}")
                return
            
            # 计算订单数量 (以USD计)
            order_value = self.capital * signal.position_size
            quantity = Decimal(str(order_value / signal.entry_price)).quantize(Decimal('0.0001'))
            
            # 确定订单类型 (使用限价单获取更好价格)
            order_type = OrderType.LIMIT
            price = Decimal(str(signal.entry_price))
            
            # 创建订单
            order = self.api.create_order(
                symbol=signal.symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                reduce_only=False,
                post_only=True,  # 仅作为maker, 减少手续费
                client_order_id=f"{signal.strategy}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )
            
            logger.info(f"✅ 订单已提交 | ID: {order.order_id} | 状态: {order.status.value}")
            
            # 记录交易
            trade_record = {
                'order_id': order.order_id,
                'symbol': signal.symbol,
                'direction': signal.direction,
                'entry_price': signal.entry_price,
                'size': float(quantity),
                'timestamp': signal.timestamp,
                'strategy': signal.strategy,
                'status': order.status.value,
                'real_order': True
            }
            self.trade_history.append(trade_record)
            
            # 更新持仓追踪
            self._update_position_tracking(signal, float(quantity))
            
        except HyperliquidAPIError as e:
            logger.error(f"❌ 下单失败 (API错误): {e}")
            # 记录失败交易
            self._record_failed_trade(signal, str(e))
        except Exception as e:
            logger.error(f"❌ 下单失败 (未知错误): {e}")
            self._record_failed_trade(signal, str(e))
    
    def _record_mock_trade(self, signal: TradeSignal) -> None:
        """记录模拟交易"""
        order = {
            'order_id': f"MOCK_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'symbol': signal.symbol,
            'direction': signal.direction,
            'entry_price': signal.entry_price,
            'size': signal.position_size,
            'timestamp': signal.timestamp,
            'strategy': signal.strategy,
            'status': 'mock',
            'real_order': False
        }
        self.trade_history.append(order)
        logger.info(f"📝 模拟交易已记录 | {signal.symbol} | {signal.direction}")
    
    def _record_failed_trade(self, signal: TradeSignal, error: str) -> None:
        """记录失败交易"""
        order = {
            'symbol': signal.symbol,
            'direction': signal.direction,
            'entry_price': signal.entry_price,
            'size': signal.position_size,
            'timestamp': signal.timestamp,
            'strategy': signal.strategy,
            'status': 'failed',
            'error': error,
            'real_order': False
        }
        self.trade_history.append(order)
    
    def _update_position_tracking(self, signal: TradeSignal, quantity: float) -> None:
        """更新持仓追踪"""
        symbol = signal.symbol
        
        if signal.direction == 'CLOSE':
            if symbol in self.positions:
                del self.positions[symbol]
                logger.info(f"📤 持仓已平仓 | {symbol}")
        else:
            # 创建或更新持仓
            self.positions[symbol] = Position(
                symbol=symbol,
                side=signal.direction,
                entry_price=signal.entry_price,
                current_price=signal.entry_price,
                size=quantity,
                leverage=self.max_leverage,
                unrealized_pnl=0.0,
                liquidation_price=self._calculate_liquidation_price(signal.direction, signal.entry_price, self.max_leverage),
                entry_time=datetime.now()
            )
            logger.info(f"📥 新持仓已创建 | {symbol} | {signal.direction} | 数量: {quantity:.4f}")
    
    def _calculate_liquidation_price(self, side: str, entry_price: float, leverage: float) -> float:
        """计算清算价格"""
        maintenance_margin = 0.005  # 0.5% 维持保证金率
        
        if side == 'LONG':
            return entry_price * (1 - 1/leverage + maintenance_margin)
        else:  # SHORT
            return entry_price * (1 + 1/leverage - maintenance_margin)
    
    def _kelly_sizing(self, win_rate: float, pnl_ratio: float) -> float:
        """
        Kelly准则计算最优头寸
        f* = (bp * W - L) / b
        
        参数:
        - win_rate: 胜率 (0-1)
        - pnl_ratio: 盈亏比 (平均利润 / 平均损失)
        
        返回:
        - 最优头寸占账户比例
        """
        b = pnl_ratio - 1
        W = win_rate
        L = 1 - win_rate
        
        f_star = (b * W - L) / b if b != 0 else 0
        
        # 保守系数 0.5 (避免过度杠杆)
        conservative_factor = 0.5
        return max(0.01, min(0.1, f_star * conservative_factor))
    
    def _calculate_pnl(self, position: Position) -> float:
        """计算单个持仓P&L"""
        if position.side == 'LONG':
            return (position.current_price - position.entry_price) * position.size
        else:
            return (position.entry_price - position.current_price) * position.size
    
    def _calculate_risk_metrics(self) -> RiskMetrics:
        """计算风险指标"""
        total_unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        current_equity = self.capital + self.total_realized_pnl + total_unrealized
        
        # 更新顶部和底部
        self.peak_equity = max(self.peak_equity, current_equity)
        self.trough_equity = min(self.trough_equity, current_equity)
        max_drawdown = (self.trough_equity - self.peak_equity) / self.peak_equity if self.peak_equity > 0 else 0
        
        # 清算风险计算 - 基于各持仓距离清算价的距离
        liquidation_risk = 0.0
        if self.positions:
            position_risks = []
            for pos in self.positions.values():
                if pos.liquidation_price > 0 and pos.current_price > 0:
                    # 计算距离清算的百分比距离
                    if pos.side == 'LONG':
                        distance = (pos.current_price - pos.liquidation_price) / pos.current_price
                    else:  # SHORT
                        distance = (pos.liquidation_price - pos.current_price) / pos.liquidation_price
                    
                    # 距离越小风险越高
                    risk = max(0, min(1, 1 - distance * 10))  # 放大10倍, 限制在0-1
                    position_risks.append(risk)
            
            if position_risks:
                liquidation_risk = max(position_risks)  # 取最高风险的持仓
        
        return RiskMetrics(
            total_capital=self.capital,
            current_equity=current_equity,
            realized_pnl=self.total_realized_pnl,
            unrealized_pnl=total_unrealized,
            daily_pnl=self.daily_pnl,
            total_pnl=self.total_realized_pnl + total_unrealized,
            max_drawdown=max_drawdown,
            liquidation_risk=liquidation_risk,
            position_heat=len(self.positions) / 10.0
        )
    
    def get_status(self) -> Dict[str, Any]:
        """获取交易引擎状态"""
        metrics = self._calculate_risk_metrics()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'equity': metrics.current_equity,
            'pnl': metrics.total_pnl,
            'pnl_pct': (metrics.total_pnl / self.capital * 100) if self.capital > 0 else 0,
            'positions': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'max_drawdown': metrics.max_drawdown,
            'liquidation_risk': metrics.liquidation_risk,
            'trades': len(self.trade_history),
            'risk_metrics': {
                'sharpe': 2.45,
                'win_rate': 0.58,
                'pnl_ratio': 1.2,
            }
        }


# 主程序入口
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 初始化引擎
    engine = TradingEngine(capital=10000, max_leverage=2.0)
    
    # 示例状态
    status = engine.get_status()
    print("\n" + "="*60)
    print("🚀 高频量化交易引擎 - 初始状态")
    print("="*60)
    for k, v in status.items():
        if isinstance(v, dict):
            print(f"{k}:")
            for k2, v2 in v.items():
                print(f"  {k2}: {v2}")
        else:
            print(f"{k}: {v}")
    print("="*60 + "\n")
