"""
特征工程模块 - 完整文档

## 概述

这是一个企业级的特征工程系统，包含200+技术指标和高级特征计算能力。

### 核心特性

1. **200+技术指标**
   - 动量指标 (30+)
   - 趋势指标 (25+)
   - 波动率指标 (20+)
   - 成交量指标 (25+)
   - 振荡器 (20+)
   - 相关性指标 (15+)
   - 链上指标 (20+)
   - 衍生品指标 (15+)
   - 高级ML特征 (30+)

2. **高性能计算**
   - 1000根K线 < 100ms
   - NumPy向量化
   - 并行处理
   - 增量计算

3. **灵活的特征工程**
   - 特征聚合
   - 标准化
   - 异常值处理
   - 特征选择
   - 特征降维

4. **缓存系统**
   - 内存缓存
   - 磁盘持久化
   - 增量更新
   - 实时流处理

5. **质量保证**
   - 完整的单元测试
   - TA-Lib对标
   - K线形态识别
   - 质量指标评估

## 文件组织

```
features/
├── features_indicators.py      # 指标计算引擎 (200+指标)
├── features_aggregator.py      # 特征聚合器
├── features_cache.py           # 缓存管理和增量计算
├── features_engineering.py     # 完整集成接口
├── test_features_engineering.py # 单元测试
├── features_examples.py        # 使用示例
└── FEATURES_README.md          # 本文档
```

## 快速开始

### 安装依赖

```bash
pip install numpy pandas scipy scikit-learn
```

### 基础用法

```python
import numpy as np
from features_engineering import FeatureEngineering
from features_indicators import OHLCV

# 准备数据
ohlcv = OHLCV(
    open=open_prices,
    high=high_prices,
    low=low_prices,
    close=close_prices,
    volume=volumes
)

# 初始化特征工程系统
fe = FeatureEngineering(enable_caching=True)

# 处理数据
result = fe.process(ohlcv)

# 访问特征
features_df = result.features
print(f"特征数: {result.metadata['n_features']}")
```

## 详细使用指南

### 1. 指标计算

#### 基础指标

```python
from features_indicators import IndicatorCalculator

calc = IndicatorCalculator()

# RSI
rsi = calc.rsi(close_prices, period=14)

# MACD
macd, signal, histogram = calc.macd(close_prices)

# 布林带
bb = calc.bollinger_bands(close_prices, period=20)
upper = bb['upper']
middle = bb['middle']
lower = bb['lower']
```

#### 高级指标

```python
# 一目均衡表
ichimoku = calc.ichimoku(high, low, close)
tenkan = ichimoku['tenkan_sen']
kijun = ichimoku['kijun_sen']

# ADX趋势
adx_result = calc.adx(high, low, close)
adx_value = adx_result['adx']
plus_di = adx_result['plus_di']
minus_di = adx_result['minus_di']

# 抛物线SAR
sar, trend = calc.psar(high, low, close)
```

#### 成交量指标

```python
# OBV
obv = calc.obv(close, volume)

# VWAP
vwap = calc.vwap(high, low, close, volume)

# MFI
mfi = calc.mfi(high, low, close, volume, period=14)

# CMF
cmf = calc.cmf(high, low, close, volume, period=20)
```

### 2. K线形态识别

```python
from features_indicators import IndicatorCalculator

calc = IndicatorCalculator()

# 识别所有形态
patterns = calc.identify_patterns(open, high, low, close)

# 检查特定形态
hammer = patterns['hammer']          # 锤子线
engulfing = patterns['bullish_engulfing']  # 看涨吞没
doji = patterns['doji']              # 十字星
```

支持的形态：
- hammer (锤子线)
- inverted_hammer (倒锤子线)
- bullish_engulfing (看涨吞没)
- bearish_engulfing (看跌吞没)
- morning_star (晨星)
- evening_star (黄昏星)
- doji (十字星)
- shooting_star (流星线)
- three_white_soldiers (上升三白兵)
- three_black_crows (下降三黑鸦)
- harami_bullish (看涨孕线)
- harami_bearish (看跌孕线)

### 3. 特征聚合和标准化

```python
from features_aggregator import FeatureAggregator, FeatureConfig

# 配置
config = FeatureConfig(
    normalize=True,           # 标准化
    handle_missing='forward_fill',  # 缺失值处理
    outlier_method='zscore',  # 异常值处理
    outlier_threshold=3.0     # 异常值阈值
)

# 聚合
agg = FeatureAggregator(config)
features_df = agg.aggregate(indicators)

# 各种处理方法
df_normalized = agg.normalize_features(df, method='zscore')
df_clean = agg.handle_missing_values(df)
df_clean = agg.remove_constant_features(df)
df_filtered, dropped = agg.remove_correlated_features(df, threshold=0.95)
```

### 4. 特征工程

```python
from features_aggregator import FeatureEngineer

engineer = FeatureEngineer()

# 创建比率特征
df_ratio = engineer.create_ratio_features(df, [('ma_fast', 'ma_slow')])

# 创建交互特征
df_inter = engineer.create_interaction_features(df, [('rsi', 'atr')])

# 创建多项式特征
df_poly = engineer.create_polynomial_features(df, ['rsi', 'atr'], degree=2)

# 创建滞后特征
df_lag = engineer.create_lag_features(df, ['close', 'volume'], lags=[1, 5, 10])

# 创建滚动特征
df_rolling = engineer.create_rolling_features(
    df, ['rsi', 'atr'], 
    window=20, 
    functions=['mean', 'std', 'min', 'max']
)
```

### 5. 特征选择

```python
# 基于方差
features_selected, names = agg.select_top_features(
    df, X, y, n_features=50, method='variance'
)

# 基于相关性
features_selected, names = agg.select_top_features(
    df, X, y, n_features=50, method='correlation'
)

# 基于互信息
features_selected, names = agg.select_top_features(
    df, X, y, n_features=50, method='mutual_info'
)
```

### 6. 特征降维

```python
from features_aggregator import FeatureReducer

# PCA降维
X_reduced, pca = FeatureReducer.pca_reduction(X, n_components=50)

# t-SNE降维
X_reduced, tsne = FeatureReducer.tsne_reduction(X, n_components=2)

# UMAP降维
X_reduced, umap = FeatureReducer.umap_reduction(X, n_components=2)
```

### 7. 缓存管理

```python
from features_cache import FeatureCache

# 创建缓存
cache = FeatureCache(cache_dir='./cache', max_memory_items=1000)

# 设置缓存
cache.set('key1', data, persist=True)

# 获取缓存
data = cache.get('key1')

# 统计信息
stats = cache.get_stats()
print(f"内存项数: {stats['memory_items']}")
print(f"命中率: {stats['memory_hit_rate']:.2%}")

# 清空缓存
cache.clear()
```

### 8. 增量计算

```python
from features_cache import IncrementalCalculator

calc = IncrementalCalculator()

# 增量计算RSI
rsi, avg_gain, avg_loss = calc.calculate_incremental_rsi(
    close, period=14, 
    prev_avg_gain=prev_gain, 
    prev_avg_loss=prev_loss
)

# 增量计算SMA
sma, sma_array = calc.calculate_incremental_sma(
    close, period=20, 
    prev_sma=previous_sma
)

# 批量增量更新
results = calc.batch_update(ohlcv, indicators_config)
```

### 9. 实时流处理

```python
fe = FeatureEngineering()
fe.enable_realtime_streaming(window_size=1000)

# 添加实时K线
for bar_data in streaming_data:
    indicators = fe.add_realtime_bar({
        'open': bar_data['o'],
        'high': bar_data['h'],
        'low': bar_data['l'],
        'close': bar_data['c'],
        'volume': bar_data['v']
    })
    
    print(f"RSI: {indicators['rsi']}")
    print(f"SMA20: {indicators['sma_20']}")
```

### 10. 特征质量评估

```python
from features_engineering import FeatureMetrics

# 稳定性评估
stability = FeatureMetrics.calculate_stability(df, window=20)

# 覆盖度评估
coverage = FeatureMetrics.calculate_coverage(df)

# 信息价值评估
iv_scores = FeatureMetrics.calculate_info_value(df, y)
```

## 性能基准

| 操作 | 时间 | 条件 |
|------|------|------|
| 1000根K线计算 | < 100ms | 所有指标 |
| 特征聚合 | ~10ms | 1000根K线 |
| 标准化 | ~5ms | 100+特征 |
| 特征选择 | ~50ms | 1000特征→50特征 |
| 缓存命中 | < 1ms | 内存缓存 |
| 增量计算 | < 1ms | 单根K线 |

## 支持的指标列表

### 动量指标 (30+)
- RSI, MACD, Stochastic, Williams %R
- ROC, Momentum, CCI, CMO
- APO, KDJ, TRIX, PPO
- 等等...

### 趋势指标 (25+)
- SMA, EMA, WMA, DEMA, TEMA
- KAMA, Ichimoku, Parabolic SAR
- ADX (DI+, DI-), Aroon
- 等等...

### 波动率指标 (20+)
- ATR, NATR, Bollinger Bands
- Keltner Channel, Std Dev
- Garman-Klass, Parkinson
- 等等...

### 成交量指标 (25+)
- OBV, VWAP, ADL, CMF
- MFI, NVI/PVI, Volume ROC
- Force Index, 等等...

### K线形态 (12+)
- Hammer, Inverted Hammer
- Bullish/Bearish Engulfing
- Morning/Evening Star
- Doji, Shooting Star
- Three White Soldiers/Black Crows
- Harami, 等等...

### 高级特征 (30+)
- 日内波动率
- 价格加速度
- 动量
- 成交量势能
- 对数收益率
- 等等...

## 故障排除

### 问题1: 计算速度慢

**解决方案:**
- 启用缓存: `enable_caching=True`
- 启用并行处理: `parallel=True`
- 减少指标数量或使用特征选择

### 问题2: 内存占用高

**解决方案:**
- 减少缓存大小: `max_memory_items=500`
- 使用磁盘缓存: `persist=True`
- 启用特征降维

### 问题3: NaN值过多

**解决方案:**
- 增加缓冲期长度
- 使用不同的缺失值处理方法
- 检查输入数据质量

### 问题4: 指标值不符合预期

**解决方案:**
- 验证输入数据格式
- 检查指标周期设置
- 对比TA-Lib结果

## API参考

### IndicatorCalculator

```python
class IndicatorCalculator:
    def rsi(close, period=14) -> np.ndarray
    def macd(close, fast=12, slow=26, signal=9) -> Tuple
    def bollinger_bands(close, period=20, num_std=2.0) -> Dict
    def stochastic_oscillator(high, low, close, k_period=14, d_period=3) -> Tuple
    def atr(high, low, close, period=14) -> np.ndarray
    def obv(close, volume) -> np.ndarray
    def vwap(high, low, close, volume) -> np.ndarray
    def ichimoku(high, low, close) -> Dict
    def psar(high, low, close, iaf=0.02, maxaf=0.2) -> Tuple
    def identify_patterns(open, high, low, close) -> Dict
    def calculate_advanced_features(open, high, low, close, volume) -> Dict
    def get_all_indicators(ohlcv) -> Dict
```

### FeatureEngineering

```python
class FeatureEngineering:
    def process(ohlcv, normalization=True, remove_outliers=True, 
                feature_selection=False, n_selected_features=50) -> FeatureResult
    def process_batch(ohlcv_list, **kwargs) -> List[FeatureResult]
    def incremental_update(ohlcv, new_bars) -> Dict
    def enable_realtime_streaming(window_size=1000) -> None
    def add_realtime_bar(bar) -> Dict
    def get_cache_stats() -> Dict
    def clear_cache() -> None
    def get_feature_importance(X, y, feature_names) -> pd.DataFrame
```

## 最佳实践

1. **数据质量**
   - 确保OHLCV数据完整和准确
   - 处理缺失值和异常值
   - 验证数据的时间序列完整性

2. **性能优化**
   - 使用缓存减少重复计算
   - 启用并行处理处理大数据集
   - 定期清理缓存

3. **特征质量**
   - 评估特征的稳定性和覆盖度
   - 移除高度相关的特征
   - 定期更新和审计特征

4. **生产部署**
   - 实施监控和告警
   - 版本管理特征配置
   - 建立回测框架

## 许可证

MIT License

## 支持

如有问题或建议，请提交Issue或Pull Request。

---

最后更新: 2024年
"""

print(__doc__)
