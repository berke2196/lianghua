"""
性能分析模块 - 计算完整的财务指标
包括：Sharpe比、最大回撤、胜率、收益因子、风险调整收益等
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """性能指标"""
    # 收益指标
    total_return: float
    annual_return: float
    monthly_return: float
    daily_return: float
    
    # 风险指标
    annual_volatility: float
    monthly_volatility: float
    daily_volatility: float
    max_drawdown: float
    max_drawdown_duration: int
    
    # 风险调整收益
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    information_ratio: Optional[float] = None
    
    # 交易指标
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    avg_trade_pnl: float
    largest_win: float
    largest_loss: float
    payoff_ratio: float
    
    # 其他
    num_trades: int
    num_winning_trades: int
    num_losing_trades: int
    avg_bars_in_trade: float


class PerformanceAnalytics:
    """性能分析器"""
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        初始化分析器
        
        Args:
            risk_free_rate: 无风险利率（年化）
        """
        self.risk_free_rate = risk_free_rate
    
    def calculate_metrics(self,
                         equity_curve: np.ndarray,
                         trades: List[Dict],
                         dates: Optional[pd.DatetimeIndex] = None) -> PerformanceMetrics:
        """
        计算所有性能指标
        
        Args:
            equity_curve: 权益曲线
            trades: 交易列表
            dates: 日期索引
        
        Returns:
            性能指标
        """
        
        # 计算收益
        returns = np.diff(equity_curve) / equity_curve[:-1]
        total_return = (equity_curve[-1] - equity_curve[0]) / equity_curve[0]
        
        # 时间信息
        if dates is not None:
            n_days = (dates[-1] - dates[0]).days + 1
            n_years = n_days / 365.25
        else:
            n_days = len(equity_curve)
            n_years = n_days / 252
        
        # 年化收益
        annual_return = (equity_curve[-1] / equity_curve[0]) ** (1 / n_years) - 1 if n_years > 0 else 0
        
        # 月化收益
        monthly_return = annual_return / 12 if n_years > 0 else 0
        
        # 日化收益
        daily_return = np.mean(returns)
        
        # 波动率
        annual_volatility = np.std(returns) * np.sqrt(252)
        monthly_volatility = np.std(returns) * np.sqrt(12)
        daily_volatility = np.std(returns)
        
        # 最大回撤
        max_dd, max_dd_duration = self._calculate_max_drawdown(equity_curve)
        
        # 夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio(returns, self.risk_free_rate / 252)
        
        # 索提诺比率
        sortino_ratio = self._calculate_sortino_ratio(returns, self.risk_free_rate / 252)
        
        # 卡玛比率
        calmar_ratio = self._calculate_calmar_ratio(annual_return, max_dd)
        
        # 交易统计
        if trades:
            winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
            losing_trades = [t for t in trades if t.get('pnl', 0) <= 0]
            
            win_rate = len(winning_trades) / len(trades)
            
            gains = sum(t.get('pnl', 0) for t in winning_trades)
            losses = abs(sum(t.get('pnl', 0) for t in losing_trades))
            profit_factor = gains / losses if losses > 0 else 0
            
            avg_win = np.mean([t.get('pnl', 0) for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.get('pnl', 0) for t in losing_trades]) if losing_trades else 0
            
            avg_trade_pnl = np.mean([t.get('pnl', 0) for t in trades])
            largest_win = max([t.get('pnl', 0) for t in trades])
            largest_loss = min([t.get('pnl', 0) for t in trades])
            
            payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            avg_bars_in_trade = np.mean([t.get('hold_bars', 0) for t in trades])
            
            num_trades = len(trades)
            num_winning = len(winning_trades)
            num_losing = len(losing_trades)
        else:
            win_rate = 0
            profit_factor = 0
            avg_win = 0
            avg_loss = 0
            avg_trade_pnl = 0
            largest_win = 0
            largest_loss = 0
            payoff_ratio = 0
            avg_bars_in_trade = 0
            num_trades = 0
            num_winning = 0
            num_losing = 0
        
        return PerformanceMetrics(
            total_return=total_return,
            annual_return=annual_return,
            monthly_return=monthly_return,
            daily_return=daily_return,
            annual_volatility=annual_volatility,
            monthly_volatility=monthly_volatility,
            daily_volatility=daily_volatility,
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            calmar_ratio=calmar_ratio,
            win_rate=win_rate,
            profit_factor=profit_factor,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_trade_pnl=avg_trade_pnl,
            largest_win=largest_win,
            largest_loss=largest_loss,
            payoff_ratio=payoff_ratio,
            num_trades=num_trades,
            num_winning_trades=num_winning,
            num_losing_trades=num_losing,
            avg_bars_in_trade=avg_bars_in_trade
        )
    
    def _calculate_max_drawdown(self, equity_curve: np.ndarray) -> Tuple[float, int]:
        """计算最大回撤和持续时间"""
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak
        
        max_dd_idx = np.argmin(drawdown)
        max_dd = drawdown[max_dd_idx]
        
        # 计算持续时间
        peak_idx = np.where(peak[:max_dd_idx + 1] == peak[max_dd_idx])[0]
        if len(peak_idx) > 0:
            duration = max_dd_idx - peak_idx[-1]
        else:
            duration = max_dd_idx
        
        return max_dd, duration
    
    def _calculate_sharpe_ratio(self,
                               returns: np.ndarray,
                               risk_free_rate: float) -> float:
        """计算夏普比率"""
        excess_returns = returns - risk_free_rate
        if np.std(excess_returns) == 0:
            return 0.0
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    def _calculate_sortino_ratio(self,
                                returns: np.ndarray,
                                risk_free_rate: float) -> float:
        """计算索提诺比率"""
        excess_returns = returns - risk_free_rate
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) == 0:
            downside_vol = np.std(excess_returns)
        else:
            downside_vol = np.sqrt(np.mean(negative_returns ** 2))
        
        if downside_vol == 0:
            return 0.0
        
        return np.mean(excess_returns) / downside_vol * np.sqrt(252)
    
    def _calculate_calmar_ratio(self,
                               annual_return: float,
                               max_drawdown: float) -> float:
        """计算卡玛比率"""
        if max_drawdown == 0 or max_drawdown >= 0:
            return 0.0
        return annual_return / abs(max_drawdown)
    
    def calculate_information_ratio(self,
                                   strategy_returns: np.ndarray,
                                   benchmark_returns: np.ndarray) -> float:
        """计算信息比率"""
        excess_returns = strategy_returns - benchmark_returns
        tracking_error = np.std(excess_returns)
        
        if tracking_error == 0:
            return 0.0
        
        return np.mean(excess_returns) / tracking_error * np.sqrt(252)
    
    def calculate_var(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """计算风险价值"""
        return np.percentile(returns, (1 - confidence) * 100)
    
    def calculate_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """计算条件风险价值（预期缺口）"""
        var = self.calculate_var(returns, confidence)
        return returns[returns <= var].mean()
    
    def calculate_monthly_returns(self,
                                 equity_curve: np.ndarray,
                                 dates: pd.DatetimeIndex) -> pd.DataFrame:
        """计算月度收益"""
        equity_series = pd.Series(equity_curve, index=dates)
        monthly_equity = equity_series.resample('M').last()
        monthly_returns = monthly_equity.pct_change()
        
        return pd.DataFrame({
            'month': monthly_equity.index,
            'equity': monthly_equity.values,
            'return': monthly_returns.values
        })
    
    def calculate_annual_returns(self,
                                equity_curve: np.ndarray,
                                dates: pd.DatetimeIndex) -> pd.DataFrame:
        """计算年度收益"""
        equity_series = pd.Series(equity_curve, index=dates)
        annual_equity = equity_series.resample('Y').last()
        annual_returns = annual_equity.pct_change()
        
        return pd.DataFrame({
            'year': annual_equity.index,
            'equity': annual_equity.values,
            'return': annual_returns.values
        })
    
    def generate_report(self,
                       equity_curve: np.ndarray,
                       trades: List[Dict],
                       dates: Optional[pd.DatetimeIndex] = None,
                       symbol: str = "Strategy") -> str:
        """生成性能报告"""
        metrics = self.calculate_metrics(equity_curve, trades, dates)
        
        report = f"""
{'='*60}
性能分析报告 - {symbol}
{'='*60}

【收益指标】
总收益:           {metrics.total_return:>10.2%}
年化收益:         {metrics.annual_return:>10.2%}
月化收益:         {metrics.monthly_return:>10.2%}
日均收益:         {metrics.daily_return:>10.4%}

【风险指标】
年化波动率:       {metrics.annual_volatility:>10.2%}
月化波动率:       {metrics.monthly_volatility:>10.2%}
日波动率:         {metrics.daily_volatility:>10.4%}
最大回撤:         {metrics.max_drawdown:>10.2%}
最大回撤持续:     {metrics.max_drawdown_duration:>10} 天

【风险调整收益】
夏普比率:         {metrics.sharpe_ratio:>10.4f}
索提诺比率:       {metrics.sortino_ratio:>10.4f}
卡玛比率:         {metrics.calmar_ratio:>10.4f}

【交易统计】
总交易数:         {metrics.num_trades:>10}
赢利交易:         {metrics.num_winning_trades:>10}
亏损交易:         {metrics.num_losing_trades:>10}
胜率:             {metrics.win_rate:>10.2%}
收益因子:         {metrics.profit_factor:>10.4f}

【交易详情】
平均赢利:         {metrics.avg_win:>10.2f}
平均亏损:         {metrics.avg_loss:>10.2f}
赔率:             {metrics.payoff_ratio:>10.4f}
平均单笔PNL:      {metrics.avg_trade_pnl:>10.2f}
最大单笔赢利:     {metrics.largest_win:>10.2f}
最大单笔亏损:     {metrics.largest_loss:>10.2f}
平均持仓周期:     {metrics.avg_bars_in_trade:>10.2f} 根K线

{'='*60}
"""
        return report
    
    def print_report(self,
                    equity_curve: np.ndarray,
                    trades: List[Dict],
                    dates: Optional[pd.DatetimeIndex] = None,
                    symbol: str = "Strategy"):
        """打印性能报告"""
        report = self.generate_report(equity_curve, trades, dates, symbol)
        print(report)


__all__ = [
    'PerformanceAnalytics',
    'PerformanceMetrics',
]
