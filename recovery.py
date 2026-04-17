"""
异常处理和恢复系统
- 网络中断、API故障、订单失败、数据不一致
- 系统崩溃恢复、市场gap应急处理
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


class RecoveryState(Enum):
    """恢复状态"""
    NORMAL = "NORMAL"
    RECOVERING = "RECOVERING"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    SHUTDOWN = "SHUTDOWN"


class FailureType(Enum):
    """故障类型"""
    NETWORK_FAILURE = "NETWORK_FAILURE"
    API_FAILURE = "API_FAILURE"
    ORDER_FAILURE = "ORDER_FAILURE"
    DATA_MISMATCH = "DATA_MISMATCH"
    SYSTEM_CRASH = "SYSTEM_CRASH"
    MARKET_GAP = "MARKET_GAP"
    UNKNOWN = "UNKNOWN"


@dataclass
class FailureRecord:
    """故障记录"""
    failure_type: FailureType
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    retry_count: int = 0
    max_retries: int = 3
    is_resolved: bool = False
    resolution_time: Optional[datetime] = None
    
    def can_retry(self) -> bool:
        """是否可以重试"""
        return self.retry_count < self.max_retries and not self.is_resolved
    
    def mark_retry(self):
        """标记重试"""
        self.retry_count += 1
    
    def mark_resolved(self):
        """标记已解决"""
        self.is_resolved = True
        self.resolution_time = datetime.now()


class RetryStrategy:
    """重试策略"""
    
    def __init__(self,
                 max_retries: int = 3,
                 initial_backoff_ms: float = 100,
                 max_backoff_ms: float = 5000,
                 backoff_multiplier: float = 2.0):
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.backoff_multiplier = backoff_multiplier
        
    def get_backoff_time(self, retry_count: int) -> float:
        """
        计算退避时间（毫秒）
        指数退避策略
        """
        backoff = self.initial_backoff_ms * (self.backoff_multiplier ** retry_count)
        backoff = min(backoff, self.max_backoff_ms)
        return backoff
    
    def should_retry(self, retry_count: int) -> bool:
        """是否应该重试"""
        return retry_count < self.max_retries


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self.opened_at = None
        
    def record_success(self):
        """记录成功"""
        self.failure_count = 0
        if self.is_open:
            self.is_open = False
            self.opened_at = None
            logger.info("Circuit breaker closed - service recovered")
    
    def record_failure(self):
        """记录故障"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            self.opened_at = datetime.now()
            logger.error(f"Circuit breaker opened - {self.failure_count} failures detected")
    
    def can_execute(self) -> bool:
        """是否可以执行"""
        if not self.is_open:
            return True
            
        # 检查是否可以尝试恢复
        if self.opened_at:
            elapsed = (datetime.now() - self.opened_at).total_seconds()
            if elapsed >= self.recovery_timeout_seconds:
                logger.info("Circuit breaker attempting recovery...")
                self.is_open = False
                self.failure_count = 0
                self.opened_at = None
                return True
                
        return False
    
    def get_status(self) -> Dict:
        """获取熔断器状态"""
        return {
            'is_open': self.is_open,
            'failure_count': self.failure_count,
            'last_failure_time': self.last_failure_time,
            'opened_at': self.opened_at
        }


class FallbackManager:
    """降级管理器"""
    
    def __init__(self):
        self.fallback_handlers: Dict[FailureType, Callable] = {}
        self.degradation_levels: Dict[str, int] = {}  # {service_name: level}
        
    def register_fallback(self,
                         failure_type: FailureType,
                         handler: Callable):
        """注册降级处理器"""
        self.fallback_handlers[failure_type] = handler
        logger.info(f"Fallback registered for {failure_type.value}")
    
    def execute_fallback(self,
                        failure_type: FailureType,
                        *args,
                        **kwargs) -> Optional[Any]:
        """执行降级处理"""
        if failure_type not in self.fallback_handlers:
            logger.warning(f"No fallback handler for {failure_type.value}")
            return None
            
        handler = self.fallback_handlers[failure_type]
        try:
            result = handler(*args, **kwargs)
            logger.info(f"Fallback executed for {failure_type.value}")
            return result
        except Exception as e:
            logger.error(f"Fallback execution failed: {e}")
            return None
    
    def set_degradation_level(self, service_name: str, level: int):
        """设置降级等级 (0=正常, 1=部分, 2=严重)"""
        self.degradation_levels[service_name] = level
        logger.warning(f"Degradation level for {service_name} set to {level}")
    
    def is_degraded(self, service_name: str) -> bool:
        """是否降级"""
        return self.degradation_levels.get(service_name, 0) > 0


class RecoveryManager:
    """恢复管理器"""
    
    def __init__(self):
        self.recovery_state = RecoveryState.NORMAL
        self.failure_history: List[FailureRecord] = []
        self.retry_strategy = RetryStrategy()
        self.circuit_breaker = CircuitBreaker()
        self.fallback_manager = FallbackManager()
        self.checkpoint_data: Dict = {}
        
    def record_failure(self,
                      failure_type: FailureType,
                      description: str) -> FailureRecord:
        """记录故障"""
        record = FailureRecord(
            failure_type=failure_type,
            description=description
        )
        self.failure_history.append(record)
        
        # 更新恢复状态
        self._update_recovery_state()
        
        logger.error(f"Failure recorded: {failure_type.value} - {description}")
        return record
    
    def _update_recovery_state(self):
        """更新恢复状态"""
        unresolved_count = sum(
            1 for f in self.failure_history if not f.is_resolved
        )
        
        critical_failures = sum(
            1 for f in self.failure_history
            if not f.is_resolved and f.failure_type in [
                FailureType.SYSTEM_CRASH,
                FailureType.MARKET_GAP
            ]
        )
        
        if critical_failures > 0:
            self.recovery_state = RecoveryState.CRITICAL
        elif unresolved_count > 3:
            self.recovery_state = RecoveryState.DEGRADED
        elif unresolved_count > 0:
            self.recovery_state = RecoveryState.RECOVERING
        else:
            self.recovery_state = RecoveryState.NORMAL
            
        logger.info(f"Recovery state updated to {self.recovery_state.value}")
    
    def retry_operation(self,
                       operation: Callable,
                       *args,
                       **kwargs) -> Optional[Any]:
        """
        重试操作
        """
        retry_count = 0
        
        while retry_count < self.retry_strategy.max_retries:
            try:
                # 检查熔断器
                if not self.circuit_breaker.can_execute():
                    logger.warning("Circuit breaker is open - cannot execute operation")
                    return None
                    
                result = operation(*args, **kwargs)
                self.circuit_breaker.record_success()
                return result
                
            except Exception as e:
                retry_count += 1
                self.circuit_breaker.record_failure()
                
                if self.retry_strategy.should_retry(retry_count):
                    backoff_time = self.retry_strategy.get_backoff_time(retry_count)
                    logger.warning(f"Operation failed, retrying in {backoff_time}ms: {e}")
                    time.sleep(backoff_time / 1000)
                else:
                    logger.error(f"Operation failed after {retry_count} retries: {e}")
                    return None
                    
        return None
    
    def handle_network_failure(self, description: str = "") -> bool:
        """
        处理网络故障
        返回: 是否可以恢复
        """
        record = self.record_failure(
            FailureType.NETWORK_FAILURE,
            f"Network disconnected: {description}"
        )
        
        # 尝试重新连接
        for attempt in range(3):
            logger.info(f"Reconnecting attempt {attempt + 1}/3...")
            time.sleep(1)
            
            # 这里应该调用实际的重连函数
            if self._test_connectivity():
                record.mark_resolved()
                self._update_recovery_state()
                return True
                
        return False
    
    def handle_api_failure(self, description: str = "") -> bool:
        """
        处理API故障
        返回: 是否可以降级
        """
        record = self.record_failure(
            FailureType.API_FAILURE,
            f"API error: {description}"
        )
        
        # 使用降级处理
        fallback_result = self.fallback_manager.execute_fallback(
            FailureType.API_FAILURE
        )
        
        if fallback_result is not None:
            self.fallback_manager.set_degradation_level('api', 1)
            logger.warning("API degraded - using fallback")
            return True
            
        return False
    
    def handle_order_failure(self, order_id: str, description: str = "") -> Dict:
        """
        处理订单故障
        返回: {status, action, new_order_id}
        """
        record = self.record_failure(
            FailureType.ORDER_FAILURE,
            f"Order {order_id} failed: {description}"
        )
        
        # 检查订单状态
        order_status = self._query_order_status(order_id)
        
        action = "RETRY"
        new_order_id = None
        
        if order_status == "FILLED":
            # 订单已成交
            record.mark_resolved()
            action = "CONFIRMED"
        elif order_status == "CANCELLED":
            # 订单已取消，需要重新提交
            new_order_id = self._resubmit_order(order_id)
            action = "RESUBMITTED"
        elif order_status == "REJECTED":
            # 订单被拒绝
            action = "REJECTED"
        else:
            # 未知状态，重试
            action = "RETRY"
            
        return {
            'status': order_status,
            'action': action,
            'new_order_id': new_order_id
        }
    
    def handle_data_mismatch(self, 
                           local_data: Dict,
                           remote_data: Dict,
                           sync_strategy: str = "remote") -> Dict:
        """
        处理数据不一致
        sync_strategy: 'remote'=使用服务器数据, 'local'=保持本地数据
        返回: {resolved, final_data}
        """
        record = self.record_failure(
            FailureType.DATA_MISMATCH,
            f"Data mismatch between local and remote"
        )
        
        if sync_strategy == "remote":
            logger.warning("Data mismatch resolved using remote data")
            record.mark_resolved()
            return {'resolved': True, 'final_data': remote_data}
        else:
            logger.warning("Data mismatch resolved using local data")
            record.mark_resolved()
            return {'resolved': True, 'final_data': local_data}
    
    def handle_system_crash(self, checkpoint_id: str) -> bool:
        """
        处理系统崩溃
        返回: 是否成功恢复
        """
        record = self.record_failure(
            FailureType.SYSTEM_CRASH,
            f"System crashed, attempting recovery from checkpoint {checkpoint_id}"
        )
        
        # 从检查点恢复
        if checkpoint_id in self.checkpoint_data:
            checkpoint = self.checkpoint_data[checkpoint_id]
            
            try:
                # 恢复关键数据
                self._restore_from_checkpoint(checkpoint)
                record.mark_resolved()
                logger.info(f"System recovered from checkpoint {checkpoint_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to restore from checkpoint: {e}")
                return False
        else:
            logger.error(f"Checkpoint {checkpoint_id} not found")
            return False
    
    def handle_market_gap(self, 
                         symbol: str,
                         gap_percent: float) -> Dict:
        """
        处理市场gap
        返回: {action, liquidation_required}
        """
        record = self.record_failure(
            FailureType.MARKET_GAP,
            f"Market gap for {symbol}: {gap_percent:.2%}"
        )
        
        # 检查是否需要强制清液
        liquidation_required = gap_percent > 0.10  # 10%以上gap
        
        if liquidation_required:
            action = "EMERGENCY_CLOSE"
            logger.critical(f"Emergency close required for {symbol} due to market gap")
        else:
            action = "MONITOR"
            logger.warning(f"Market gap detected for {symbol}, monitoring...")
            
        return {
            'action': action,
            'liquidation_required': liquidation_required,
            'gap_percent': gap_percent
        }
    
    def save_checkpoint(self, checkpoint_id: str, data: Dict):
        """保存检查点"""
        self.checkpoint_data[checkpoint_id] = {
            'timestamp': datetime.now(),
            'data': data
        }
        logger.info(f"Checkpoint saved: {checkpoint_id}")
    
    def _test_connectivity(self) -> bool:
        """测试连接"""
        # 这里应该实现实际的连接测试
        return True
    
    def _query_order_status(self, order_id: str) -> str:
        """查询订单状态"""
        # 这里应该实现实际的订单查询
        return "UNKNOWN"
    
    def _resubmit_order(self, order_id: str) -> str:
        """重新提交订单"""
        # 这里应该实现实际的订单重新提交
        return f"NEW_{order_id}"
    
    def _restore_from_checkpoint(self, checkpoint: Dict):
        """从检查点恢复"""
        # 这里应该实现实际的恢复逻辑
        logger.info("Restoring system state from checkpoint...")
    
    def get_recovery_status(self) -> Dict:
        """获取恢复状态"""
        unresolved_failures = [
            f for f in self.failure_history if not f.is_resolved
        ]
        
        return {
            'state': self.recovery_state.value,
            'unresolved_failures': len(unresolved_failures),
            'circuit_breaker_status': self.circuit_breaker.get_status(),
            'total_failures': len(self.failure_history),
            'recent_failures': [
                {
                    'type': f.failure_type.value,
                    'description': f.description,
                    'timestamp': f.timestamp
                }
                for f in unresolved_failures[-5:]
            ]
        }
