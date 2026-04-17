"""
特征缓存管理 - 支持高效的增量计算和缓存

功能：
- 特征缓存存储
- 增量计算
- 缓存失效
- 持久化存储
- 实时更新
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import pickle
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""
    data: Any
    timestamp: datetime = field(default_factory=datetime.now)
    hash_value: str = ""
    version: int = 1

    def is_expired(self, ttl_seconds: int = 3600) -> bool:
        """检查是否过期"""
        elapsed = (datetime.now() - self.timestamp).total_seconds()
        return elapsed > ttl_seconds


class FeatureCache:
    """
    特征缓存管理器
    
    支持：
    - 多级缓存 (内存+磁盘)
    - 增量更新
    - 自动失效
    - 版本管理
    """

    def __init__(self, cache_dir: str = "./feature_cache", 
                 max_memory_items: int = 1000,
                 ttl_seconds: int = 3600):
        """
        初始化缓存
        
        Args:
            cache_dir: 缓存目录
            max_memory_items: 最大内存项数
            ttl_seconds: 缓存生存时间
        """
        self.cache_dir = cache_dir
        self.max_memory_items = max_memory_items
        self.ttl_seconds = ttl_seconds

        self.memory_cache: Dict[str, CacheEntry] = {}
        self.access_count: Dict[str, int] = {}
        self.access_time: Dict[str, datetime] = {}

        # 创建缓存目录
        import os
        os.makedirs(cache_dir, exist_ok=True)

    def _compute_hash(self, data: Any) -> str:
        """计算数据哈希值"""
        if isinstance(data, (list, np.ndarray)):
            data_bytes = np.array(data).tobytes()
        elif isinstance(data, pd.DataFrame):
            data_bytes = pd.util.hash_pandas_object(data, index=True).values.tobytes()
        elif isinstance(data, dict):
            data_bytes = json.dumps(data, sort_keys=True, default=str).encode()
        else:
            data_bytes = str(data).encode()

        return hashlib.md5(data_bytes).hexdigest()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存项
        
        Args:
            key: 缓存键
        
        Returns:
            缓存数据或None
        """
        # 优先查询内存缓存
        if key in self.memory_cache:
            entry = self.memory_cache[key]
            if not entry.is_expired(self.ttl_seconds):
                self.access_count[key] = self.access_count.get(key, 0) + 1
                self.access_time[key] = datetime.now()
                logger.debug(f"内存缓存命中: {key}")
                return entry.data
            else:
                # 缓存过期，删除
                del self.memory_cache[key]
                logger.debug(f"缓存已过期: {key}")

        # 尝试从磁盘缓存加载
        disk_data = self._load_from_disk(key)
        if disk_data is not None:
            entry = disk_data
            if not entry.is_expired(self.ttl_seconds):
                self._check_memory_cache_size()
                self.memory_cache[key] = entry
                logger.debug(f"从磁盘缓存加载: {key}")
                return entry.data

        return None

    def set(self, key: str, data: Any, persist: bool = False) -> None:
        """
        设置缓存项
        
        Args:
            key: 缓存键
            data: 数据
            persist: 是否持久化到磁盘
        """
        hash_value = self._compute_hash(data)

        entry = CacheEntry(data=data, hash_value=hash_value)

        # 检查内存缓存大小
        self._check_memory_cache_size()

        self.memory_cache[key] = entry
        self.access_count[key] = 0
        self.access_time[key] = datetime.now()

        logger.debug(f"缓存已设置: {key}")

        # 可选持久化
        if persist:
            self._save_to_disk(key, entry)
            logger.debug(f"缓存已持久化: {key}")

    def delete(self, key: str) -> None:
        """删除缓存项"""
        if key in self.memory_cache:
            del self.memory_cache[key]
            if key in self.access_count:
                del self.access_count[key]
            if key in self.access_time:
                del self.access_time[key]

        self._delete_from_disk(key)
        logger.debug(f"缓存已删除: {key}")

    def clear(self) -> None:
        """清空所有缓存"""
        self.memory_cache.clear()
        self.access_count.clear()
        self.access_time.clear()

        import shutil
        import os
        if os.path.exists(self.cache_dir):
            shutil.rmtree(self.cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

        logger.info("所有缓存已清空")

    def _check_memory_cache_size(self) -> None:
        """检查并管理内存缓存大小"""
        if len(self.memory_cache) >= self.max_memory_items:
            # 移除最少访问的项
            lru_key = min(self.access_count, key=self.access_count.get)
            self._save_to_disk(lru_key, self.memory_cache[lru_key])
            del self.memory_cache[lru_key]
            logger.debug(f"内存缓存已满，移除最少访问项: {lru_key}")

    def _save_to_disk(self, key: str, entry: CacheEntry) -> None:
        """保存到磁盘"""
        import os

        filepath = os.path.join(self.cache_dir, f"{key}.cache")

        try:
            with open(filepath, 'wb') as f:
                pickle.dump(entry, f)
        except Exception as e:
            logger.error(f"无法保存缓存到磁盘: {e}")

    def _load_from_disk(self, key: str) -> Optional[CacheEntry]:
        """从磁盘加载"""
        import os

        filepath = os.path.join(self.cache_dir, f"{key}.cache")

        if not os.path.exists(filepath):
            return None

        try:
            with open(filepath, 'rb') as f:
                entry = pickle.load(f)
                return entry
        except Exception as e:
            logger.error(f"无法从磁盘加载缓存: {e}")
            return None

    def _delete_from_disk(self, key: str) -> None:
        """从磁盘删除"""
        import os

        filepath = os.path.join(self.cache_dir, f"{key}.cache")

        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                logger.error(f"无法删除磁盘缓存: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_accesses = sum(self.access_count.values())
        
        return {
            'memory_items': len(self.memory_cache),
            'total_accesses': total_accesses,
            'memory_hit_rate': total_accesses / (len(self.access_count) + 1) if self.access_count else 0,
            'oldest_entry': min(self.access_time.values()) if self.access_time else None,
            'newest_entry': max(self.access_time.values()) if self.access_time else None,
        }


class IncrementalCalculator:
    """
    增量计算器
    
    支持对新增数据进行高效的增量指标计算
    """

    def __init__(self, cache: Optional[FeatureCache] = None):
        """初始化增量计算器"""
        self.cache = cache or FeatureCache()
        self.historical_data = {}

    def update(self, ohlcv: Dict[str, np.ndarray], new_bars: Dict[str, np.ndarray]) -> Dict:
        """
        增量更新指标
        
        Args:
            ohlcv: 当前OHLCV数据
            new_bars: 新增的K线数据
        
        Returns:
            更新后的指标
        """
        # 合并新数据
        for key in new_bars:
            if key in ohlcv:
                ohlcv[key] = np.concatenate([ohlcv[key], new_bars[key]])

        # 清除相关缓存
        self.cache.delete('indicators')

        return ohlcv

    def calculate_incremental_rsi(self, close: np.ndarray, period: int = 14,
                                  prev_avg_gain: Optional[float] = None,
                                  prev_avg_loss: Optional[float] = None) -> Tuple[np.ndarray, float, float]:
        """
        增量计算RSI
        
        Args:
            close: 收盘价数组
            period: 周期
            prev_avg_gain: 前一个平均涨幅
            prev_avg_loss: 前一个平均跌幅
        
        Returns:
            (RSI值, 新的平均涨幅, 新的平均跌幅)
        """
        if len(close) < 2:
            return np.full_like(close, np.nan), 0, 0

        # 只计算最后一个值
        delta = close[-1] - close[-2]
        gain = delta if delta > 0 else 0
        loss = -delta if delta < 0 else 0

        if prev_avg_gain is None or prev_avg_loss is None:
            # 初次计算
            deltas = np.diff(close[-period-1:])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
        else:
            # 增量计算
            avg_gain = (prev_avg_gain * (period - 1) + gain) / period
            avg_loss = (prev_avg_loss * (period - 1) + loss) / period

        # 计算RSI
        if avg_loss == 0:
            rsi = 100 if gain > 0 else 0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        result = np.full_like(close, np.nan, dtype=float)
        result[-1] = rsi

        return result, avg_gain, avg_loss

    def calculate_incremental_sma(self, close: np.ndarray, period: int,
                                  prev_sma: Optional[float] = None) -> Tuple[float, np.ndarray]:
        """
        增量计算SMA
        
        Args:
            close: 收盘价数组
            period: 周期
            prev_sma: 前一个SMA值
        
        Returns:
            (当前SMA值, SMA数组)
        """
        if len(close) < period:
            return np.mean(close), np.full_like(close, np.nan)

        if prev_sma is None:
            # 初次计算
            sma = np.mean(close[-period:])
        else:
            # 增量计算
            sma = prev_sma + (close[-1] - close[-period]) / period

        result = np.full_like(close, np.nan, dtype=float)
        result[-1] = sma

        return sma, result

    def calculate_incremental_ema(self, close: np.ndarray, period: int,
                                  prev_ema: Optional[float] = None) -> Tuple[float, np.ndarray]:
        """增量计算EMA"""
        multiplier = 2 / (period + 1)

        if prev_ema is None:
            # 初次计算
            ema = np.mean(close[-period:])
        else:
            # 增量计算
            ema = close[-1] * multiplier + prev_ema * (1 - multiplier)

        result = np.full_like(close, np.nan, dtype=float)
        result[-1] = ema

        return ema, result

    def batch_update(self, ohlcv: Dict[str, np.ndarray], 
                     indicators_config: Dict[str, Any]) -> Dict:
        """
        批量增量更新多个指标
        
        Args:
            ohlcv: OHLCV数据
            indicators_config: 指标配置
        
        Returns:
            更新后的指标结果
        """
        results = {}

        # 从缓存获取前一个值
        cache_key = 'indicator_state'
        prev_state = self.cache.get(cache_key) or {}

        # RSI
        if 'rsi' in indicators_config:
            period = indicators_config['rsi'].get('period', 14)
            prev_avg_gain = prev_state.get('rsi_avg_gain')
            prev_avg_loss = prev_state.get('rsi_avg_loss')

            rsi, avg_gain, avg_loss = self.calculate_incremental_rsi(
                ohlcv['close'], period, prev_avg_gain, prev_avg_loss
            )
            results['rsi'] = rsi
            prev_state['rsi_avg_gain'] = avg_gain
            prev_state['rsi_avg_loss'] = avg_loss

        # SMA
        if 'sma' in indicators_config:
            periods = indicators_config['sma'].get('periods', [20])
            for p in periods:
                prev_sma = prev_state.get(f'sma_{p}')
                sma, sma_array = self.calculate_incremental_sma(
                    ohlcv['close'], p, prev_sma
                )
                results[f'sma_{p}'] = sma_array
                prev_state[f'sma_{p}'] = sma

        # EMA
        if 'ema' in indicators_config:
            periods = indicators_config['ema'].get('periods', [20])
            for p in periods:
                prev_ema = prev_state.get(f'ema_{p}')
                ema, ema_array = self.calculate_incremental_ema(
                    ohlcv['close'], p, prev_ema
                )
                results[f'ema_{p}'] = ema_array
                prev_state[f'ema_{p}'] = ema

        # 保存状态到缓存
        self.cache.set(cache_key, prev_state, persist=True)

        return results


class RealtimeFeatureStream:
    """
    实时特征流处理
    
    处理流式数据并实时计算特征
    """

    def __init__(self, window_size: int = 1000):
        """初始化实时特征流"""
        self.window_size = window_size
        self.ohlcv_buffer = {
            'open': deque(maxlen=window_size),
            'high': deque(maxlen=window_size),
            'low': deque(maxlen=window_size),
            'close': deque(maxlen=window_size),
            'volume': deque(maxlen=window_size),
        }
        self.calculator = IncrementalCalculator()
        self.latest_indicators = {}

    def add_bar(self, bar: Dict[str, float]) -> Dict:
        """
        添加新K线
        
        Args:
            bar: K线数据 {'open': ..., 'high': ..., 'low': ..., 'close': ..., 'volume': ...}
        
        Returns:
            最新计算的指标
        """
        # 添加到缓冲区
        for key in self.ohlcv_buffer:
            self.ohlcv_buffer[key].append(bar[key])

        # 转换为numpy数组
        ohlcv = {
            key: np.array(list(buffer)) for key, buffer in self.ohlcv_buffer.items()
        }

        # 计算指标（只计算最后几个值）
        if len(ohlcv['close']) >= 14:
            # RSI
            rsi, _, _ = self.calculator.calculate_incremental_rsi(
                ohlcv['close'], 14
            )
            self.latest_indicators['rsi'] = rsi[-1] if not np.isnan(rsi[-1]) else None

            # SMA
            sma_20, _ = self.calculator.calculate_incremental_sma(
                ohlcv['close'], 20
            )
            self.latest_indicators['sma_20'] = sma_20

            # EMA
            ema_12, _ = self.calculator.calculate_incremental_ema(
                ohlcv['close'], 12
            )
            self.latest_indicators['ema_12'] = ema_12

        return self.latest_indicators


# 导入所需的库
from collections import deque


if __name__ == '__main__':
    # 测试
    print("✓ 特征缓存模块已加载")
