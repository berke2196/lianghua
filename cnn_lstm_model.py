"""
CNN-LSTM Hybrid Model
Combines convolutional feature extraction with LSTM temporal modeling.
"""

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
import numpy as np
from typing import Tuple, List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConvBlock(nn.Module):
    """Convolutional block with batch norm and activation"""
    
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
        dropout: float = 0.2
    ):
        super().__init__()
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding
        )
        self.bn = nn.BatchNorm1d(out_channels)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.conv(x)
        x = self.bn(x)
        x = self.activation(x)
        x = self.dropout(x)
        return x


class CNNEncoder(nn.Module):
    """CNN feature extractor"""
    
    def __init__(
        self,
        input_channels: int = 200,
        output_channels: int = 64,
        kernel_sizes: List[int] = None,
        dropout: float = 0.2
    ):
        super().__init__()
        
        if kernel_sizes is None:
            kernel_sizes = [3, 5, 7]
        
        # Multi-scale convolutions
        self.conv_blocks = nn.ModuleList([
            ConvBlock(input_channels, output_channels, kernel_size=k, dropout=dropout)
            for k in kernel_sizes
        ])
        
        self.output_channels = output_channels * len(kernel_sizes)
        
        # Fusion layer
        self.fusion = nn.Sequential(
            nn.Linear(self.output_channels, output_channels),
            nn.ReLU(),
            nn.Dropout(dropout)
        )
        
        self.output_channels = output_channels
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch_size, seq_len, input_channels)
        Returns:
            (batch_size, seq_len, output_channels)
        """
        # Transpose for CNN: (batch_size, channels, seq_len)
        x = x.transpose(1, 2)
        
        # Multi-scale convolutions
        conv_outputs = [conv(x) for conv in self.conv_blocks]
        
        # Concatenate along channel dimension
        x = torch.cat(conv_outputs, dim=1)
        
        # Transpose back: (batch_size, seq_len, channels)
        x = x.transpose(1, 2)
        
        # Fusion
        batch_size, seq_len, channels = x.shape
        x = x.reshape(-1, channels)
        x = self.fusion(x)
        x = x.reshape(batch_size, seq_len, -1)
        
        return x


class CNNLSTMPredictor(nn.Module):
    """
    CNN-LSTM hybrid model for time series prediction
    
    Architecture:
    - CNN layers extract spatial features using multi-scale kernels
    - LSTM layers capture temporal dependencies
    - Fusion layer combines both representations
    """
    
    def __init__(
        self,
        input_size: int = 200,
        cnn_channels: int = 64,
        lstm_hidden: int = 32,
        num_lstm_layers: int = 2,
        num_classes: int = 3,
        dropout: float = 0.2,
        bidirectional: bool = True
    ):
        super().__init__()
        
        # CNN encoder for feature extraction
        self.cnn_encoder = CNNEncoder(
            input_channels=input_size,
            output_channels=cnn_channels,
            kernel_sizes=[3, 5, 7],
            dropout=dropout
        )
        
        # LSTM for temporal modeling
        lstm_input_size = self.cnn_encoder.output_channels
        self.lstm = nn.LSTM(
            input_size=lstm_input_size,
            hidden_size=lstm_hidden,
            num_layers=num_lstm_layers,
            dropout=dropout if num_lstm_layers > 1 else 0,
            bidirectional=bidirectional,
            batch_first=True
        )
        
        # Calculate LSTM output size
        lstm_output_size = lstm_hidden * (2 if bidirectional else 1)
        
        # Fusion and classification layers
        self.fusion = nn.Sequential(
            nn.Linear(lstm_output_size, lstm_output_size // 2),
            nn.BatchNorm1d(lstm_output_size // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(lstm_output_size // 2, lstm_output_size // 4),
            nn.BatchNorm1d(lstm_output_size // 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            
            nn.Linear(lstm_output_size // 4, num_classes)
        )
        
        self.softmax = nn.Softmax(dim=1)
        self._init_weights()
    
    def _init_weights(self):
        """Xavier initialization"""
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
            x: (batch_size, seq_len, input_size)
            
        Returns:
            logits, probabilities
        """
        # CNN feature extraction
        cnn_features = self.cnn_encoder(x)
        
        # LSTM temporal modeling
        lstm_out, (h_n, c_n) = self.lstm(cnn_features)
        
        # Use last hidden state
        last_hidden = lstm_out[:, -1, :]
        
        # Classification
        logits = self.fusion(last_hidden)
        probs = self.softmax(logits)
        
        return logits, probs
    
    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        """Extract learned features without classification"""
        self.eval()
        with torch.no_grad():
            cnn_features = self.cnn_encoder(x)
            lstm_out, _ = self.lstm(cnn_features)
            return lstm_out[:, -1, :]
    
    def predict(self, x: torch.Tensor) -> Tuple[np.ndarray, np.ndarray]:
        """Predict with confidence scores"""
        self.eval()
        with torch.no_grad():
            logits, probs = self.forward(x)
        
        predictions = torch.argmax(probs, dim=1).cpu().numpy()
        probabilities = probs.cpu().numpy()
        
        return predictions, probabilities


class CNNLSTMTrainer:
    """Trainer for CNN-LSTM model"""
    
    def __init__(
        self,
        model: CNNLSTMPredictor,
        device: torch.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
        learning_rate: float = 0.001,
        weight_decay: float = 1e-5,
        class_weights: Optional[torch.Tensor] = None
    ):
        self.model = model.to(device)
        self.device = device
        
        # AdamW optimizer with weight decay
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=learning_rate,
            weight_decay=weight_decay
        )
        
        # Loss function
        if class_weights is not None:
            class_weights = class_weights.to(device)
        self.criterion = nn.CrossEntropyLoss(weight=class_weights, label_smoothing=0.1)
        
        # Learning rate scheduler
        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
            verbose=True
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
            
            self.optimizer.zero_grad()
            logits, probs = self.model(x_batch)
            loss = self.criterion(logits, y_batch)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            
            total_loss += loss.item()
            preds = torch.argmax(probs, dim=1)
            correct += (preds == y_batch).sum().item()
            total += y_batch.size(0)
        
        return {
            'loss': total_loss / len(train_loader),
            'accuracy': correct / total
        }
    
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
        
        return {
            'loss': total_loss / len(val_loader),
            'accuracy': correct / total
        }
    
    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: int = 50,
        patience: int = 10,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """Full training loop with early stopping"""
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(epochs):
            train_metrics = self.train_epoch(train_loader)
            val_metrics = self.validate(val_loader)
            
            self.training_history['train_loss'].append(train_metrics['loss'])
            self.training_history['val_loss'].append(val_metrics['loss'])
            self.training_history['train_acc'].append(train_metrics['accuracy'])
            self.training_history['val_acc'].append(val_metrics['accuracy'])
            
            # Step scheduler
            self.scheduler.step(val_metrics['loss'])
            
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
    
    def save_checkpoint(self, path: str):
        """Save model checkpoint"""
        checkpoint = {
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'history': self.training_history
        }
        torch.save(checkpoint, path)
        logger.info(f"Checkpoint saved to {path}")
    
    def load_checkpoint(self, path: str):
        """Load model checkpoint"""
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state'])
        self.training_history = checkpoint['history']
        logger.info(f"Checkpoint loaded from {path}")
