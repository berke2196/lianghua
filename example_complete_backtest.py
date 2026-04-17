"""
完整回测框架示例
演示如何使用所有组件完成端到端的回测
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging

# 导入回测框架组件
from backtester_engine import BacktestEngine
from backtester_core import Backtester, BacktestConfig
from backtester_optimizer import ParameterOptimizer, ParameterSpace, OptimizationMethod
from backtester_walkforward import WalkForwardValidator, SplitMethod
from backtester_analytics import PerformanceAnalytics
from backtester_visualizer import BacktestVisualizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_sample_data(n_bars: int = 1000, seed: int = 42) -> pd.DataFrame:
    """生成示例数据"""
    np.random.seed(seed)
    
    dates = pd.date_range(start='2020-01-01', periods=n_bars, freq='D')
    
    # 生成价格
    price = 100
    prices = [price]
    for _ in range(n_bars - 1):
        returns = np.random.normal(0.0005, 0.02)
        price = price * (1 + returns)
        prices.append(price)
    
    prices = np.array(prices)
    
    data = pd.DataFrame({
        'date': dates,
        'open': prices * (1 + np.random.normal(0, 0.005, n_bars)),
        'high': prices * (1 + np.abs(np.random.normal(0, 0.01, n_bars))),
        'low': prices * (1 - np.abs(np.random.normal(0, 0.01, n_bars))),
        'close': prices,
        'volume': np.random.lognormal(10, 2, n_bars),
    })
    
    # 确保high >= close >= low
    data['high'] = data[['high', 'close']].max(axis=1)
    data['low'] = data[['low', 'close']].min(axis=1)
    
    data.set_index('date', inplace=True)
    return data


def example_signal_function(data: pd.DataFrame, params: dict = None, is_sample: bool = True) -> np.ndarray:
    """简单的信号生成函数"""
    if params is None:
        params = {'sma_fast': 5, 'sma_slow': 20}
    
    sma_fast = data['close'].rolling(params['sma_fast']).mean()
    sma_slow = data['close'].rolling(params['sma_slow']).mean()
    
    signals = np.zeros(len(data))
    signals[sma_fast > sma_slow] = 1
    signals[sma_fast < sma_slow] = -1
    
    return signals, {'sharpe_ratio': np.random.uniform(0, 2)}


def example_basic_backtest():
    """示例1：基础回测"""
    print("\n" + "="*60)
    print("示例1: 基础回测")
    print("="*60)
    
    # 生成数据
    data = generate_sample_data(1000)
    print(f"✓ 生成 {len(data)} 根K线")
    
    # 初始化回测器
    config = BacktestConfig(
        initial_capital=100000,
        commission=0.001,
        slippage=0.001,
        position_size=0.95
    )
    backtester = Backtester(config)
    print("✓ 初始化回测器")
    
    # 计算特征
    data_with_features = backtester.calculate_features(data)
    print(f"✓ 计算特征，共 {len(data_with_features.columns)} 列")
    
    # 生成信号
    signals = backtester.generate_signals(
        data_with_features,
        lambda d: example_signal_function(d)[0]
    )
    print(f"✓ 生成信号：{np.sum(signals > 0)} 买 + {np.sum(signals < 0)} 卖")
    
    # 执行回测
    result = backtester.execute_backtest(
        symbol='BTC/USDT',
        data=data_with_features,
        signals=signals,
        start_date=data.index[0],
        end_date=data.index[-1]
    )
    print(f"✓ 回测完成")
    
    # 输出结果
    print(f"\n回测结果：")
    print(f"  初始资金: ${config.initial_capital:,.2f}")
    print(f"  最终资金: ${result.final_equity:,.2f}")
    print(f"  总收益:   {result.total_return:.2%}")
    print(f"  年化收益: {result.annual_return:.2%}")
    print(f"  夏普比率: {result.sharpe_ratio:.4f}")
    print(f"  最大回撤: {result.max_drawdown:.2%}")
    print(f"  交易数:   {result.num_trades}")
    print(f"  胜率:     {result.win_rate:.2%}")
    print(f"  收益因子: {result.profit_factor:.4f}")


def example_parameter_optimization():
    """示例2：参数优化"""
    print("\n" + "="*60)
    print("示例2: 参数优化")
    print("="*60)
    
    data = generate_sample_data(1000)
    config = BacktestConfig()
    backtester = Backtester(config)
    
    # 目标函数 - 最大化夏普比率
    def objective_func(params):
        try:
            data_with_features = backtester.calculate_features(data)
            
            # 使用参数生成信号
            sma_fast = data_with_features['close'].rolling(int(params['sma_fast'])).mean()
            sma_slow = data_with_features['close'].rolling(int(params['sma_slow'])).mean()
            
            signals = np.zeros(len(data_with_features))
            signals[sma_fast > sma_slow] = 1
            signals[sma_fast < sma_slow] = -1
            
            result = backtester.execute_backtest(
                symbol='BTC/USDT',
                data=data_with_features,
                signals=signals
            )
            
            return result.sharpe_ratio
        except:
            return -1
    
    # 定义参数空间
    parameter_spaces = [
        ParameterSpace(name='sma_fast', min_value=3, max_value=10, step=1),
        ParameterSpace(name='sma_slow', min_value=15, max_value=50, step=5),
    ]
    
    # 执行优化
    optimizer = ParameterOptimizer(
        objective_func=objective_func,
        parameter_spaces=parameter_spaces,
        max_iterations=20,
        maximize=True
    )
    
    print("执行网格搜索...")
    result = optimizer.optimize(method=OptimizationMethod.GRID_SEARCH)
    
    print(f"✓ 优化完成")
    print(f"  最优参数: {result.best_params}")
    print(f"  最优得分: {result.best_score:.4f}")
    print(f"  评估次数: {result.total_evaluations}")


def example_walk_forward_validation():
    """示例3：走测验证"""
    print("\n" + "="*60)
    print("示例3: 走测验证")
    print("="*60)
    
    data = generate_sample_data(1000)
    
    # 初始化走测验证器
    validator = WalkForwardValidator(
        data=data,
        train_size=200,
        test_size=50,
        step_size=50,
        method=SplitMethod.ROLLING
    )
    print(f"✓ 初始化走测验证器")
    
    # 生成分割
    splits = validator.generate_splits()
    print(f"✓ 生成 {len(splits)} 个走测分割")
    
    # 定义策略函数
    def strategy_func(data, params, is_sample=True):
        signals = example_signal_function(data, params, is_sample)[0]
        metrics = {
            'sharpe_ratio': np.random.uniform(0.5, 2.0),
            'returns': np.random.uniform(0.01, 0.05)
        }
        return signals, metrics
    
    # 定义参数优化函数
    def param_optimizer(train_data):
        best_params = {'sma_fast': 5, 'sma_slow': 20}
        metrics = {'sharpe_ratio': np.random.uniform(1, 1.5)}
        return best_params, metrics
    
    # 执行走测验证
    wf_result = validator.run_walk_forward(
        strategy_func=strategy_func,
        param_optimizer=param_optimizer
    )
    
    print(f"\n走测结果：")
    print(f"  样本内平均夏普: {wf_result.is_avg_sharpe:.4f}")
    print(f"  样本外平均夏普: {wf_result.oos_avg_sharpe:.4f}")
    print(f"  IS-OOS相关性: {wf_result.is_oos_correlation:.4f}")
    print(f"  性能下降: {wf_result.degradation:.2%}")
    print(f"  参数稳定性: {wf_result.stability:.4f}")
    
    # 稳定性检查
    stability_check = validator.stability_check(wf_result)
    print(f"\n稳定性检查：")
    print(f"  是否鲁棒: {stability_check['is_robust']}")
    print(f"  综合评分: {stability_check['overall_score']:.4f}")


def example_performance_analysis():
    """示例4：性能分析"""
    print("\n" + "="*60)
    print("示例4: 性能分析")
    print("="*60)
    
    data = generate_sample_data(1000)
    
    # 运行回测
    config = BacktestConfig()
    backtester = Backtester(config)
    data_with_features = backtester.calculate_features(data)
    signals = backtester.generate_signals(data_with_features, lambda d: example_signal_function(d)[0])
    result = backtester.execute_backtest('BTC/USDT', data_with_features, signals)
    
    # 性能分析
    analytics = PerformanceAnalytics(risk_free_rate=0.02)
    metrics = analytics.calculate_metrics(
        equity_curve=result.equity_curve,
        trades=result.trades,
        dates=data.index
    )
    
    # 打印报告
    analytics.print_report(
        equity_curve=result.equity_curve,
        trades=result.trades,
        dates=data.index,
        symbol='BTC/USDT'
    )


def example_visualization():
    """示例5：可视化"""
    print("\n" + "="*60)
    print("示例5: 可视化")
    print("="*60)
    
    data = generate_sample_data(500)
    
    # 运行回测
    config = BacktestConfig()
    backtester = Backtester(config)
    data_with_features = backtester.calculate_features(data)
    signals = backtester.generate_signals(data_with_features, lambda d: example_signal_function(d)[0])
    result = backtester.execute_backtest('BTC/USDT', data_with_features, signals)
    
    # 可视化
    visualizer = BacktestVisualizer()
    
    # 绘制权益曲线
    fig = visualizer.plot_equity_curve(
        equity_curve=result.equity_curve,
        dates=data.index,
        title='BTC/USDT - Equity Curve'
    )
    visualizer.save_figure(fig, 'equity_curve.png')
    print("✓ 保存权益曲线: equity_curve.png")
    
    # 绘制K线图
    fig = visualizer.plot_ohlc(
        data=data_with_features,
        signals=signals,
        title='BTC/USDT - OHLC Chart with Signals'
    )
    visualizer.save_figure(fig, 'ohlc_chart.png')
    print("✓ 保存K线图: ohlc_chart.png")
    
    # 绘制回撤
    fig = visualizer.plot_underwater(
        equity_curve=result.equity_curve,
        dates=data.index,
        title='Drawdown'
    )
    visualizer.save_figure(fig, 'drawdown.png')
    print("✓ 保存回撤图: drawdown.png")
    
    # 绘制多个指标
    returns = np.diff(result.equity_curve) / result.equity_curve[:-1]
    fig = visualizer.plot_multiple_metrics(
        equity_curve=result.equity_curve,
        returns=returns,
        trades=result.trades,
        dates=data.index
    )
    visualizer.save_figure(fig, 'metrics_dashboard.png')
    print("✓ 保存指标仪表板: metrics_dashboard.png")


def example_high_frequency_backtest():
    """示例6：高速回测 - 1000根K线 < 1秒"""
    print("\n" + "="*60)
    print("示例6: 高速回测 (VectorBT加速)")
    print("="*60)
    
    import time
    
    # 生成大量数据
    data = generate_sample_data(10000)
    print(f"✓ 生成 {len(data)} 根K线")
    
    # 高速回测引擎
    engine = BacktestEngine(
        initial_capital=100000,
        use_polars=True,
        use_multiprocessing=True
    )
    
    # 生成信号
    sma_fast = data['close'].rolling(5).mean().values
    sma_slow = data['close'].rolling(20).mean().values
    signals = np.zeros(len(data))
    signals[sma_fast > sma_slow] = 1
    signals[sma_fast < sma_slow] = -1
    
    # 计时
    start_time = time.time()
    result = engine.vectorized_signal_processing(data, signals)
    elapsed = time.time() - start_time
    
    print(f"✓ 回测完成")
    print(f"  耗时: {elapsed:.4f} 秒")
    print(f"  速度: {len(data)/elapsed:.0f} 根K线/秒")
    print(f"  加速倍数: {len(data) / (elapsed * 1000):.1f}x (相对1秒回测1000根)")
    print(f"  交易数: {result['num_trades']}")
    print(f"  最终权益: ${result['final_equity']:,.2f}")


def main():
    """运行所有示例"""
    print("\n" + "█"*60)
    print("█ 完整回测框架演示".center(58) + " █")
    print("█ Complete Backtesting Framework Demo".center(60) + "█")
    print("█"*60)
    
    try:
        example_basic_backtest()
        example_parameter_optimization()
        example_walk_forward_validation()
        example_performance_analysis()
        example_visualization()
        example_high_frequency_backtest()
        
        print("\n" + "="*60)
        print("✓ 所有示例执行完成!")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == '__main__':
    main()
