"""
特征工程使用指南和示例

包含：
1. 基础用法示例
2. 高级配置
3. 实时流处理
4. 性能优化
5. 故障排除
"""

import numpy as np
import pandas as pd
from features_engineering import FeatureEngineering, FeatureMetrics
from features_indicators import OHLCV


# ==================== 1. 基础用法 ====================

def example_basic_usage():
    """
    基础用法示例
    
    演示如何创建特征工程系统并处理OHLCV数据
    """
    print("\n" + "=" * 60)
    print("示例1: 基础用法")
    print("=" * 60)

    # 创建或加载OHLCV数据
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

    # 初始化特征工程系统
    fe = FeatureEngineering(enable_caching=True)

    # 处理数据
    result = fe.process(
        ohlcv,
        normalization=True,
        remove_outliers=True,
        feature_selection=False
    )

    print(f"\n✓ 处理完成")
    print(f"  - 特征数: {result.metadata['n_features']}")
    print(f"  - 样本数: {result.metadata['n_samples']}")
    print(f"  - 指标总数: {result.metadata['indicators_count']}")

    print(f"\n✓ 特征矩阵形状: {result.features.shape}")
    print(f"✓ 特征列表:")
    print(result.features.columns.tolist()[:10], "...")

    return result


# ==================== 2. 高级特征工程 ====================

def example_advanced_features():
    """
    高级特征工程示例
    
    包括特征选择、特征创建等
    """
    print("\n" + "=" * 60)
    print("示例2: 高级特征工程")
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

    fe = FeatureEngineering()

    # 处理并进行特征选择
    result = fe.process(
        ohlcv,
        normalization=True,
        remove_outliers=True,
        feature_selection=True,
        n_selected_features=50
    )

    print(f"\n✓ 特征选择后")
    print(f"  - 最终特征数: {result.metadata['n_features']}")
    print(f"  - 特征列表 (前10个):")
    for i, col in enumerate(result.features.columns[:10]):
        print(f"    {i+1}. {col}")


# ==================== 3. 特征质量评估 ====================

def example_feature_quality():
    """
    特征质量评估示例
    
    评估特征的稳定性和覆盖度
    """
    print("\n" + "=" * 60)
    print("示例3: 特征质量评估")
    print("=" * 60)

    # 生成测试数据
    np.random.seed(42)
    n = 500

    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close_prices + np.random.randn(n) * 0.1,
        high=close_prices + np.abs(np.random.randn(n) * 0.5),
        low=close_prices - np.abs(np.random.randn(n) * 0.5),
        close=close_prices,
        volume=np.random.randint(1000, 10000, n)
    )

    fe = FeatureEngineering()
    result = fe.process(ohlcv)

    # 计算稳定性
    stability = FeatureMetrics.calculate_stability(result.features, window=50)

    print(f"\n✓ 特征稳定性分析")
    print(f"  - 稳定特征 (> 0.7):")
    stable_features = [f for f, s in stability.items() if s > 0.7]
    for feat in stable_features[:5]:
        print(f"    - {feat}: {stability[feat]:.4f}")

    print(f"\n  - 不稳定特征 (< 0.3):")
    unstable_features = [f for f, s in stability.items() if s < 0.3]
    for feat in unstable_features[:5]:
        print(f"    - {feat}: {stability[feat]:.4f}")

    # 计算覆盖度
    coverage = FeatureMetrics.calculate_coverage(result.features)

    print(f"\n✓ 特征覆盖度分析")
    print(f"  - 完全覆盖特征 ({sum(1 for v in coverage.values() if v == 1.0)}):")
    complete_coverage = sum(1 for v in coverage.values() if v == 1.0)
    print(f"    占比: {complete_coverage / len(coverage) * 100:.1f}%")

    print(f"\n  - 最小覆盖度: {min(coverage.values()):.2%}")
    print(f"  - 平均覆盖度: {np.mean(list(coverage.values())):.2%}")


# ==================== 4. 实时流处理 ====================

def example_realtime_streaming():
    """
    实时流处理示例
    
    演示如何处理流式数据
    """
    print("\n" + "=" * 60)
    print("示例4: 实时流处理")
    print("=" * 60)

    fe = FeatureEngineering()
    fe.enable_realtime_streaming(window_size=100)

    print(f"\n✓ 实时特征流已启用")

    # 模拟实时K线数据
    np.random.seed(42)
    price = 100.0

    print(f"\n✓ 处理实时K线数据:")

    for i in range(50):
        # 生成随机K线
        price += np.random.randn() * 0.5
        bar = {
            'open': price,
            'high': price + abs(np.random.randn() * 0.5),
            'low': price - abs(np.random.randn() * 0.5),
            'close': price,
            'volume': int(np.random.uniform(1000, 5000))
        }

        # 添加到实时流
        indicators = fe.add_realtime_bar(bar)

        if i % 10 == 0 and i > 0:
            print(f"  Bar {i}: Close={bar['close']:.2f}, "
                  f"RSI={indicators.get('rsi', 'N/A')}, "
                  f"SMA20={indicators.get('sma_20', 'N/A')}")

    print(f"\n✓ 实时流处理完成")


# ==================== 5. 批量处理 ====================

def example_batch_processing():
    """
    批量处理示例
    
    演示如何处理多个数据集
    """
    print("\n" + "=" * 60)
    print("示例5: 批量处理")
    print("=" * 60)

    np.random.seed(42)

    # 创建多个OHLCV数据集
    ohlcv_list = []

    for j in range(3):
        n = 500
        close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)

        ohlcv = OHLCV(
            open=close_prices + np.random.randn(n) * 0.1,
            high=close_prices + np.abs(np.random.randn(n) * 0.5),
            low=close_prices - np.abs(np.random.randn(n) * 0.5),
            close=close_prices,
            volume=np.random.randint(1000, 10000, n)
        )
        ohlcv_list.append(ohlcv)

    fe = FeatureEngineering(parallel=True)

    print(f"\n✓ 批量处理 {len(ohlcv_list)} 个数据集")

    results = fe.process_batch(ohlcv_list, normalization=True)

    print(f"\n✓ 批量处理完成")
    print(f"  - 处理的数据集数: {len(results)}")
    for i, result in enumerate(results):
        print(f"  - 数据集 {i+1}: {result.metadata['n_features']} 个特征")


# ==================== 6. 缓存管理 ====================

def example_cache_management():
    """
    缓存管理示例
    
    演示如何管理特征缓存
    """
    print("\n" + "=" * 60)
    print("示例6: 缓存管理")
    print("=" * 60)

    fe = FeatureEngineering(enable_caching=True)

    # 生成数据
    np.random.seed(42)
    n = 500

    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close_prices + np.random.randn(n) * 0.1,
        high=close_prices + np.abs(np.random.randn(n) * 0.5),
        low=close_prices - np.abs(np.random.randn(n) * 0.5),
        close=close_prices,
        volume=np.random.randint(1000, 10000, n)
    )

    # 第一次处理（从缓存中加载）
    result1 = fe.process(ohlcv)

    # 获取缓存统计
    stats = fe.get_cache_stats()

    print(f"\n✓ 缓存统计")
    print(f"  - 内存项数: {stats.get('memory_items', 0)}")
    print(f"  - 缓存命中率: {stats.get('memory_hit_rate', 0):.2%}")

    # 清空缓存
    fe.clear_cache()
    print(f"\n✓ 缓存已清空")

    stats_after = fe.get_cache_stats()
    print(f"  - 清空后内存项数: {stats_after.get('memory_items', 0)}")


# ==================== 7. 性能优化 ====================

def example_performance_optimization():
    """
    性能优化示例
    
    演示如何优化计算性能
    """
    print("\n" + "=" * 60)
    print("示例7: 性能优化")
    print("=" * 60)

    import time

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

    # 方案1: 启用缓存和并行处理
    print(f"\n✓ 测试配置1: 缓存 + 并行")

    fe1 = FeatureEngineering(enable_caching=True, parallel=True)
    start = time.time()
    result1 = fe1.process(ohlcv)
    elapsed1 = (time.time() - start) * 1000

    print(f"  - 处理时间: {elapsed1:.2f}ms")

    # 方案2: 禁用缓存但启用并行
    print(f"\n✓ 测试配置2: 无缓存 + 并行")

    fe2 = FeatureEngineering(enable_caching=False, parallel=True)
    start = time.time()
    result2 = fe2.process(ohlcv)
    elapsed2 = (time.time() - start) * 1000

    print(f"  - 处理时间: {elapsed2:.2f}ms")

    # 方案3: 启用缓存但不并行
    print(f"\n✓ 测试配置3: 缓存 + 无并行")

    fe3 = FeatureEngineering(enable_caching=True, parallel=False)
    start = time.time()
    result3 = fe3.process(ohlcv)
    elapsed3 = (time.time() - start) * 1000

    print(f"  - 处理时间: {elapsed3:.2f}ms")

    print(f"\n✓ 性能比较:")
    print(f"  - 最快配置: {min(elapsed1, elapsed2, elapsed3):.2f}ms")
    print(f"  - 平均时间: {np.mean([elapsed1, elapsed2, elapsed3]):.2f}ms")


# ==================== 8. 数据导出 ====================

def example_data_export():
    """
    数据导出示例
    
    演示如何导出特征数据
    """
    print("\n" + "=" * 60)
    print("示例8: 数据导出")
    print("=" * 60)

    # 生成数据
    np.random.seed(42)
    n = 100

    close_prices = 100 + np.cumsum(np.random.randn(n) * 0.5)
    ohlcv = OHLCV(
        open=close_prices + np.random.randn(n) * 0.1,
        high=close_prices + np.abs(np.random.randn(n) * 0.5),
        low=close_prices - np.abs(np.random.randn(n) * 0.5),
        close=close_prices,
        volume=np.random.randint(1000, 10000, n)
    )

    fe = FeatureEngineering()
    result = fe.process(ohlcv, feature_selection=True, n_selected_features=20)

    # 导出为CSV
    result.features.to_csv('features_export.csv', index=False)
    print(f"\n✓ 特征已导出到: features_export.csv")

    # 显示样本
    print(f"\n✓ 特征数据样本 (前5行，前5列):")
    print(result.features.iloc[:5, :5])

    # 导出元数据
    import json

    metadata = {
        'n_features': result.metadata['n_features'],
        'n_samples': result.metadata['n_samples'],
        'n_indicators': result.metadata['indicators_count'],
        'feature_names': result.features.columns.tolist()
    }

    with open('features_metadata.json', 'w') as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✓ 元数据已导出到: features_metadata.json")


# ==================== 主程序 ====================

def main():
    """
    运行所有示例
    """
    print("\n")
    print("*" * 60)
    print("特征工程模块使用示例")
    print("*" * 60)

    # 1. 基础用法
    example_basic_usage()

    # 2. 高级特征
    example_advanced_features()

    # 3. 特征质量评估
    example_feature_quality()

    # 4. 实时流处理
    example_realtime_streaming()

    # 5. 批量处理
    example_batch_processing()

    # 6. 缓存管理
    example_cache_management()

    # 7. 性能优化
    example_performance_optimization()

    # 8. 数据导出
    example_data_export()

    print("\n" + "*" * 60)
    print("所有示例执行完成！")
    print("*" * 60 + "\n")


if __name__ == '__main__':
    main()
