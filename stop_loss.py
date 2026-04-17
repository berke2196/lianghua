"""
三防线止损系统
- 防线1: 硬止损 (单笔固定止损、持仓时间、连续亏损)
- 防线2: 热线告警 (清算风险、头寸热度、VaR、CVaR、自动减仓)
- 防线3: 日亏损限制 (日/周亏损限制、自动恢复)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    SAFE = "SAFE"  # 0-20%
    WARNING = "WARNING"  # 20-50%
    CRITICAL = "CRITICAL"  # 50-80%
    EMERGENCY = "EMERGENCY"  # 80%+


@dataclass
class StopLossConfig:
    """止损配置"""
    # 防线1 - 硬止损
    single_trade_stop_loss: float = 0.02  # -2%
    max_holding_time_minutes: int = 60
    consecutive_loss_threshold: int = 3
    
    # 防线2 - 热线告警
    liquidation_risk_threshold: float = 0.8
    position_heat_threshold: float = 0.7
    var_confidence: float = 0.99
    cvar_threshold: float = 0.05
    auto_reduce_risk_threshold: float = 0.5
    
    # 防线3 - 日亏损限制
    daily_loss_limit: float = 0.05  # 5%
    daily_loss_warning: float = 0.03  # 3%
    weekly_loss_limit: float = 0.20  # 20%
    
    # 恢复参数
    recovery_wait_minutes: int = 30
    auto_recovery_enabled: bool = True


@dataclass
class Position:
    """头寸信息"""
    symbol: str
    size: float
    entry_price: float
    current_price: float
    entry_time: datetime = field(default_factory=datetime.now)
    leverage: float = 1.0
    collateral: float = 0.0
    
    def get_unrealized_pnl(self) -> float:
        """获取未实现盈亏"""
        return (self.current_price - self.entry_price) * self.size
    
    def get_unrealized_pnl_percent(self) -> float:
        """获取未实现盈亏百分比"""
        if self.entry_price == 0:
            return 0
        return (self.current_price - self.entry_price) / self.entry_price
    
    def get_holding_time_minutes(self) -> int:
        """获取持仓时间（分钟）"""
        return int((datetime.now() - self.entry_time).total_seconds() / 60)
    
    def is_profitable(self) -> bool:
        """是否盈利"""
        return self.get_unrealized_pnl_percent() > 0


class FirstLineStopLoss:
    """防线1 - 硬止损"""
    
    def __init__(self, config: StopLossConfig = None):
        self.config = config or StopLossConfig()
        self.consecutive_loss_count = 0
        self.last_loss_time = None
        
    def check_single_trade_stop_loss(self, position: Position) -> Tuple[bool, str]:
        """
        检查单笔固定止损
        返回: (是否触发, 原因)
        """
        pnl_percent = position.get_unrealized_pnl_percent()
        
        if pnl_percent < -self.config.single_trade_stop_loss:
            reason = f"Single trade stop loss triggered: {pnl_percent:.2%} < {-self.config.single_trade_stop_loss:.2%}"
            logger.warning(reason)
            return True, reason
            
        return False, ""
    
    def check_holding_time_stop_loss(self, position: Position) -> Tuple[bool, str]:
        """
        检查持仓时间止损
        返回: (是否触发, 原因)
        """
        holding_time = position.get_holding_time_minutes()
        
        if holding_time > self.config.max_holding_time_minutes:
            reason = f"Holding time stop loss triggered: {holding_time}min > {self.config.max_holding_time_minutes}min"
            logger.warning(reason)
            return True, reason
            
        return False, ""
    
    def update_consecutive_loss(self, position: Position):
        """更新连续亏损计数"""
        if not position.is_profitable():
            self.consecutive_loss_count += 1
            self.last_loss_time = datetime.now()
        else:
            self.consecutive_loss_count = 0
    
    def check_consecutive_loss_stop_loss(self) -> Tuple[bool, str]:
        """
        检查连续亏损止损
        返回: (是否触发, 原因)
        """
        if self.consecutive_loss_count >= self.config.consecutive_loss_threshold:
            reason = f"Consecutive loss stop loss triggered: {self.consecutive_loss_count} consecutive losses"
            logger.warning(reason)
            return True, reason
            
        return False, ""
    
    def reset_consecutive_loss_count(self):
        """重置连续亏损计数"""
        self.consecutive_loss_count = 0


class SecondLineHotline:
    """防线2 - 热线告警"""
    
    def __init__(self, config: StopLossConfig = None):
        self.config = config or StopLossConfig()
        self.position_history: List[Dict] = []
        
    def calculate_liquidation_risk(self, 
                                  collateral: float,
                                  position_value: float,
                                  leverage: float) -> float:
        """
        计算清算风险
        清算风险 = 当前亏损 / (可用保证金)
        范围: 0~1，越接近1越危险
        """
        if collateral <= 0:
            return 0
            
        # 计算保证金使用率
        margin_used = position_value / leverage if leverage > 0 else position_value
        available_margin = collateral - margin_used
        
        if available_margin <= 0:
            return 1.0
            
        # 风险 = 距离清算的距离比
        risk = 1 - (available_margin / collateral) if collateral > 0 else 0
        return max(0, min(1, risk))
    
    def calculate_position_heat(self,
                               position_value: float,
                               max_position_value: float,
                               unrealized_pnl_percent: float) -> float:
        """
        计算头寸热度 (0-1)
        综合考虑: 头寸大小、盈亏情况
        """
        # 头寸大小贡献 (0-0.5)
        size_heat = min(0.5, position_value / (max_position_value + 1e-8))
        
        # 盈亏贡献 (0-0.5)
        if unrealized_pnl_percent > 0.1:
            # 大盈利，风险降低
            pnl_heat = 0.1
        elif unrealized_pnl_percent < -0.05:
            # 亏损中，风险增加
            pnl_heat = 0.5
        else:
            pnl_heat = 0.3
            
        heat = size_heat + pnl_heat
        return max(0, min(1, heat))
    
    def calculate_var(self, 
                     returns: np.ndarray,
                     confidence: float = None) -> float:
        """
        计算风险价值 (Value at Risk)
        VaR = 在给定置信度下，最大可能损失
        """
        if confidence is None:
            confidence = self.config.var_confidence
            
        if len(returns) < 10:
            return 0
            
        var = np.percentile(returns, (1 - confidence) * 100)
        return var
    
    def calculate_cvar(self,
                      returns: np.ndarray,
                      confidence: float = None) -> float:
        """
        计算条件风险值 (Conditional Value at Risk)
        CVaR = 超过VaR的平均损失
        """
        if confidence is None:
            confidence = self.config.var_confidence
            
        if len(returns) < 10:
            return 0
            
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        cvar = np.mean(returns[returns <= var_threshold])
        return cvar
    
    def get_risk_level(self, liquidation_risk: float) -> RiskLevel:
        """获取风险等级"""
        if liquidation_risk >= 0.8:
            return RiskLevel.EMERGENCY
        elif liquidation_risk >= 0.5:
            return RiskLevel.CRITICAL
        elif liquidation_risk >= 0.2:
            return RiskLevel.WARNING
        else:
            return RiskLevel.SAFE
    
    def check_auto_reduce(self, liquidation_risk: float) -> Tuple[bool, float]:
        """
        检查是否需要自动减仓
        返回: (是否需要减仓, 减仓比例)
        """
        if liquidation_risk > self.config.auto_reduce_risk_threshold:
            # 计算减仓比例
            reduce_ratio = min(0.5, (liquidation_risk - self.config.auto_reduce_risk_threshold) / 0.3)
            reason = f"Auto reduce triggered: liquidation_risk={liquidation_risk:.2%}, reduce={reduce_ratio:.2%}"
            logger.warning(reason)
            return True, reduce_ratio
            
        return False, 0


class ThirdLineDaily:
    """防线3 - 日亏损限制"""
    
    def __init__(self, config: StopLossConfig = None):
        self.config = config or StopLossConfig()
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.daily_start_time = datetime.now()
        self.weekly_start_time = datetime.now()
        self.trading_paused = False
        self.pause_start_time = None
        
    def add_pnl(self, pnl: float):
        """添加盈亏"""
        current_time = datetime.now()
        
        # 检查是否需要重置日/周计数
        if (current_time - self.daily_start_time).days >= 1:
            self.daily_pnl = 0.0
            self.daily_start_time = current_time
            
        if (current_time - self.weekly_start_time).days >= 7:
            self.weekly_pnl = 0.0
            self.weekly_start_time = current_time
            
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
    
    def check_daily_loss_limit(self, account_equity: float) -> Tuple[bool, str]:
        """
        检查日亏损限制
        返回: (是否超限, 原因)
        """
        if account_equity <= 0:
            return False, ""
            
        daily_loss_percent = -self.daily_pnl / account_equity
        
        if daily_loss_percent > self.config.daily_loss_limit:
            reason = f"Daily loss limit exceeded: {daily_loss_percent:.2%} > {self.config.daily_loss_limit:.2%}"
            logger.error(reason)
            return True, reason
        elif daily_loss_percent > self.config.daily_loss_warning:
            reason = f"Daily loss warning: {daily_loss_percent:.2%} > {self.config.daily_loss_warning:.2%}"
            logger.warning(reason)
            
        return False, ""
    
    def check_weekly_loss_limit(self, account_equity: float) -> Tuple[bool, str]:
        """
        检查周亏损限制
        返回: (是否超限, 原因)
        """
        if account_equity <= 0:
            return False, ""
            
        weekly_loss_percent = -self.weekly_pnl / account_equity
        
        if weekly_loss_percent > self.config.weekly_loss_limit:
            reason = f"Weekly loss limit exceeded: {weekly_loss_percent:.2%} > {self.config.weekly_loss_limit:.2%}"
            logger.error(reason)
            return True, reason
            
        return False, ""
    
    def pause_trading(self):
        """暂停交易"""
        self.trading_paused = True
        self.pause_start_time = datetime.now()
        logger.warning("Trading paused due to loss limits")
    
    def try_recover(self) -> bool:
        """
        尝试恢复交易
        返回: 是否可以恢复
        """
        if not self.trading_paused:
            return True
            
        if not self.config.auto_recovery_enabled:
            return False
            
        if self.pause_start_time is None:
            return False
            
        elapsed_minutes = (datetime.now() - self.pause_start_time).total_seconds() / 60
        
        if elapsed_minutes >= self.config.recovery_wait_minutes:
            self.trading_paused = False
            self.pause_start_time = None
            logger.info("Trading recovered after recovery period")
            return True
            
        return False


class ComprehensiveStopLossManager:
    """综合止损管理器"""
    
    def __init__(self, config: StopLossConfig = None):
        self.config = config or StopLossConfig()
        self.first_line = FirstLineStopLoss(config)
        self.second_line = SecondLineHotline(config)
        self.third_line = ThirdLineDaily(config)
        self.positions: Dict[str, Position] = {}
        self.closed_positions: List[Dict] = []
        
    def add_position(self, position: Position):
        """添加头寸"""
        self.positions[position.symbol] = position
        
    def update_position_price(self, symbol: str, current_price: float):
        """更新头寸价格"""
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price
    
    def check_first_line(self, symbol: str) -> Tuple[bool, str]:
        """检查防线1"""
        if symbol not in self.positions:
            return False, ""
            
        position = self.positions[symbol]
        
        # 检查单笔止损
        should_stop, reason = self.first_line.check_single_trade_stop_loss(position)
        if should_stop:
            return True, reason
            
        # 检查持仓时间止损
        should_stop, reason = self.first_line.check_holding_time_stop_loss(position)
        if should_stop:
            return True, reason
            
        # 更新连续亏损
        self.first_line.update_consecutive_loss(position)
        
        # 检查连续亏损止损
        should_stop, reason = self.first_line.check_consecutive_loss_stop_loss()
        if should_stop:
            return True, reason
            
        return False, ""
    
    def check_second_line(self, symbol: str, account_collateral: float) -> Tuple[RiskLevel, str]:
        """检查防线2"""
        if symbol not in self.positions:
            return RiskLevel.SAFE, ""
            
        position = self.positions[symbol]
        position_value = position.size * position.current_price
        
        # 计算清液险
        liquidation_risk = self.second_line.calculate_liquidation_risk(
            account_collateral,
            position_value,
            position.leverage
        )
        
        # 计算头寸热度
        position_heat = self.second_line.calculate_position_heat(
            position_value,
            account_collateral * 0.1,  # 最大头寸 = 抵押品的10%
            position.get_unrealized_pnl_percent()
        )
        
        # 综合风险
        combined_risk = max(liquidation_risk, position_heat)
        risk_level = self.second_line.get_risk_level(combined_risk)
        
        reason = f"Risk level: {risk_level.value}, liquidation_risk={liquidation_risk:.2%}, position_heat={position_heat:.2%}"
        return risk_level, reason
    
    def check_third_line(self, account_equity: float) -> Tuple[bool, str]:
        """检查防线3"""
        # 检查日亏损
        exceeded, reason = self.third_line.check_daily_loss_limit(account_equity)
        if exceeded:
            self.third_line.pause_trading()
            return True, reason
            
        # 检查周亏损
        exceeded, reason = self.third_line.check_weekly_loss_limit(account_equity)
        if exceeded:
            return True, reason
            
        # 尝试恢复
        self.third_line.try_recover()
        
        return self.third_line.trading_paused, "Trading paused" if self.third_line.trading_paused else ""
    
    def comprehensive_check(self, 
                           symbol: str,
                           account_collateral: float,
                           account_equity: float) -> Tuple[bool, str]:
        """
        综合检查所有防线
        返回: (是否应该平仓, 原因)
        """
        # 检查防线1
        should_close, reason1 = self.check_first_line(symbol)
        if should_close:
            return True, f"First line: {reason1}"
            
        # 检查防线2
        risk_level, reason2 = self.check_second_line(symbol, account_collateral)
        if risk_level == RiskLevel.EMERGENCY:
            return True, f"Second line: {reason2}"
            
        # 检查防线3
        trading_paused, reason3 = self.check_third_line(account_equity)
        if trading_paused:
            return True, f"Third line: {reason3}"
            
        return False, ""
    
    def close_position(self, symbol: str, close_price: float, reason: str = ""):
        """平仓"""
        if symbol in self.positions:
            position = self.positions[symbol]
            pnl = position.get_unrealized_pnl()
            
            self.closed_positions.append({
                'symbol': symbol,
                'entry_price': position.entry_price,
                'close_price': close_price,
                'size': position.size,
                'pnl': pnl,
                'pnl_percent': position.get_unrealized_pnl_percent(),
                'holding_time_minutes': position.get_holding_time_minutes(),
                'reason': reason,
                'close_time': datetime.now()
            })
            
            # 更新日/周盈亏
            self.third_line.add_pnl(pnl)
            
            # 重置连续亏损计数
            if position.get_unrealized_pnl_percent() >= 0:
                self.first_line.reset_consecutive_loss_count()
                
            logger.info(f"Position closed: {symbol}, PnL={pnl:.2f}, reason={reason}")
            del self.positions[symbol]
