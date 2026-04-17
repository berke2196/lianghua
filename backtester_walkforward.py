"""
走测验证（Walk-Forward Analysis）
支持时间序列分割、滚动窗口验证、参数更新、性能对比、稳定性检查
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class SplitMethod(Enum):
    """数据分割方法"""
    ROLLING = "rolling"
    ANCHORED = "anchored"
    PURGED = "purged"
    EMBARGO = "embargo"


@dataclass
class WalkForwardSplit:
    """走测分割"""
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_indices: np.ndarray
    test_indices: np.ndarray


@dataclass
class WalkForwardResult:
    """走测结果"""
    symbol: str
    splits: List[WalkForwardSplit]
    in_sample_results: List[Dict[str, Any]]
    out_of_sample_results: List[Dict[str, Any]]
    optimized_params: List[Dict[str, Any]]
    is_period_params: List[Dict[str, Any]]
    oos_period_params: List[Dict[str, Any]]
    
    # 统计指标
    is_avg_sharpe: float = 0.0
    oos_avg_sharpe: float = 0.0
    is_oos_correlation: float = 0.0
    degradation: float = 0.0  # IS到OOS的性能下降
    stability: float = 0.0  # 参数稳定性


class WalkForwardValidator:
    """走测验证器"""
    
    def __init__(self,
                 data: pd.DataFrame,
                 train_size: int = 252,
                 test_size: int = 63,
                 step_size: Optional[int] = None,
                 method: SplitMethod = SplitMethod.ROLLING,
                 embargo_size: int = 0):
        """
        初始化走测验证器
        
        Args:
            data: 完整的历史数据
            train_size: 训练集大小（天数）
            test_size: 测试集大小（天数）
            step_size: 步进大小，默认为test_size
            method: 分割方法
            embargo_size: 禁入期大小
        """
        self.data = data
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size or test_size
        self.method = method
        self.embargo_size = embargo_size
        
        logger.info(f"WalkForwardValidator initialized: "
                   f"data_length={len(data)}, train={train_size}, test={test_size}")
    
    def generate_splits(self) -> List[WalkForwardSplit]:
        """生成走测分割"""
        splits = []
        
        if self.method == SplitMethod.ROLLING:
            splits = self._generate_rolling_splits()
        elif self.method == SplitMethod.ANCHORED:
            splits = self._generate_anchored_splits()
        elif self.method == SplitMethod.PURGED:
            splits = self._generate_purged_splits()
        elif self.method == SplitMethod.EMBARGO:
            splits = self._generate_embargo_splits()
        
        logger.info(f"Generated {len(splits)} walk-forward splits")
        return splits
    
    def _generate_rolling_splits(self) -> List[WalkForwardSplit]:
        """滚动窗口分割"""
        splits = []
        
        for i in range(0, len(self.data) - self.train_size - self.test_size, self.step_size):
            train_start = i
            train_end = i + self.train_size
            test_start = train_end
            test_end = test_start + self.test_size
            
            if test_end <= len(self.data):
                split = WalkForwardSplit(
                    train_start=self.data.index[train_start],
                    train_end=self.data.index[train_end - 1],
                    test_start=self.data.index[test_start],
                    test_end=self.data.index[test_end - 1],
                    train_indices=np.arange(train_start, train_end),
                    test_indices=np.arange(test_start, test_end)
                )
                splits.append(split)
        
        return splits
    
    def _generate_anchored_splits(self) -> List[WalkForwardSplit]:
        """锚定分割 - 训练集固定，测试集向后移动"""
        splits = []
        
        train_end = self.train_size
        
        for i in range(0, len(self.data) - train_end - self.test_size, self.step_size):
            test_start = train_end + i
            test_end = test_start + self.test_size
            
            if test_end <= len(self.data):
                split = WalkForwardSplit(
                    train_start=self.data.index[0],
                    train_end=self.data.index[train_end - 1],
                    test_start=self.data.index[test_start],
                    test_end=self.data.index[test_end - 1],
                    train_indices=np.arange(0, train_end),
                    test_indices=np.arange(test_start, test_end)
                )
                splits.append(split)
        
        return splits
    
    def _generate_purged_splits(self) -> List[WalkForwardSplit]:
        """净化分割 - 移除训练-测试之间的数据"""
        splits = []
        purge_size = max(1, self.test_size // 2)
        
        for i in range(0, len(self.data) - self.train_size - self.test_size - purge_size, 
                      self.step_size):
            train_start = i
            train_end = i + self.train_size
            purge_end = train_end + purge_size
            test_start = purge_end
            test_end = test_start + self.test_size
            
            if test_end <= len(self.data):
                split = WalkForwardSplit(
                    train_start=self.data.index[train_start],
                    train_end=self.data.index[train_end - 1],
                    test_start=self.data.index[test_start],
                    test_end=self.data.index[test_end - 1],
                    train_indices=np.arange(train_start, train_end),
                    test_indices=np.arange(test_start, test_end)
                )
                splits.append(split)
        
        return splits
    
    def _generate_embargo_splits(self) -> List[WalkForwardSplit]:
        """禁入分割 - 测试集后面添加禁入期"""
        splits = []
        
        for i in range(0, len(self.data) - self.train_size - self.test_size - 
                      self.embargo_size, self.step_size):
            train_start = i
            train_end = i + self.train_size
            embargo_start = train_end + self.embargo_size
            test_start = embargo_start
            test_end = test_start + self.test_size
            
            if test_end <= len(self.data):
                split = WalkForwardSplit(
                    train_start=self.data.index[train_start],
                    train_end=self.data.index[train_end - 1],
                    test_start=self.data.index[test_start],
                    test_end=self.data.index[test_end - 1],
                    train_indices=np.arange(train_start, train_end),
                    test_indices=np.arange(test_start, test_end)
                )
                splits.append(split)
        
        return splits
    
    def run_walk_forward(self,
                        strategy_func: Callable,
                        param_optimizer: Optional[Callable] = None,
                        parallel: bool = False,
                        max_workers: int = 4) -> WalkForwardResult:
        """
        执行走测验证
        
        Args:
            strategy_func: 策略函数，返回信号和性能指标
            param_optimizer: 参数优化函数，可选
            parallel: 是否并行处理
            max_workers: 最大工作进程数
        
        Returns:
            走测结果
        """
        logger.info("Starting walk-forward validation")
        
        splits = self.generate_splits()
        
        in_sample_results = []
        out_of_sample_results = []
        optimized_params = []
        is_period_params = []
        oos_period_params = []
        
        for split_idx, split in enumerate(splits):
            logger.info(f"Processing split {split_idx + 1}/{len(splits)}")
            
            # 获取训练和测试数据
            train_data = self.data.iloc[split.train_indices]
            test_data = self.data.iloc[split.test_indices]
            
            # 参数优化
            if param_optimizer is not None:
                best_params, is_result = param_optimizer(train_data)
                optimized_params.append(best_params)
                is_period_params.append(is_result)
            else:
                best_params = {}
            
            # 样本内测试
            is_signals, is_metrics = strategy_func(train_data, best_params, is_sample=True)
            in_sample_results.append(is_metrics)
            
            # 样本外测试
            oos_signals, oos_metrics = strategy_func(test_data, best_params, is_sample=False)
            out_of_sample_results.append(oos_metrics)
            oos_period_params.append(oos_metrics)
        
        # 计算统计指标
        is_sharpes = [r.get('sharpe_ratio', 0) for r in in_sample_results]
        oos_sharpes = [r.get('sharpe_ratio', 0) for r in out_of_sample_results]
        
        is_avg_sharpe = np.mean(is_sharpes) if is_sharpes else 0
        oos_avg_sharpe = np.mean(oos_sharpes) if oos_sharpes else 0
        
        # IS-OOS相关性
        is_oos_corr = self._calculate_is_oos_correlation(
            in_sample_results,
            out_of_sample_results
        )
        
        # 性能下降
        degradation = self._calculate_degradation(is_avg_sharpe, oos_avg_sharpe)
        
        # 参数稳定性
        stability = self._calculate_parameter_stability(optimized_params)
        
        result = WalkForwardResult(
            symbol=self.data.columns[0] if len(self.data.columns) > 0 else "unknown",
            splits=splits,
            in_sample_results=in_sample_results,
            out_of_sample_results=out_of_sample_results,
            optimized_params=optimized_params,
            is_period_params=is_period_params,
            oos_period_params=oos_period_params,
            is_avg_sharpe=is_avg_sharpe,
            oos_avg_sharpe=oos_avg_sharpe,
            is_oos_correlation=is_oos_corr,
            degradation=degradation,
            stability=stability
        )
        
        logger.info(f"Walk-forward validation completed:\n"
                   f"  IS Sharpe: {is_avg_sharpe:.4f}\n"
                   f"  OOS Sharpe: {oos_avg_sharpe:.4f}\n"
                   f"  Degradation: {degradation:.2%}\n"
                   f"  Stability: {stability:.4f}")
        
        return result
    
    def _calculate_is_oos_correlation(self,
                                     is_results: List[Dict],
                                     oos_results: List[Dict]) -> float:
        """计算样本内外相关性"""
        is_sharpes = [r.get('sharpe_ratio', 0) for r in is_results]
        oos_sharpes = [r.get('sharpe_ratio', 0) for r in oos_results]
        
        if len(is_sharpes) > 1:
            return np.corrcoef(is_sharpes, oos_sharpes)[0, 1]
        return 0.0
    
    def _calculate_degradation(self, is_sharpe: float, oos_sharpe: float) -> float:
        """计算性能下降"""
        if is_sharpe > 0:
            return 1 - (oos_sharpe / is_sharpe)
        return 0.0
    
    def _calculate_parameter_stability(self, params_list: List[Dict]) -> float:
        """计算参数稳定性"""
        if not params_list or len(params_list) < 2:
            return 0.0
        
        param_values = {}
        for params in params_list:
            for key, value in params.items():
                if key not in param_values:
                    param_values[key] = []
                param_values[key].append(value)
        
        # 计算每个参数的变异系数
        cv_list = []
        for key, values in param_values.items():
            values = np.array(values)
            if np.mean(values) != 0:
                cv = np.std(values) / np.mean(values)
                cv_list.append(cv)
        
        # 稳定性 = 1 - 平均变异系数
        if cv_list:
            stability = 1 - np.mean(cv_list)
            return max(0, min(1, stability))
        return 0.0
    
    def compare_strategies(self,
                          strategy1_results: WalkForwardResult,
                          strategy2_results: WalkForwardResult,
                          metric: str = 'sharpe_ratio') -> Dict[str, Any]:
        """
        比较两个策略
        
        Args:
            strategy1_results: 策略1的走测结果
            strategy2_results: 策略2的走测结果
            metric: 比较指标
        
        Returns:
            比较结果
        """
        s1_is = [r.get(metric, 0) for r in strategy1_results.in_sample_results]
        s1_oos = [r.get(metric, 0) for r in strategy1_results.out_of_sample_results]
        
        s2_is = [r.get(metric, 0) for r in strategy2_results.in_sample_results]
        s2_oos = [r.get(metric, 0) for r in strategy2_results.out_of_sample_results]
        
        # T检验
        from scipy import stats
        
        _, p_value_oos = stats.ttest_ind(s1_oos, s2_oos)
        
        return {
            'strategy1_is_mean': np.mean(s1_is),
            'strategy1_is_std': np.std(s1_is),
            'strategy1_oos_mean': np.mean(s1_oos),
            'strategy1_oos_std': np.std(s1_oos),
            'strategy2_is_mean': np.mean(s2_is),
            'strategy2_is_std': np.std(s2_is),
            'strategy2_oos_mean': np.mean(s2_oos),
            'strategy2_oos_std': np.std(s2_oos),
            'oos_p_value': p_value_oos,
            'winner': 'strategy1' if np.mean(s1_oos) > np.mean(s2_oos) else 'strategy2'
        }
    
    def stability_check(self, result: WalkForwardResult) -> Dict[str, Any]:
        """
        稳定性检查
        
        Returns:
            稳定性检查结果
        """
        checks = {}
        
        # 1. 参数稳定性
        checks['parameter_stability'] = result.stability
        checks['parameter_stable'] = result.stability > 0.7
        
        # 2. 性能下降
        checks['degradation'] = result.degradation
        checks['degradation_acceptable'] = result.degradation < 0.3
        
        # 3. 样本内外相关性
        checks['is_oos_correlation'] = result.is_oos_correlation
        checks['correlation_good'] = result.is_oos_correlation > 0.5
        
        # 4. 一致性
        oos_sharpes = [r.get('sharpe_ratio', 0) for r in result.out_of_sample_results]
        positive_periods = sum(1 for s in oos_sharpes if s > 0)
        consistency = positive_periods / len(oos_sharpes) if oos_sharpes else 0
        
        checks['consistency'] = consistency
        checks['consistency_good'] = consistency > 0.6
        
        # 综合评分
        checks['overall_score'] = (
            0.3 * result.stability +
            0.3 * (1 - min(result.degradation, 1)) +
            0.2 * (result.is_oos_correlation if result.is_oos_correlation > 0 else 0) +
            0.2 * consistency
        )
        
        checks['is_robust'] = checks['overall_score'] > 0.6
        
        return checks


__all__ = [
    'WalkForwardValidator',
    'SplitMethod',
    'WalkForwardSplit',
    'WalkForwardResult',
]
