"""
头寸管理系统
- 头寸追踪、杠杆计算、清算价格、保证金监控
- 多币种支持、对冲管理、动态杠杆、最大持仓限制
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PositionMode(Enum):
    """头寸模式"""
    LONG = "LONG"  # 多头
    SHORT = "SHORT"  # 空头
    FLAT = "FLAT"  # 平仓


@dataclass
class PositionData:
    """头寸数据"""
    symbol: str
    mode: PositionMode
    quantity: float
    entry_price: float
    current_price: float
    leverage: float
    collateral_amount: float
    margin_ratio: float = 0.0  # 保证金率
    funding_rate: float = 0.0  # 资金费率
    entry_time: datetime = field(default_factory=datetime.now)
    
    def get_notional_value(self) -> float:
        """获取名义价值"""
        return abs(self.quantity) * self.current_price
    
    def get_margin_used(self) -> float:
        """获取使用的保证金"""
        return self.get_notional_value() / self.leverage
    
    def get_unrealized_pnl(self) -> float:
        """获取未实现盈亏"""
        if self.mode == PositionMode.LONG:
            return self.quantity * (self.current_price - self.entry_price)
        else:
            return self.quantity * (self.entry_price - self.current_price)
    
    def get_roi(self) -> float:
        """获取投资回报率"""
        margin_used = self.get_margin_used()
        if margin_used == 0:
            return 0
        return self.get_unrealized_pnl() / margin_used
    
    def get_liquidation_price(self) -> float:
        """获取清算价格"""
        if self.leverage <= 1:
            return 0
            
        # 清算价格 = 入场价 * (1 - 1/杠杆) for long
        # 清算价格 = 入场价 * (1 + 1/杠杆) for short
        liquidation_factor = 1 / self.leverage
        
        if self.mode == PositionMode.LONG:
            return self.entry_price * (1 - liquidation_factor * 0.95)
        else:
            return self.entry_price * (1 + liquidation_factor * 0.95)
    
    def get_distance_to_liquidation_percent(self) -> float:
        """获取距离清算的距离百分比"""
        liq_price = self.get_liquidation_price()
        
        if liq_price == 0:
            return 100
            
        if self.mode == PositionMode.LONG:
            distance = (self.current_price - liq_price) / liq_price
        else:
            distance = (liq_price - self.current_price) / liq_price
            
        return max(0, distance) * 100


@dataclass
class PortfolioMetrics:
    """投资组合指标"""
    total_collateral: float
    used_collateral: float
    available_collateral: float
    margin_ratio: float
    total_notional: float
    total_unrealized_pnl: float
    total_roi: float
    portfolio_leverage: float
    total_positions: int
    number_of_longs: int
    number_of_shorts: int
    net_delta: float
    portfolio_heat: float
    max_position_size: float
    min_distance_to_liquidation: float


class PositionManager:
    """头寸管理器"""
    
    def __init__(self):
        self.positions: Dict[str, PositionData] = {}
        self.max_leverage = 10.0
        self.max_collateral_per_position = 0.2  # 单个头寸最多使用总抵押品的20%
        self.position_history: List[Dict] = []
        self.hedges: Dict[str, List[str]] = {}  # 对冲关系
        
    def open_position(self, 
                     symbol: str,
                     mode: PositionMode,
                     quantity: float,
                     entry_price: float,
                     leverage: float,
                     collateral_amount: float) -> Tuple[bool, str]:
        """
        打开头寸
        返回: (是否成功, 原因)
        """
        # 验证杠杆
        if leverage > self.max_leverage:
            return False, f"Leverage {leverage} exceeds max {self.max_leverage}"
            
        if leverage < 1:
            return False, "Leverage must be >= 1"
            
        # 验证数量
        if quantity <= 0:
            return False, "Quantity must be positive"
            
        # 创建头寸
        position = PositionData(
            symbol=symbol,
            mode=mode,
            quantity=quantity,
            entry_price=entry_price,
            current_price=entry_price,
            leverage=leverage,
            collateral_amount=collateral_amount
        )
        
        # 更新头寸
        if symbol in self.positions:
            # 加仓
            old_pos = self.positions[symbol]
            if old_pos.mode != mode:
                return False, f"Cannot add to opposite position for {symbol}"
                
            # 更新平均入场价
            total_value = old_pos.quantity * old_pos.entry_price + quantity * entry_price
            total_qty = old_pos.quantity + quantity
            position.entry_price = total_value / total_qty
            position.quantity = total_qty
            position.collateral_amount = old_pos.collateral_amount + collateral_amount
        
        self.positions[symbol] = position
        logger.info(f"Position opened: {symbol} {mode.value} x{quantity} @{entry_price:.2f}, leverage={leverage}")
        return True, ""
    
    def close_position(self, symbol: str, close_price: float) -> Tuple[bool, str, float]:
        """
        平仓
        返回: (是否成功, 原因, 盈亏)
        """
        if symbol not in self.positions:
            return False, f"Position {symbol} not found", 0
            
        position = self.positions[symbol]
        pnl = position.get_unrealized_pnl()
        
        # 记录历史
        self.position_history.append({
            'symbol': symbol,
            'mode': position.mode.value,
            'quantity': position.quantity,
            'entry_price': position.entry_price,
            'close_price': close_price,
            'pnl': pnl,
            'roi': pnl / position.collateral_amount if position.collateral_amount > 0 else 0,
            'holding_time': (datetime.now() - position.entry_time).total_seconds() / 60,
        })
        
        del self.positions[symbol]
        logger.info(f"Position closed: {symbol}, PnL={pnl:.2f}, close_price={close_price:.2f}")
        return True, "", pnl
    
    def update_price(self, symbol: str, current_price: float):
        """更新头寸价格"""
        if symbol in self.positions:
            self.positions[symbol].current_price = current_price
    
    def adjust_leverage(self, symbol: str, new_leverage: float) -> Tuple[bool, str]:
        """
        调整杠杆
        返回: (是否成功, 原因)
        """
        if symbol not in self.positions:
            return False, f"Position {symbol} not found"
            
        if new_leverage > self.max_leverage or new_leverage < 1:
            return False, f"Invalid leverage {new_leverage}"
            
        self.positions[symbol].leverage = new_leverage
        logger.info(f"Leverage adjusted for {symbol}: {new_leverage}")
        return True, ""
    
    def calculate_margin_ratio(self, 
                               total_collateral: float,
                               used_collateral: float) -> float:
        """
        计算保证金率
        保证金率 = 可用保证金 / 使用的保证金
        """
        if used_collateral == 0:
            return 100
            
        available = total_collateral - used_collateral
        margin_ratio = available / used_collateral if used_collateral > 0 else 100
        return margin_ratio
    
    def calculate_portfolio_metrics(self, total_collateral: float) -> PortfolioMetrics:
        """计算投资组合指标"""
        used_collateral = 0
        total_notional = 0
        total_unrealized_pnl = 0
        number_of_longs = 0
        number_of_shorts = 0
        net_delta = 0
        max_position_size = 0
        min_distance_to_liquidation = 100
        
        for symbol, position in self.positions.items():
            margin_used = position.get_margin_used()
            used_collateral += margin_used
            
            notional = position.get_notional_value()
            total_notional += notional
            
            unrealized_pnl = position.get_unrealized_pnl()
            total_unrealized_pnl += unrealized_pnl
            
            if position.mode == PositionMode.LONG:
                number_of_longs += 1
                net_delta += abs(position.quantity)
            else:
                number_of_shorts += 1
                net_delta -= abs(position.quantity)
                
            max_position_size = max(max_position_size, notional)
            distance = position.get_distance_to_liquidation_percent()
            min_distance_to_liquidation = min(min_distance_to_liquidation, distance)
        
        available_collateral = total_collateral - used_collateral
        
        # 计算投资组合杠杆
        portfolio_leverage = total_notional / (total_collateral + 1e-8)
        
        # 计算投资组合热度
        portfolio_heat = used_collateral / total_collateral if total_collateral > 0 else 0
        
        # 计算总ROI
        total_roi = total_unrealized_pnl / total_collateral if total_collateral > 0 else 0
        
        margin_ratio = self.calculate_margin_ratio(total_collateral, used_collateral)
        
        return PortfolioMetrics(
            total_collateral=total_collateral,
            used_collateral=used_collateral,
            available_collateral=available_collateral,
            margin_ratio=margin_ratio,
            total_notional=total_notional,
            total_unrealized_pnl=total_unrealized_pnl,
            total_roi=total_roi,
            portfolio_leverage=portfolio_leverage,
            total_positions=len(self.positions),
            number_of_longs=number_of_longs,
            number_of_shorts=number_of_shorts,
            net_delta=net_delta,
            portfolio_heat=portfolio_heat,
            max_position_size=max_position_size,
            min_distance_to_liquidation=min_distance_to_liquidation
        )
    
    def get_position_summary(self) -> Dict:
        """获取头寸汇总"""
        summary = {}
        for symbol, position in self.positions.items():
            summary[symbol] = {
                'mode': position.mode.value,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'current_price': position.current_price,
                'notional_value': position.get_notional_value(),
                'unrealized_pnl': position.get_unrealized_pnl(),
                'roi': position.get_roi(),
                'leverage': position.leverage,
                'liquidation_price': position.get_liquidation_price(),
                'distance_to_liquidation_percent': position.get_distance_to_liquidation_percent(),
                'margin_used': position.get_margin_used(),
                'funding_rate': position.funding_rate,
            }
        return summary
    
    def set_hedge(self, primary_symbol: str, hedge_symbol: str):
        """设置对冲关系"""
        if primary_symbol not in self.hedges:
            self.hedges[primary_symbol] = []
        self.hedges[primary_symbol].append(hedge_symbol)
        logger.info(f"Hedge set: {primary_symbol} hedged by {hedge_symbol}")
    
    def get_hedge_positions(self, symbol: str) -> List[PositionData]:
        """获取对冲头寸"""
        if symbol not in self.hedges:
            return []
            
        hedge_positions = []
        for hedge_symbol in self.hedges[symbol]:
            if hedge_symbol in self.positions:
                hedge_positions.append(self.positions[hedge_symbol])
                
        return hedge_positions
    
    def calculate_net_exposure(self) -> float:
        """
        计算净敞口
        = 多头总名义价值 - 空头总名义价值
        """
        long_exposure = 0
        short_exposure = 0
        
        for position in self.positions.values():
            if position.mode == PositionMode.LONG:
                long_exposure += position.get_notional_value()
            else:
                short_exposure += position.get_notional_value()
                
        return long_exposure - short_exposure
    
    def check_position_limits(self, 
                             symbol: str,
                             quantity: float,
                             total_collateral: float) -> Tuple[bool, str]:
        """
        检查头寸限制
        返回: (是否满足限制, 原因)
        """
        # 检查单个头寸大小限制
        notional = quantity * (self.positions[symbol].current_price 
                              if symbol in self.positions else 1000)
        
        max_allowed = total_collateral * self.max_collateral_per_position
        
        if notional > max_allowed:
            return False, f"Position size {notional:.2f} exceeds max {max_allowed:.2f}"
            
        return True, ""
    
    def rebalance_portfolio(self, 
                           target_allocation: Dict[str, float],
                           total_collateral: float) -> Dict[str, float]:
        """
        重新平衡投资组合
        
        Args:
            target_allocation: {'symbol': 分配比例}
            total_collateral: 总抵押品
            
        Returns:
            {'symbol': 目标头寸大小}
        """
        rebalanced_positions = {}
        
        for symbol, allocation in target_allocation.items():
            if allocation == 0:
                continue
                
            target_collateral = total_collateral * allocation
            current_position = self.positions.get(symbol)
            
            if current_position:
                current_notional = current_position.get_notional_value()
                target_notional = target_collateral * current_position.leverage
                
                rebalanced_positions[symbol] = {
                    'target_notional': target_notional,
                    'current_notional': current_notional,
                    'adjustment': target_notional - current_notional
                }
            else:
                rebalanced_positions[symbol] = {
                    'target_notional': target_collateral,
                    'current_notional': 0,
                    'adjustment': target_collateral
                }
        
        logger.info(f"Portfolio rebalanced: {rebalanced_positions}")
        return rebalanced_positions
    
    def estimate_liquidation_risk(self, total_collateral: float) -> float:
        """
        估计清液风险 (0-1)
        """
        metrics = self.calculate_portfolio_metrics(total_collateral)
        
        if metrics.min_distance_to_liquidation == 100:
            return 0
            
        # 风险 = 1 - 距离比例
        risk = 1 - (metrics.min_distance_to_liquidation / 100)
        return max(0, min(1, risk))
