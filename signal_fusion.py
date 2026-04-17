"""
Signal Fusion Engine
Intelligent fusion of multiple model predictions with dynamic weighting.
"""

import numpy as np
import torch
import torch.nn as nn
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Individual model signal"""
    model_name: str
    prediction: int  # 0: Up, 1: Down, 2: Sideways
    confidence: float  # 0.0-1.0
    timestamp: datetime
    metadata: Dict[str, Any] = None


class DynamicWeighter(nn.Module):
    """Neural network-based learnable weight generator"""
    
    def __init__(self, input_dim: int, hidden_dim: int = 64, num_models: int = 5):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, num_models),
            nn.Softmax(dim=-1)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input features (batch_size, input_dim)
        Returns:
            weights: (batch_size, num_models)
        """
        return self.network(x)


class BayesianFusion:
    """Bayesian fusion of predictions"""
    
    def __init__(self, num_classes: int = 3):
        self.num_classes = num_classes
        self.class_priors = np.ones(num_classes) / num_classes
    
    def fuse(self, signals: List[Signal]) -> Tuple[int, float, Dict[str, Any]]:
        """
        Bayesian fusion of signals
        
        Args:
            signals: List of Signal objects
            
        Returns:
            prediction: Fused class
            confidence: Fusion confidence
            fusion_info: Debug information
        """
        if not signals:
            return 2, 0.5, {}
        
        # Initialize posterior as prior
        posteriors = self.class_priors.copy()
        
        # Update with each signal (likelihood)
        for signal in signals:
            # Likelihood: confidence for predicted class, (1-confidence)/(num_classes-1) for others
            likelihood = np.ones(self.num_classes) * (1 - signal.confidence) / (self.num_classes - 1)
            likelihood[signal.prediction] = signal.confidence
            
            # Bayesian update
            posteriors *= likelihood
        
        # Normalize
        posteriors = posteriors / (posteriors.sum() + 1e-8)
        
        prediction = np.argmax(posteriors)
        confidence = posteriors[prediction]
        
        return prediction, confidence, {
            'posteriors': posteriors,
            'num_signals': len(signals)
        }


class ConflictDetector:
    """Detect conflicts between signals"""
    
    @staticmethod
    def compute_conflict_score(signals: List[Signal]) -> float:
        """
        Compute conflict level (0: no conflict, 1: maximum conflict)
        
        Based on prediction variance and confidence distribution.
        """
        if len(signals) < 2:
            return 0.0
        
        predictions = np.array([s.prediction for s in signals])
        confidences = np.array([s.confidence for s in signals])
        
        # Prediction disagreement
        unique_predictions = len(np.unique(predictions))
        prediction_conflict = (unique_predictions - 1) / 2.0
        
        # Confidence variance
        confidence_variance = confidences.std() / (confidences.mean() + 1e-8)
        
        # Combined conflict score
        conflict_score = (prediction_conflict + confidence_variance) / 2.0
        
        return min(1.0, conflict_score)
    
    @staticmethod
    def resolve_conflict(
        signals: List[Signal],
        resolution_method: str = 'confidence_weighted'
    ) -> Tuple[int, float]:
        """
        Resolve conflicts between signals
        
        Methods:
        - confidence_weighted: Use confidence as weights
        - majority_vote: Simple majority voting
        - entropy_minimization: Choose prediction with minimum entropy
        """
        if resolution_method == 'confidence_weighted':
            predictions = [s.prediction for s in signals]
            confidences = [s.confidence for s in signals]
            
            weighted_votes = np.zeros(3)
            for pred, conf in zip(predictions, confidences):
                weighted_votes[pred] += conf
            
            final_pred = np.argmax(weighted_votes)
            final_conf = weighted_votes[final_pred] / sum(confidences)
            
            return final_pred, final_conf
        
        elif resolution_method == 'majority_vote':
            predictions = [s.prediction for s in signals]
            pred_counts = np.bincount(predictions, minlength=3)
            final_pred = np.argmax(pred_counts)
            final_conf = pred_counts[final_pred] / len(signals)
            
            return final_pred, final_conf
        
        else:  # entropy_minimization
            return ConflictDetector.resolve_conflict(signals, 'confidence_weighted')


class MultiTimeframeFusion:
    """Fuse predictions from multiple timeframes"""
    
    def __init__(self, timeframe_weights: Dict[str, float] = None):
        """
        Args:
            timeframe_weights: Weights for each timeframe
                e.g., {'1m': 0.1, '5m': 0.2, '1h': 0.4, '1d': 0.3}
        """
        self.timeframe_weights = timeframe_weights or {
            '1m': 0.1,
            '5m': 0.15,
            '15m': 0.2,
            '1h': 0.3,
            '4h': 0.15,
            '1d': 0.1
        }
    
    def fuse(self, predictions: Dict[str, Tuple[int, float]]) -> Tuple[int, float]:
        """
        Fuse predictions from multiple timeframes
        
        Args:
            predictions: Dict mapping timeframe -> (prediction, confidence)
            
        Returns:
            fused_prediction, fused_confidence
        """
        weighted_votes = np.zeros(3)
        total_weight = 0
        
        for timeframe, (pred, conf) in predictions.items():
            weight = self.timeframe_weights.get(timeframe, 0.1)
            weighted_votes[pred] += weight * conf
            total_weight += weight
        
        weighted_votes = weighted_votes / (total_weight + 1e-8)
        
        fused_pred = np.argmax(weighted_votes)
        fused_conf = weighted_votes[fused_pred]
        
        return fused_pred, fused_conf


class SignalFusionEngine:
    """
    Main signal fusion engine combining all fusion methods
    """
    
    def __init__(
        self,
        num_models: int = 5,
        fusion_method: str = 'bayesian',
        enable_conflict_detection: bool = True,
        enable_dynamic_weighting: bool = True
    ):
        self.num_models = num_models
        self.fusion_method = fusion_method
        self.enable_conflict_detection = enable_conflict_detection
        self.enable_dynamic_weighting = enable_dynamic_weighting
        
        # Fusion strategies
        self.bayesian_fusion = BayesianFusion()
        self.conflict_detector = ConflictDetector()
        self.mtf_fusion = MultiTimeframeFusion()
        
        # Learnable weights (if enabled)
        if enable_dynamic_weighting:
            self.weight_generator = DynamicWeighter(
                input_dim=50,  # Feature dimension
                hidden_dim=64,
                num_models=num_models
            )
        else:
            self.weight_generator = None
        
        # Historical performance tracking
        self.signal_history = []
        self.performance_metrics = {
            model_id: {'correct': 0, 'total': 0}
            for model_id in range(num_models)
        }
    
    def fuse_signals(
        self,
        signals: List[Signal],
        features: Optional[torch.Tensor] = None,
        method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main fusion method combining multiple signals
        
        Args:
            signals: List of Signal objects from different models
            features: Optional feature vector for dynamic weighting
            method: Override default fusion method
            
        Returns:
            Fusion result with prediction, confidence, and metadata
        """
        method = method or self.fusion_method
        
        if not signals:
            return {
                'prediction': 2,
                'confidence': 0.0,
                'signals': [],
                'warning': 'No signals provided'
            }
        
        # Detect conflicts
        conflict_score = 0.0
        if self.enable_conflict_detection and len(signals) > 1:
            conflict_score = self.conflict_detector.compute_conflict_score(signals)
        
        # Get adaptive weights
        weights = self._get_adaptive_weights(signals, features)
        
        # Apply weights to signals
        weighted_signals = self._apply_weights(signals, weights)
        
        # Fuse based on selected method
        if method == 'bayesian':
            prediction, confidence, fusion_info = self.bayesian_fusion.fuse(weighted_signals)
        elif method == 'majority_vote':
            prediction, confidence = self.conflict_detector.resolve_conflict(
                weighted_signals,
                'majority_vote'
            )
            fusion_info = {}
        elif method == 'neural':
            prediction, confidence = self._neural_fusion(weighted_signals)
            fusion_info = {}
        else:
            prediction, confidence, fusion_info = self.bayesian_fusion.fuse(weighted_signals)
        
        # Risk adjustment
        risk_adjustment = self._compute_risk_adjustment(signals, confidence, conflict_score)
        
        result = {
            'prediction': prediction,
            'confidence': confidence,
            'risk_adjusted_confidence': confidence * risk_adjustment,
            'conflict_score': conflict_score,
            'weights': weights,
            'num_signals': len(signals),
            'fusion_info': fusion_info,
            'signals': [(s.model_name, s.prediction, s.confidence) for s in signals],
            'timestamp': datetime.now().isoformat()
        }
        
        # Store in history
        self.signal_history.append(result)
        
        return result
    
    def _get_adaptive_weights(
        self,
        signals: List[Signal],
        features: Optional[torch.Tensor] = None
    ) -> np.ndarray:
        """Get adaptive weights based on confidence and performance"""
        if self.weight_generator is None or features is None:
            # Static weighting based on confidence
            confidences = np.array([s.confidence for s in signals])
            weights = confidences / (confidences.sum() + 1e-8)
            return weights
        
        # Dynamic weighting using neural network
        with torch.no_grad():
            weights = self.weight_generator(features)
        
        return weights.cpu().numpy().flatten()
    
    def _apply_weights(
        self,
        signals: List[Signal],
        weights: np.ndarray
    ) -> List[Signal]:
        """Apply weights to signals by adjusting confidence"""
        weighted_signals = []
        for signal, weight in zip(signals, weights):
            weighted_signal = Signal(
                model_name=signal.model_name,
                prediction=signal.prediction,
                confidence=signal.confidence * weight,
                timestamp=signal.timestamp,
                metadata=signal.metadata
            )
            weighted_signals.append(weighted_signal)
        
        return weighted_signals
    
    def _neural_fusion(self, signals: List[Signal]) -> Tuple[int, float]:
        """Neural network-based fusion (placeholder)"""
        # In production, would use trained neural network
        predictions = [s.prediction for s in signals]
        confidences = [s.confidence for s in signals]
        
        pred_scores = np.zeros(3)
        for pred, conf in zip(predictions, confidences):
            pred_scores[pred] += conf
        
        final_pred = np.argmax(pred_scores)
        final_conf = pred_scores[final_pred] / (sum(confidences) + 1e-8)
        
        return final_pred, final_conf
    
    def _compute_risk_adjustment(
        self,
        signals: List[Signal],
        confidence: float,
        conflict_score: float
    ) -> float:
        """
        Compute risk adjustment factor
        Lower values mean higher risk
        """
        # Base adjustment
        adjustment = 1.0
        
        # Reduce confidence if high conflict
        adjustment *= (1.0 - conflict_score * 0.3)
        
        # Reduce if few signals
        adjustment *= (min(len(signals), 5) / 5.0)
        
        # Reduce if base confidence is low
        adjustment *= max(0.5, confidence)
        
        return np.clip(adjustment, 0.3, 1.0)
    
    def update_performance(self, model_id: int, prediction: int, actual: int):
        """Update model performance metrics"""
        self.performance_metrics[model_id]['total'] += 1
        if prediction == actual:
            self.performance_metrics[model_id]['correct'] += 1
    
    def get_model_accuracies(self) -> Dict[int, float]:
        """Get accuracy for each model"""
        accuracies = {}
        for model_id, metrics in self.performance_metrics.items():
            if metrics['total'] > 0:
                accuracies[model_id] = metrics['correct'] / metrics['total']
            else:
                accuracies[model_id] = 0.5  # Default neutral
        
        return accuracies
    
    def reset_performance_metrics(self):
        """Reset all performance metrics"""
        for model_id in self.performance_metrics:
            self.performance_metrics[model_id] = {'correct': 0, 'total': 0}


class SignalValidator:
    """Validate signals for quality and anomalies"""
    
    @staticmethod
    def validate_signal(signal: Signal) -> Tuple[bool, str]:
        """
        Validate a signal
        
        Returns:
            (is_valid, reason)
        """
        # Check prediction is valid
        if signal.prediction not in [0, 1, 2]:
            return False, f"Invalid prediction: {signal.prediction}"
        
        # Check confidence in valid range
        if not (0.0 <= signal.confidence <= 1.0):
            return False, f"Invalid confidence: {signal.confidence}"
        
        # Check model name is not empty
        if not signal.model_name:
            return False, "Empty model name"
        
        return True, "Valid"
    
    @staticmethod
    def detect_anomalies(signals: List[Signal]) -> List[Tuple[int, str]]:
        """
        Detect anomalous signals
        
        Returns:
            List of (signal_index, anomaly_type)
        """
        anomalies = []
        
        if len(signals) < 2:
            return anomalies
        
        confidences = np.array([s.confidence for s in signals])
        
        # Detect outlier confidences
        mean_conf = confidences.mean()
        std_conf = confidences.std()
        
        for i, sig in enumerate(signals):
            if abs(sig.confidence - mean_conf) > 2 * std_conf:
                anomalies.append((i, 'outlier_confidence'))
        
        return anomalies
