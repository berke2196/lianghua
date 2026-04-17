"""
订单执行引擎 - 完整的订单管理和执行
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIAL = "PARTIAL"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OrderType(Enum):
    """订单类型"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderSide(Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


@dataclass
class Order:
    """订单数据"""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    quantity: float = 0
    price: float = 0
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    filled_quantity: float = 0
    average_price: float = 0
    fees: float = 0
    
    def get_filled_percent(self) -> float:
        """获取成交百分比"""
        if self.quantity == 0:
            return 0
        return self.filled_quantity / self.quantity
    
    def get_remaining_quantity(self) -> float:
        """获取剩余数量"""
        return self.quantity - self.filled_quantity
    
    def is_filled(self) -> bool:
        """是否完全成交"""
        return self.filled_quantity >= self.quantity


class ExecutionQuality:
    """执行质量评估"""
    
    def __init__(self):
        self.completed_orders: List[Order] = []
        self.total_slippage = 0
        self.total_fees = 0
        
    def add_filled_order(self, order: Order, market_price: float):
        """添加成交的订单"""
        self.completed_orders.append(order)
        
        # 计算滑点
        if order.side == OrderSide.BUY:
            slippage = order.average_price - market_price
        else:
            slippage = market_price - order.average_price
            
        self.total_slippage += slippage * order.filled_quantity
        self.total_fees += order.fees
        
    def get_average_slippage(self) -> float:
        """获取平均滑点"""
        if not self.completed_orders:
            return 0
            
        total_qty = sum(o.filled_quantity for o in self.completed_orders)
        if total_qty == 0:
            return 0
            
        return self.total_slippage / total_qty
    
    def get_average_fees_percent(self) -> float:
        """获取平均费率"""
        if not self.completed_orders:
            return 0
            
        total_value = sum(
            o.average_price * o.filled_quantity 
            for o in self.completed_orders
        )
        
        if total_value == 0:
            return 0
            
        return self.total_fees / total_value
    
    def get_execution_summary(self) -> Dict:
        """获取执行汇总"""
        return {
            'total_orders': len(self.completed_orders),
            'total_quantity': sum(o.filled_quantity for o in self.completed_orders),
            'average_slippage': self.get_average_slippage(),
            'total_fees': self.total_fees,
            'average_fees_percent': self.get_average_fees_percent(),
            'fill_rate': self._calculate_fill_rate()
        }
    
    def _calculate_fill_rate(self) -> float:
        """计算成交率"""
        if not self.completed_orders:
            return 0
            
        filled = sum(
            1 for o in self.completed_orders 
            if o.status == OrderStatus.FILLED
        )
        
        return filled / len(self.completed_orders)


class OrderExecutor:
    """订单执行器"""
    
    def __init__(self):
        self.pending_orders: Dict[str, Order] = {}
        self.completed_orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        self.execution_quality = ExecutionQuality()
        
    def submit_order(self, order: Order) -> Tuple[bool, str]:
        """提交订单"""
        if order.quantity <= 0:
            return False, "Invalid quantity"
            
        if order.price <= 0 and order.order_type == OrderType.LIMIT:
            return False, "Invalid price"
            
        order.status = OrderStatus.SUBMITTED
        order.updated_at = datetime.now()
        
        self.pending_orders[order.order_id] = order
        self.order_history.append(order)
        
        logger.info(f"Order submitted: {order.order_id} {order.side.value} {order.quantity} {order.symbol} @ {order.price}")
        return True, ""
    
    def fill_order(self, 
                   order_id: str,
                   filled_qty: float,
                   fill_price: float,
                   is_partial: bool = False) -> Tuple[bool, str]:
        """填充订单"""
        if order_id not in self.pending_orders:
            return False, f"Order {order_id} not found"
            
        order = self.pending_orders[order_id]
        
        if filled_qty > order.get_remaining_quantity():
            return False, "Filled quantity exceeds order quantity"
            
        # 更新成交信息
        total_filled = order.filled_quantity + filled_qty
        
        # 计算新的平均价
        if order.filled_quantity > 0:
            order.average_price = (
                (order.average_price * order.filled_quantity + fill_price * filled_qty) /
                total_filled
            )
        else:
            order.average_price = fill_price
            
        order.filled_quantity = total_filled
        order.updated_at = datetime.now()
        
        if is_partial or filled_qty < order.get_remaining_quantity():
            order.status = OrderStatus.PARTIAL
        elif filled_qty == order.get_remaining_quantity():
            order.status = OrderStatus.FILLED
            
        logger.info(f"Order filled: {order_id}, {filled_qty} @ {fill_price}")
        
        # 如果完全成交，移到完成列表
        if order.status == OrderStatus.FILLED:
            self.completed_orders[order_id] = order
            del self.pending_orders[order_id]
            
        return True, ""
    
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """取消订单"""
        if order_id not in self.pending_orders:
            return False, f"Order {order_id} not found"
            
        order = self.pending_orders[order_id]
        order.status = OrderStatus.CANCELLED
        order.updated_at = datetime.now()
        
        # 移到完成列表
        self.completed_orders[order_id] = order
        del self.pending_orders[order_id]
        
        logger.info(f"Order cancelled: {order_id}")
        return True, ""
    
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """获取订单状态"""
        if order_id in self.pending_orders:
            return self.pending_orders[order_id]
        elif order_id in self.completed_orders:
            return self.completed_orders[order_id]
        else:
            return None
    
    def get_pending_orders(self, symbol: str = None) -> List[Order]:
        """获取待处理订单"""
        if symbol:
            return [o for o in self.pending_orders.values() if o.symbol == symbol]
        else:
            return list(self.pending_orders.values())
    
    def get_completed_orders(self, symbol: str = None, limit: int = 100) -> List[Order]:
        """获取已完成订单"""
        if symbol:
            orders = [o for o in self.completed_orders.values() if o.symbol == symbol]
        else:
            orders = list(self.completed_orders.values())
            
        # 返回最新的订单
        return sorted(orders, key=lambda o: o.updated_at, reverse=True)[:limit]
    
    def get_order_book_statistics(self) -> Dict:
        """获取订单簿统计"""
        pending = list(self.pending_orders.values())
        
        stats = {
            'total_pending': len(pending),
            'total_buy_qty': sum(o.quantity for o in pending if o.side == OrderSide.BUY),
            'total_sell_qty': sum(o.quantity for o in pending if o.side == OrderSide.SELL),
            'average_price': self._calculate_average_price(pending),
            'oldest_order_age': self._calculate_oldest_order_age(pending),
        }
        
        return stats
    
    def _calculate_average_price(self, orders: List[Order]) -> float:
        """计算平均价格"""
        if not orders:
            return 0
            
        total_value = sum(o.price * o.quantity for o in orders)
        total_qty = sum(o.quantity for o in orders)
        
        if total_qty == 0:
            return 0
            
        return total_value / total_qty
    
    def _calculate_oldest_order_age(self, orders: List[Order]) -> int:
        """计算最旧订单的年龄（秒）"""
        if not orders:
            return 0
            
        oldest = min(orders, key=lambda o: o.created_at)
        age = (datetime.now() - oldest.created_at).total_seconds()
        
        return int(age)


class OrderManager:
    """订单管理器 - 综合管理"""
    
    def __init__(self):
        self.executor = OrderExecutor()
        self.execution_quality = ExecutionQuality()
        self.order_limits: Dict[str, Dict] = {}  # {symbol: {daily_limit, hourly_limit}}
        
    def set_order_limits(self, symbol: str, daily_limit: int, hourly_limit: int):
        """设置订单限制"""
        self.order_limits[symbol] = {
            'daily_limit': daily_limit,
            'hourly_limit': hourly_limit,
            'daily_count': 0,
            'hourly_count': 0,
            'last_reset': datetime.now()
        }
    
    def check_order_limits(self, symbol: str) -> Tuple[bool, str]:
        """检查订单限制"""
        if symbol not in self.order_limits:
            return True, ""
            
        limits = self.order_limits[symbol]
        now = datetime.now()
        
        # 重置计数
        if (now - limits['last_reset']).total_seconds() >= 3600:
            limits['daily_count'] = 0
            limits['hourly_count'] = 0
            limits['last_reset'] = now
            
        # 检查限制
        if limits['daily_count'] >= limits['daily_limit']:
            return False, f"Daily order limit ({limits['daily_limit']}) exceeded"
            
        if limits['hourly_count'] >= limits['hourly_limit']:
            return False, f"Hourly order limit ({limits['hourly_limit']}) exceeded"
            
        return True, ""
    
    def submit_order_with_limits(self, order: Order) -> Tuple[bool, str]:
        """提交受限的订单"""
        # 检查限制
        allowed, reason = self.check_order_limits(order.symbol)
        if not allowed:
            return False, reason
            
        # 提交订单
        success, msg = self.executor.submit_order(order)
        
        if success:
            # 更新计数
            limits = self.order_limits[order.symbol]
            limits['daily_count'] += 1
            limits['hourly_count'] += 1
            
        return success, msg
    
    def get_execution_summary(self) -> Dict:
        """获取执行汇总"""
        completed = self.executor.get_completed_orders(limit=1000)
        
        for order in completed:
            if order.status == OrderStatus.FILLED:
                self.execution_quality.add_filled_order(order, order.average_price)
                
        return self.execution_quality.get_execution_summary()
