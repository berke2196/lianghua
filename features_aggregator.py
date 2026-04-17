"""
特征聚合器 - 收集、标准化和聚合所有指标

功能：
- 多指标聚合
- 特征标准化
- 特征选择
- 维度约简
- 特征重要性评分
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """特征配置"""
    normalize: bool = True
    handle_missing: str = 'drop'  # drop, forward_fill, mean
    outlier_method: str = 'zscore'  # zscore, iqr, none
    outlier_threshold: float = 3.0


class FeatureAggregator:
    """
    特征聚合器
    
    将多个指标聚合成统一的特征矩阵
    """

    def __init__(self, config: Optional[FeatureConfig] = None):
        """初始化聚合器"""
        self.config = config or FeatureConfig()
        self.feature_names = []
        self.feature_scalers = {}
        self.feature_means = {}
        self.feature_stds = {}

    def flatten_features(self, indicators: Dict) -> pd.DataFrame:
        """
        展平指标字典为特征矩阵
        
        Args:
            indicators: 指标字典
        
        Returns:
            特征DataFrame
        """
        features = {}
        
        for key, value in indicators.items():
            if isinstance(value, np.ndarray):
                if value.ndim == 1:
                    features[key] = value
                else:
                    logger.warning(f"跳过多维特征: {key}")
            elif isinstance(value, dict):
                # 处理嵌套字典 (如MACD、Bollinger Bands等)
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, np.ndarray) and sub_value.ndim == 1:
                        features[f'{key}_{sub_key}'] = sub_value
            elif isinstance(value, tuple):
                # 处理元组 (如某些返回多值的指标)
                for i, v in enumerate(value):
                    if isinstance(v, np.ndarray) and v.ndim == 1:
                        features[f'{key}_{i}'] = v

        df = pd.DataFrame(features)
        self.feature_names = list(df.columns)
        
        return df

    def normalize_features(self, df: pd.DataFrame, 
                          method: str = 'zscore') -> pd.DataFrame:
        """
        标准化特征
        
        Args:
            df: 特征DataFrame
            method: 标准化方法 ('zscore', 'minmax', 'robust')
        
        Returns:
            标准化后的DataFrame
        """
        df_normalized = df.copy()

        if method == 'zscore':
            for col in df.columns:
                mean = df[col].mean()
                std = df[col].std()
                self.feature_means[col] = mean
                self.feature_stds[col] = std

                if std > 0:
                    df_normalized[col] = (df[col] - mean) / std
                else:
                    df_normalized[col] = 0

        elif method == 'minmax':
            for col in df.columns:
                min_val = df[col].min()
                max_val = df[col].max()
                self.feature_scalers[col] = (min_val, max_val)

                if max_val - min_val > 0:
                    df_normalized[col] = (df[col] - min_val) / (max_val - min_val)
                else:
                    df_normalized[col] = 0.5

        elif method == 'robust':
            for col in df.columns:
                q1 = df[col].quantile(0.25)
                q3 = df[col].quantile(0.75)
                median = df[col].median()
                iqr = q3 - q1

                self.feature_scalers[col] = (median, iqr)

                if iqr > 0:
                    df_normalized[col] = (df[col] - median) / iqr
                else:
                    df_normalized[col] = 0

        return df_normalized

    def handle_missing_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        处理缺失值
        
        Args:
            df: 特征DataFrame
        
        Returns:
            处理后的DataFrame
        """
        df_clean = df.copy()

        if self.config.handle_missing == 'drop':
            df_clean = df_clean.dropna()
        elif self.config.handle_missing == 'forward_fill':
            df_clean = df_clean.fillna(method='ffill').fillna(method='bfill')
        elif self.config.handle_missing == 'mean':
            for col in df_clean.columns:
                df_clean[col].fillna(df_clean[col].mean(), inplace=True)

        return df_clean

    def remove_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        移除异常值
        
        Args:
            df: 特征DataFrame
        
        Returns:
            清理后的DataFrame
        """
        df_clean = df.copy()

        if self.config.outlier_method == 'zscore':
            z_scores = np.abs((df_clean - df_clean.mean()) / df_clean.std())
            df_clean = df_clean[np.all(z_scores < self.config.outlier_threshold, axis=1)]

        elif self.config.outlier_method == 'iqr':
            Q1 = df_clean.quantile(0.25)
            Q3 = df_clean.quantile(0.75)
            IQR = Q3 - Q1

            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            mask = (df_clean >= lower_bound) & (df_clean <= upper_bound)
            df_clean = df_clean[mask.all(axis=1)]

        return df_clean

    def remove_constant_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """移除常数特征"""
        return df.loc[:, (df.std() > 0) | (df.std().isna())]

    def remove_correlated_features(self, df: pd.DataFrame, 
                                   threshold: float = 0.95) -> Tuple[pd.DataFrame, List[str]]:
        """
        移除高度相关的特征
        
        Args:
            df: 特征DataFrame
            threshold: 相关性阈值
        
        Returns:
            (清理后的DataFrame, 移除的特征名称列表)
        """
        # 计算相关性矩阵
        corr_matrix = df.corr().abs()

        # 获取上三角矩阵
        upper = corr_matrix.where(
            np.triu(np.ones(corr_matrix.shape), k=1).astype(bool)
        )

        # 找到高度相关的特征对
        to_drop = [column for column in upper.columns if any(upper[column] > threshold)]

        # 保留指标较少的特征
        df_clean = df.drop(columns=to_drop)

        return df_clean, to_drop

    def select_top_features(self, df: pd.DataFrame, X: np.ndarray, y: np.ndarray,
                           n_features: int = 50,
                           method: str = 'variance') -> Tuple[pd.DataFrame, List[str]]:
        """
        选择最重要的特征
        
        Args:
            df: 特征DataFrame
            X: 特征矩阵
            y: 目标向量
            n_features: 选择的特征数
            method: 选择方法 ('variance', 'correlation', 'mutual_info')
        
        Returns:
            (选择后的DataFrame, 选择的特征名称列表)
        """
        selected_features = []

        if method == 'variance':
            # 基于方差的特征选择
            variances = df.var().values
            top_indices = np.argsort(variances)[-n_features:]
            selected_features = [df.columns[i] for i in top_indices]

        elif method == 'correlation':
            # 基于与目标的相关性
            correlations = []
            for col in df.columns:
                try:
                    corr = np.abs(np.corrcoef(df[col].fillna(0), y)[0, 1])
                    correlations.append(corr if np.isfinite(corr) else 0)
                except:
                    correlations.append(0)

            top_indices = np.argsort(correlations)[-n_features:]
            selected_features = [df.columns[i] for i in top_indices]

        elif method == 'mutual_info':
            # 基于互信息的特征选择
            try:
                from sklearn.feature_selection import mutual_info_regression
                mi_scores = mutual_info_regression(X, y, random_state=42)
                top_indices = np.argsort(mi_scores)[-n_features:]
                selected_features = [df.columns[i] for i in top_indices]
            except ImportError:
                logger.warning("sklearn未安装，使用方差法替代")
                return self.select_top_features(df, X, y, n_features, 'variance')

        df_selected = df[selected_features]
        return df_selected, selected_features

    def calculate_feature_importance(self, X: np.ndarray, y: np.ndarray,
                                    feature_names: List[str],
                                    model_type: str = 'tree') -> pd.DataFrame:
        """
        计算特征重要性
        
        Args:
            X: 特征矩阵
            y: 目标向量
            feature_names: 特征名称
            model_type: 模型类型 ('tree', 'permutation', 'shap')
        
        Returns:
            特征重要性DataFrame
        """
        importances = []

        if model_type == 'tree':
            try:
                from sklearn.ensemble import RandomForestRegressor
                
                rf = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
                rf.fit(X, y)
                importances = rf.feature_importances_

            except ImportError:
                logger.warning("sklearn未安装")
                return None

        elif model_type == 'permutation':
            try:
                from sklearn.inspection import permutation_importance
                from sklearn.ensemble import RandomForestRegressor

                rf = RandomForestRegressor(n_estimators=100, random_state=42)
                rf.fit(X, y)
                result = permutation_importance(rf, X, y, n_repeats=10, random_state=42)
                importances = result.importances_mean

            except ImportError:
                logger.warning("sklearn未安装")
                return None

        importance_df = pd.DataFrame({
            'feature': feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)

        return importance_df

    def aggregate(self, indicators: Dict, config: Optional[FeatureConfig] = None
                 ) -> pd.DataFrame:
        """
        完整的特征聚合流程
        
        Args:
            indicators: 指标字典
            config: 可选的配置覆盖
        
        Returns:
            处理后的特征DataFrame
        """
        if config:
            self.config = config

        # 1. 展平特征
        df = self.flatten_features(indicators)
        logger.info(f"初始特征数: {len(df.columns)}")

        # 2. 处理缺失值
        df = self.handle_missing_values(df)
        logger.info(f"处理缺失值后: {len(df)} 行")

        # 3. 移除常数特征
        initial_cols = len(df.columns)
        df = self.remove_constant_features(df)
        logger.info(f"移除 {initial_cols - len(df.columns)} 个常数特征")

        # 4. 移除高度相关特征
        initial_cols = len(df.columns)
        df, dropped = self.remove_correlated_features(df)
        logger.info(f"移除 {len(dropped)} 个高度相关特征")

        # 5. 移除异常值
        initial_rows = len(df)
        df = self.remove_outliers(df)
        logger.info(f"移除 {initial_rows - len(df)} 行异常值")

        # 6. 标准化特征
        if self.config.normalize:
            df = self.normalize_features(df)
            logger.info("特征已标准化")

        logger.info(f"最终特征数: {len(df.columns)}")

        return df


class FeatureReducer:
    """
    特征降维工具
    
    支持PCA, TSNE, UMAP等方法
    """

    @staticmethod
    def pca_reduction(X: np.ndarray, n_components: int = 50) -> Tuple[np.ndarray, object]:
        """PCA降维"""
        try:
            from sklearn.decomposition import PCA

            pca = PCA(n_components=n_components, random_state=42)
            X_reduced = pca.fit_transform(X)

            logger.info(f"PCA方差解释比: {pca.explained_variance_ratio_.sum():.4f}")

            return X_reduced, pca

        except ImportError:
            logger.error("sklearn未安装")
            return X, None

    @staticmethod
    def tsne_reduction(X: np.ndarray, n_components: int = 2,
                      perplexity: float = 30.0) -> Tuple[np.ndarray, object]:
        """t-SNE降维"""
        try:
            from sklearn.manifold import TSNE

            tsne = TSNE(n_components=n_components, perplexity=perplexity, 
                       random_state=42, n_jobs=-1)
            X_reduced = tsne.fit_transform(X)

            return X_reduced, tsne

        except ImportError:
            logger.error("sklearn未安装")
            return X, None

    @staticmethod
    def umap_reduction(X: np.ndarray, n_components: int = 2) -> Tuple[np.ndarray, object]:
        """UMAP降维"""
        try:
            import umap

            reducer = umap.UMAP(n_components=n_components, random_state=42)
            X_reduced = reducer.fit_transform(X)

            return X_reduced, reducer

        except ImportError:
            logger.error("umap-learn未安装")
            return X, None


class FeatureEngineer:
    """
    特征工程师 - 创建新的组合特征
    """

    @staticmethod
    def create_ratio_features(df: pd.DataFrame, 
                             ratios: List[Tuple[str, str]]) -> pd.DataFrame:
        """
        创建比率特征
        
        Args:
            df: 特征DataFrame
            ratios: 比率对列表 [(分子, 分母), ...]
        
        Returns:
            添加了比率特征的DataFrame
        """
        df_new = df.copy()

        for num, den in ratios:
            if num in df.columns and den in df.columns:
                with np.errstate(divide='ignore', invalid='ignore'):
                    df_new[f'{num}_ratio_{den}'] = (
                        np.where(df[den] != 0, df[num] / df[den], np.nan)
                    )

        return df_new

    @staticmethod
    def create_interaction_features(df: pd.DataFrame, 
                                   interactions: List[Tuple[str, str]]) -> pd.DataFrame:
        """
        创建交互特征
        
        Args:
            df: 特征DataFrame
            interactions: 交互对列表 [(特征1, 特征2), ...]
        
        Returns:
            添加了交互特征的DataFrame
        """
        df_new = df.copy()

        for feat1, feat2 in interactions:
            if feat1 in df.columns and feat2 in df.columns:
                df_new[f'{feat1}_x_{feat2}'] = df[feat1] * df[feat2]

        return df_new

    @staticmethod
    def create_polynomial_features(df: pd.DataFrame, 
                                  features: List[str], 
                                  degree: int = 2) -> pd.DataFrame:
        """创建多项式特征"""
        df_new = df.copy()

        for feat in features:
            if feat in df.columns:
                for d in range(2, degree + 1):
                    df_new[f'{feat}_pow_{d}'] = df[feat] ** d

        return df_new

    @staticmethod
    def create_lag_features(df: pd.DataFrame, features: List[str],
                           lags: List[int]) -> pd.DataFrame:
        """创建滞后特征"""
        df_new = df.copy()

        for feat in features:
            if feat in df.columns:
                for lag in lags:
                    df_new[f'{feat}_lag_{lag}'] = df[feat].shift(lag)

        return df_new

    @staticmethod
    def create_rolling_features(df: pd.DataFrame, features: List[str],
                               window: int = 20,
                               functions: List[str] = ['mean', 'std', 'min', 'max']) -> pd.DataFrame:
        """
        创建滚动窗口特征
        
        Args:
            df: 特征DataFrame
            features: 特征列表
            window: 窗口大小
            functions: 滚动函数列表
        
        Returns:
            添加了滚动特征的DataFrame
        """
        df_new = df.copy()

        for feat in features:
            if feat in df.columns:
                for func in functions:
                    if func == 'mean':
                        df_new[f'{feat}_rolling_mean_{window}'] = (
                            df[feat].rolling(window=window).mean()
                        )
                    elif func == 'std':
                        df_new[f'{feat}_rolling_std_{window}'] = (
                            df[feat].rolling(window=window).std()
                        )
                    elif func == 'min':
                        df_new[f'{feat}_rolling_min_{window}'] = (
                            df[feat].rolling(window=window).min()
                        )
                    elif func == 'max':
                        df_new[f'{feat}_rolling_max_{window}'] = (
                            df[feat].rolling(window=window).max()
                        )

        return df_new


if __name__ == '__main__':
    # 测试
    print("✓ 特征聚合器模块已加载")
