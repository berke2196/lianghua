"""
特征工程模块 - 完整集成接口

统一的特征工程API，整合所有指标计算、聚合、缓存功能
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
import logging
from dataclasses import dataclass

from features_indicators import IndicatorCalculator, OHLCV
from features_aggregator import FeatureAggregator, FeatureConfig, FeatureEngineer, FeatureReducer
from features_cache import FeatureCache, IncrementalCalculator, RealtimeFeatureStream

logger = logging.getLogger(__name__)


@dataclass
class FeatureResult:
    """特征结果对象"""
    features: pd.DataFrame
    indicators: Dict
    metadata: Dict


class FeatureEngineering:
    """
    完整的特征工程系统
    
    提供统一的API用于：
    1. 计算200+技术指标
    2. 聚合和标准化特征
    3. 缓存管理
    4. 增量计算
    5. 实时流处理
    """

    def __init__(self, cache_dir: str = "./feature_cache", 
                 enable_caching: bool = True,
                 parallel: bool = True):
        """
        初始化特征工程系统
        
        Args:
            cache_dir: 缓存目录
            enable_caching: 是否启用缓存
            parallel: 是否启用并行计算
        """
        self.indicator_calc = IndicatorCalculator()
        self.feature_agg = FeatureAggregator()
        self.incremental_calc = IncrementalCalculator()
        self.realtime_stream = None

        self.enable_caching = enable_caching
        self.parallel = parallel

        if enable_caching:
            self.cache = FeatureCache(cache_dir=cache_dir)
        else:
            self.cache = None

        logger.info("特征工程系统已初始化")

    def process(self, ohlcv: OHLCV, 
               normalization: bool = True,
               remove_outliers: bool = True,
               feature_selection: bool = False,
               n_selected_features: int = 50) -> FeatureResult:
        """
        完整的特征处理流程
        
        Args:
            ohlcv: OHLCV数据
            normalization: 是否标准化
            remove_outliers: 是否移除异常值
            feature_selection: 是否进行特征选择
            n_selected_features: 选择的特征数
        
        Returns:
            FeatureResult对象
        """
        # 1. 检查缓存
        cache_key = f"features_{id(ohlcv)}"
        if self.cache and self.cache.get(cache_key):
            logger.info("从缓存加载特征")
            return self.cache.get(cache_key)

        # 2. 计算所有指标
        logger.info("计算技术指标...")
        indicators = self.indicator_calc.get_all_indicators(ohlcv)

        # 3. 聚合特征
        logger.info("聚合特征...")
        config = FeatureConfig(
            normalize=normalization,
            handle_missing='forward_fill',
            outlier_method='zscore' if remove_outliers else 'none'
        )
        features_df = self.feature_agg.aggregate(indicators, config)

        # 4. 特征工程（创建新特征）
        logger.info("创建高级特征...")
        engineer = FeatureEngineer()

        # 创建滚动特征
        rolling_features = ['rsi', 'macd_0', 'atr', 'obv']
        available_rolling = [f for f in rolling_features if f in features_df.columns]
        if available_rolling:
            features_df = engineer.create_rolling_features(
                features_df, available_rolling, window=20
            )

        # 5. 特征选择
        if feature_selection and len(features_df) > 0 and len(features_df.columns) > n_selected_features:
            logger.info(f"选择前{n_selected_features}个特征...")
            X = features_df.values
            # 使用简单的方差选择
            features_df, selected = self.feature_agg.select_top_features(
                features_df, X, np.ones(len(X)), 
                n_features=n_selected_features,
                method='variance'
            )

        # 6. 创建结果对象
        result = FeatureResult(
            features=features_df,
            indicators=indicators,
            metadata={
                'n_features': len(features_df.columns),
                'n_samples': len(features_df),
                'indicators_count': sum(
                    1 for v in indicators.values() 
                    if isinstance(v, (np.ndarray, dict, tuple))
                )
            }
        )

        # 7. 缓存结果
        if self.cache:
            self.cache.set(cache_key, result, persist=True)

        logger.info(f"✓ 特征处理完成: {result.metadata['n_features']} 个特征")

        return result

    def process_batch(self, ohlcv_list: List[OHLCV], 
                     **kwargs) -> List[FeatureResult]:
        """
        批量处理多组OHLCV数据
        
        Args:
            ohlcv_list: OHLCV数据列表
            **kwargs: 传递给process的参数
        
        Returns:
            FeatureResult列表
        """
        results = []

        if self.parallel:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(self.process, ohlcv, **kwargs): i 
                    for i, ohlcv in enumerate(ohlcv_list)
                }

                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        logger.error(f"处理失败: {e}")

        else:
            for ohlcv in ohlcv_list:
                result = self.process(ohlcv, **kwargs)
                results.append(result)

        return results

    def incremental_update(self, ohlcv: OHLCV, 
                          new_bars: Dict[str, np.ndarray]) -> Dict:
        """
        增量更新（适用于实时流）
        
        Args:
            ohlcv: 当前OHLCV数据
            new_bars: 新增的K线数据
        
        Returns:
            更新后的指标
        """
        logger.info("执行增量更新...")

        # 更新OHLCV数据
        updated_ohlcv = {
            'open': np.concatenate([ohlcv.open, new_bars.get('open', [])]),
            'high': np.concatenate([ohlcv.high, new_bars.get('high', [])]),
            'low': np.concatenate([ohlcv.low, new_bars.get('low', [])]),
            'close': np.concatenate([ohlcv.close, new_bars.get('close', [])]),
            'volume': np.concatenate([ohlcv.volume, new_bars.get('volume', [])]),
        }

        # 计算新的指标
        indicators = self.incremental_calc.batch_update(
            updated_ohlcv,
            indicators_config={
                'rsi': {'period': 14},
                'sma': {'periods': [20]},
                'ema': {'periods': [12, 26]},
            }
        )

        return indicators

    def enable_realtime_streaming(self, window_size: int = 1000):
        """启用实时流处理"""
        self.realtime_stream = RealtimeFeatureStream(window_size=window_size)
        logger.info("实时特征流已启用")

    def add_realtime_bar(self, bar: Dict[str, float]) -> Dict:
        """
        添加实时K线
        
        Args:
            bar: K线数据
        
        Returns:
            最新的指标
        """
        if self.realtime_stream is None:
            raise RuntimeError("实时流未启用")

        return self.realtime_stream.add_bar(bar)

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        if self.cache:
            return self.cache.get_stats()
        return {}

    def clear_cache(self):
        """清空缓存"""
        if self.cache:
            self.cache.clear()
            logger.info("缓存已清空")

    def get_feature_importance(self, X: np.ndarray, y: np.ndarray,
                             feature_names: List[str]) -> pd.DataFrame:
        """
        获取特征重要性
        
        Args:
            X: 特征矩阵
            y: 目标向量
            feature_names: 特征名称
        
        Returns:
            特征重要性DataFrame
        """
        return self.feature_agg.calculate_feature_importance(
            X, y, feature_names, model_type='tree'
        )


class FeatureMetrics:
    """特征质量评估"""

    @staticmethod
    def calculate_stability(features_df: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """
        计算特征稳定性（滚动相关性）
        
        Args:
            features_df: 特征DataFrame
            window: 窗口大小
        
        Returns:
            各特征的稳定性得分
        """
        stability_scores = {}

        for col in features_df.columns:
            rolling_corr = features_df[col].rolling(window=window).corr(
                features_df[col].shift(1)
            )
            stability_scores[col] = rolling_corr.mean()

        return stability_scores

    @staticmethod
    def calculate_coverage(features_df: pd.DataFrame) -> Dict[str, float]:
        """
        计算特征覆盖度（非NaN比例）
        
        Args:
            features_df: 特征DataFrame
        
        Returns:
            各特征的覆盖度
        """
        coverage = {}

        for col in features_df.columns:
            non_nan_count = features_df[col].notna().sum()
            coverage[col] = non_nan_count / len(features_df)

        return coverage

    @staticmethod
    def calculate_info_value(features_df: pd.DataFrame, y: np.ndarray) -> Dict[str, float]:
        """
        计算信息价值 (Information Value)
        
        Args:
            features_df: 特征DataFrame
            y: 目标向量 (二分类)
        
        Returns:
            各特征的IV值
        """
        iv_scores = {}

        for col in features_df.columns:
            # 离散化特征
            n_bins = min(10, len(features_df[col].unique()))
            X_binned = pd.cut(features_df[col].dropna(), bins=n_bins, duplicates='drop')

            # 计算分布
            event = (y == 1).sum()
            non_event = (y == 0).sum()

            iv = 0
            for bin_idx in X_binned.unique():
                bin_mask = X_binned == bin_idx
                pct_event = bin_mask[y == 1].sum() / event if event > 0 else 0
                pct_non_event = bin_mask[y == 0].sum() / non_event if non_event > 0 else 0

                if pct_event > 0 and pct_non_event > 0:
                    iv += (pct_event - pct_non_event) * np.log(pct_event / pct_non_event)

            iv_scores[col] = iv

        return iv_scores


def benchmark_indicators():
    """基准测试指标计算速度"""
    import time

    print("\n" + "=" * 60)
    print("特征工程模块基准测试")
    print("=" * 60)

    # 生成测试数据
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

    # 测试指标计算速度
    fe = FeatureEngineering()

    start_time = time.time()
    result = fe.process(ohlcv)
    elapsed = (time.time() - start_time) * 1000

    print(f"\n✓ 1000根K线处理时间: {elapsed:.2f}ms")
    print(f"✓ 计算特征数: {result.metadata['n_features']}")
    print(f"✓ 计算指标数: {result.metadata['indicators_count']}")

    # 打印缓存统计
    if fe.cache:
        stats = fe.get_cache_stats()
        print(f"\n缓存统计:")
        print(f"  - 内存项数: {stats.get('memory_items', 0)}")
        print(f"  - 缓存命中率: {stats.get('memory_hit_rate', 0):.2%}")

    print("=" * 60 + "\n")

    return elapsed < 100  # 目标：< 100ms


if __name__ == '__main__':
    # 运行基准测试
    success = benchmark_indicators()
    if success:
        print("✓ 性能测试通过！")
    else:
        print("⚠ 性能测试未达到目标")
