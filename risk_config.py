"""
风险管理系统配置文件
包含所有系统参数和阈值
"""

from dataclasses import dataclass
from enum import Enum


class Environment(Enum):
    """运行环境"""
    DEVELOPMENT = "DEVELOPMENT"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"


@dataclass
class KellyConfig:
    """Kelly准则配置"""
    min_allocation: float = 0.01  # 1% 最小配置
    max_allocation: float = 0.25  # 25% 最大配置
    confidence_level: float = 0.99  # 99% 置信度
    leverage_limit: float = 3.0  # 最大杠杆
    bankruptcy_risk_limit: float = 0.001  # 0.1% 破产风险限制
    lookback_period: int = 100  # 回溯期
    rebalance_frequency: int = 20  # 重平衡频率
    

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
class PositionConfig:
    """头寸管理配置"""
    max_leverage: float = 10.0
    max_collateral_per_position: float = 0.2  # 单个头寸最多使用总抵押品的20%
    rebalance_frequency_minutes: int = 60
    enable_hedging: bool = True
    enable_net_exposure_limit: bool = True
    max_net_exposure_ratio: float = 1.0  # 净敞口最多100%


@dataclass
class OrderConfig:
    """订单配置"""
    # 执行参数
    default_execution_algorithm: str = "ADAPTIVE"
    vwap_time_slots: int = 10
    twap_max_time_seconds: int = 300
    iceberg_min_visible_qty: float = 100
    
    # 限制
    max_daily_orders: Dict[str, int] = None  # {symbol: limit}
    max_hourly_orders: Dict[str, int] = None
    max_slippage_percent: float = 0.10  # 0.1% 最大滑点
    min_execution_probability: float = 0.90  # 90% 最小成交概率
    
    # 费用
    maker_fee_percent: float = 0.01  # 0.01% maker费用
    taker_fee_percent: float = 0.05  # 0.05% taker费用


@dataclass
class RiskConfig:
    """风险监控配置"""
    # 告警阈值
    margin_ratio_warning: float = 2.0
    margin_ratio_critical: float = 1.5
    leverage_warning: float = 5.0
    leverage_critical: float = 8.0
    pnl_loss_warning: float = -0.05
    pnl_loss_critical: float = -0.10
    liquidation_distance_warning: float = 0.1
    liquidation_distance_critical: float = 0.05
    system_latency_warning_ms: float = 100
    system_latency_critical_ms: float = 500
    network_latency_warning_ms: float = 200
    network_latency_critical_ms: float = 1000
    
    # 监控参数
    metrics_recording_interval_seconds: int = 5
    alert_history_limit: int = 1000
    prediction_lookahead_minutes: int = 60
    enable_anomaly_detection: bool = True
    enable_auto_recovery_alerts: bool = True


@dataclass
class RecoveryConfig:
    """异常恢复配置"""
    # 重试参数
    max_retries: int = 3
    initial_backoff_ms: float = 100
    max_backoff_ms: float = 5000
    backoff_multiplier: float = 2.0
    
    # 熔断器
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout_seconds: int = 60
    
    # 检查点
    checkpoint_interval_seconds: int = 300  # 5分钟
    checkpoint_retention_limit: int = 100
    enable_auto_checkpoint: bool = True
    
    # 故障处理
    network_reconnect_attempts: int = 5
    network_reconnect_interval_seconds: int = 1
    api_fallback_enabled: bool = True
    data_sync_on_mismatch: str = "remote"  # remote/local


@dataclass
class SystemConfig:
    """系统配置"""
    # 环境
    environment: Environment = Environment.PRODUCTION
    debug_mode: bool = False
    log_level: str = "INFO"
    
    # 性能
    enable_performance_monitoring: bool = True
    performance_log_interval_seconds: int = 60
    max_operations_per_second: int = 1000
    
    # 存储
    enable_persistence: bool = True
    persistence_path: str = "./data"
    backup_interval_seconds: int = 3600
    
    # 通知
    enable_notifications: bool = True
    notification_channels: List[str] = None  # ['discord', 'telegram', 'email']
    alert_notification_level: str = "WARNING"  # INFO/WARNING/CRITICAL/EMERGENCY


class RiskManagementConfig:
    """风险管理系统完整配置"""
    
    def __init__(self, environment: Environment = Environment.PRODUCTION):
        self.environment = environment
        self.kelly = KellyConfig()
        self.stop_loss = StopLossConfig()
        self.position = PositionConfig()
        self.order = OrderConfig()
        self.risk = RiskConfig()
        self.recovery = RecoveryConfig()
        self.system = SystemConfig(environment=environment)
        
        # 根据环境调整配置
        self._apply_environment_settings()
    
    def _apply_environment_settings(self):
        """根据环境应用配置"""
        if self.environment == Environment.DEVELOPMENT:
            self.system.debug_mode = True
            self.system.log_level = "DEBUG"
            self.kelly.max_allocation = 0.05  # 开发环境降低配置
            self.stop_loss.single_trade_stop_loss = 0.10  # 更宽松的止损
            
        elif self.environment == Environment.STAGING:
            self.system.log_level = "INFO"
            self.kelly.max_allocation = 0.15  # 中等配置
            
        elif self.environment == Environment.PRODUCTION:
            self.system.log_level = "WARNING"
            self.kelly.max_allocation = 0.25  # 生产配置
            self.recovery.enable_auto_checkpoint = True
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'environment': self.environment.value,
            'kelly': self._dataclass_to_dict(self.kelly),
            'stop_loss': self._dataclass_to_dict(self.stop_loss),
            'position': self._dataclass_to_dict(self.position),
            'order': self._dataclass_to_dict(self.order),
            'risk': self._dataclass_to_dict(self.risk),
            'recovery': self._dataclass_to_dict(self.recovery),
            'system': self._dataclass_to_dict(self.system),
        }
    
    @staticmethod
    def _dataclass_to_dict(obj) -> Dict:
        """将dataclass转换为字典"""
        if hasattr(obj, '__dataclass_fields__'):
            return {k: getattr(obj, k) for k in obj.__dataclass_fields__}
        return {}


# 预定义的配置模板

def get_conservative_config() -> RiskManagementConfig:
    """保守配置 - 优先安全"""
    config = RiskManagementConfig(Environment.PRODUCTION)
    config.kelly.max_allocation = 0.05
    config.kelly.leverage_limit = 1.5
    config.stop_loss.single_trade_stop_loss = 0.015
    config.stop_loss.daily_loss_limit = 0.02
    config.position.max_leverage = 2.0
    config.order.max_slippage_percent = 0.05
    config.risk.margin_ratio_warning = 3.0
    config.risk.margin_ratio_critical = 2.0
    return config


def get_balanced_config() -> RiskManagementConfig:
    """均衡配置 - 风险收益平衡"""
    config = RiskManagementConfig(Environment.PRODUCTION)
    config.kelly.max_allocation = 0.15
    config.kelly.leverage_limit = 3.0
    config.stop_loss.single_trade_stop_loss = 0.02
    config.stop_loss.daily_loss_limit = 0.05
    config.position.max_leverage = 5.0
    config.order.max_slippage_percent = 0.10
    config.risk.margin_ratio_warning = 2.5
    config.risk.margin_ratio_critical = 1.5
    return config


def get_aggressive_config() -> RiskManagementConfig:
    """激进配置 - 优先收益"""
    config = RiskManagementConfig(Environment.PRODUCTION)
    config.kelly.max_allocation = 0.25
    config.kelly.leverage_limit = 5.0
    config.stop_loss.single_trade_stop_loss = 0.03
    config.stop_loss.daily_loss_limit = 0.10
    config.position.max_leverage = 10.0
    config.order.max_slippage_percent = 0.20
    config.risk.margin_ratio_warning = 2.0
    config.risk.margin_ratio_critical = 1.0
    return config


def get_development_config() -> RiskManagementConfig:
    """开发配置"""
    config = RiskManagementConfig(Environment.DEVELOPMENT)
    return config


# 默认配置实例
DEFAULT_CONFIG = get_balanced_config()


if __name__ == "__main__":
    # 测试配置
    config = RiskManagementConfig()
    
    print("Kelly配置:")
    print(f"  Max allocation: {config.kelly.max_allocation}")
    print(f"  Leverage limit: {config.kelly.leverage_limit}")
    
    print("\n止损配置:")
    print(f"  Single trade stop loss: {config.stop_loss.single_trade_stop_loss:.2%}")
    print(f"  Daily loss limit: {config.stop_loss.daily_loss_limit:.2%}")
    print(f"  Weekly loss limit: {config.stop_loss.weekly_loss_limit:.2%}")
    
    print("\n头寸配置:")
    print(f"  Max leverage: {config.position.max_leverage}")
    print(f"  Max collateral per position: {config.position.max_collateral_per_position:.2%}")
    
    print("\n风险阈值:")
    print(f"  Margin ratio warning: {config.risk.margin_ratio_warning}")
    print(f"  Margin ratio critical: {config.risk.margin_ratio_critical}")
    print(f"  Leverage warning: {config.risk.leverage_warning}x")
    print(f"  Leverage critical: {config.risk.leverage_critical}x")
