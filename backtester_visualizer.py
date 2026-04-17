"""
可视化模块 - K线图、P&L曲线、高水位线、信号标记等
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.dates import DateFormatter, MonthLocator
import seaborn as sns
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BacktestVisualizer:
    """回测结果可视化"""
    
    def __init__(self, figsize: Tuple[int, int] = (14, 10), style: str = 'seaborn-v0_8-darkgrid'):
        """初始化可视化器"""
        self.figsize = figsize
        self.style = style
        try:
            plt.style.use(style)
        except:
            plt.style.use('default')
    
    def plot_equity_curve(self,
                         equity_curve: np.ndarray,
                         dates: Optional[pd.DatetimeIndex] = None,
                         title: str = "Equity Curve",
                         ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制权益曲线"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        
        if dates is None:
            dates = pd.date_range(start='2020-01-01', periods=len(equity_curve), freq='D')
        
        ax.plot(dates, equity_curve, linewidth=2, label='Equity')
        ax.fill_between(dates, equity_curve, alpha=0.3)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Equity ($)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return ax
    
    def plot_drawdown(self,
                     equity_curve: np.ndarray,
                     dates: Optional[pd.DatetimeIndex] = None,
                     title: str = "Drawdown",
                     ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制回撤"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        
        if dates is None:
            dates = pd.date_range(start='2020-01-01', periods=len(equity_curve), freq='D')
        
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak * 100
        
        colors = ['red' if x < 0 else 'green' for x in drawdown]
        ax.bar(dates, drawdown, color=colors, alpha=0.6)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        return ax
    
    def plot_ohlc(self,
                  data: pd.DataFrame,
                  signals: Optional[np.ndarray] = None,
                  title: str = "OHLC Chart",
                  fig: Optional[plt.Figure] = None) -> plt.Figure:
        """绘制K线图"""
        if fig is None:
            fig, ax = plt.subplots(figsize=(14, 7))
        else:
            ax = fig.add_subplot(111)
        
        # 绘制K线
        width = 0.6
        width2 = 0.05
        
        up = data[data['close'] >= data['open']]
        down = data[data['close'] < data['open']]
        
        # 上升K线
        ax.bar(up.index, up['close'] - up['open'], width, bottom=up['open'],
              color='red', edgecolor='red', alpha=0.8)
        ax.plot(up.index, up[['high', 'low']], color='red', linewidth=1)
        
        # 下降K线
        ax.bar(down.index, down['close'] - down['open'], width, bottom=down['open'],
              color='green', edgecolor='green', alpha=0.8)
        ax.plot(down.index, down[['high', 'low']], color='green', linewidth=1)
        
        # 绘制信号
        if signals is not None:
            buy_signals = np.where(signals == 1)[0]
            sell_signals = np.where(signals == -1)[0]
            
            for idx in buy_signals:
                if idx < len(data):
                    ax.scatter(idx, data.iloc[idx]['low'] * 0.99, marker='^',
                              color='green', s=100, zorder=5, label='Buy' if idx == buy_signals[0] else '')
            
            for idx in sell_signals:
                if idx < len(data):
                    ax.scatter(idx, data.iloc[idx]['high'] * 1.01, marker='v',
                              color='red', s=100, zorder=5, label='Sell' if idx == sell_signals[0] else '')
        
        # 绘制移动平均线
        if 'sma_20' in data.columns:
            ax.plot(data.index, data['sma_20'], label='SMA(20)', alpha=0.7, linewidth=1.5)
        if 'sma_50' in data.columns:
            ax.plot(data.index, data['sma_50'], label='SMA(50)', alpha=0.7, linewidth=1.5)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price ($)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def plot_returns_distribution(self,
                                 returns: np.ndarray,
                                 title: str = "Returns Distribution",
                                 ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制收益分布"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        # 直方图
        ax.hist(returns, bins=50, alpha=0.7, edgecolor='black')
        
        # 添加正态分布曲线
        mu, sigma = np.mean(returns), np.std(returns)
        x = np.linspace(mu - 4*sigma, mu + 4*sigma, 100)
        ax.plot(x, len(returns) * (x[1] - x[0]) * 
               (1/np.sqrt(2*np.pi*sigma**2)) * np.exp(-(x-mu)**2/(2*sigma**2)),
               'r-', linewidth=2, label='Normal Distribution')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Daily Returns')
        ax.set_ylabel('Frequency')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        return ax
    
    def plot_heatmap(self,
                    data: pd.DataFrame,
                    title: str = "Correlation Heatmap",
                    figsize: Optional[Tuple] = None,
                    fig: Optional[plt.Figure] = None) -> plt.Figure:
        """绘制热力图"""
        if figsize is None:
            figsize = self.figsize
        
        if fig is None:
            fig = plt.figure(figsize=figsize)
        
        corr = data.corr()
        sns.heatmap(corr, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                   square=True, ax=plt.gca(), cbar_kws={'label': 'Correlation'})
        
        plt.title(title, fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        return fig
    
    def plot_monthly_returns(self,
                            returns: pd.Series,
                            title: str = "Monthly Returns",
                            fig: Optional[plt.Figure] = None) -> plt.Figure:
        """绘制月度收益热力图"""
        if fig is None:
            fig = plt.figure(figsize=(12, 6))
        
        # 获取月度收益
        monthly = returns.resample('M').sum()
        
        # 创建透视表
        monthly_df = pd.DataFrame({
            'year': [d.year for d in monthly.index],
            'month': [d.month for d in monthly.index],
            'return': monthly.values
        })
        
        pivot = monthly_df.pivot(index='month', columns='year', values='return')
        
        # 绘制热力图
        sns.heatmap(pivot, annot=True, fmt='.2%', cmap='RdYlGn', center=0,
                   cbar_kws={'label': 'Monthly Return'})
        
        plt.title(title, fontsize=14, fontweight='bold')
        plt.ylabel('Month')
        plt.xlabel('Year')
        plt.tight_layout()
        
        return fig
    
    def plot_pnl_distribution(self,
                             trades: List[Dict],
                             title: str = "P&L Distribution",
                             ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制P&L分布"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(10, 6))
        
        pnls = [t.get('pnl', 0) for t in trades]
        
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p <= 0]
        
        ax.hist(winning, bins=30, alpha=0.7, label='Wins', color='green', edgecolor='black')
        ax.hist(losing, bins=30, alpha=0.7, label='Losses', color='red', edgecolor='black')
        
        ax.axvline(np.mean(pnls), color='blue', linestyle='--', linewidth=2, label='Mean')
        ax.axvline(0, color='black', linestyle='-', linewidth=1)
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('P&L ($)')
        ax.set_ylabel('Frequency')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        return ax
    
    def plot_underwater(self,
                       equity_curve: np.ndarray,
                       dates: Optional[pd.DatetimeIndex] = None,
                       title: str = "Underwater Plot (Drawdown)",
                       ax: Optional[plt.Axes] = None) -> plt.Axes:
        """绘制水下图（回撤可视化）"""
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 6))
        
        if dates is None:
            dates = pd.date_range(start='2020-01-01', periods=len(equity_curve), freq='D')
        
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak * 100
        
        # 填充负值
        ax.fill_between(dates, drawdown, 0, where=(drawdown <= 0),
                       color='red', alpha=0.5, label='Drawdown')
        
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_xlabel('Date')
        ax.set_ylabel('Drawdown (%)')
        ax.set_ylim(top=0)
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return ax
    
    def plot_multiple_metrics(self,
                             equity_curve: np.ndarray,
                             returns: np.ndarray,
                             trades: List[Dict],
                             dates: Optional[pd.DatetimeIndex] = None) -> plt.Figure:
        """绘制多个指标"""
        if dates is None:
            dates = pd.date_range(start='2020-01-01', periods=len(equity_curve), freq='D')
        
        fig = plt.figure(figsize=(14, 12))
        
        # 权益曲线
        ax1 = plt.subplot(3, 2, 1)
        ax1.plot(dates, equity_curve, linewidth=2)
        ax1.set_title('Equity Curve')
        ax1.grid(True, alpha=0.3)
        
        # 回撤
        ax2 = plt.subplot(3, 2, 2)
        peak = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - peak) / peak * 100
        ax2.fill_between(dates, drawdown, 0, color='red', alpha=0.5)
        ax2.set_title('Drawdown')
        ax2.grid(True, alpha=0.3)
        
        # 日收益
        ax3 = plt.subplot(3, 2, 3)
        ax3.bar(dates[1:], returns, alpha=0.7, width=1)
        ax3.set_title('Daily Returns')
        ax3.grid(True, alpha=0.3, axis='y')
        
        # 收益分布
        ax4 = plt.subplot(3, 2, 4)
        ax4.hist(returns, bins=50, alpha=0.7, edgecolor='black')
        ax4.set_title('Returns Distribution')
        ax4.grid(True, alpha=0.3, axis='y')
        
        # P&L分布
        ax5 = plt.subplot(3, 2, 5)
        pnls = [t.get('pnl', 0) for t in trades]
        winning = [p for p in pnls if p > 0]
        losing = [p for p in pnls if p <= 0]
        ax5.hist(winning, bins=20, alpha=0.7, label='Wins', color='green')
        ax5.hist(losing, bins=20, alpha=0.7, label='Losses', color='red')
        ax5.set_title('P&L Distribution')
        ax5.legend()
        ax5.grid(True, alpha=0.3, axis='y')
        
        # 累积收益
        ax6 = plt.subplot(3, 2, 6)
        cumulative_returns = np.cumprod(1 + returns) - 1
        ax6.plot(dates[1:], cumulative_returns * 100, linewidth=2)
        ax6.set_title('Cumulative Returns (%)')
        ax6.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig
    
    def save_figure(self, fig: plt.Figure, filepath: str):
        """保存图表"""
        fig.savefig(filepath, dpi=300, bbox_inches='tight')
        logger.info(f"Figure saved to {filepath}")


__all__ = [
    'BacktestVisualizer',
]
