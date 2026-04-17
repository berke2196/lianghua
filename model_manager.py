"""
Model Manager and Evaluation Framework
Comprehensive model lifecycle management with K-fold cross-validation and A/B testing.
"""

import torch
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_auc_score, auc
)
from sklearn.model_selection import KFold

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Container for model evaluation metrics"""
    accuracy: float
    precision: float
    recall: float
    f1: float
    confusion_matrix: np.ndarray
    roc_auc: Optional[float] = None
    timestamp: str = ""
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'confusion_matrix': self.confusion_matrix.tolist(),
            'roc_auc': self.roc_auc,
            'timestamp': self.timestamp,
            'metadata': self.metadata or {}
        }


@dataclass
class ModelInfo:
    """Model metadata and configuration"""
    name: str
    model_type: str  # 'lstm', 'transformer', 'cnn_lstm', 'ppo', 'dqn', 'a3c'
    version: str
    created_at: str
    input_dim: int
    output_dim: int
    hyperparameters: Dict[str, Any]
    metrics: Optional[ModelMetrics] = None
    deployment_status: str = 'ready'  # 'ready', 'training', 'deprecated'


class ModelEvaluator:
    """Comprehensive model evaluation with multiple metrics"""
    
    def __init__(self, num_classes: int = 3):
        self.num_classes = num_classes
    
    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_probs: Optional[np.ndarray] = None
    ) -> ModelMetrics:
        """
        Evaluate model predictions
        
        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            y_probs: Prediction probabilities for AUC (one-vs-rest)
            
        Returns:
            ModelMetrics object with all evaluation metrics
        """
        # Basic metrics
        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average='weighted', zero_division=0)
        recall = recall_score(y_true, y_pred, average='weighted', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='weighted', zero_division=0)
        cm = confusion_matrix(y_true, y_pred, labels=range(self.num_classes))
        
        # ROC AUC (One-vs-Rest for multiclass)
        roc_auc = None
        if y_probs is not None and y_probs.shape[1] == self.num_classes:
            try:
                roc_auc = roc_auc_score(
                    y_true, y_probs,
                    multi_class='ovr',
                    average='weighted'
                )
            except:
                roc_auc = None
        
        return ModelMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            confusion_matrix=cm,
            roc_auc=roc_auc,
            timestamp=datetime.now().isoformat()
        )
    
    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model_fn,  # Function that returns a model
        n_splits: int = 5,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        K-fold cross-validation
        
        Args:
            X: Feature data
            y: Labels
            model_fn: Function that returns fresh model instance
            n_splits: Number of folds
            verbose: Print progress
            
        Returns:
            Cross-validation results
        """
        kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
        fold_results = []
        
        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            
            # Train model
            model = model_fn()
            # Assume model has train and predict methods
            # This is a framework for handling different model types
            
            # Get predictions
            y_pred, y_probs = model.predict(X_val)
            
            # Evaluate
            metrics = self.evaluate(y_val, y_pred, y_probs)
            fold_results.append(metrics.to_dict())
            
            if verbose:
                logger.info(f"Fold {fold+1}/{n_splits} - Accuracy: {metrics.accuracy:.4f}")
        
        # Aggregate results
        accuracies = [r['accuracy'] for r in fold_results]
        f1_scores = [r['f1'] for r in fold_results]
        
        return {
            'fold_results': fold_results,
            'mean_accuracy': np.mean(accuracies),
            'std_accuracy': np.std(accuracies),
            'mean_f1': np.mean(f1_scores),
            'std_f1': np.std(f1_scores),
            'num_folds': n_splits
        }
    
    def robustness_test(
        self,
        X: np.ndarray,
        y: np.ndarray,
        model,
        perturbation_std: float = 0.1,
        num_trials: int = 10
    ) -> Dict[str, Any]:
        """
        Test model robustness to input perturbations
        
        Args:
            X: Feature data
            y: Labels
            model: Trained model
            perturbation_std: Standard deviation of Gaussian noise
            num_trials: Number of perturbation trials
            
        Returns:
            Robustness metrics
        """
        accuracies = []
        
        # Clean predictions
        clean_pred, _ = model.predict(X)
        clean_acc = accuracy_score(y, clean_pred)
        
        for trial in range(num_trials):
            # Add Gaussian noise
            X_perturbed = X + np.random.randn(*X.shape) * perturbation_std
            
            # Predictions on perturbed data
            pred_perturbed, _ = model.predict(X_perturbed)
            acc_perturbed = accuracy_score(y, pred_perturbed)
            accuracies.append(acc_perturbed)
        
        robustness_score = np.mean([clean_acc - acc for acc in accuracies])
        
        return {
            'clean_accuracy': clean_acc,
            'mean_perturbed_accuracy': np.mean(accuracies),
            'std_perturbed_accuracy': np.std(accuracies),
            'robustness_score': robustness_score,  # Higher is more robust
            'perturbation_std': perturbation_std
        }


class ModelSelector:
    """Select best model from ensemble based on performance"""
    
    @staticmethod
    def select_by_metrics(
        models: Dict[str, ModelInfo],
        weights: Dict[str, float] = None
    ) -> str:
        """
        Select model with best weighted metrics
        
        Args:
            models: Dict of model_name -> ModelInfo
            weights: Metric weights {'accuracy': 0.4, 'f1': 0.3, ...}
            
        Returns:
            Name of best model
        """
        if weights is None:
            weights = {'f1': 0.5, 'accuracy': 0.3, 'recall': 0.2}
        
        best_score = -1
        best_model = None
        
        for name, info in models.items():
            if info.metrics is None:
                continue
            
            score = (
                weights.get('accuracy', 0) * info.metrics.accuracy +
                weights.get('precision', 0) * info.metrics.precision +
                weights.get('recall', 0) * info.metrics.recall +
                weights.get('f1', 0) * info.metrics.f1
            )
            
            if score > best_score:
                best_score = score
                best_model = name
        
        return best_model
    
    @staticmethod
    def stacking_select(
        models: Dict[str, ModelInfo],
        meta_labels: np.ndarray,
        method: str = 'voting'
    ) -> str:
        """
        Select models for stacking ensemble
        
        Args:
            models: Dict of model_name -> ModelInfo
            meta_labels: Training labels for meta-learner
            method: 'voting' or 'weighted'
            
        Returns:
            Selected model for meta-learner
        """
        if method == 'voting':
            # Majority voting on predictions
            return ModelSelector.select_by_metrics(models)
        else:
            # Weighted combination
            return ModelSelector.select_by_metrics(
                models,
                weights={'f1': 0.5, 'accuracy': 0.5}
            )


class ModelManager:
    """Central model lifecycle management"""
    
    def __init__(self, storage_path: str = 'models'):
        self.storage_path = storage_path
        self.models: Dict[str, ModelInfo] = {}
        self.evaluator = ModelEvaluator()
        self.version_history: Dict[str, List[ModelInfo]] = {}
    
    def register_model(
        self,
        name: str,
        model_type: str,
        input_dim: int,
        output_dim: int,
        hyperparameters: Dict[str, Any],
        version: str = '1.0.0'
    ) -> ModelInfo:
        """Register a new model"""
        model_info = ModelInfo(
            name=name,
            model_type=model_type,
            version=version,
            created_at=datetime.now().isoformat(),
            input_dim=input_dim,
            output_dim=output_dim,
            hyperparameters=hyperparameters
        )
        
        self.models[name] = model_info
        
        if name not in self.version_history:
            self.version_history[name] = []
        self.version_history[name].append(model_info)
        
        logger.info(f"Registered model: {name} v{version}")
        return model_info
    
    def evaluate_model(
        self,
        name: str,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_probs: Optional[np.ndarray] = None
    ) -> ModelMetrics:
        """Evaluate a registered model"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        
        metrics = self.evaluator.evaluate(y_true, y_pred, y_probs)
        self.models[name].metrics = metrics
        
        logger.info(f"Evaluated model: {name}")
        logger.info(f"  Accuracy: {metrics.accuracy:.4f}")
        logger.info(f"  F1 Score: {metrics.f1:.4f}")
        
        return metrics
    
    def get_model_info(self, name: str) -> ModelInfo:
        """Get model information"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        return self.models[name]
    
    def list_models(self) -> List[ModelInfo]:
        """List all registered models"""
        return list(self.models.values())
    
    def save_model_state(self, name: str, model: torch.nn.Module, path: str):
        """Save model state dict"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        
        torch.save(model.state_dict(), path)
        logger.info(f"Saved model state: {name} to {path}")
    
    def load_model_state(self, model: torch.nn.Module, path: str) -> torch.nn.Module:
        """Load model state dict"""
        model.load_state_dict(torch.load(path))
        logger.info(f"Loaded model state from {path}")
        return model
    
    def export_model_config(self, name: str) -> str:
        """Export model configuration as JSON"""
        if name not in self.models:
            raise ValueError(f"Model {name} not found")
        
        model_info = self.models[name]
        config = {
            'name': model_info.name,
            'model_type': model_info.model_type,
            'version': model_info.version,
            'input_dim': model_info.input_dim,
            'output_dim': model_info.output_dim,
            'hyperparameters': model_info.hyperparameters,
            'created_at': model_info.created_at
        }
        
        if model_info.metrics:
            config['metrics'] = model_info.metrics.to_dict()
        
        return json.dumps(config, indent=2)
    
    def compare_models(self, model_names: List[str]) -> Dict[str, Any]:
        """Compare multiple models"""
        comparison = {}
        
        for name in model_names:
            if name not in self.models:
                continue
            
            info = self.models[name]
            if info.metrics:
                comparison[name] = {
                    'type': info.model_type,
                    'version': info.version,
                    'accuracy': info.metrics.accuracy,
                    'f1': info.metrics.f1,
                    'precision': info.metrics.precision,
                    'recall': info.metrics.recall
                }
        
        return comparison
    
    def perform_ab_test(
        self,
        model_a: str,
        model_b: str,
        X_test: np.ndarray,
        y_test: np.ndarray,
        predictions_a: np.ndarray,
        predictions_b: np.ndarray
    ) -> Dict[str, Any]:
        """
        Perform A/B test between two models
        
        Returns:
            Statistical comparison results
        """
        acc_a = accuracy_score(y_test, predictions_a)
        acc_b = accuracy_score(y_test, predictions_b)
        
        # Simple statistical test (McNemar's test would be better)
        difference = acc_a - acc_b
        
        return {
            'model_a': model_a,
            'model_b': model_b,
            'accuracy_a': acc_a,
            'accuracy_b': acc_b,
            'difference': difference,
            'winner': model_a if acc_a > acc_b else model_b,
            'improvement': abs(difference) * 100  # Percentage
        }


class OnlineLearner:
    """Support for online incremental learning"""
    
    def __init__(self, model, batch_size: int = 32, learning_rate: float = 1e-4):
        self.model = model
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        self.criterion = torch.nn.CrossEntropyLoss()
    
    def learn_batch(self, X_batch: np.ndarray, y_batch: np.ndarray, device: torch.device):
        """Learn from a new batch of data"""
        self.model.train()
        
        X_tensor = torch.FloatTensor(X_batch).to(device)
        y_tensor = torch.LongTensor(y_batch).to(device)
        
        self.optimizer.zero_grad()
        logits, _ = self.model(X_tensor)
        loss = self.criterion(logits, y_tensor)
        loss.backward()
        
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()
        
        return loss.item()
    
    def continuous_learn(
        self,
        data_stream,  # Iterator of (X, y) batches
        num_batches: int = 100,
        device: torch.device = torch.device('cpu')
    ) -> List[float]:
        """Continuously learn from data stream"""
        losses = []
        
        for i, (X_batch, y_batch) in enumerate(data_stream):
            if i >= num_batches:
                break
            
            loss = self.learn_batch(X_batch, y_batch, device)
            losses.append(loss)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Batch {i+1}/{num_batches} - Loss: {loss:.4f}")
        
        return losses
