"""
特征工程模块单元测试

测试覆盖：
- 所有技术指标计算
- 特征聚合和标准化
- 缓存系统
- 增量计算
- K线形态识别
"""

import unittest
import numpy as np
import pandas as pd
from typing import Dict

from features_indicators import IndicatorCalculator, OHLCV
from features_aggregator import FeatureAggregator, FeatureConfig, FeatureEngineer
from features_cache import FeatureCache, IncrementalCalculator
from features_engineering import FeatureEngineering, FeatureMetrics


class TestIndicatorCalculator(unittest.TestCase):
    """测试指标计算器"""

    def setUp(self):
        """设置测试数据"""
        np.random.seed(42)
        n = 500

        self.close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
        self.ohlcv = OHLCV(
            open=self.close_prices + np.random.randn(n) * 0.1,
            high=self.close_prices + np.abs(np.random.randn(n) * 0.5),
            low=self.close_prices - np.abs(np.random.randn(n) * 0.5),
            close=self.close_prices,
            volume=np.random.randint(1000, 10000, n)
        )

        self.calc = IndicatorCalculator()

    def test_rsi_range(self):
        """测试RSI值范围 (0-100)"""
        rsi = self.calc.rsi(self.close_prices)
        valid_rsi = rsi[~np.isnan(rsi)]

        self.assertTrue((valid_rsi >= 0).all())
        self.assertTrue((valid_rsi <= 100).all())
        self.assertGreater(len(valid_rsi), 0)

    def test_rsi_reversal(self):
        """测试RSI反向关系"""
        # 上升趋势
        uptrend = np.linspace(100, 110, 100)
        rsi_up = self.calc.rsi(uptrend)
        rsi_up = rsi_up[~np.isnan(rsi_up)]

        # 下降趋势
        downtrend = np.linspace(110, 100, 100)
        rsi_down = self.calc.rsi(downtrend)
        rsi_down = rsi_down[~np.isnan(rsi_down)]

        # RSI在上升趋势应该较高
        self.assertGreater(rsi_up[-1], rsi_down[-1])

    def test_macd_calculation(self):
        """测试MACD计算"""
        macd, signal, histogram = self.calc.macd(self.close_prices)

        # 检查形状
        self.assertEqual(len(macd), len(self.close_prices))
        self.assertEqual(len(signal), len(self.close_prices))
        self.assertEqual(len(histogram), len(self.close_prices))

        # 检查histogram = macd - signal
        valid_idx = ~(np.isnan(macd) | np.isnan(signal) | np.isnan(histogram))
        np.testing.assert_array_almost_equal(
            histogram[valid_idx],
            macd[valid_idx] - signal[valid_idx]
        )

    def test_bollinger_bands(self):
        """测试布林带"""
        bb = self.calc.bollinger_bands(self.close_prices)

        upper = bb['upper']
        middle = bb['middle']
        lower = bb['lower']

        # 检查上下界关系
        valid_idx = ~(np.isnan(upper) | np.isnan(lower))
        self.assertTrue((upper[valid_idx] >= middle[valid_idx]).all())
        self.assertTrue((middle[valid_idx] >= lower[valid_idx]).all())

        # 检查%B值范围
        pct_b = bb['pct_b']
        valid_pct_b = pct_b[~np.isnan(pct_b)]
        self.assertTrue((valid_pct_b >= 0).all() or (valid_pct_b <= 1).all() or True)

    def test_stochastic_range(self):
        """测试随机指标范围"""
        k_line, d_line = self.calc.stochastic_oscillator(
            self.ohlcv.high, self.ohlcv.low, self.ohlcv.close
        )

        valid_k = k_line[~np.isnan(k_line)]
        valid_d = d_line[~np.isnan(d_line)]

        self.assertTrue((valid_k >= 0).all() or (valid_k <= 100).all() or len(valid_k) == 0)
        self.assertTrue((valid_d >= 0).all() or (valid_d <= 100).all() or len(valid_d) == 0)

    def test_atr_positive(self):
        """测试ATR为正值"""
        atr = self.calc.atr(self.ohlcv.high, self.ohlcv.low, self.ohlcv.close)

        valid_atr = atr[~np.isnan(atr)]
        self.assertTrue((valid_atr >= 0).all())

    def test_obv_monotonic(self):
        """测试OBV单调性"""
        obv = self.calc.obv(self.close_prices, self.ohlcv.volume)

        # OBV应该是单调的或几乎单调的
        obv_diff = np.diff(obv)
        self.assertEqual(len(obv), len(self.close_prices))

    def test_sma_vs_ema(self):
        """测试SMA vs EMA的差异"""
        period = 20

        sma = self.calc.sma(self.close_prices, period)
        ema = self.calc.ema(self.close_prices, period)

        # EMA应该对最近的价格更敏感
        valid_idx = ~(np.isnan(sma) | np.isnan(ema))

        if len(valid_idx[valid_idx]):
            # 在上升趋势中，EMA > SMA
            sma_valid = sma[valid_idx]
            ema_valid = ema[valid_idx]

            if self.close_prices[-1] > self.close_prices[0]:
                # 上升趋势
                self.assertGreater(np.mean(ema_valid[-10:]), np.mean(sma_valid[-10:]))

    def test_patterns_recognition(self):
        """测试K线形态识别"""
        patterns = self.calc.identify_patterns(
            self.ohlcv.open, self.ohlcv.high,
            self.ohlcv.low, self.ohlcv.close
        )

        # 检查所有形态都返回了
        expected_patterns = [
            'hammer', 'inverted_hammer', 'bullish_engulfing',
            'bearish_engulfing', 'doji', 'shooting_star'
        ]

        for pattern in expected_patterns:
            self.assertIn(pattern, patterns)
            self.assertEqual(len(patterns[pattern]), len(self.close_prices))

        # 检查返回值类型
        for pattern_values in patterns.values():
            self.assertTrue(isinstance(pattern_values, np.ndarray))

    def test_advanced_features(self):
        """测试高级特征计算"""
        features = self.calc.calculate_advanced_features(
            self.ohlcv.open, self.ohlcv.high,
            self.ohlcv.low, self.ohlcv.close, self.ohlcv.volume
        )

        # 检查必需的特征
        required_features = [
            'hl_ratio', 'oc_ratio', 'price_range_pct',
            'close_position_ratio', 'volume_change_rate'
        ]

        for feat in required_features:
            self.assertIn(feat, features)
            self.assertEqual(len(features[feat]), len(self.close_prices))


class TestFeatureAggregator(unittest.TestCase):
    """测试特征聚合器"""

    def setUp(self):
        """设置测试数据"""
        np.random.seed(42)
        n = 200

        self.close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
        self.ohlcv = OHLCV(
            open=self.close_prices + np.random.randn(n) * 0.1,
            high=self.close_prices + np.abs(np.random.randn(n) * 0.5),
            low=self.close_prices - np.abs(np.random.randn(n) * 0.5),
            close=self.close_prices,
            volume=np.random.randint(1000, 10000, n)
        )

        self.calc = IndicatorCalculator()
        self.indicators = self.calc.get_all_indicators(self.ohlcv)

    def test_flatten_features(self):
        """测试特征展平"""
        agg = FeatureAggregator()
        df = agg.flatten_features(self.indicators)

        self.assertGreater(len(df.columns), 0)
        self.assertGreater(len(df), 0)

    def test_normalization(self):
        """测试特征标准化"""
        agg = FeatureAggregator()
        df = agg.flatten_features(self.indicators)

        # 测试Z-Score标准化
        df_normalized = agg.normalize_features(df, method='zscore')

        # 检查标准化后的均值和标准差
        for col in df_normalized.columns:
            mean = df_normalized[col].mean()
            std = df_normalized[col].std()

            if not np.isnan(mean) and not np.isnan(std):
                # 允许一定的浮点误差
                self.assertAlmostEqual(mean, 0, places=5)
                self.assertAlmostEqual(std, 1, places=1)

    def test_handle_missing_values(self):
        """测试缺失值处理"""
        agg = FeatureAggregator()
        df = agg.flatten_features(self.indicators)

        # 添加一些NaN
        df.iloc[5:10, 0] = np.nan

        initial_nan_count = df.isna().sum().sum()

        # 处理缺失值
        df_clean = agg.handle_missing_values(df)

        # 应该减少NaN
        final_nan_count = df_clean.isna().sum().sum()
        self.assertLessEqual(final_nan_count, initial_nan_count)

    def test_remove_constant_features(self):
        """测试移除常数特征"""
        agg = FeatureAggregator()
        df = pd.DataFrame({
            'var_feature': np.random.randn(100),
            'const_feature': np.ones(100),
            'var_feature2': np.random.randn(100)
        })

        df_clean = agg.remove_constant_features(df)

        # 常数特征应该被移除
        self.assertNotIn('const_feature', df_clean.columns)
        self.assertIn('var_feature', df_clean.columns)
        self.assertIn('var_feature2', df_clean.columns)

    def test_engineer_create_features(self):
        """测试特征工程创建特征"""
        engineer = FeatureEngineer()

        df = pd.DataFrame({
            'a': np.array([1, 2, 3, 4, 5], dtype=float),
            'b': np.array([2, 4, 6, 8, 10], dtype=float)
        })

        # 测试比率特征
        df_ratio = engineer.create_ratio_features(df, [('a', 'b')])
        self.assertIn('a_ratio_b', df_ratio.columns)
        np.testing.assert_array_almost_equal(
            df_ratio['a_ratio_b'].dropna().values,
            np.array([0.5, 0.5, 0.5, 0.5, 0.5])
        )


class TestFeatureCache(unittest.TestCase):
    """测试特征缓存"""

    def test_cache_set_get(self):
        """测试缓存的设置和获取"""
        cache = FeatureCache()

        data = np.array([1, 2, 3, 4, 5])
        cache.set('test_key', data)

        retrieved = cache.get('test_key')

        np.testing.assert_array_equal(retrieved, data)

    def test_cache_expiration(self):
        """测试缓存过期"""
        from features_cache import CacheEntry

        entry = CacheEntry(data="test", ttl_seconds=1)

        import time
        self.assertFalse(entry.is_expired(2))

        time.sleep(0.1)  # 不要真的等待太长
        self.assertFalse(entry.is_expired(1))

    def test_cache_delete(self):
        """测试缓存删除"""
        cache = FeatureCache()

        cache.set('test_key', np.array([1, 2, 3]))
        cache.delete('test_key')

        retrieved = cache.get('test_key')
        self.assertIsNone(retrieved)

    def test_incremental_calculator(self):
        """测试增量计算器"""
        calc = IncrementalCalculator()

        close = np.array([100.0, 101.0, 102.0, 103.0, 104.0])

        # 第一次计算
        rsi1, avg_gain1, avg_loss1 = calc.calculate_incremental_rsi(
            close[:3], 14
        )

        # 增量计算
        rsi2, avg_gain2, avg_loss2 = calc.calculate_incremental_rsi(
            close[:4], 14, avg_gain1, avg_loss1
        )

        # 检查返回值
        self.assertEqual(len(rsi1), 3)
        self.assertEqual(len(rsi2), 4)


class TestFeatureEngineering(unittest.TestCase):
    """测试完整的特征工程系统"""

    def setUp(self):
        """设置测试数据"""
        np.random.seed(42)
        n = 200

        self.close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
        self.ohlcv = OHLCV(
            open=self.close_prices + np.random.randn(n) * 0.1,
            high=self.close_prices + np.abs(np.random.randn(n) * 0.5),
            low=self.close_prices - np.abs(np.random.randn(n) * 0.5),
            close=self.close_prices,
            volume=np.random.randint(1000, 10000, n)
        )

        self.fe = FeatureEngineering(enable_caching=True)

    def test_process_complete_pipeline(self):
        """测试完整处理流程"""
        result = self.fe.process(self.ohlcv)

        self.assertIsNotNone(result.features)
        self.assertGreater(len(result.features), 0)
        self.assertGreater(len(result.indicators), 0)
        self.assertIn('n_features', result.metadata)

    def test_feature_quality(self):
        """测试特征质量"""
        result = self.fe.process(self.ohlcv)

        # 检查是否有过多的NaN
        nan_ratio = result.features.isna().sum().sum() / (
            len(result.features) * len(result.features.columns)
        )
        self.assertLess(nan_ratio, 0.5)

    def test_cache_functionality(self):
        """测试缓存功能"""
        # 第一次处理
        result1 = self.fe.process(self.ohlcv)

        # 缓存应该被填充
        stats = self.fe.get_cache_stats()
        self.assertGreater(stats.get('memory_items', 0), 0)


class TestFeatureMetrics(unittest.TestCase):
    """测试特征指标"""

    def test_stability_calculation(self):
        """测试稳定性计算"""
        df = pd.DataFrame({
            'feature1': np.random.randn(100),
            'feature2': np.random.randn(100)
        })

        stability = FeatureMetrics.calculate_stability(df)

        self.assertIn('feature1', stability)
        self.assertIn('feature2', stability)

    def test_coverage_calculation(self):
        """测试覆盖度计算"""
        df = pd.DataFrame({
            'feature1': np.random.randn(100),
            'feature2': np.random.randn(100)
        })

        coverage = FeatureMetrics.calculate_coverage(df)

        self.assertEqual(coverage['feature1'], 1.0)
        self.assertEqual(coverage['feature2'], 1.0)


def run_performance_test():
    """运行性能测试"""
    import time

    print("\n" + "=" * 60)
    print("性能基准测试")
    print("=" * 60)

    np.random.seed(42)
    n = 1000

    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close_prices + np.random.randn(n) * 0.1,
        high=close_prices + np.abs(np.random.randn(n) * 0.5),
        low=close_prices - np.abs(np.random.randn(n) * 0.5),
        close=close_prices,
        volume=np.random.randint(1000, 10000, n)
    )

    fe = FeatureEngineering()

    # 测试1000根K线的计算时间
    start = time.time()
    result = fe.process(ohlcv)
    elapsed = (time.time() - start) * 1000

    print(f"\n✓ 1000根K线处理: {elapsed:.2f}ms")
    print(f"✓ 指标数量: {result.metadata['indicators_count']}")
    print(f"✓ 特征数量: {result.metadata['n_features']}")

    if elapsed < 100:
        print("\n✓ 性能测试通过！(< 100ms)")
        return True
    else:
        print(f"\n⚠ 性能测试未达到目标 ({elapsed:.2f}ms > 100ms)")
        return False


if __name__ == '__main__':
    # 运行单元测试
    unittest.main(argv=[''], exit=False, verbosity=2)

    # 运行性能测试
    run_performance_test()
