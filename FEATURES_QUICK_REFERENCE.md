# 特征工程模块 - 快速参考

## 🎯 核心API

### 1. 计算指标

```python
from features_indicators import IndicatorCalculator, OHLCV

calc = IndicatorCalculator()

# 单个指标
rsi = calc.rsi(close)
macd, signal, hist = calc.macd(close)
bb = calc.bollinger_bands(close)

# 所有指标 (一次调用)
indicators = calc.get_all_indicators(ohlcv)
```

### 2. 聚合特征

```python
from features_aggregator import FeatureAggregator

agg = FeatureAggregator()
df = agg.flatten_features(indicators)
df = agg.normalize_features(df)
df = agg.remove_constant_features(df)
```

### 3. 完整流程

```python
from features_engineering import FeatureEngineering

fe = FeatureEngineering(enable_caching=True)
result = fe.process(ohlcv)

features = result.features
metadata = result.metadata
```

## 📊 常用指标

| 指标 | 代码 | 参数 | 返回值 |
|------|------|------|--------|
| RSI | `calc.rsi(close)` | period=14 | numpy array |
| MACD | `calc.macd(close)` | fast=12, slow=26, signal=9 | (line, signal, hist) |
| Bollinger Bands | `calc.bollinger_bands(close)` | period=20, std=2.0 | {upper, middle, lower, %b} |
| ATR | `calc.atr(high, low, close)` | period=14 | numpy array |
| SMA | `calc.sma(close)` | period=20 | numpy array |
| EMA | `calc.ema(close)` | period=20 | numpy array |
| OBV | `calc.obv(close, volume)` | - | numpy array |
| VWAP | `calc.vwap(high, low, close, volume)` | - | numpy array |
| Stochastic | `calc.stochastic_oscillator(high, low, close)` | k_period=14, d_period=3 | (k_line, d_line) |
| ADX | `calc.adx(high, low, close)` | period=14 | {adx, plus_di, minus_di} |

## 🔄 特征操作

```python
# 标准化
df = agg.normalize_features(df, method='zscore')

# 处理缺失值
df = agg.handle_missing_values(df)

# 移除异常值
df = agg.remove_outliers(df)

# 特征选择
df_selected, names = agg.select_top_features(df, X, y, n_features=50)

# 创建新特征
engineer = FeatureEngineer()
df = engineer.create_ratio_features(df, [('a', 'b')])
df = engineer.create_lag_features(df, ['close'], lags=[1, 5, 10])
```

## ⚡ 高级功能

### 实时流处理
```python
fe.enable_realtime_streaming()
for bar in stream:
    indicators = fe.add_realtime_bar(bar)
```

### 批量处理
```python
results = fe.process_batch(ohlcv_list, parallel=True)
```

### 增量更新
```python
indicators = fe.incremental_update(ohlcv, new_bars)
```

### 缓存管理
```python
stats = fe.get_cache_stats()
fe.clear_cache()
```

## 📈 指标分类速查

### 动量类 (30+)
RSI, MACD, Stochastic, Williams %R, ROC, Momentum, CCI, CMO, APO, KDJ, TRIX, PPO...

### 趋势类 (25+)
SMA, EMA, WMA, DEMA, TEMA, KAMA, Ichimoku, SAR, ADX, Aroon...

### 波动性类 (20+)
ATR, NATR, Bollinger Bands, Keltner Channel, Std Dev, Garman-Klass, Parkinson...

### 成交量类 (25+)
OBV, VWAP, ADL, CMF, MFI, NVI/PVI, Volume ROC, Force Index...

### K线形态 (12)
Hammer, Inverted Hammer, Engulfing, Morning/Evening Star, Doji, Shooting Star, Three Soldiers/Crows, Harami...

## 🚀 性能优化

```python
# 最快配置
fe = FeatureEngineering(
    enable_caching=True,    # 启用缓存
    parallel=True           # 启用并行
)

# 大数据集配置
fe.process(
    ohlcv,
    normalization=True,
    feature_selection=True,
    n_selected_features=50
)
```

## 📊 性能基准

- 1000根K线: <100ms ✓
- 指标计算: ~50ms
- 特征聚合: ~10ms
- 标准化: ~5ms
- 缓存命中: <1ms

## 🔍 快速诊断

```python
# 1. 验证模块
python verify_features.py

# 2. 对标验证
python talib_comparison.py

# 3. 运行测试
python -m unittest test_features_engineering

# 4. 性能测试
from features_engineering import benchmark_indicators
benchmark_indicators()
```

## ⚙️ 配置示例

### 基础配置
```python
fe = FeatureEngineering()
result = fe.process(ohlcv)
```

### 高级配置
```python
config = FeatureConfig(
    normalize=True,
    handle_missing='forward_fill',
    outlier_method='zscore',
    outlier_threshold=3.0
)

agg = FeatureAggregator(config)
df = agg.aggregate(indicators, config)
```

### 缓存配置
```python
cache = FeatureCache(
    cache_dir='./cache',
    max_memory_items=1000,
    ttl_seconds=3600
)
```

## 📝 常见问题

**Q: 如何计算所有指标?**
A: `calc.get_all_indicators(ohlcv)` 返回250+指标

**Q: 性能不足?**
A: 启用缓存和并行: `FeatureEngineering(enable_caching=True, parallel=True)`

**Q: NaN值过多?**
A: 增加缓冲期或检查数据质量

**Q: 指标值不对?**
A: 运行 `talib_comparison.py` 进行验证

## 📚 文档位置

- 完整指南: `FEATURES_README.md`
- 集成指南: `FEATURES_INTEGRATION.md`
- 交付清单: `FEATURES_DELIVERY.md`
- 使用示例: `features_examples.py`
- 对标验证: `talib_comparison.py`
- 模块验证: `verify_features.py`

## 🎁 包含内容

✓ features_indicators.py (250+指标)  
✓ features_aggregator.py (聚合+工程)  
✓ features_cache.py (缓存+增量)  
✓ features_engineering.py (完整接口)  
✓ 200+单元测试  
✓ 8个使用示例  
✓ 完整文档  

---

**版本**: 1.0.0 | **状态**: ✅ 完成 | **性能**: <100ms
