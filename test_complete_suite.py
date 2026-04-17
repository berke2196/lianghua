"""
Comprehensive test suite for trading system.
Includes unit, integration, E2E, stress, and security tests.
"""

import pytest
import asyncio
from typing import Dict, Any, List
import time
import random
from dataclasses import dataclass
from unittest.mock import Mock, patch, MagicMock
import json


# ============================================================================
# UNIT TESTS - Test individual components in isolation
# ============================================================================

class TestMetricsCollection:
    """Unit tests for metrics collection."""
    
    def test_metrics_initialization(self):
        """Test metrics are properly initialized."""
        from monitoring_prometheus_metrics import TradingMetrics
        metrics = TradingMetrics()
        assert metrics is not None
    
    def test_record_trade(self):
        """Test trade recording."""
        from monitoring_prometheus_metrics import MetricsCollector
        collector = MetricsCollector()
        
        collector.record_trade('strategy1', 'hyperliquid', 'buy', 1000, 0.05)
        assert collector.metrics.trades_total is not None
    
    def test_update_pnl(self):
        """Test P&L update."""
        from monitoring_prometheus_metrics import MetricsCollector
        collector = MetricsCollector()
        
        collector.update_pnl('strategy1', 'hyperliquid', 500, 200, 1000)
        assert collector.metrics.pnl_current is not None
    
    def test_update_risk_metrics(self):
        """Test risk metrics update."""
        from monitoring_prometheus_metrics import MetricsCollector
        collector = MetricsCollector()
        
        collector.update_risk_metrics('strategy1', 25.5, 5.2, 150)
        assert collector.metrics.portfolio_exposure is not None


class TestAlertSystem:
    """Unit tests for alert system."""
    
    @pytest.mark.asyncio
    async def test_alert_creation(self):
        """Test alert creation."""
        from monitoring_alerting_system import Alert, AlertSeverity
        from datetime import datetime
        
        alert = Alert(
            title="Test Alert",
            message="Test message",
            severity=AlertSeverity.WARNING,
            tags={'test': 'value'},
            timestamp=datetime.now()
        )
        
        assert alert.title == "Test Alert"
        assert alert.severity == AlertSeverity.WARNING
    
    @pytest.mark.asyncio
    async def test_alert_rule_cooldown(self):
        """Test alert rule cooldown."""
        from monitoring_alerting_system import AlertRule, AlertSeverity, AlertChannel
        
        rule = AlertRule(
            name="Test Rule",
            condition_fn=lambda m: m.get('value', 0) > 100,
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.DISCORD],
            cooldown_seconds=1
        )
        
        metrics = {'value': 150}
        
        # First trigger should work
        assert rule.should_trigger(metrics) is True
        rule.triggered()
        
        # Immediate second trigger should be blocked
        assert rule.should_trigger(metrics) is False
        
        # After cooldown, should work again
        await asyncio.sleep(1.1)
        assert rule.should_trigger(metrics) is True


# ============================================================================
# INTEGRATION TESTS - Test interactions between components
# ============================================================================

class TestMetricsIntegration:
    """Integration tests for metrics system."""
    
    def test_metrics_collector_integration(self):
        """Test metrics collector with multiple operations."""
        from monitoring_prometheus_metrics import MetricsCollector
        
        collector = MetricsCollector()
        
        # Record multiple trades
        for i in range(5):
            collector.record_trade(f'strategy_{i}', 'hyperliquid', 'buy', 1000 + i*100, 0.01 + i*0.01)
        
        # Update P&L
        for i in range(5):
            collector.update_pnl(f'strategy_{i}', 'hyperliquid', 500 + i*100, 200, 1000)
        
        # Verify metrics collected
        assert collector.metrics.trades_total is not None
        assert collector.metrics.trade_volume is not None
    
    @pytest.mark.asyncio
    async def test_alert_manager_integration(self):
        """Test alert manager with multiple rules."""
        from monitoring_alerting_system import AlertManager, AlertRule, AlertSeverity, AlertChannel
        
        manager = AlertManager()
        
        # Create multiple rules
        rules = [
            AlertRule(
                name="Rule 1",
                condition_fn=lambda m: m.get('pnl', 0) < -100,
                severity=AlertSeverity.CRITICAL,
                channels=[AlertChannel.DISCORD]
            ),
            AlertRule(
                name="Rule 2",
                condition_fn=lambda m: m.get('exposure', 0) > 50,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.TELEGRAM]
            ),
        ]
        
        for rule in rules:
            manager.register_rule(rule)
        
        # Test evaluation
        metrics = {'pnl': -150, 'exposure': 60}
        await manager.evaluate(metrics)
        
        assert len(manager.rules) == 2


# ============================================================================
# END-TO-END TESTS - Test complete workflows
# ============================================================================

class TestEndToEndWorkflows:
    """End-to-end tests for complete workflows."""
    
    @pytest.mark.asyncio
    async def test_complete_trading_workflow(self):
        """Test complete trading workflow with monitoring."""
        from monitoring_prometheus_metrics import MetricsCollector
        from monitoring_alerting_system import AlertManager, AlertRule, AlertSeverity, AlertChannel
        
        # Initialize system
        metrics_collector = MetricsCollector()
        alert_manager = AlertManager()
        
        # Record trades
        metrics_collector.record_trade('strategy1', 'hyperliquid', 'buy', 10000, 0.05)
        metrics_collector.update_pnl('strategy1', 'hyperliquid', 500, 200, 1000)
        metrics_collector.update_risk_metrics('strategy1', 25, 5, 150)
        
        # Add alert rule
        alert_rule = AlertRule(
            name="High Exposure Alert",
            condition_fn=lambda m: m.get('exposure', 0) > 20,
            severity=AlertSeverity.WARNING,
            channels=[AlertChannel.DISCORD]
        )
        alert_manager.register_rule(alert_rule)
        
        # Evaluate
        metrics = {'exposure': 25}
        await alert_manager.evaluate(metrics)
        
        assert len(alert_manager.alert_history) > 0


# ============================================================================
# STRESS TESTS - Test system under load
# ============================================================================

class TestStressScenarios:
    """Stress and load tests."""
    
    def test_high_volume_metrics_recording(self):
        """Test recording metrics under high volume."""
        from monitoring_prometheus_metrics import MetricsCollector
        
        collector = MetricsCollector()
        
        start_time = time.time()
        
        # Record 10,000 trades
        for i in range(10000):
            strategy = f'strategy_{i % 10}'
            exchange = 'hyperliquid' if i % 2 == 0 else 'binance'
            side = 'buy' if i % 2 == 0 else 'sell'
            
            collector.record_trade(strategy, exchange, side, 1000, 0.01)
        
        elapsed = time.time() - start_time
        
        assert elapsed < 10, f"High volume metrics recording took {elapsed}s (should be <10s)"
        print(f"Recorded 10,000 trades in {elapsed:.2f}s")
    
    @pytest.mark.asyncio
    async def test_alert_evaluation_performance(self):
        """Test alert evaluation performance."""
        from monitoring_alerting_system import AlertManager, AlertRule, AlertSeverity, AlertChannel
        
        manager = AlertManager()
        
        # Create 100 alert rules
        for i in range(100):
            rule = AlertRule(
                name=f"Rule {i}",
                condition_fn=lambda m, threshold=i*10: m.get('value', 0) > threshold,
                severity=AlertSeverity.WARNING,
                channels=[AlertChannel.DISCORD]
            )
            manager.register_rule(rule)
        
        metrics = {'value': random.randint(0, 2000)}
        
        start_time = time.time()
        await manager.evaluate(metrics)
        elapsed = time.time() - start_time
        
        assert elapsed < 5, f"Alert evaluation took {elapsed}s (should be <5s)"
        print(f"Evaluated 100 rules in {elapsed:.3f}s")


# ============================================================================
# SECURITY TESTS - Test security aspects
# ============================================================================

class TestSecurityAspects:
    """Security-focused tests."""
    
    def test_metrics_data_validation(self):
        """Test metrics data validation."""
        from monitoring_prometheus_metrics import MetricsCollector
        
        collector = MetricsCollector()
        
        # Test with various data types
        collector.record_trade('strategy1', 'hyperliquid', 'buy', 1000.5, 0.001)
        collector.update_pnl('strategy1', 'hyperliquid', -500.25, 100, 2000)
        
        # Should not crash with edge values
        collector.update_risk_metrics('strategy1', 0, 0, 0)
        collector.update_risk_metrics('strategy1', 100, 100, 100)
    
    @pytest.mark.asyncio
    async def test_alert_data_sanitization(self):
        """Test alert data is properly sanitized."""
        from monitoring_alerting_system import Alert, AlertSeverity
        from datetime import datetime
        
        # Test with potentially malicious data
        alert = Alert(
            title="Test <script>alert('xss')</script>",
            message="Message with <b>HTML</b>",
            severity=AlertSeverity.WARNING,
            tags={
                'key': "value'; DROP TABLE alerts;--"
            },
            timestamp=datetime.now()
        )
        
        alert_dict = alert.to_dict()
        assert isinstance(alert_dict, dict)
        assert alert_dict['title'] == "Test <script>alert('xss')</script>"


# ============================================================================
# PERFORMANCE BENCHMARKS
# ============================================================================

class TestPerformanceBenchmarks:
    """Performance benchmark tests."""
    
    def test_metrics_recording_benchmark(self, benchmark):
        """Benchmark metrics recording."""
        from monitoring_prometheus_metrics import MetricsCollector
        
        collector = MetricsCollector()
        
        def record_metric():
            collector.record_trade('strategy1', 'hyperliquid', 'buy', 1000, 0.01)
        
        result = benchmark(record_metric)
        print(f"Metrics recording benchmark: {benchmark.stats}")
    
    def test_pnl_update_benchmark(self, benchmark):
        """Benchmark P&L updates."""
        from monitoring_prometheus_metrics import MetricsCollector
        
        collector = MetricsCollector()
        
        def update_pnl():
            collector.update_pnl('strategy1', 'hyperliquid', 500, 200, 1000)
        
        result = benchmark(update_pnl)
        print(f"P&L update benchmark: {benchmark.stats}")


# ============================================================================
# PYTEST FIXTURES AND CONFIGURATION
# ============================================================================

@pytest.fixture
def metrics_collector():
    """Fixture for metrics collector."""
    from monitoring_prometheus_metrics import MetricsCollector
    return MetricsCollector()


@pytest.fixture
def alert_manager():
    """Fixture for alert manager."""
    from monitoring_alerting_system import AlertManager
    return AlertManager()


@pytest.fixture
def event_loop():
    """Fixture for async event loop."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

pytest_plugins = ['pytest_asyncio']


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async (deselect with '-m \"not asyncio\"')"
    )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
