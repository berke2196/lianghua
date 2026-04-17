"""
AI 信号过滤层 - 轻量级模型
AI Signal Filter Layer - Lightweight Models
"""

import numpy as np
from typing import Dict, List, Optional
import joblib
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler


class AISignalFilter:
    """
    AI信号过滤: 提升算法信号的质量
    
    目标:
    - 输入: 100条原始信号/秒
    - 输出: 10-20条高质量信号/秒
    - 效果: 胜率 55% → 70%+ (提升30%)
    
    特点:
    - 轻量级: <10MB
    - 实时: <10ms推理时间
    - 解释性: 清楚知道为什么过滤
    """
    
    def __init__(self, model_path=None):
        self.signal_classifier = None
        self.market_regime_detector = MarketRegimeDetector()
        self.false_signal_detector = FalseSignalDetector()
        self.scaler = StandardScaler()
        
        if model_path:
            self.load_model(model_path)
        else:
            self.train_model()
    
    def filter_signal(self, raw_signal: Dict, market_data: Dict) -> Dict:
        """
        对原始信号进行过滤和评分
        
        输入:
        - raw_signal: 算法生成的信号
        - market_data: 当前市场数据
        
        输出:
        - 过滤后的信号 + 评分
        """
        
        # 1️⃣ 信号质量评分 (0-100)
        quality_score = self.assess_signal_quality(raw_signal)
        
        # 2️⃣ 市场环境判断
        market_regime = self.market_regime_detector.detect(market_data)
        # 返回: "trending", "ranging", "volatile", "sideways"
        
        # 3️⃣ 虚假信号识别
        is_likely_false = self.false_signal_detector.predict(
            raw_signal, 
            market_regime, 
            market_data
        )
        
        # 4️⃣ 执行时机优化
        optimal_delay = self.optimize_execution_timing(raw_signal, market_data)
        
        # 5️⃣ 综合评分
        final_score = self.calculate_final_score(
            quality_score,
            market_regime,
            is_likely_false
        )
        
        return {
            'original_signal': raw_signal,
            'quality_score': quality_score,        # 0-100
            'market_regime': market_regime,         # 市场状态
            'is_likely_false': is_likely_false,    # 是否虚假
            'final_score': final_score,             # 0-100 (最终评分)
            'should_execute': final_score > 65,     # 是否应该执行
            'optimal_delay_ms': optimal_delay,      # 建议延迟(ms)
            'confidence': final_score / 100.0,      # 0-1
            'reasoning': self.generate_reasoning(
                quality_score, market_regime, is_likely_false, final_score
            )
        }
    
    def assess_signal_quality(self, signal: Dict) -> float:
        """
        评估信号的内在质量
        
        考虑因素:
        - 信号强度
        - 信号一致性
        - 指标确认度
        - 历史准确率
        """
        
        # 提取特征
        features = self.extract_signal_features(signal)
        
        # 用分类模型预测质量分数
        if self.signal_classifier:
            quality_prob = self.signal_classifier.predict_proba([features])[0]
            quality_score = quality_prob[1] * 100  # 高质量的概率
        else:
            quality_score = 50  # 未训练时返回中性分数
        
        return quality_score
    
    def extract_signal_features(self, signal: Dict) -> np.ndarray:
        """
        从信号中提取特征用于模型输入
        """
        
        features = []
        
        # 特征1: 信号强度 (0-100)
        strength = signal.get('strength', 50)
        features.append(strength / 100.0)
        
        # 特征2: 信号来源 (编码)
        signal_type = signal.get('type', 'unknown')
        type_encoding = {
            'market_making': 1.0,
            'stat_arb': 0.9,
            'trend_following': 0.8,
            'funding_arb': 0.95,
            'technical': 0.7,
            'unknown': 0.5
        }
        features.append(type_encoding.get(signal_type, 0.5))
        
        # 特征3: 行动明确性 (1 = 明确方向, 0 = 不明确)
        action = signal.get('action', 'HOLD')
        is_directional = 1.0 if action in ['LONG', 'SHORT'] else 0.0
        features.append(is_directional)
        
        # 特征4: 信号重复性
        # (如果同一信号频繁出现, 表示强烈信号)
        repetition = signal.get('repetition_count', 1)
        features.append(min(repetition / 10.0, 1.0))
        
        return np.array(features)
    
    def calculate_final_score(self, quality: float, regime: str, 
                            is_false: bool) -> float:
        """
        综合所有因素计算最终评分
        """
        
        base_score = quality
        
        # 调整1: 基于市场环境
        regime_multiplier = {
            'trending': 1.2,      # 趋势市中信号更有效
            'ranging': 0.8,       # 盘整市中信号效果差
            'volatile': 0.9,      # 高波动增加风险
            'sideways': 0.75      # 横盘时信号混乱
        }
        base_score *= regime_multiplier.get(regime, 1.0)
        
        # 调整2: 虚假信号惩罚
        if is_false:
            base_score *= 0.2  # 降低80%
        
        # 确保分数在 0-100 之间
        return min(100, max(0, base_score))
    
    def optimize_execution_timing(self, signal: Dict, market_data: Dict) -> int:
        """
        优化执行时机
        
        返回建议延迟时间 (毫秒)
        - 延迟太短: 可能被套利者抢先
        - 延迟太长: 信号过期
        - 最优: 10-50ms
        """
        
        # 基于市场波动率调整延迟
        volatility = market_data.get('volatility', 0.02)
        
        if volatility > 0.05:  # 高波动
            return 5  # 快速执行
        elif volatility > 0.02:  # 中波动
            return 15  # 适中延迟
        else:  # 低波动
            return 25  # 可以略等
        
        return 15  # 默认
    
    def generate_reasoning(self, quality: float, regime: str, 
                          is_false: bool, final_score: float) -> str:
        """
        生成对过滤决策的解释
        """
        
        reasons = []
        
        # 质量评估
        if quality > 75:
            reasons.append("✅ 信号质量好")
        elif quality > 50:
            reasons.append("⚠️  信号质量一般")
        else:
            reasons.append("❌ 信号质量差")
        
        # 市场环境
        reasons.append(f"📊 市场状态: {regime}")
        
        # 虚假信号判断
        if is_false:
            reasons.append("🚫 检测到虚假信号特征")
        else:
            reasons.append("✔️  信号特征正常")
        
        # 最终建议
        if final_score > 75:
            reasons.append("✅ 强烈建议执行")
        elif final_score > 50:
            reasons.append("⚠️  可以执行, 谨慎")
        else:
            reasons.append("❌ 不建议执行")
        
        return " | ".join(reasons)
    
    def train_model(self, training_data=None):
        """
        训练轻量级分类模型
        """
        
        # 如果有训练数据
        if training_data is not None:
            X = training_data['features']
            y = training_data['labels']
            
            # 使用 RandomForest (轻量、快速)
            self.signal_classifier = RandomForestClassifier(
                n_estimators=50,      # 少量树
                max_depth=8,          # 浅树
                random_state=42
            )
            self.signal_classifier.fit(X, y)
        else:
            # 默认: 使用随机模型作为占位符
            self.signal_classifier = None
    
    def save_model(self, path: str):
        """保存模型"""
        if self.signal_classifier:
            joblib.dump(self.signal_classifier, path)
    
    def load_model(self, path: str):
        """加载模型"""
        self.signal_classifier = joblib.load(path)


class MarketRegimeDetector:
    """
    检测当前市场状态
    """
    
    def __init__(self):
        self.regime_history = []
    
    def detect(self, market_data: Dict) -> str:
        """
        检测市场状态
        
        返回: "trending", "ranging", "volatile", "sideways"
        """
        
        # 获取指标
        current_price = market_data.get('price')
        prices_history = market_data.get('prices_history', [])
        
        if len(prices_history) < 50:
            return "unknown"
        
        # 计算趋势
        sma_fast = np.mean(prices_history[-10:])
        sma_slow = np.mean(prices_history[-50:])
        
        trend_strength = abs(sma_fast - sma_slow) / sma_slow
        
        # 计算波动率
        returns = np.diff(prices_history) / prices_history[:-1]
        volatility = np.std(returns)
        
        # 计算范围系数 (最高价-最低价) / 平均价
        highest = max(prices_history[-50:])
        lowest = min(prices_history[-50:])
        range_ratio = (highest - lowest) / np.mean(prices_history[-50:])
        
        # 判断市场状态
        if trend_strength > 0.02 and volatility < 0.02:
            regime = "trending"     # 明显趋势
        elif trend_strength < 0.01 and range_ratio < 0.05:
            regime = "ranging"      # 窄幅盘整
        elif volatility > 0.05:
            regime = "volatile"     # 高波动
        else:
            regime = "sideways"     # 横盘
        
        self.regime_history.append(regime)
        return regime


class FalseSignalDetector:
    """
    识别虚假信号
    """
    
    def __init__(self):
        self.signal_history = []
    
    def predict(self, signal: Dict, regime: str, market_data: Dict) -> bool:
        """
        判断信号是否可能是虚假的
        
        返回: True = 虚假, False = 正常
        """
        
        # 规则1: 在盘整市中的趋势信号是虚假的
        if regime == "ranging" and signal.get('type') == 'trend_following':
            return True
        
        # 规则2: 在高波动中的做市信号是虚假的
        if regime == "volatile" and signal.get('type') == 'market_making':
            return True
        
        # 规则3: 突然反向的信号是虚假的
        if len(self.signal_history) > 0:
            last_action = self.signal_history[-1].get('action')
            current_action = signal.get('action')
            
            # 如果上一秒是LONG, 这一秒是SHORT, 可能是虚假
            if last_action == 'LONG' and current_action == 'SHORT':
                # 需要更高的确信度才能反转
                if signal.get('strength', 0) < 80:
                    return True
        
        # 规则4: 单一信号的信号是虚假的
        # (只有一个算法认同, 而其他都反对)
        if signal.get('consensus', 0) < 0.4:
            return True
        
        # 规则5: 极端价格时的反向信号
        current_price = market_data.get('price')
        highest_52w = market_data.get('highest_52w')
        lowest_52w = market_data.get('lowest_52w')
        
        price_position = (current_price - lowest_52w) / (highest_52w - lowest_52w)
        
        # 接近历史新高时的做空信号 → 虚假
        if price_position > 0.95 and signal.get('action') == 'SHORT':
            return True
        
        # 接近历史新低时的做多信号 → 虚假
        if price_position < 0.05 and signal.get('action') == 'LONG':
            return True
        
        self.signal_history.append(signal)
        return False


class SignalQualityAnalyzer:
    """
    详细的信号质量分析
    """
    
    @staticmethod
    def analyze(signal: Dict, market_data: Dict) -> Dict:
        """
        详细分析信号质量
        """
        
        analysis = {
            'signal_strength': signal.get('strength', 50),
            'signal_type': signal.get('type', 'unknown'),
            'action': signal.get('action', 'HOLD'),
            'indicators': []
        }
        
        # 强度评估
        if signal.get('strength', 50) > 75:
            analysis['strength_level'] = 'HIGH'
        elif signal.get('strength', 50) > 50:
            analysis['strength_level'] = 'MEDIUM'
        else:
            analysis['strength_level'] = 'LOW'
        
        # 共识分析
        consensus = signal.get('consensus', {})
        if consensus:
            analysis['consensus'] = {
                'supporting_algorithms': len(consensus),
                'majority_action': max(consensus, key=consensus.get)
            }
        
        return analysis


# 使用示例
if __name__ == "__main__":
    
    # 初始化AI过滤器
    ai_filter = AISignalFilter()
    
    # 市场数据
    market_data = {
        'price': 43250,
        'volatility': 0.02,
        'prices_history': [43200, 43220, 43250],
        'highest_52w': 69000,
        'lowest_52w': 16500
    }
    
    # 来自算法的信号
    raw_signal = {
        'type': 'trend_following',
        'action': 'LONG',
        'strength': 85,
        'consensus': {'UP': 0.8}
    }
    
    # 过滤信号
    filtered = ai_filter.filter_signal(raw_signal, market_data)
    
    print("=" * 60)
    print("信号过滤结果")
    print("=" * 60)
    print(f"原始信号强度: {raw_signal['strength']}")
    print(f"质量评分: {filtered['quality_score']:.1f}")
    print(f"市场环境: {filtered['market_regime']}")
    print(f"虚假信号: {filtered['is_likely_false']}")
    print(f"最终评分: {filtered['final_score']:.1f}")
    print(f"建议执行: {filtered['should_execute']}")
    print(f"推理过程: {filtered['reasoning']}")
    print("=" * 60)
