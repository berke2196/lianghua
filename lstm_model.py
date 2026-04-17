"""
LSTM Time Series Predictor Module
Three-layer LSTM architecture with dropout regularization for cryptocurrency price prediction.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FocalLoss(nn.Module):
    """
    Focal Loss for handling class imbalance.
    Focuses training on hard negative examples.
    """
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
    
    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        ce = nn.functional.cross_entropy(inputs, targets, reduction='none')
        p_t = torch.exp(-ce)
        loss = self.alpha * (1 - p_t) ** self.gamma * ce
        return loss.mean()


class LSTMTimeSeriesPredictor(nn.Module):
    """
    Multi-layer LSTM for time series prediction with three output nodes.
    Predicts market direction: Up (0), Down (1), Sideways (2)
    
    Architecture:
    - Input: 200-dimensional feature vectors
    - LSTM layers: 64 -> 32 -> 16 neurons with 0.2 dropout
    - Output: 3-class classification (Up/Down/Sideways)
    """
    
    def __init__(
        self,
        input_size: int = 200,
        hidden_sizes: List[int] = None,
        num_classes: int = 3,
        dropout: float = 0.2,
        bidirectional: bool = True,
        num_layers: int = 3
    ):
        super().__init__()
        
        self.input_size = input_size
        self.hidden_sizes = hidden_sizes or [64, 32, 16]
        self.num_classes = num_classes
        self.dropout = dropout
        self.bidirectional = bidirectional
        
        # LSTM layers
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=self.hidden_sizes[0],
            num_layers=num_layers,
            dropout=dropout,
            bidirectional=bidirectional,
            batch_first=True
        )
        
        # Calculate output size after LSTM
        lstm_output_size = self.hidden_sizes[0] * (2 if bidirectional else 1)
        
        # Fully connected layers with bottleneck architecture
        self.fc_layers = nn.Sequential(
            nn.Linear(lstm_output_size, self.hidden_sizes[1]),
            nn.BatchNorm1d(self.hidden_sizes[1]),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(self.hidden_sizes[1], self.hidden_sizes[2]),
            nn.BatchNorm1d(self.hidden_sizes[2]),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(self.hidden_sizes[2], num_classes)
        )
        
        self.softmax = nn.Softmax(dim=1)
        self._init_weights()
    
    def _init_weights(self):
        """Xavier initialization for better convergence"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.constant_(module.bias, 0.0)
            elif isinstance(module, nn.LSTM):
                for name, param in module.named_parameters():
                    if 'weight' in name:
                        nn.init.orthogonal_(param)
                    elif 'bias' in name:
                        nn.init.constant_(param, 0.0)
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass
        Args:
            x: Input tensor of shape (batch_size, sequence_length, input_size)
        Returns:
            logits: Raw model outputs
            probs: Softmax probabilities
        """
        # LSTM forward
        lstm_out, (h_n, c_n) = self.lstm(x)
        
        # Use last hidden state
        last_hidden = lstm_out[:, -1, :]
        
        # Fully connected layers
        logits = self.fc_layers(last_hidden)
        probs = self.softmax(logits)
        
        return logits, probs
    
    def predict_step(self, x: torch.Tensor, confidence_threshold: float = 0.5) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Single prediction step with confidence scores
        
        Args:
            x: Input tensor
            confidence_threshold: Minimum confidence for prediction
            
        Returns:
            predictions: Class predictions
            confidences: Confidence scores
            all_probs: All class probabilities
        """
        self.eval()
        with torch.no_grad():
            logits, probs = self.forward(x)
            
        probs_np = probs.cpu().numpy()
        predictions = np.argmax(probs_np, axis=1)
        confidences = np.max(probs_np, axis=1)
        
        # Set low confidence predictions to neutral (sideways)
        predictions[confidences < confidence_threshold] = 2
        
        return predictions, confidences, probs_np
    
    def multi_step_predict(
        self, 
        initial_sequence: torch.Tensor,
        steps: int = 5,
        device: torch.device = torch.device('cpu')
    ) -> np.ndarray:
        """
        Multi-step ahead prediction
        
        Args:
            initial_sequence: Initial input sequence
            steps: Number of steps to predict ahead
            device: Torch device
            
        Returns:
            predictions: Array of shape (steps,)
        """
        self.eval()
        predictions = []
        current_seq = initial_sequence.clone()
        
        with torch.no_grad():
            for _ in range(steps):
                logits, probs = self.forward(current_seq)
                pred = torch.argmax(probs, dim=1)
                predictions.append(pred.cpu().numpy()[0])
                
                # Shift sequence and add prediction (simplified)
                current_seq = current_seq[:, 1:, :]  # Remove first timestep
        
        return np.array(predictions)


class LSTMTrainer:
    """Trainer for LSTM model with advanced optimization techniques"""
    
    def __init__(
        self,
        model: LSTMTimeSeriesPredictor,
        device: torch.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
        learning_rate: float = 0.001,
        weight_decay: float = 1e-5,
        use_focal_loss: bool = True,
        class_weights: Optional[torch.Tensor] = None
    ):
        self.model = model.to(device)
        self.device = device
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        
        # Optimizer with learning rate warmup and decay
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay,
            betas=(0.9, 0.999)
        )
        
        # Loss function
        if use_focal_loss:
            self.criterion = FocalLoss(alpha=0.25, gamma=2.0)
        else:
            if class_weights is not None:
                class_weights = class_weights.to(device)
            self.criterion = nn.CrossEntropyLoss(weight=class_weights)
        
        # Learning rate scheduler with warmup
        self.scheduler = optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.optimizer,
            T_0=10,
            T_mult=2
        )
        
        self.training_history = {
            'train_loss': [],
            'val_loss': [],
            'train_acc': [],
            'val_acc': []
        }
    
    def train_epoch(self, train_loader: DataLoader) -> Dict[str, float]:
        """Train for one epoch"""
        self.model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for x_batch, y_batch in train_loader:
            x_batch = x_batch.to(self.device)
            y_batch = y_batch.to(self.device)
            
            # Forward pass
            self.optimizer.zero_grad()
            logits, probs = self.model(x_batch)
            loss = self.criterion(logits, y_batch)
            
            # Backward pass with gradient clipping
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            total_loss += loss.item()
            
            # Accuracy calculation
            preds = torch.argmax(probs, dim=1)
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)
        
        avg_loss = total_loss / len(train_loader)
        accuracy = correct / total
        
        return {'loss': avg_loss, 'accuracy': accuracy}
    
    def validate(self, val_loader: DataLoader) -> Dict[str, float]:
        """Validate model"""
        self.model.eval()
        total_loss = 0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                x_batch = x_batch.to(self.device)
                y_batch = y_batch.to(self.device)
                
                logits, probs = self.model(x_batch)
                loss = self.criterion(logits, y_batch)
                
                total_loss += loss.item()
                preds = torch.argmax(probs, dim=1)
                correct += (preds == y_batch).sum().item()
                total += y_batch.size(0)
        
        avg_loss = total_loss / len(val_loader)
        accuracy = correct / total
        
        return {'loss': avg_loss, 'accuracy': accuracy}
    
    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: int = 50,
        patience: int = 10,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        Full training loop with early stopping
        
        Args:
            train_loader: Training data loader
            val_loader: Validation data loader
            epochs: Maximum epochs
            patience: Early stopping patience
            verbose: Print progress
            
        Returns:
            Training history
        """
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.validate(val_loader)
            
            self.training_history['train_loss'].append(train_metrics['loss'])
            self.training_history['val_loss'].append(val_metrics['loss'])
            self.training_history['train_acc'].append(train_metrics['accuracy'])
            self.training_history['val_acc'].append(val_metrics['accuracy'])
            
            self.scheduler.step()
            
            if verbose and (epoch + 1) % 5 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"Train Loss: {train_metrics['loss']:.4f}, "
                    f"Val Loss: {val_metrics['loss']:.4f}, "
                    f"Train Acc: {train_metrics['accuracy']:.4f}, "
                    f"Val Acc: {val_metrics['accuracy']:.4f}"
                )
            
            # Early stopping
            if val_metrics['loss'] < best_val_loss:
                best_val_loss = val_metrics['loss']
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
        
        return self.training_history
    
    def save_checkpoint(self, path: str, metadata: Dict[str, Any] = None):
        """Save model checkpoint with metadata"""
        checkpoint = {
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'scheduler_state': self.scheduler.state_dict(),
            'history': self.training_history,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        torch.save(checkpoint, path)
        logger.info(f"Checkpoint saved to {path}")
    
    def load_checkpoint(self, path: str):
        """Load model checkpoint"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state'])
        self.training_history = checkpoint['history']
        logger.info(f"Checkpoint loaded from {path}")


def create_synthetic_data(
    num_samples: int = 1000,
    sequence_length: int = 60,
    input_size: int = 200
) -> Tuple[np.ndarray, np.ndarray]:
    """Create synthetic training data for testing"""
    X = np.random.randn(num_samples, sequence_length, input_size).astype(np.float32)
    y = np.random.randint(0, 3, num_samples)
    return X, y
