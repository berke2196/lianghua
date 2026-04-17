"""
实时风险监控系统
- 实时P&L、账户权益、杠杆率、保证金
- 清算距离、头寸热度、系统延迟、网络状态
- 告警、异常检测、故障预警
"""

import numpy as np
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """告警等级"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class Alert:
    """告警"""
    level: AlertLevel
    title: str
    description: str
    timestamp: datetime = field(default_factory=datetime.now)
    is_resolved: bool = False
    
    def __str__(self):
        return f"[{self.level.value}] {self.title}: {self.description}"


@dataclass
class RiskMetrics:
    """风险指标"""
    timestamp: datetime
    account_equity: float  # 账户权益
    used_margin: float  # 使用保证金
    available_margin: float  # 可用保证金
    margin_ratio: float  # 保证金率
    total_pnl: float  # 总盈亏
    total_pnl_percent: float  # 总盈亏百分比
    portfolio_leverage: float  # 投资组合杠杆
    portfolio_heat: float  # 投资组合热度
    clearance_distance_percent: float  # 清算距离
    liquidation_risk: float  # 清液风险
    system_latency_ms: float  # 系统延迟
    network_latency_ms: float  # 网络延迟
    portfolio_correlation: float  # 投资组合相关性


class RiskMonitor:
    """风险监控"""
    
    def __init__(self):
        self.metrics_history: List[RiskMetrics] = []
        self.alerts: List[Alert] = []
        self.thresholds = {
            'margin_ratio_warning': 2.0,
            'margin_ratio_critical': 1.5,
            'leverage_warning': 5.0,
            'leverage_critical': 8.0,
            'pnl_loss_warning': -0.05,
            'pnl_loss_critical': -0.10,
            'liquidation_distance_warning': 0.1,
            'liquidation_distance_critical': 0.05,
            'system_latency_warning': 100,
            'system_latency_critical': 500,
            'network_latency_warning': 200,
            'network_latency_critical': 1000,
        }
        
    def record_metrics(self, metrics: RiskMetrics):
        """记录指标"""
        self.metrics_history.append(metrics)
        
        # 只保留最近1000条
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]
    
    def check_margin_ratio(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查保证金率"""
        if metrics.margin_ratio < self.thresholds['margin_ratio_critical']:
            alert = Alert(
                level=AlertLevel.EMERGENCY,
                title="CRITICAL Margin Ratio",
                description=f"Margin ratio {metrics.margin_ratio:.2f} is critical"
            )
            return alert
        elif metrics.margin_ratio < self.thresholds['margin_ratio_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Low Margin Ratio",
                description=f"Margin ratio {metrics.margin_ratio:.2f} is low"
            )
            return alert
            
        return None
    
    def check_leverage(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查杠杆"""
        if metrics.portfolio_leverage > self.thresholds['leverage_critical']:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="High Leverage",
                description=f"Portfolio leverage {metrics.portfolio_leverage:.2f}x exceeds critical threshold"
            )
            return alert
        elif metrics.portfolio_leverage > self.thresholds['leverage_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Elevated Leverage",
                description=f"Portfolio leverage {metrics.portfolio_leverage:.2f}x is elevated"
            )
            return alert
            
        return None
    
    def check_pnl(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查盈亏"""
        if metrics.total_pnl_percent < self.thresholds['pnl_loss_critical']:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="Severe Loss",
                description=f"Total loss {metrics.total_pnl_percent:.2%} exceeds critical threshold"
            )
            return alert
        elif metrics.total_pnl_percent < self.thresholds['pnl_loss_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Significant Loss",
                description=f"Total loss {metrics.total_pnl_percent:.2%}"
            )
            return alert
            
        return None
    
    def check_liquidation_distance(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查清算距离"""
        if metrics.clearance_distance_percent < self.thresholds['liquidation_distance_critical']:
            alert = Alert(
                level=AlertLevel.EMERGENCY,
                title="Liquidation Risk CRITICAL",
                description=f"Distance to liquidation {metrics.clearance_distance_percent:.2%} is critical"
            )
            return alert
        elif metrics.clearance_distance_percent < self.thresholds['liquidation_distance_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Liquidation Risk Warning",
                description=f"Distance to liquidation {metrics.clearance_distance_percent:.2%} is low"
            )
            return alert
            
        return None
    
    def check_system_latency(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查系统延迟"""
        if metrics.system_latency_ms > self.thresholds['system_latency_critical']:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="System Latency Critical",
                description=f"System latency {metrics.system_latency_ms:.1f}ms exceeds threshold"
            )
            return alert
        elif metrics.system_latency_ms > self.thresholds['system_latency_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="System Latency High",
                description=f"System latency {metrics.system_latency_ms:.1f}ms is elevated"
            )
            return alert
            
        return None
    
    def check_network_latency(self, metrics: RiskMetrics) -> Optional[Alert]:
        """检查网络延迟"""
        if metrics.network_latency_ms > self.thresholds['network_latency_critical']:
            alert = Alert(
                level=AlertLevel.CRITICAL,
                title="Network Latency Critical",
                description=f"Network latency {metrics.network_latency_ms:.1f}ms exceeds threshold"
            )
            return alert
        elif metrics.network_latency_ms > self.thresholds['network_latency_warning']:
            alert = Alert(
                level=AlertLevel.WARNING,
                title="Network Latency High",
                description=f"Network latency {metrics.network_latency_ms:.1f}ms is elevated"
            )
            return alert
            
        return None
    
    def detect_anomalies(self, metrics: RiskMetrics) -> List[Alert]:
        """异常检测"""
        anomalies = []
        
        # 检查所有指标
        for check_func in [
            self.check_margin_ratio,
            self.check_leverage,
            self.check_pnl,
            self.check_liquidation_distance,
            self.check_system_latency,
            self.check_network_latency
        ]:
            alert = check_func(metrics)
            if alert:
                anomalies.append(alert)
                
        return anomalies
    
    def update_alerts(self, new_alerts: List[Alert]):
        """更新告警"""
        for alert in new_alerts:
            # 检查是否已存在类似告警
            existing = next(
                (a for a in self.alerts 
                 if a.title == alert.title and not a.is_resolved),
                None
            )
            
            if existing:
                # 更新时间戳
                existing.timestamp = alert.timestamp
            else:
                self.alerts.append(alert)
                logger.warning(str(alert))
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [a for a in self.alerts if not a.is_resolved]
    
    def resolve_alert(self, alert_title: str):
        """解决告警"""
        for alert in self.alerts:
            if alert.title == alert_title:
                alert.is_resolved = True
                logger.info(f"Alert resolved: {alert_title}")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """获取风险汇总"""
        if not self.metrics_history:
            return {}
            
        latest = self.metrics_history[-1]
        
        summary = {
            'timestamp': latest.timestamp,
            'account_equity': latest.account_equity,
            'total_pnl': latest.total_pnl,
            'total_pnl_percent': latest.total_pnl_percent,
            'margin_ratio': latest.margin_ratio,
            'portfolio_leverage': latest.portfolio_leverage,
            'portfolio_heat': latest.portfolio_heat,
            'liquidation_risk': latest.liquidation_risk,
            'clearance_distance_percent': latest.clearance_distance_percent,
            'system_latency_ms': latest.system_latency_ms,
            'network_latency_ms': latest.network_latency_ms,
            'active_alerts': len(self.get_active_alerts()),
        }
        
        return summary
    
    def predict_liquidation(self) -> Optional[datetime]:
        """
        预测清算时间
        基于当前盈亏速率
        """
        if len(self.metrics_history) < 10:
            return None
            
        # 获取最近10条记录
        recent = self.metrics_history[-10:]
        
        # 计算盈亏变化趋势
        pnl_changes = [
            recent[i].total_pnl_percent - recent[i-1].total_pnl_percent
            for i in range(1, len(recent))
        ]
        
        avg_change = np.mean(pnl_changes)
        
        if avg_change >= 0:
            # 盈利或持平，不会清液
            return None
            
        # 获取当前离清液的距离
        latest = recent[-1]
        distance = latest.clearance_distance_percent
        
        if distance <= 0:
            # 已清液
            return datetime.now()
            
        # 计算需要多少时间会清液
        # 假设每5秒记录一次数据
        changes_per_minute = (60 / 5) * np.mean(pnl_changes)
        
        if changes_per_minute >= 0:
            return None
            
        minutes_to_liquidation = -distance / changes_per_minute
        
        predicted_time = datetime.now() + timedelta(minutes=minutes_to_liquidation)
        
        logger.warning(f"Liquidation predicted in {minutes_to_liquidation:.1f} minutes")
        return predicted_time
    
    def forecast_metrics(self, 
                        minutes_ahead: int = 60,
                        lookback_minutes: int = 30) -> Optional[RiskMetrics]:
        """
        预测未来风险指标
        """
        if len(self.metrics_history) < 20:
            return None
            
        # 获取回溯期的数据
        seconds_back = lookback_minutes * 60
        now = datetime.now()
        recent = [
            m for m in self.metrics_history
            if (now - m.timestamp).total_seconds() <= seconds_back
        ]
        
        if len(recent) < 2:
            return None
            
        # 计算趋势
        latest = recent[-1]
        oldest = recent[0]
        
        pnl_change = latest.total_pnl_percent - oldest.total_pnl_percent
        pnl_change_rate = pnl_change / lookback_minutes
        
        # 预测
        predicted_pnl = latest.total_pnl_percent + pnl_change_rate * minutes_ahead
        
        # 简单线性预测其他指标
        equity_change = latest.account_equity * predicted_pnl
        
        return RiskMetrics(
            timestamp=now + timedelta(minutes=minutes_ahead),
            account_equity=latest.account_equity + equity_change,
            used_margin=latest.used_margin,
            available_margin=latest.available_margin - equity_change,
            margin_ratio=latest.margin_ratio,
            total_pnl=latest.total_pnl + (latest.account_equity * pnl_change_rate * minutes_ahead),
            total_pnl_percent=predicted_pnl,
            portfolio_leverage=latest.portfolio_leverage,
            portfolio_heat=latest.portfolio_heat,
            clearance_distance_percent=max(0, latest.clearance_distance_percent - abs(pnl_change_rate * minutes_ahead * 100)),
            liquidation_risk=min(1, latest.liquidation_risk + abs(pnl_change_rate * minutes_ahead)),
            system_latency_ms=latest.system_latency_ms,
            network_latency_ms=latest.network_latency_ms,
            portfolio_correlation=latest.portfolio_correlation
        )


class PerformanceMonitor:
    """性能监控"""
    
    def __init__(self):
        self.operation_times: Dict[str, List[float]] = {}
        self.operation_counts: Dict[str, int] = {}
        
    def record_operation(self, operation_name: str, duration_ms: float):
        """记录操作"""
        if operation_name not in self.operation_times:
            self.operation_times[operation_name] = []
            self.operation_counts[operation_name] = 0
            
        self.operation_times[operation_name].append(duration_ms)
        self.operation_counts[operation_name] += 1
        
        # 只保留最近1000条
        if len(self.operation_times[operation_name]) > 1000:
            self.operation_times[operation_name] = self.operation_times[operation_name][-1000:]
    
    def get_operation_stats(self, operation_name: str = None) -> Dict:
        """获取操作统计"""
        if operation_name:
            if operation_name not in self.operation_times:
                return {}
                
            times = self.operation_times[operation_name]
            return {
                'count': len(times),
                'avg_ms': np.mean(times),
                'min_ms': np.min(times),
                'max_ms': np.max(times),
                'p95_ms': np.percentile(times, 95),
                'p99_ms': np.percentile(times, 99),
            }
        else:
            stats = {}
            for op in self.operation_times:
                stats[op] = self.get_operation_stats(op)
            return stats
