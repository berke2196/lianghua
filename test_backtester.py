"""
回测框架测试套件
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from backtester_engine import BacktestEngine
from backtester_core import Backtester, BacktestConfig
from backtester_optimizer import (
    ParameterOptimizer,
    ParameterSpace,
    OptimizationMethod,
    GridSearchOptimizer,
    RandomSearchOptimizer,
    GeneticOptimizer,
    PSOOptimizer
)
from backtester_walkforward import WalkForwardValidator, SplitMethod
from backtester_analytics import PerformanceAnalytics
from backtester_visualizer import BacktestVisualizer


@pytest.fixture
def sample_data():
    """生成测试数据"""
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', periods=500, freq='D')
    
    price = 100
    prices = [price]
    for _ in range(499):
        price = price * (1 + np.random.normal(0.0005, 0.02))
        prices.append(price)
    
    prices = np.array(prices)
    
    data = pd.DataFrame({
        'open': prices * (1 + np.random.normal(0, 0.005, 500)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.01, 500))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.01, 500))),
        'close': prices,
        'volume': np.random.lognormal(10, 2, 500),
    }, index=dates)
    
    data['high'] = data[['high', 'close']].max(axis=1)
    data['low'] = data[['low', 'close']].min(axis=1)
    
    return data


class TestBacktestEngine:
    """测试回测引擎"""
    
    def test_initialization(self):
        """测试初始化"""
        engine = BacktestEngine(initial_capital=100000)
        assert engine.initial_capital == 100000
        assert engine.current_capital == 100000
        assert len(engine.trades) == 0
    
    def test_vectorized_processing(self, sample_data):
        """测试向量化处理"""
        engine = BacktestEngine()
        signals = np.random.choice([-1, 0, 1], size=len(sample_data))
        
        result = engine.vectorized_signal_processing(sample_data, signals)
        
        assert 'equity' in result
        assert 'trades' in result
        assert len(result['equity']) == len(sample_data)
    
    def test_calculate_returns(self, sample_data):
        """测试收益计算"""
        engine = BacktestEngine()
        returns = engine.calculate_returns(sample_data)
        
        assert len(returns) == len(sample_data)
        assert returns[0] == 0  # 第一个收益为0
    
    def test_calculate_drawdown(self, sample_data):
        """测试回撤计算"""
        engine = BacktestEngine()
        equity = np.array([100, 110, 105, 95, 100, 120])
        
        max_dd, dd_curve = engine.calculate_drawdown(equity)
        
        assert max_dd < 0  # 回撤为负
        assert len(dd_curve) == len(equity)
    
    def test_calculate_sharpe_ratio(self, sample_data):
        """测试夏普比率"""
        engine = BacktestEngine()
        returns = engine.calculate_returns(sample_data)
        
        sharpe = engine.calculate_sharpe_ratio(returns)
        
        assert isinstance(sharpe, (int, float))
    
    def test_reset(self):
        """测试重置"""
        engine = BacktestEngine(initial_capital=100000)
        engine.current_capital = 50000
        engine.bars_processed = 100
        
        engine.reset()
        
        assert engine.current_capital == engine.initial_capital
        assert engine.bars_processed == 0


class TestBacktester:
    """测试完整回测器"""
    
    def test_initialization(self):
        """测试初始化"""
        config = BacktestConfig(initial_capital=100000)
        backtester = Backtester(config)
        
        assert backtester.config.initial_capital == 100000
    
    def test_calculate_features(self, sample_data):
        """测试特征计算"""
        backtester = Backtester()
        data_with_features = backtester.calculate_features(sample_data)
        
        # 检查特征列
        assert 'returns' in data_with_features.columns
        assert 'log_returns' in data_with_features.columns
        assert 'sma_20' in data_with_features.columns
        assert 'rsi_14' in data_with_features.columns
    
    def test_generate_signals(self, sample_data):
        """测试信号生成"""
        backtester = Backtester()
        data_with_features = backtester.calculate_features(sample_data)
        
        signals = backtester.generate_signals(
            data_with_features,
            lambda d: (d['sma_5'] > d['sma_20']).astype(int)
        )
        
        assert len(signals) == len(sample_data)
        assert np.all(np.isin(signals, [0, 1]))
    
    def test_execute_backtest(self, sample_data):
        """测试回测执行"""
        config = BacktestConfig(initial_capital=100000)
        backtester = Backtester(config)
        
        data_with_features = backtester.calculate_features(sample_data)
        
        # 简单的SMA策略
        sma_5 = data_with_features['close'].rolling(5).mean()
        sma_20 = data_with_features['close'].rolling(20).mean()
        signals = np.where(sma_5 > sma_20, 1, -1)
        signals[:20] = 0
        
        result = backtester.execute_backtest(
            symbol='TEST',
            data=data_with_features,
            signals=signals
        )
        
        assert result.final_equity > 0
        assert result.num_trades >= 0
        assert len(result.equity_curve) == len(sample_data)


class TestOptimizer:
    """测试参数优化器"""
    
    def test_grid_search_initialization(self):
        """测试网格搜索初始化"""
        def obj_func(params):
            return params['x'] ** 2
        
        spaces = [ParameterSpace('x', 0, 10)]
        optimizer = GridSearchOptimizer(obj_func, spaces, max_iterations=10)
        
        assert optimizer.objective_func is not None
        assert len(optimizer.parameter_spaces) == 1
    
    def test_grid_search_optimize(self):
        """测试网格搜索"""
        def obj_func(params):
            return -(params['x'] - 5) ** 2  # 最大值在x=5
        
        spaces = [ParameterSpace('x', 0, 10, step=1)]
        optimizer = GridSearchOptimizer(obj_func, spaces, max_iterations=10)
        
        result = optimizer.optimize()
        
        assert result.best_params is not None
        assert 'x' in result.best_params
    
    def test_random_search(self):
        """测试随机搜索"""
        def obj_func(params):
            return -(params['x'] - 5) ** 2
        
        spaces = [ParameterSpace('x', 0, 10)]
        optimizer = RandomSearchOptimizer(obj_func, spaces, max_iterations=10)
        
        result = optimizer.optimize()
        
        assert result.best_params is not None
        assert len(result.optimization_history) > 0
    
    def test_genetic_optimization(self):
        """测试遗传算法"""
        def obj_func(params):
            return -(params['x'] - 5) ** 2
        
        spaces = [ParameterSpace('x', 0, 10)]
        optimizer = GeneticOptimizer(
            obj_func, spaces, max_iterations=10,
            population_size=10
        )
        
        result = optimizer.optimize()
        
        assert result.best_params is not None
    
    def test_pso_optimization(self):
        """测试粒子群算法"""
        def obj_func(params):
            return -(params['x'] - 5) ** 2
        
        spaces = [ParameterSpace('x', 0, 10)]
        optimizer = PSOOptimizer(
            obj_func, spaces, max_iterations=10,
            num_particles=10
        )
        
        result = optimizer.optimize()
        
        assert result.best_params is not None


class TestWalkForward:
    """测试走测验证"""
    
    def test_generate_rolling_splits(self, sample_data):
        """测试生成滚动分割"""
        validator = WalkForwardValidator(
            sample_data,
            train_size=100,
            test_size=50,
            method=SplitMethod.ROLLING
        )
        
        splits = validator.generate_splits()
        
        assert len(splits) > 0
        for split in splits:
            assert len(split.train_indices) == 100
            assert len(split.test_indices) == 50
    
    def test_generate_anchored_splits(self, sample_data):
        """测试生成锚定分割"""
        validator = WalkForwardValidator(
            sample_data,
            train_size=100,
            test_size=50,
            method=SplitMethod.ANCHORED
        )
        
        splits = validator.generate_splits()
        
        assert len(splits) > 0
        # 第一个split的训练集应该从0开始
        assert splits[0].train_indices[0] == 0


class TestPerformanceAnalytics:
    """测试性能分析"""
    
    def test_calculate_metrics(self, sample_data):
        """测试指标计算"""
        equity = np.linspace(100000, 110000, 100)
        trades = [
            {'pnl': 1000, 'pnl_pct': 0.01, 'hold_bars': 10},
            {'pnl': -500, 'pnl_pct': -0.005, 'hold_bars': 5},
            {'pnl': 2000, 'pnl_pct': 0.02, 'hold_bars': 15},
        ]
        
        analytics = PerformanceAnalytics()
        metrics = analytics.calculate_metrics(equity, trades, sample_data.index[:100])
        
        assert metrics.total_return > 0
        assert metrics.sharpe_ratio >= 0
        assert metrics.win_rate >= 0
        assert metrics.profit_factor >= 0
    
    def test_calculate_var(self):
        """测试VaR计算"""
        returns = np.random.normal(0.001, 0.02, 1000)
        analytics = PerformanceAnalytics()
        
        var_95 = analytics.calculate_var(returns, confidence=0.95)
        
        assert var_95 < 0  # VaR应该为负


class TestVisualizer:
    """测试可视化"""
    
    def test_initialization(self):
        """测试初始化"""
        visualizer = BacktestVisualizer(figsize=(12, 8))
        
        assert visualizer.figsize == (12, 8)
    
    def test_plot_equity_curve(self, sample_data):
        """测试绘制权益曲线"""
        equity = np.linspace(100000, 110000, len(sample_data))
        visualizer = BacktestVisualizer()
        
        ax = visualizer.plot_equity_curve(equity, sample_data.index)
        
        assert ax is not None


# 集成测试
class TestIntegration:
    """集成测试"""
    
    def test_complete_workflow(self, sample_data):
        """测试完整工作流"""
        # 1. 回测
        config = BacktestConfig()
        backtester = Backtester(config)
        data_with_features = backtester.calculate_features(sample_data)
        
        sma_5 = data_with_features['close'].rolling(5).mean()
        sma_20 = data_with_features['close'].rolling(20).mean()
        signals = np.where(sma_5 > sma_20, 1, -1)
        signals[:20] = 0
        
        result = backtester.execute_backtest('TEST', data_with_features, signals)
        
        # 2. 性能分析
        analytics = PerformanceAnalytics()
        metrics = analytics.calculate_metrics(
            result.equity_curve,
            result.trades,
            sample_data.index
        )
        
        assert metrics.total_return >= 0
        
        # 3. 可视化
        visualizer = BacktestVisualizer()
        fig = visualizer.plot_equity_curve(result.equity_curve, sample_data.index)
        
        assert fig is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
