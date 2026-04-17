"""
Prometheus metrics for trading platform monitoring.
Provides custom metrics for P&L, risk, latency, and system performance.
"""

from prometheus_client import Counter, Gauge, Histogram, Summary
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class MetricsConfig:
    """Configuration for metrics collection."""
    environment: str = "production"
    service_name: str = "trading-engine"
    namespace: str = "trading"


class TradingMetrics:
    """Central metrics registry for trading operations."""
    
    def __init__(self, config: Optional[MetricsConfig] = None):
        self.config = config or MetricsConfig()
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all prometheus metrics."""
        
        # Trade execution metrics
        self.trades_total = Counter(
            'trades_total',
            'Total number of trades executed',
            ['strategy', 'exchange', 'side'],
            registry=None
        )
        
        self.trade_volume = Counter(
            'trade_volume_usdt',
            'Total trading volume in USDT',
            ['strategy', 'exchange'],
            registry=None
        )
        
        self.trade_latency = Histogram(
            'trade_latency_seconds',
            'Trade execution latency in seconds',
            ['strategy', 'exchange'],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
            registry=None
        )
        
        # P&L metrics
        self.pnl_current = Gauge(
            'pnl_current_usdt',
            'Current P&L in USDT',
            ['strategy', 'exchange'],
            registry=None
        )
        
        self.pnl_daily = Gauge(
            'pnl_daily_usdt',
            'Daily P&L in USDT',
            ['strategy', 'exchange'],
            registry=None
        )
        
        self.pnl_monthly = Gauge(
            'pnl_monthly_usdt',
            'Monthly P&L in USDT',
            ['strategy', 'exchange'],
            registry=None
        )
        
        self.win_rate = Gauge(
            'win_rate_percent',
            'Win rate percentage',
            ['strategy', 'exchange'],
            registry=None
        )
        
        # Risk metrics
        self.position_size = Gauge(
            'position_size_usdt',
            'Current position size in USDT',
            ['strategy', 'symbol'],
            registry=None
        )
        
        self.portfolio_exposure = Gauge(
            'portfolio_exposure_percent',
            'Total portfolio exposure percentage',
            ['strategy'],
            registry=None
        )
        
        self.drawdown = Gauge(
            'drawdown_percent',
            'Maximum drawdown percentage',
            ['strategy'],
            registry=None
        )
        
        self.var_95 = Gauge(
            'var_95_usdt',
            'Value at Risk 95% confidence in USDT',
            ['strategy'],
            registry=None
        )
        
        # System metrics
        self.order_queue_size = Gauge(
            'order_queue_size',
            'Number of pending orders',
            ['strategy', 'exchange'],
            registry=None
        )
        
        self.websocket_connections = Gauge(
            'websocket_connections',
            'Active WebSocket connections',
            ['exchange'],
            registry=None
        )
        
        self.api_errors = Counter(
            'api_errors_total',
            'Total API errors',
            ['exchange', 'error_type'],
            registry=None
        )
        
        self.api_requests = Counter(
            'api_requests_total',
            'Total API requests',
            ['exchange', 'method'],
            registry=None
        )
        
        self.api_latency = Histogram(
            'api_latency_seconds',
            'API request latency in seconds',
            ['exchange', 'method'],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
            registry=None
        )
        
        # Data processing metrics
        self.candle_processing_time = Histogram(
            'candle_processing_time_ms',
            'Time to process candle in milliseconds',
            ['symbol'],
            buckets=(1, 5, 10, 50, 100, 500),
            registry=None
        )
        
        self.signals_generated = Counter(
            'signals_generated_total',
            'Total trading signals generated',
            ['strategy', 'signal_type'],
            registry=None
        )
        
        # Resource metrics
        self.memory_usage = Gauge(
            'memory_usage_mb',
            'Memory usage in MB',
            ['component'],
            registry=None
        )
        
        self.cpu_usage = Gauge(
            'cpu_usage_percent',
            'CPU usage percentage',
            ['component'],
            registry=None
        )
        
        self.database_connections = Gauge(
            'database_connections',
            'Active database connections',
            ['database', 'pool'],
            registry=None
        )
        
        self.cache_hits = Counter(
            'cache_hits_total',
            'Total cache hits',
            ['cache_name'],
            registry=None
        )
        
        self.cache_misses = Counter(
            'cache_misses_total',
            'Total cache misses',
            ['cache_name'],
            registry=None
        )


class MetricsCollector:
    """Collects and manages metrics for the trading system."""
    
    def __init__(self, metrics: Optional[TradingMetrics] = None):
        self.metrics = metrics or TradingMetrics()
    
    def record_trade(self, strategy: str, exchange: str, side: str, 
                    volume_usdt: float, latency: float):
        """Record a trade execution."""
        self.metrics.trades_total.labels(
            strategy=strategy, exchange=exchange, side=side
        ).inc()
        self.metrics.trade_volume.labels(
            strategy=strategy, exchange=exchange
        ).inc(volume_usdt)
        self.metrics.trade_latency.labels(
            strategy=strategy, exchange=exchange
        ).observe(latency)
    
    def update_pnl(self, strategy: str, exchange: str, 
                   current: float, daily: float, monthly: float):
        """Update P&L metrics."""
        self.metrics.pnl_current.labels(
            strategy=strategy, exchange=exchange
        ).set(current)
        self.metrics.pnl_daily.labels(
            strategy=strategy, exchange=exchange
        ).set(daily)
        self.metrics.pnl_monthly.labels(
            strategy=strategy, exchange=exchange
        ).set(monthly)
    
    def update_risk_metrics(self, strategy: str, exposure: float, 
                           drawdown: float, var_95: float):
        """Update risk metrics."""
        self.metrics.portfolio_exposure.labels(
            strategy=strategy
        ).set(exposure)
        self.metrics.drawdown.labels(
            strategy=strategy
        ).set(drawdown)
        self.metrics.var_95.labels(
            strategy=strategy
        ).set(var_95)
    
    def record_api_request(self, exchange: str, method: str, latency: float, 
                          error: Optional[str] = None):
        """Record API request."""
        self.metrics.api_requests.labels(
            exchange=exchange, method=method
        ).inc()
        self.metrics.api_latency.labels(
            exchange=exchange, method=method
        ).observe(latency)
        if error:
            self.metrics.api_errors.labels(
                exchange=exchange, error_type=error
            ).inc()
    
    def record_signal(self, strategy: str, signal_type: str):
        """Record signal generation."""
        self.metrics.signals_generated.labels(
            strategy=strategy, signal_type=signal_type
        ).inc()
    
    def update_position(self, strategy: str, symbol: str, size: float):
        """Update position metrics."""
        self.metrics.position_size.labels(
            strategy=strategy, symbol=symbol
        ).set(size)


def track_performance(metrics_collector: MetricsCollector):
    """Decorator to track function performance."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                latency = time.time() - start_time
                logger.debug(f"{func.__name__} took {latency:.3f}s")
            return func(*args, **kwargs)
        return wrapper
    return decorator


class MetricsExporter:
    """Exports metrics to Prometheus."""
    
    def __init__(self, metrics: TradingMetrics):
        self.metrics = metrics
    
    def export_metrics(self) -> Dict[str, Any]:
        """Export all metrics."""
        return {
            'trades_total': self.metrics.trades_total,
            'trade_volume': self.metrics.trade_volume,
            'trade_latency': self.metrics.trade_latency,
            'pnl_current': self.metrics.pnl_current,
            'pnl_daily': self.metrics.pnl_daily,
            'pnl_monthly': self.metrics.pnl_monthly,
            'position_size': self.metrics.position_size,
            'portfolio_exposure': self.metrics.portfolio_exposure,
            'drawdown': self.metrics.drawdown,
            'var_95': self.metrics.var_95,
            'api_requests': self.metrics.api_requests,
            'api_errors': self.metrics.api_errors,
            'api_latency': self.metrics.api_latency,
        }


if __name__ == '__main__':
    config = MetricsConfig(
        environment='production',
        service_name='trading-engine'
    )
    metrics = TradingMetrics(config)
    collector = MetricsCollector(metrics)
    
    collector.record_trade('trend_follow', 'hyperliquid', 'buy', 1000, 0.05)
    collector.update_pnl('trend_follow', 'hyperliquid', 500, 200, 1000)
    collector.update_risk_metrics('trend_follow', 25.5, 5.2, 150)
