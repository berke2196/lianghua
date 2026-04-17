"""
订单执行优化系统
- VWAP、TWAP、冰山单、机器学习优化
- 最小化滑点、最大化成交率、隐蔽意图
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ExecutionAlgorithm(Enum):
    """执行算法"""
    VWAP = "VWAP"  # 成交量加权平均价
    TWAP = "TWAP"  # 时间加权平均价
    ICEBERG = "ICEBERG"  # 冰山单
    ML_OPTIMIZED = "ML_OPTIMIZED"  # 机器学习优化
    ADAPTIVE = "ADAPTIVE"  # 自适应


@dataclass
class OrderBook:
    """委托簿"""
    bids: List[Tuple[float, float]]  # [(价格, 数量)]
    asks: List[Tuple[float, float]]
    mid_price: float
    timestamp: datetime
    
    def get_bid_ask_spread(self) -> float:
        """获取买卖差"""
        if not self.bids or not self.asks:
            return 0
        return self.asks[0][0] - self.bids[0][0]
    
    def get_total_bid_volume(self, n_levels: int = 5) -> float:
        """获取买方总量"""
        return sum(qty for _, qty in self.bids[:n_levels])
    
    def get_total_ask_volume(self, n_levels: int = 5) -> float:
        """获取卖方总量"""
        return sum(qty for _, qty in self.asks[:n_levels])


@dataclass
class ExecutionPlan:
    """执行计划"""
    symbol: str
    total_quantity: float
    target_price: float  # 目标价格
    algorithm: ExecutionAlgorithm
    max_slippage: float  # 最大滑点
    time_limit_seconds: int  # 时间限制
    splits: List[Dict] = field(default_factory=list)  # 分割计划
    created_at: datetime = field(default_factory=datetime.now)


class VWAPExecutor:
    """VWAP执行器 - 成交量加权平均价"""
    
    def __init__(self):
        self.historical_volumes: Dict[str, List[float]] = {}
        
    def calculate_vwap(self, prices: List[float], volumes: List[float]) -> float:
        """
        计算VWAP
        VWAP = Σ(price * volume) / Σ(volume)
        """
        if not prices or len(prices) != len(volumes):
            return 0
            
        total_value = sum(p * v for p, v in zip(prices, volumes))
        total_volume = sum(volumes)
        
        if total_volume == 0:
            return 0
            
        return total_value / total_volume
    
    def create_execution_plan(self,
                            symbol: str,
                            quantity: float,
                            order_book: OrderBook,
                            time_slots: int = 10) -> ExecutionPlan:
        """
        创建VWAP执行计划
        
        Args:
            symbol: 交易品种
            quantity: 总数量
            order_book: 委托簿
            time_slots: 时间分割数
        """
        # 预测每个时间槽的成交量
        if symbol in self.historical_volumes:
            avg_volume = np.mean(self.historical_volumes[symbol][-20:])
        else:
            avg_volume = order_book.get_total_ask_volume() * 2
            
        plan = ExecutionPlan(
            symbol=symbol,
            total_quantity=quantity,
            target_price=order_book.mid_price,
            algorithm=ExecutionAlgorithm.VWAP,
            max_slippage=0.001,
            time_limit_seconds=300
        )
        
        # 生成分割计划
        for i in range(time_slots):
            slot_qty = quantity / time_slots
            slot_price = order_book.mid_price  # VWAP跟随市场
            
            plan.splits.append({
                'time_slot': i,
                'quantity': slot_qty,
                'target_price': slot_price,
                'time_offset_seconds': (i + 1) * 300 // time_slots
            })
            
        logger.info(f"VWAP execution plan created for {symbol}: {time_slots} slots")
        return plan
    
    def adjust_order_speed(self, 
                          current_volume: float,
                          expected_volume: float) -> float:
        """
        调整订单速度
        如果当前成交量大于预期，加快速度；反之减慢
        """
        if expected_volume == 0:
            return 1.0
            
        volume_ratio = current_volume / expected_volume
        
        if volume_ratio > 1.2:
            # 成交量多，加快速度
            return 1.2
        elif volume_ratio < 0.8:
            # 成交量少，减慢速度
            return 0.8
        else:
            return 1.0


class TWAPExecutor:
    """TWAP执行器 - 时间加权平均价"""
    
    def create_execution_plan(self,
                            symbol: str,
                            quantity: float,
                            order_book: OrderBook,
                            time_limit_seconds: int = 300) -> ExecutionPlan:
        """
        创建TWAP执行计划
        
        均匀分散订单，隐蔽意图
        """
        # 计算时间分割
        time_slots = max(10, time_limit_seconds // 30)
        
        plan = ExecutionPlan(
            symbol=symbol,
            total_quantity=quantity,
            target_price=order_book.mid_price,
            algorithm=ExecutionAlgorithm.TWAP,
            max_slippage=0.0015,
            time_limit_seconds=time_limit_seconds
        )
        
        # 均匀分割
        for i in range(time_slots):
            slot_qty = quantity / time_slots
            slot_time = time_limit_seconds * (i + 1) / time_slots
            
            plan.splits.append({
                'time_slot': i,
                'quantity': slot_qty,
                'target_price': order_book.mid_price,
                'time_offset_seconds': int(slot_time)
            })
            
        logger.info(f"TWAP execution plan created for {symbol}: {time_slots} slots, {time_limit_seconds}s total")
        return plan
    
    def apply_market_impact_adjustment(self,
                                      order_book: OrderBook,
                                      total_quantity: float) -> float:
        """
        市场冲击调整
        大单会增加价格冲击
        """
        available_liquidity = order_book.get_total_ask_volume(10)
        
        if total_quantity > available_liquidity * 2:
            # 大单冲击
            impact = 1 + (total_quantity / available_liquidity - 1) * 0.01
            return impact
        elif total_quantity > available_liquidity:
            # 中等冲击
            return 1.005
        else:
            # 小冲击
            return 1.001


class IcebergExecutor:
    """冰山单执行器 - 隐藏真实数量"""
    
    def __init__(self):
        self.visible_ratio_range = (0.1, 0.3)  # 显示比例范围
        self.price_offset_range = (0.0005, 0.002)  # 价格偏移范围
        
    def create_execution_plan(self,
                            symbol: str,
                            quantity: float,
                            order_book: OrderBook,
                            min_visible_qty: float = 100) -> ExecutionPlan:
        """
        创建冰山单执行计划
        
        隐藏真实数量，逐批显示
        """
        # 随机确定显示比例
        visible_ratio = np.random.uniform(
            self.visible_ratio_range[0],
            self.visible_ratio_range[1]
        )
        
        visible_qty = max(min_visible_qty, quantity * visible_ratio)
        price_offset = np.random.uniform(
            self.price_offset_range[0],
            self.price_offset_range[1]
        )
        
        plan = ExecutionPlan(
            symbol=symbol,
            total_quantity=quantity,
            target_price=order_book.mid_price + price_offset,
            algorithm=ExecutionAlgorithm.ICEBERG,
            max_slippage=0.002,
            time_limit_seconds=600
        )
        
        # 生成冰山订单
        num_icebergs = int(np.ceil(quantity / visible_qty))
        
        for i in range(num_icebergs):
            remaining = quantity - (i * visible_qty)
            exec_qty = min(visible_qty, remaining)
            
            plan.splits.append({
                'iceberg_index': i,
                'visible_quantity': exec_qty,
                'total_hidden_quantity': remaining,
                'target_price': plan.target_price,
                'time_offset_seconds': 60 * i
            })
            
        logger.info(f"Iceberg execution plan created for {symbol}: {num_icebergs} icebergs")
        return plan


class OrderOptimizer:
    """订单优化器 - 综合执行"""
    
    def __init__(self):
        self.vwap_executor = VWAPExecutor()
        self.twap_executor = TWAPExecutor()
        self.iceberg_executor = IcebergExecutor()
        
    def estimate_slippage(self,
                         order_book: OrderBook,
                         order_quantity: float,
                         is_buy: bool = True) -> float:
        """
        估计滑点
        """
        if is_buy:
            # 估计需要与多少档位成交
            cumulative_qty = 0
            weighted_price = 0
            
            for price, qty in order_book.asks:
                if cumulative_qty + qty >= order_quantity:
                    # 最后一档
                    last_qty = order_quantity - cumulative_qty
                    weighted_price += price * last_qty
                    break
                else:
                    weighted_price += price * qty
                    cumulative_qty += qty
                    
            weighted_price /= order_quantity
            slippage = (weighted_price - order_book.mid_price) / order_book.mid_price
        else:
            # 卖出滑点计算
            cumulative_qty = 0
            weighted_price = 0
            
            for price, qty in order_book.bids:
                if cumulative_qty + qty >= order_quantity:
                    last_qty = order_quantity - cumulative_qty
                    weighted_price += price * last_qty
                    break
                else:
                    weighted_price += price * qty
                    cumulative_qty += qty
                    
            weighted_price /= order_quantity
            slippage = (order_book.mid_price - weighted_price) / order_book.mid_price
            
        return slippage
    
    def estimate_execution_probability(self,
                                      order_book: OrderBook,
                                      order_price: float,
                                      is_buy: bool = True) -> float:
        """
        估计成交概率
        """
        if is_buy:
            # 查看是否在买价附近
            best_ask = order_book.asks[0][0] if order_book.asks else float('inf')
            
            if order_price >= best_ask:
                return 1.0
            else:
                # 根据距离估计概率
                price_gap = best_ask - order_price
                spread = order_book.get_bid_ask_spread()
                
                if spread == 0:
                    return 0.5
                    
                probability = max(0, 1 - price_gap / (spread * 2))
                return probability
        else:
            # 卖出
            best_bid = order_book.bids[0][0] if order_book.bids else 0
            
            if order_price <= best_bid:
                return 1.0
            else:
                price_gap = order_price - best_bid
                spread = order_book.get_bid_ask_spread()
                
                if spread == 0:
                    return 0.5
                    
                probability = max(0, 1 - price_gap / (spread * 2))
                return probability
    
    def detect_large_order(self, order_book: OrderBook, order_qty: float) -> bool:
        """
        检测是否为大单
        """
        avg_ask_volume = order_book.get_total_ask_volume(5) / 5
        
        # 如果订单量超过平均的5倍，认为是大单
        return order_qty > avg_ask_volume * 5
    
    def predict_market_impact(self,
                             order_book: OrderBook,
                             order_quantity: float,
                             is_buy: bool = True) -> float:
        """
        预测市场冲击
        """
        total_liquidity = order_book.get_total_ask_volume(10) if is_buy else order_book.get_total_bid_volume(10)
        
        if total_liquidity == 0:
            return 0.01  # 默认1%
            
        # 冲击比例 ≈ 订单量 / 流动性 * 系数
        impact_ratio = order_quantity / total_liquidity
        
        if impact_ratio > 1:
            # 冲击 > 100%
            market_impact = 0.03
        elif impact_ratio > 0.5:
            # 冲击 50-100%
            market_impact = 0.02
        elif impact_ratio > 0.1:
            # 冲击 10-50%
            market_impact = 0.01
        else:
            # 冲击 < 10%
            market_impact = 0.003
            
        return market_impact
    
    def recommend_algorithm(self,
                           symbol: str,
                           quantity: float,
                           order_book: OrderBook,
                           time_limit_seconds: int = 300) -> Tuple[ExecutionAlgorithm, ExecutionPlan]:
        """
        推荐执行算法
        """
        # 检测大单
        is_large = self.detect_large_order(order_book, quantity)
        
        # 计算滑点和冲击
        slippage = self.estimate_slippage(order_book, quantity)
        impact = self.predict_market_impact(order_book, quantity)
        
        logger.info(f"Order analysis: large={is_large}, slippage={slippage:.4f}, impact={impact:.4f}")
        
        # 根据情况选择算法
        if is_large and time_limit_seconds >= 300:
            # 大单，时间充足 -> VWAP
            algo = ExecutionAlgorithm.VWAP
            plan = self.vwap_executor.create_execution_plan(
                symbol, quantity, order_book, time_slots=10
            )
        elif time_limit_seconds >= 300:
            # 中等单，时间充足 -> TWAP
            algo = ExecutionAlgorithm.TWAP
            plan = self.twap_executor.create_execution_plan(
                symbol, quantity, order_book, time_limit_seconds
            )
        else:
            # 时间紧张 -> 冰山单
            algo = ExecutionAlgorithm.ICEBERG
            plan = self.iceberg_executor.create_execution_plan(
                symbol, quantity, order_book
            )
            
        return algo, plan
    
    def optimize_execution(self,
                          symbol: str,
                          quantity: float,
                          order_book: OrderBook,
                          target_price: float = None,
                          time_limit_seconds: int = 300) -> Dict:
        """
        优化执行计划
        """
        if target_price is None:
            target_price = order_book.mid_price
            
        algo, plan = self.recommend_algorithm(
            symbol, quantity, order_book, time_limit_seconds
        )
        
        # 估计性能指标
        slippage = self.estimate_slippage(order_book, quantity)
        exec_prob = self.estimate_execution_probability(
            order_book, target_price
        )
        market_impact = self.predict_market_impact(
            order_book, quantity
        )
        
        return {
            'algorithm': algo.value,
            'execution_plan': plan,
            'estimated_slippage': slippage,
            'execution_probability': exec_prob,
            'market_impact': market_impact,
            'expected_execution_price': target_price * (1 + slippage),
            'time_limit_seconds': time_limit_seconds
        }
