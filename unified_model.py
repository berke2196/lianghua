"""
Unified Trading Model
Single interface combining all models with automatic selection and ensemble methods.
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result from prediction"""
    prediction: int  # 0: Up, 1: Down, 2: Sideways
    confidence: float
    timestamp: str
    model_type: str
    all_predictions: Dict[str, Tuple[int, float]]  # model_name -> (pred, conf)
    ensemble_method: str
    risk_score: float  # 0-1, higher = riskier


class UnifiedTradingModel:
    """
    Unified interface for all trading models
    Combines LSTM, Transformer, CNN-LSTM, PPO, DQN, A3C into single interface.
    Supports automatic model selection and ensemble predictions.
    """
    
    def __init__(self, device: torch.device = torch.device('cpu')):
        self.device = device
        self.models: Dict[str, Any] = {}
        self.model_types: Dict[str, str] = {}  # model_name -> type
        self.weights: Dict[str, float] = {}  # Model weights
        self.performance_history: List[Dict[str, Any]] = []
        self.prediction_history: List[PredictionResult] = []
    
    def register_model(
        self,
        name: str,
        model: Any,
        model_type: str,
        weight: float = 1.0,
        active: bool = True
    ):
        """Register a model in the unified system"""
        self.models[name] = {
            'model': model,
            'active': active,
            'created_at': datetime.now().isoformat(),
            'predictions': [],
            'correct': 0,
            'total': 0
        }
        self.model_types[name] = model_type
        self.weights[name] = weight
        
        logger.info(f"Registered model: {name} ({model_type}) with weight {weight}")
    
    def deactivate_model(self, name: str):
        """Deactivate a model temporarily"""
        if name in self.models:
            self.models[name]['active'] = False
            logger.info(f"Deactivated model: {name}")
    
    def activate_model(self, name: str):
        """Activate a model"""
        if name in self.models:
            self.models[name]['active'] = True
            logger.info(f"Activated model: {name}")
    
    def predict_single(
        self,
        name: str,
        X: torch.Tensor,
        confidence_threshold: float = 0.5
    ) -> Tuple[int, float]:
        """
        Get prediction from single model
        
        Args:
            name: Model name
            X: Input tensor
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            (prediction, confidence)
        """
        if name not in self.models or not self.models[name]['active']:
            raise ValueError(f"Model {name} not found or inactive")
        
        model = self.models[name]['model']
        model_type = self.model_types[name]
        
        model.eval()
        with torch.no_grad():
            if model_type in ['lstm', 'transformer', 'cnn_lstm']:
                logits, probs = model(X)
                pred = torch.argmax(probs, dim=1)[0].item()
                conf = probs[0, pred].item()
            else:  # RL models
                pred, conf = self._get_rl_prediction(model, X)
        
        # Apply confidence threshold
        if conf < confidence_threshold:
            pred = 2  # Default to sideways
        
        return pred, conf
    
    def _get_rl_prediction(self, model: Any, X: torch.Tensor) -> Tuple[int, float]:
        """Get prediction from RL model"""
        # RL models have different interface
        # This is a placeholder - actual implementation depends on RL model
        pred = np.random.randint(0, 3)
        conf = 0.5
        return pred, conf
    
    def predict_ensemble(
        self,
        X: torch.Tensor,
        method: str = 'weighted_vote',
        confidence_threshold: float = 0.5
    ) -> Tuple[int, float, Dict[str, Any]]:
        """
        Ensemble prediction from all active models
        
        Args:
            X: Input tensor
            method: 'weighted_vote', 'majority_vote', 'bayesian', 'stacking'
            confidence_threshold: Minimum confidence
            
        Returns:
            (prediction, confidence, metadata)
        """
        predictions = {}
        
        # Get predictions from all active models
        for name in self.models:
            if not self.models[name]['active']:
                continue
            
            try:
                pred, conf = self.predict_single(name, X, confidence_threshold)
                predictions[name] = (pred, conf)
            except Exception as e:
                logger.warning(f"Error getting prediction from {name}: {e}")
                continue
        
        if not predictions:
            raise ValueError("No active models available")
        
        # Apply ensemble method
        if method == 'weighted_vote':
            final_pred, final_conf = self._weighted_vote(predictions)
        elif method == 'majority_vote':
            final_pred, final_conf = self._majority_vote(predictions)
        elif method == 'bayesian':
            final_pred, final_conf = self._bayesian_fusion(predictions)
        elif method == 'stacking':
            final_pred, final_conf = self._stacking_fusion(predictions, X)
        else:
            final_pred, final_conf = self._weighted_vote(predictions)
        
        metadata = {
            'method': method,
            'num_models': len(predictions),
            'individual_predictions': predictions,
            'model_agreement': self._compute_agreement(predictions)
        }
        
        return final_pred, final_conf, metadata
    
    def _weighted_vote(
        self,
        predictions: Dict[str, Tuple[int, float]]
    ) -> Tuple[int, float]:
        """Weighted voting ensemble"""
        votes = np.zeros(3)
        total_weight = 0
        
        for model_name, (pred, conf) in predictions.items():
            weight = self.weights.get(model_name, 1.0)
            votes[pred] += weight * conf
            total_weight += weight
        
        if total_weight > 0:
            votes = votes / total_weight
        
        final_pred = np.argmax(votes)
        final_conf = votes[final_pred]
        
        return final_pred, final_conf
    
    def _majority_vote(
        self,
        predictions: Dict[str, Tuple[int, float]]
    ) -> Tuple[int, float]:
        """Majority voting ensemble"""
        preds = [pred for pred, _ in predictions.values()]
        confs = [conf for _, conf in predictions.values()]
        
        pred_counts = np.bincount(preds, minlength=3)
        final_pred = np.argmax(pred_counts)
        final_conf = pred_counts[final_pred] / len(preds)
        
        return final_pred, final_conf
    
    def _bayesian_fusion(
        self,
        predictions: Dict[str, Tuple[int, float]]
    ) -> Tuple[int, float]:
        """Bayesian fusion of predictions"""
        priors = np.ones(3) / 3.0
        posteriors = priors.copy()
        
        for model_name, (pred, conf) in predictions.items():
            # Likelihood
            likelihood = np.ones(3) * (1 - conf) / 2.0
            likelihood[pred] = conf
            
            # Bayesian update
            posteriors *= likelihood
        
        # Normalize
        posteriors = posteriors / (posteriors.sum() + 1e-8)
        
        final_pred = np.argmax(posteriors)
        final_conf = posteriors[final_pred]
        
        return final_pred, final_conf
    
    def _stacking_fusion(
        self,
        predictions: Dict[str, Tuple[int, float]],
        X: torch.Tensor
    ) -> Tuple[int, float]:
        """Stacking ensemble (uses weighted vote as meta-learner)"""
        # In production, would use trained meta-learner
        return self._weighted_vote(predictions)
    
    def _compute_agreement(
        self,
        predictions: Dict[str, Tuple[int, float]]
    ) -> float:
        """
        Compute model agreement (0-1)
        1 = perfect agreement, 0 = maximum disagreement
        """
        if len(predictions) < 2:
            return 1.0
        
        preds = [pred for pred, _ in predictions.values()]
        unique_preds = len(set(preds))
        
        # Agreement = 1 - (unique_predictions - 1) / (num_classes - 1)
        agreement = 1.0 - (unique_preds - 1) / 2.0
        
        return agreement
    
    def predict(
        self,
        X: torch.Tensor,
        ensemble_method: str = 'weighted_vote',
        use_ensemble: bool = True,
        confidence_threshold: float = 0.5
    ) -> PredictionResult:
        """
        Main prediction interface
        
        Args:
            X: Input tensor
            ensemble_method: Method for ensemble predictions
            use_ensemble: Whether to use ensemble or best model
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            PredictionResult object
        """
        if use_ensemble:
            pred, conf, metadata = self.predict_ensemble(
                X, ensemble_method, confidence_threshold
            )
            all_preds = metadata['individual_predictions']
        else:
            # Use best model
            best_model = self._select_best_model()
            pred, conf = self.predict_single(best_model, X, confidence_threshold)
            all_preds = {best_model: (pred, conf)}
            metadata = {'method': 'best_model', 'best_model': best_model}
        
        # Compute risk score
        risk_score = self._compute_risk_score(pred, conf, metadata)
        
        result = PredictionResult(
            prediction=pred,
            confidence=conf,
            timestamp=datetime.now().isoformat(),
            model_type='ensemble' if use_ensemble else 'single',
            all_predictions=all_preds,
            ensemble_method=ensemble_method,
            risk_score=risk_score
        )
        
        self.prediction_history.append(result)
        return result
    
    def _select_best_model(self) -> str:
        """Select model with best historical performance"""
        best_model = None
        best_accuracy = -1
        
        for name in self.models:
            if not self.models[name]['active']:
                continue
            
            stats = self.models[name]
            if stats['total'] > 0:
                accuracy = stats['correct'] / stats['total']
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_model = name
        
        return best_model or list(self.models.keys())[0]
    
    def _compute_risk_score(
        self,
        pred: int,
        conf: float,
        metadata: Dict[str, Any]
    ) -> float:
        """
        Compute risk score for the prediction
        0 = low risk, 1 = high risk
        """
        # Base risk = inverse of confidence
        risk = 1.0 - conf
        
        # Increase risk if low model agreement
        agreement = metadata.get('model_agreement', 1.0)
        risk *= (1.0 + (1.0 - agreement))
        
        # Sideways predictions are riskier
        if pred == 2:
            risk *= 1.2
        
        return min(1.0, risk)
    
    def update_feedback(
        self,
        model_name: str,
        prediction: int,
        actual: int
    ):
        """Update model performance based on actual outcome"""
        if model_name not in self.models:
            return
        
        stats = self.models[model_name]
        stats['total'] += 1
        if prediction == actual:
            stats['correct'] += 1
        
        # Track in history
        self.performance_history.append({
            'model': model_name,
            'timestamp': datetime.now().isoformat(),
            'prediction': prediction,
            'actual': actual,
            'correct': prediction == actual
        })
    
    def get_model_accuracies(self) -> Dict[str, float]:
        """Get accuracy for each model"""
        accuracies = {}
        
        for name in self.models:
            stats = self.models[name]
            if stats['total'] > 0:
                accuracies[name] = stats['correct'] / stats['total']
            else:
                accuracies[name] = 0.0
        
        return accuracies
    
    def rebalance_weights(self, method: str = 'accuracy_based'):
        """
        Dynamically rebalance model weights
        
        Args:
            method: 'accuracy_based' or 'recency_weighted'
        """
        if method == 'accuracy_based':
            accuracies = self.get_model_accuracies()
            total_acc = sum(max(acc, 0.5) for acc in accuracies.values())
            
            for name, acc in accuracies.items():
                self.weights[name] = max(acc, 0.5) / total_acc
        
        logger.info(f"Rebalanced weights: {self.weights}")
    
    def export_predictions_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Export recent predictions log"""
        return [
            {
                'timestamp': result.timestamp,
                'prediction': result.prediction,
                'confidence': result.confidence,
                'risk_score': result.risk_score,
                'ensemble_method': result.ensemble_method
            }
            for result in self.prediction_history[-limit:]
        ]
    
    def get_model_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered models"""
        info = {}
        
        for name in self.models:
            stats = self.models[name]
            accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0.0
            
            info[name] = {
                'type': self.model_types[name],
                'active': stats['active'],
                'weight': self.weights[name],
                'accuracy': accuracy,
                'predictions': stats['total'],
                'created_at': stats['created_at']
            }
        
        return info
