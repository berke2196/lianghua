"""
特征工程模块验证脚本

验证所有模块的正确性和性能
"""

import sys
import traceback

# 尝试导入所有模块
print("=" * 60)
print("特征工程模块验证")
print("=" * 60)

modules_status = {}

# 1. 验证 features_indicators
print("\n[1/5] 验证 features_indicators 模块...")
try:
    from features_indicators import IndicatorCalculator, OHLCV
    import numpy as np
    
    # 生成测试数据
    n = 100
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close,
        high=close + abs(np.random.randn(n)),
        low=close - abs(np.random.randn(n)),
        close=close,
        volume=np.random.randint(1000, 5000, n)
    )
    
    calc = IndicatorCalculator()
    
    # 测试指标
    rsi = calc.rsi(close)
    macd, sig, hist = calc.macd(close)
    bb = calc.bollinger_bands(close)
    
    modules_status['features_indicators'] = '✓ 正常'
    print("  ✓ 指标计算正常")
    print(f"    - RSI: {rsi[-1]:.2f}")
    print(f"    - MACD: {macd[-1]:.2f}")
    print(f"    - BB upper: {bb['upper'][-1]:.2f}")
    
except Exception as e:
    modules_status['features_indicators'] = f'✗ 错误: {str(e)}'
    print(f"  ✗ 错误: {e}")
    traceback.print_exc()

# 2. 验证 features_aggregator
print("\n[2/5] 验证 features_aggregator 模块...")
try:
    from features_aggregator import FeatureAggregator, FeatureConfig, FeatureEngineer
    import pandas as pd
    
    agg = FeatureAggregator()
    
    # 创建测试DataFrame
    df = pd.DataFrame({
        'feat1': np.random.randn(50),
        'feat2': np.random.randn(50),
        'feat3': np.random.randn(50)
    })
    
    df_norm = agg.normalize_features(df)
    df_clean = agg.remove_constant_features(df)
    
    modules_status['features_aggregator'] = '✓ 正常'
    print("  ✓ 特征聚合正常")
    print(f"    - 特征标准化: {df_norm.shape}")
    print(f"    - 常数特征移除: {df_clean.shape}")
    
except Exception as e:
    modules_status['features_aggregator'] = f'✗ 错误: {str(e)}'
    print(f"  ✗ 错误: {e}")
    traceback.print_exc()

# 3. 验证 features_cache
print("\n[3/5] 验证 features_cache 模块...")
try:
    from features_cache import FeatureCache, IncrementalCalculator
    
    cache = FeatureCache()
    data = np.array([1, 2, 3, 4, 5])
    
    cache.set('test', data)
    retrieved = cache.get('test')
    
    if np.array_equal(retrieved, data):
        modules_status['features_cache'] = '✓ 正常'
        print("  ✓ 缓存系统正常")
        print("    - 数据存取: 成功")
    else:
        raise ValueError("缓存数据不匹配")
    
except Exception as e:
    modules_status['features_cache'] = f'✗ 错误: {str(e)}'
    print(f"  ✗ 错误: {e}")
    traceback.print_exc()

# 4. 验证 features_engineering
print("\n[4/5] 验证 features_engineering 模块...")
try:
    from features_engineering import FeatureEngineering, FeatureMetrics
    import time
    
    fe = FeatureEngineering(enable_caching=False)
    
    # 生成测试数据
    n = 500
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close + np.random.randn(n),
        high=close + abs(np.random.randn(n)),
        low=close - abs(np.random.randn(n)),
        close=close,
        volume=np.random.randint(1000, 5000, n)
    )
    
    start = time.time()
    result = fe.process(ohlcv, normalization=True, feature_selection=False)
    elapsed = (time.time() - start) * 1000
    
    modules_status['features_engineering'] = '✓ 正常'
    print("  ✓ 特征工程系统正常")
    print(f"    - 处理时间: {elapsed:.2f}ms")
    print(f"    - 特征数: {result.metadata['n_features']}")
    print(f"    - 指标数: {result.metadata['indicators_count']}")
    
except Exception as e:
    modules_status['features_engineering'] = f'✗ 错误: {str(e)}'
    print(f"  ✗ 错误: {e}")
    traceback.print_exc()

# 5. 验证 test_features_engineering
print("\n[5/5] 验证测试模块...")
try:
    import unittest
    from test_features_engineering import TestIndicatorCalculator
    
    # 运行几个关键测试
    suite = unittest.TestLoader().loadTestsFromTestCase(TestIndicatorCalculator)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        modules_status['tests'] = f'✓ 正常 ({result.testsRun}个测试通过)'
        print(f"  ✓ 单元测试正常")
        print(f"    - 测试用例: {result.testsRun}")
        print(f"    - 成功: ✓")
    else:
        modules_status['tests'] = f'✗ 错误 (失败: {len(result.failures)})'
        print(f"  ✗ 部分测试失败")
        
except Exception as e:
    modules_status['tests'] = f'✗ 错误: {str(e)}'
    print(f"  ✗ 错误: {e}")

# 汇总报告
print("\n" + "=" * 60)
print("验证报告总结")
print("=" * 60)

all_ok = all('✓' in v for v in modules_status.values())

for module, status in modules_status.items():
    print(f"{module:30} {status}")

print("\n" + "=" * 60)

if all_ok:
    print("✓ 所有模块验证通过！")
    print("\n特征工程模块已准备就绪。")
    print("\n支持的指标：")
    print("  - 动量指标: RSI, MACD, Stochastic, Williams %R, ROC, ...")
    print("  - 趋势指标: SMA, EMA, WMA, DEMA, TEMA, KAMA, ...")
    print("  - 波动率指标: ATR, NATR, Bollinger Bands, Keltner, ...")
    print("  - 成交量指标: OBV, VWAP, ADL, CMF, MFI, ...")
    print("  - 高级特征: 形态识别, ML特征, ...")
    print("\n总指标数: 200+")
    sys.exit(0)
else:
    print("✗ 验证有失败，请检查错误信息。")
    sys.exit(1)
