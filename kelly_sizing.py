"""
Kelly准则资金管理系统
- 基础Kelly: f = (bp*W - L) / b
- 修正Kelly (保守系数): f* = f / 2~4
- 动态调整: 基于实时绩效
- 多资产Kelly: 投资组合级别
- 风险调整: VaR和CVaR
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConservativenessLevel(Enum):
    """保守系数等级"""
    AGGRESSIVE = 2.0  # f/2
    NORMAL = 2.5  # f/2.5
    CONSERVATIVE = 3.0  # f/3
    VERY_CONSERVATIVE = 4.0  # f/4


@dataclass
class KellyConfig:
    """Kelly配置"""
    min_allocation: float = 0.01  # 1% 最小配置
    max_allocation: float = 0.25  # 25% 最大配置
    confidence_level: float = 0.99  # 99% 置信度
    leverage_limit: float = 3.0  # 最大杠杆
    bankruptcy_risk_limit: float = 0.001  # 0.1% 破产风险限制
    lookback_period: int = 100  # 回溯期
    rebalance_frequency: int = 20  # 重平衡频率


class KellyCalculator:
    """Kelly准则计算器"""
    
    def __init__(self, config: KellyConfig = None):
        self.config = config or KellyConfig()
        self.trade_history: List[Dict] = []
        self.performance_metrics = {}
        
    def calculate_basic_kelly(self, 
                             win_rate: float,
                             win_loss_ratio: float,
                             avg_win: float,
                             avg_loss: float) -> float:
        """
        计算基础Kelly准则
        
        f = (p * b - q) / b
        其中:
        - p: 胜率 (win_rate)
        - q: 败率 (1 - p)
        - b: 赔率 (avg_win / avg_loss)
        """
        if avg_loss == 0:
            return 0
            
        p = win_rate
        q = 1 - p
        b = avg_win / avg_loss if avg_loss != 0 else 0
        
        if b == 0:
            return 0
            
        kelly = (p * b - q) / b
        
        # 确保Kelly值在有效范围内
        kelly = max(0, min(kelly, self.config.max_allocation))
        
        logger.debug(f"Basic Kelly: {kelly:.4f} (p={p:.2%}, b={b:.2f})")
        return kelly
    
    def calculate_adjusted_kelly(self, 
                                basic_kelly: float,
                                conservativeness: ConservativenessLevel) -> float:
        """修正Kelly准则 - 应用保守系数"""
        adjusted = basic_kelly / conservativeness.value
        adjusted = max(self.config.min_allocation, 
                      min(adjusted, self.config.max_allocation))
        
        logger.debug(f"Adjusted Kelly: {adjusted:.4f} (factor={conservativeness.value})")
        return adjusted
    
    def calculate_var_kelly(self, 
                           returns: np.ndarray,
                           confidence: float = None) -> float:
        """
        基于VaR的Kelly计算
        VaR: 损失分布的百分比
        """
        if confidence is None:
            confidence = self.config.confidence_level
            
        if len(returns) < 10:
            return 0
            
        var = np.percentile(returns, (1 - confidence) * 100)
        
        # 调整Kelly基于VaR
        kelly_fraction = 1 - (1 - confidence)
        
        logger.debug(f"VaR-based Kelly: VaR={var:.4f}, Fraction={kelly_fraction:.4f}")
        return kelly_fraction
    
    def calculate_cvar_kelly(self,
                            returns: np.ndarray,
                            confidence: float = None) -> float:
        """
        基于CVaR(条件风险值)的Kelly计算
        CVaR: 超过VaR的平均损失
        """
        if confidence is None:
            confidence = self.config.confidence_level
            
        if len(returns) < 10:
            return 0
            
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        cvar = np.mean(returns[returns <= var_threshold])
        
        # CVaR更保守，调整更大
        kelly_fraction = max(0, 1 - abs(cvar))
        
        logger.debug(f"CVaR-based Kelly: CVaR={cvar:.4f}, Fraction={kelly_fraction:.4f}")
        return kelly_fraction
    
    def calculate_dynamic_kelly(self,
                               returns: np.ndarray,
                               baseline_kelly: float) -> float:
        """
        动态Kelly计算 - 基于实时绩效
        """
        if len(returns) < 10:
            return baseline_kelly
            
        # 计算Sharpe比率
        excess_returns = returns - 0  # 假设无风险率为0
        sharpe = np.mean(excess_returns) / (np.std(excess_returns) + 1e-8)
        
        # 基于Sharpe调整Kelly
        if sharpe > 1:
            # 表现好，可以增加配置
            adjustment = min(1.2, 1 + sharpe * 0.1)
        elif sharpe < -1:
            # 表现差，减少配置
            adjustment = max(0.3, 1 + sharpe * 0.2)
        else:
            adjustment = 1.0
            
        dynamic_kelly = baseline_kelly * adjustment
        dynamic_kelly = max(self.config.min_allocation, 
                           min(dynamic_kelly, self.config.max_allocation))
        
        logger.debug(f"Dynamic Kelly: {dynamic_kelly:.4f} (Sharpe={sharpe:.2f}, adjustment={adjustment:.2f})")
        return dynamic_kelly
    
    def calculate_portfolio_kelly(self,
                                 assets: Dict[str, Dict],
                                 correlation_matrix: np.ndarray) -> Dict[str, float]:
        """
        多资产Kelly配置 - 投资组合级别
        
        考虑资产间相关性
        """
        allocations = {}
        
        if not assets:
            return allocations
            
        asset_names = list(assets.keys())
        n_assets = len(asset_names)
        
        # 计算每个资产的Kelly
        individual_kellys = {}
        for asset_name, asset_data in assets.items():
            kelly = self.calculate_basic_kelly(
                asset_data['win_rate'],
                asset_data['win_loss_ratio'],
                asset_data['avg_win'],
                asset_data['avg_loss']
            )
            individual_kellys[asset_name] = kelly
        
        # 考虑相关性的组合优化
        if correlation_matrix is not None and correlation_matrix.shape == (n_assets, n_assets):
            # 简单的相关性调整
            total_kelly = sum(individual_kellys.values())
            
            if total_kelly > self.config.max_allocation:
                # 按比例缩放
                scale = self.config.max_allocation / (total_kelly + 1e-8)
                for asset_name in individual_kellys:
                    allocations[asset_name] = individual_kellys[asset_name] * scale
            else:
                allocations = individual_kellys
        else:
            allocations = individual_kellys
            
        logger.debug(f"Portfolio Kelly allocations: {allocations}")
        return allocations
    
    def calculate_leverage_optimization(self,
                                       kelly_fraction: float,
                                       equity: float,
                                       volatility: float) -> Tuple[float, float]:
        """
        杠杆最优化
        
        返回: (最优杠杆, 配置大小)
        """
        # 基础杠杆
        base_leverage = 1 / (volatility + 0.01)
        base_leverage = min(base_leverage, self.config.leverage_limit)
        
        # Kelly调整杠杆
        optimal_leverage = kelly_fraction * base_leverage
        optimal_leverage = min(optimal_leverage, self.config.leverage_limit)
        
        # 计算配置大小
        allocation_size = equity * kelly_fraction * optimal_leverage
        
        logger.debug(f"Leverage optimization: leverage={optimal_leverage:.2f}, allocation={allocation_size:.2f}")
        return optimal_leverage, allocation_size
    
    def calculate_bankruptcy_risk(self,
                                 kelly_fraction: float,
                                 returns: np.ndarray) -> float:
        """
        计算破产风险
        破产风险 = 出现连续亏损导致资金耗尽的概率
        """
        if len(returns) < 10 or kelly_fraction == 0:
            return 0
            
        # 最坏情况下的连续亏损
        cumulative_drawdown = np.min(np.cumsum(returns * kelly_fraction))
        
        # 破产风险估计
        if cumulative_drawdown < -1:
            bankruptcy_risk = 1.0
        else:
            bankruptcy_risk = max(0, -cumulative_drawdown)
            
        logger.debug(f"Bankruptcy risk: {bankruptcy_risk:.4f} (limit={self.config.bankruptcy_risk_limit})")
        
        if bankruptcy_risk > self.config.bankruptcy_risk_limit:
            logger.warning(f"Bankruptcy risk {bankruptcy_risk:.4f} exceeds limit {self.config.bankruptcy_risk_limit}")
            
        return bankruptcy_risk
    
    def calculate_overheat_protection(self,
                                     recent_returns: np.ndarray,
                                     baseline_kelly: float) -> float:
        """
        过热保护 - 连续盈利时降低风险
        """
        if len(recent_returns) < 5:
            return baseline_kelly
            
        # 计算连续胜利数
        consecutive_wins = 0
        max_consecutive_wins = 0
        
        for ret in recent_returns[-20:]:
            if ret > 0:
                consecutive_wins += 1
                max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
            else:
                consecutive_wins = 0
                
        # 过热检测
        if max_consecutive_wins >= 5:
            # 降低Kelly配置
            reduction_factor = 1 - (max_consecutive_wins - 4) * 0.1
            protected_kelly = baseline_kelly * max(0.3, reduction_factor)
            logger.warning(f"Overheat detected: {max_consecutive_wins} consecutive wins, reducing Kelly to {protected_kelly:.4f}")
            return protected_kelly
            
        return baseline_kelly
    
    def add_trade(self, trade: Dict):
        """记录交易"""
        self.trade_history.append(trade)
        
        if len(self.trade_history) > self.config.lookback_period:
            self.trade_history = self.trade_history[-self.config.lookback_period:]
    
    def calculate_performance_metrics(self) -> Dict:
        """计算性能指标"""
        if len(self.trade_history) < 2:
            return {}
            
        returns = np.array([t['return'] for t in self.trade_history])
        
        metrics = {
            'total_trades': len(self.trade_history),
            'win_rate': np.sum(returns > 0) / len(returns),
            'avg_win': np.mean(returns[returns > 0]) if np.any(returns > 0) else 0,
            'avg_loss': -np.mean(returns[returns < 0]) if np.any(returns < 0) else 0,
            'sharpe_ratio': np.mean(returns) / (np.std(returns) + 1e-8),
            'max_drawdown': np.min(np.cumsum(returns)),
            'total_return': np.sum(returns),
        }
        
        self.performance_metrics = metrics
        logger.info(f"Performance metrics: {metrics}")
        return metrics
    
    def recommend_kelly(self) -> Tuple[float, ConservativenessLevel]:
        """推荐Kelly配置"""
        if not self.performance_metrics:
            return self.config.min_allocation, ConservativenessLevel.VERY_CONSERVATIVE
            
        metrics = self.performance_metrics
        
        # 基于Sharpe选择保守系数
        sharpe = metrics.get('sharpe_ratio', 0)
        
        if sharpe > 1.5:
            level = ConservativenessLevel.AGGRESSIVE
        elif sharpe > 0.5:
            level = ConservativenessLevel.NORMAL
        elif sharpe > 0:
            level = ConservativenessLevel.CONSERVATIVE
        else:
            level = ConservativenessLevel.VERY_CONSERVATIVE
            
        # 计算推荐的Kelly
        win_rate = metrics.get('win_rate', 0.5)
        avg_win = metrics.get('avg_win', 0.01)
        avg_loss = metrics.get('avg_loss', 0.01)
        
        if avg_loss > 0:
            win_loss_ratio = avg_win / avg_loss
        else:
            win_loss_ratio = 1
            
        basic_kelly = self.calculate_basic_kelly(win_rate, win_loss_ratio, avg_win, avg_loss)
        recommended_kelly = self.calculate_adjusted_kelly(basic_kelly, level)
        
        logger.info(f"Recommended Kelly: {recommended_kelly:.4f} with conservativeness level {level.name}")
        return recommended_kelly, level


class PortfolioKellyManager:
    """投资组合Kelly管理器"""
    
    def __init__(self, config: KellyConfig = None):
        self.config = config or KellyConfig()
        self.kelly_calc = KellyCalculator(config)
        self.positions: Dict[str, Dict] = {}
        self.total_equity = 1.0
        
    def update_position(self, symbol: str, position_data: Dict):
        """更新头寸"""
        self.positions[symbol] = position_data
        
    def rebalance(self) -> Dict[str, float]:
        """重新平衡投资组合"""
        if not self.positions:
            return {}
            
        allocations = self.kelly_calc.calculate_portfolio_kelly(
            self.positions,
            correlation_matrix=None
        )
        
        # 转换为头寸大小
        position_sizes = {}
        for symbol, allocation in allocations.items():
            position_sizes[symbol] = self.total_equity * allocation
            
        logger.info(f"Portfolio rebalanced: {position_sizes}")
        return position_sizes
