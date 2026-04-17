# 回测框架快速参考指南

## 1. 最小化示例 (30秒上手)

```python
import pandas as pd
from backtester_core import Backtester, BacktestConfig

# 加载数据
data = pd.read_csv('data.csv', index_col='date')

# 创建回测器
backtester = Backtester()

# 计算特征
data = backtester.calculate_features(data)

# 定义策略
def strategy(data):
    sma5 = data['close'].rolling(5).mean()
    sma20 = data['close'].rolling(20).mean()
    return (sma5 > sma20).astype(int)

# 生成信号
signals = backtester.generate_signals(data, strategy)

# 执行回测
result = backtester.execute_backtest('BTC', data, signals)

# 打印结果
print(f"Return: {result.total_return:.2%}")
print(f"Sharpe: {result.sharpe_ratio:.4f}")
```

## 2. 常用参数

```python
# 回测配置
config = BacktestConfig(
    initial_capital=100000,      # 初始资金
    commission=0.001,             # 手续费 (0.1%)
    slippage=0.001,              # 滑点 (0.1%)
    position_size=0.95,          # 头寸大小 (95%资金)
    max_positions=10,            # 最大头寸数
    stop_loss_pct=0.02,          # 止损 (2%)
    take_profit_pct=0.05,        # 止盈 (5%)
)
```

## 3. 优化方法对比

| 方法 | 速度 | 准确度 | 参数多 |
|------|------|--------|--------|
| GridSearch | 慢 | 高 | 否 |
| Random | 快 | 中 | 是 |
| Genetic | 中 | 高 | 是 |
| PSO | 快 | 高 | 是 |
| SimulatedAnnealing | 中 | 中 | 是 |

## 4. 常用特征

```python
# 移动平均
data['sma_20'] = data['close'].rolling(20).mean()
data['ema_20'] = data['close'].ewm(span=20).mean()

# 动量指标
data['rsi_14'] = calculate_rsi(data['close'], 14)
data['macd'] = data['close'].ewm(12).mean() - data['close'].ewm(26).mean()

# 波动率
data['atr_14'] = calculate_atr(data, 14)

# 成交量
data['obv'] = calculate_obv(data)
data['cmf'] = calculate_cmf(data, 20)
```

## 5. 性能指标含义

| 指标 | 含义 | 好的范围 |
|------|------|----------|
| Sharpe | 风险调整收益 | > 1.0 |
| Sortino | 只考虑下行风险 | > 1.0 |
| Calmar | 收益/回撤比 | > 1.0 |
| MaxDD | 最大回撤 | < 20% |
| Win Rate | 胜率 | > 50% |
| Profit Factor | 赢利/亏损 | > 1.5 |

## 6. 优化代码片段

### 网格搜索
```python
from backtester_optimizer import ParameterOptimizer, OptimizationMethod

result = optimizer.optimize(method=OptimizationMethod.GRID_SEARCH)
```

### 遗传算法
```python
result = optimizer.optimize(
    method=OptimizationMethod.GENETIC,
    population_size=50,
    mutation_rate=0.1,
    crossover_rate=0.8
)
```

### PSO
```python
result = optimizer.optimize(
    method=OptimizationMethod.PSO,
    num_particles=50,
    w=0.7,
    c1=1.5,
    c2=1.5
)
```

## 7. 走测验证

```python
from backtester_walkforward import WalkForwardValidator, SplitMethod

# 创建验证器
validator = WalkForwardValidator(
    data=data,
    train_size=252,      # 1年
    test_size=63,        # 3个月
    method=SplitMethod.ROLLING
)

# 执行验证
result = validator.run_walk_forward(
    strategy_func=strategy_func,
    param_optimizer=param_optimizer
)

# 检查稳定性
stability = validator.stability_check(result)
print(f"Is Robust: {stability['is_robust']}")
```

## 8. 可视化

```python
from backtester_visualizer import BacktestVisualizer

viz = BacktestVisualizer()

# 权益曲线
viz.plot_equity_curve(equity, dates)

# K线图
viz.plot_ohlc(data, signals)

# 回撤
viz.plot_drawdown(equity, dates)

# 多图表
viz.plot_multiple_metrics(equity, returns, trades, dates)

# 保存
viz.save_figure(fig, 'chart.png')
```

## 9. 性能分析

```python
from backtester_analytics import PerformanceAnalytics

analytics = PerformanceAnalytics(risk_free_rate=0.02)

# 计算指标
metrics = analytics.calculate_metrics(equity, trades, dates)

# 打印报告
analytics.print_report(equity, trades, dates, 'BTC/USDT')

# 额外指标
var = analytics.calculate_var(returns, 0.95)
cvar = analytics.calculate_cvar(returns, 0.95)
```

## 10. 性能优化

```python
# 启用加速
engine = BacktestEngine(
    use_polars=True,              # Polars向量化
    use_multiprocessing=True,     # 多进程
    max_workers=4                 # 4个核
)

# 内存优化
data = engine.optimize_memory(data)

# 并行处理
results = engine.parallel_backtest(data_list, signals_list)
```

## 11. 常见陷阱

❌ **不要：**
- 在整个数据集上优化参数（会过拟合）
- 忽视slippage和commission
- 不检查样本外性能
- 交易太频繁

✓ **应该：**
- 使用走测验证
- 设置合理的commission (0.1%-0.5%)
- 检查IS-OOS相关性
- 优先考虑简单策略

## 12. 调试技巧

```python
# 启用日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 检查数据
print(data.describe())
print(data.head())

# 检查信号
print(f"Buy signals: {(signals == 1).sum()}")
print(f"Sell signals: {(signals == -1).sum()}")

# 检查结果
print(result.equity_curve[:10])
print(result.trades[:5])
```

## 13. 常用配置预设

### 保守策略
```python
BacktestConfig(
    commission=0.005,
    slippage=0.01,
    position_size=0.5,
    stop_loss_pct=0.03
)
```

### 激进策略
```python
BacktestConfig(
    commission=0.001,
    slippage=0.001,
    position_size=0.95,
    stop_loss_pct=0.01
)
```

### 日内交易
```python
BacktestConfig(
    commission=0.001,
    slippage=0.002,
    position_size=0.8
)
```

## 14. 典型工作流

1. **数据准备** (5分钟)
   - 加载历史数据
   - 检查数据质量

2. **策略开发** (1小时)
   - 定义特征
   - 编写信号函数
   - 快速回测验证

3. **参数优化** (30分钟)
   - 选择优化方法
   - 定义参数空间
   - 执行优化

4. **走测验证** (30分钟)
   - 运行走测
   - 检查稳定性
   - 评估鲁棒性

5. **最终评估** (15分钟)
   - 完整回测
   - 生成报告
   - 可视化结果

## 15. 快速诊断

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Sharpe = 0 | 无交易或全赔 | 调整信号阈值 |
| 回撤很大 | 风险管理不足 | 增加止损 |
| 过拟合 | IS >> OOS | 简化策略/更多数据 |
| 太慢 | 数据量大 | 启用加速/并行 |

---

**快速问题排查：**

```bash
# 安装依赖
pip install -r requirements_backtester.txt

# 运行测试
pytest test_backtester.py -v

# 运行示例
python example_complete_backtest.py
```

**更多帮助：** 见 `BACKTESTER_README.md`
