"""
完整的回测流程管理
支持：数据加载、特征计算、模型推理、信号生成、订单执行、风险管理
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Callable
from datetime import datetime
import logging
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """信号类型"""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 100000
    commission: float = 0.001
    slippage: float = 0.001
    position_size: float = 0.95
    max_positions: int = 10
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.05
    use_risk_management: bool = True
    use_feature_cache: bool = True
    feature_cache_dir: str = "./cache/features"
    data_cache_dir: str = "./cache/data"
    log_level: str = "INFO"


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_return: float
    annual_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    num_trades: int
    num_winning_trades: int
    num_losing_trades: int
    avg_trade_pnl: float
    largest_win: float
    largest_loss: float
    equity_curve: np.ndarray = field(default_factory=lambda: np.array([]))
    trades: List[Dict] = field(default_factory=list)
    daily_returns: np.ndarray = field(default_factory=lambda: np.array([]))


class Backtester:
    """完整的回测系统"""
    
    def __init__(self, config: BacktestConfig = None):
        """初始化回测器"""
        self.config = config or BacktestConfig()
        self.logger = self._setup_logger()
        
        # 数据缓存
        self.data_cache: Dict[str, pd.DataFrame] = {}
        self.features_cache: Dict[str, pd.DataFrame] = {}
        
        # 回测状态
        self.current_date = None
        self.positions: Dict[str, Dict] = {}
        self.equity_history = []
        self.orders = []
        self.trades = []
        
        self.logger.info(f"Backtester initialized with config: {config}")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        logger.setLevel(self.config.log_level)
        return logger
    
    def load_data(self, 
                  symbol: str,
                  start_date: datetime,
                  end_date: datetime,
                  data_source: Optional[Callable] = None) -> pd.DataFrame:
        """
        加载历史数据
        
        Args:
            symbol: 交易对
            start_date: 开始日期
            end_date: 结束日期
            data_source: 数据源函数
        
        Returns:
            OHLCV数据
        """
        cache_key = f"{symbol}_{start_date}_{end_date}"
        
        # 从缓存加载
        if cache_key in self.data_cache:
            self.logger.info(f"Loaded {symbol} from cache")
            return self.data_cache[cache_key]
        
        # 从数据源加载
        if data_source is None:
            raise ValueError("data_source is required when data not in cache")
        
        data = data_source(symbol, start_date, end_date)
        
        # 验证数据
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        if not all(col in data.columns for col in required_columns):
            raise ValueError(f"Data must contain columns: {required_columns}")
        
        # 计算基础特征
        data = self._calculate_ohlc_features(data)
        
        # 缓存数据
        self.data_cache[cache_key] = data
        
        self.logger.info(f"Loaded {len(data)} bars for {symbol}")
        return data
    
    def _calculate_ohlc_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """计算OHLC特征"""
        df = data.copy()
        
        # 基础特征
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['hl_ratio'] = df['high'] / df['low']
        df['cc_ratio'] = df['close'] / df['close'].shift(1)
        df['oc_ratio'] = df['open'] / df['close']
        
        # 成交量特征
        df['volume_sma'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['volume_sma']
        
        # 波动率
        df['volatility'] = df['returns'].rolling(20).std()
        df['high_low'] = (df['high'] - df['low']) / df['close']
        
        return df.fillna(method='bfill')
    
    def calculate_features(self,
                          data: pd.DataFrame,
                          feature_functions: Optional[List[Callable]] = None,
                          cache: bool = True) -> pd.DataFrame:
        """
        计算特征
        
        Args:
            data: OHLCV数据
            feature_functions: 特征计算函数列表
            cache: 是否缓存特征
        
        Returns:
            包含特征的数据
        """
        df = data.copy()
        
        # 默认特征函数
        if feature_functions is None:
            feature_functions = [
                self._calculate_ma_features,
                self._calculate_momentum_features,
                self._calculate_volatility_features,
                self._calculate_volume_features,
            ]
        
        # 计算特征
        for func in feature_functions:
            try:
                df = func(df)
            except Exception as e:
                self.logger.warning(f"Error calculating features with {func.__name__}: {e}")
        
        return df
    
    def _calculate_ma_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """移动平均特征"""
        for period in [5, 10, 20, 50, 200]:
            data[f'sma_{period}'] = data['close'].rolling(period).mean()
            data[f'ema_{period}'] = data['close'].ewm(span=period).mean()
        
        data['ma_5_20_cross'] = (data['sma_5'] > data['sma_20']).astype(int)
        data['ma_20_50_cross'] = (data['sma_20'] > data['sma_50']).astype(int)
        
        return data
    
    def _calculate_momentum_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """动量特征"""
        data['rsi_14'] = self._calculate_rsi(data['close'], 14)
        data['rsi_28'] = self._calculate_rsi(data['close'], 28)
        
        data['macd'] = data['close'].ewm(span=12).mean() - data['close'].ewm(span=26).mean()
        data['macd_signal'] = data['macd'].ewm(span=9).mean()
        data['macd_hist'] = data['macd'] - data['macd_signal']
        
        data['momentum'] = data['close'] - data['close'].shift(10)
        
        return data
    
    def _calculate_volatility_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """波动率特征"""
        data['atr_14'] = self._calculate_atr(data, 14)
        data['bb_upper'] = data['close'].rolling(20).mean() + \
                          data['close'].rolling(20).std() * 2
        data['bb_lower'] = data['close'].rolling(20).mean() - \
                          data['close'].rolling(20).std() * 2
        data['bb_width'] = (data['bb_upper'] - data['bb_lower']) / data['close']
        
        return data
    
    def _calculate_volume_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """成交量特征"""
        data['obv'] = self._calculate_obv(data)
        data['ad'] = self._calculate_ad(data)
        data['cmf'] = self._calculate_cmf(data, 20)
        
        return data
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """计算ATR"""
        tr1 = data['high'] - data['low']
        tr2 = abs(data['high'] - data['close'].shift())
        tr3 = abs(data['low'] - data['close'].shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
    
    def _calculate_obv(self, data: pd.DataFrame) -> pd.Series:
        """计算OBV"""
        obv = (data['volume'] * (2 * (data['close'] - data['close'].shift()).gt(0) - 1)).fillna(0).cumsum()
        return obv
    
    def _calculate_ad(self, data: pd.DataFrame) -> pd.Series:
        """计算A/D Line"""
        clv = ((data['close'] - data['low']) - (data['high'] - data['close'])) / \
              (data['high'] - data['low'] + 1e-8)
        ad = (clv * data['volume']).fillna(0).cumsum()
        return ad
    
    def _calculate_cmf(self, data: pd.DataFrame, period: int = 20) -> pd.Series:
        """计算CMF"""
        clv = ((data['close'] - data['low']) - (data['high'] - data['close'])) / \
              (data['high'] - data['low'] + 1e-8)
        cmf = (clv * data['volume']).rolling(period).sum() / data['volume'].rolling(period).sum()
        return cmf
    
    def generate_signals(self,
                        data: pd.DataFrame,
                        signal_func: Callable) -> np.ndarray:
        """
        生成交易信号
        
        Args:
            data: 包含特征的数据
            signal_func: 信号生成函数
        
        Returns:
            信号数组 (1: 买, -1: 卖, 0: 无)
        """
        signals = signal_func(data)
        
        # 验证信号
        if not isinstance(signals, (np.ndarray, pd.Series)):
            raise ValueError("signal_func must return numpy array or pandas Series")
        
        if isinstance(signals, pd.Series):
            signals = signals.values
        
        # 确保信号为整数
        signals = np.round(signals).astype(int)
        
        self.logger.info(f"Generated signals: {np.sum(signals > 0)} buy, {np.sum(signals < 0)} sell")
        
        return signals
    
    def execute_backtest(self,
                        symbol: str,
                        data: pd.DataFrame,
                        signals: np.ndarray,
                        start_date: datetime = None,
                        end_date: datetime = None) -> BacktestResult:
        """
        执行完整回测
        
        Args:
            symbol: 交易对
            data: OHLCV数据
            signals: 交易信号
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            回测结果
        """
        start_date = start_date or data.index[0]
        end_date = end_date or data.index[-1]
        
        self.logger.info(f"Starting backtest for {symbol} from {start_date} to {end_date}")
        
        # 初始化
        n = len(data)
        closes = data['close'].values
        highs = data['high'].values
        lows = data['low'].values
        volumes = data['volume'].values
        
        equity = np.full(n, self.config.initial_capital, dtype=np.float64)
        trades = []
        position = None
        entry_price = None
        entry_idx = None
        current_capital = self.config.initial_capital
        
        for i in range(1, n):
            # 风险管理
            if position is not None:
                # 止损
                pnl_pct = (closes[i] - entry_price) / entry_price * position['direction']
                if pnl_pct <= -self.config.stop_loss_pct:
                    exit_price = closes[i]
                    pnl = (exit_price - entry_price) * position['qty'] * position['direction']
                    commission = pnl * self.config.commission
                    net_pnl = pnl - commission
                    
                    trades.append({
                        'entry_date': data.index[entry_idx],
                        'exit_date': data.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'quantity': position['qty'],
                        'pnl': net_pnl,
                        'pnl_pct': net_pnl / (entry_price * position['qty']),
                        'hold_bars': i - entry_idx,
                        'reason': 'stop_loss'
                    })
                    
                    current_capital += net_pnl
                    position = None
                    entry_price = None
                
                # 止盈
                elif pnl_pct >= self.config.take_profit_pct:
                    exit_price = closes[i]
                    pnl = (exit_price - entry_price) * position['qty'] * position['direction']
                    commission = pnl * self.config.commission
                    net_pnl = pnl - commission
                    
                    trades.append({
                        'entry_date': data.index[entry_idx],
                        'exit_date': data.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'quantity': position['qty'],
                        'pnl': net_pnl,
                        'pnl_pct': net_pnl / (entry_price * position['qty']),
                        'hold_bars': i - entry_idx,
                        'reason': 'take_profit'
                    })
                    
                    current_capital += net_pnl
                    position = None
                    entry_price = None
            
            # 处理信号
            if signals[i] != 0 and signals[i] != (signals[i-1] if i > 0 else 0):
                # 平仓现有头寸
                if position is not None:
                    exit_price = closes[i]
                    pnl = (exit_price - entry_price) * position['qty'] * position['direction']
                    commission = pnl * self.config.commission
                    net_pnl = pnl - commission
                    
                    trades.append({
                        'entry_date': data.index[entry_idx],
                        'exit_date': data.index[i],
                        'entry_price': entry_price,
                        'exit_price': exit_price,
                        'quantity': position['qty'],
                        'pnl': net_pnl,
                        'pnl_pct': net_pnl / (entry_price * position['qty']),
                        'hold_bars': i - entry_idx,
                        'reason': 'signal'
                    })
                    
                    current_capital += net_pnl
                    position = None
                    entry_price = None
                
                # 建立新头寸
                if signals[i] != 0:
                    qty = (current_capital * self.config.position_size) / closes[i]
                    entry_price = closes[i]
                    entry_idx = i
                    position = {
                        'direction': signals[i],
                        'qty': qty,
                        'entry_price': entry_price
                    }
            
            # 计算权益
            if position is not None:
                unrealized_pnl = (closes[i] - entry_price) * position['qty'] * position['direction']
                equity[i] = current_capital + unrealized_pnl
            else:
                equity[i] = current_capital
        
        # 计算统计指标
        final_equity = equity[-1]
        total_return = (final_equity - self.config.initial_capital) / self.config.initial_capital
        daily_returns = np.diff(equity) / equity[:-1]
        
        # 计算年化收益
        days = (end_date - start_date).days
        years = days / 365
        annual_return = (final_equity / self.config.initial_capital) ** (1 / years) - 1 if years > 0 else total_return
        
        # 计算最大回撤
        peak = np.maximum.accumulate(equity)
        drawdown = (equity - peak) / peak
        max_drawdown = np.min(drawdown)
        
        # 计算交易统计
        if trades:
            winning_trades = [t for t in trades if t['pnl'] > 0]
            losing_trades = [t for t in trades if t['pnl'] <= 0]
            win_rate = len(winning_trades) / len(trades)
            
            gains = sum(t['pnl'] for t in winning_trades)
            losses = abs(sum(t['pnl'] for t in losing_trades))
            profit_factor = gains / losses if losses > 0 else 0
            
            avg_trade_pnl = np.mean([t['pnl'] for t in trades])
            largest_win = max([t['pnl'] for t in trades])
            largest_loss = min([t['pnl'] for t in trades])
        else:
            win_rate = 0
            profit_factor = 0
            avg_trade_pnl = 0
            largest_win = 0
            largest_loss = 0
        
        # 计算夏普比率
        sharpe_ratio = 0
        if np.std(daily_returns) > 0:
            sharpe_ratio = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)
        
        result = BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.config.initial_capital,
            final_equity=final_equity,
            total_return=total_return,
            annual_return=annual_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            num_trades=len(trades),
            num_winning_trades=len(winning_trades) if trades else 0,
            num_losing_trades=len(losing_trades) if trades else 0,
            avg_trade_pnl=avg_trade_pnl,
            largest_win=largest_win,
            largest_loss=largest_loss,
            equity_curve=equity,
            trades=trades,
            daily_returns=daily_returns
        )
        
        self.logger.info(f"Backtest completed: {result}")
        
        return result
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"Backtester(config={self.config})"


__all__ = ['Backtester', 'BacktestConfig', 'BacktestResult']
