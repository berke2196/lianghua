"""
Comprehensive Unit Tests for Deep Learning Trading Models
Tests cover all models, trainers, evaluators, and the unified system.
"""

import unittest
import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset
import tempfile
import os

# Import all modules
from lstm_model import LSTMTimeSeriesPredictor, LSTMTrainer, create_synthetic_data
from transformer_model import TransformerPredictor, TransformerTrainer
from cnn_lstm_model import CNNLSTMPredictor, CNNLSTMTrainer
from rl_agent import PPOAgent, DQNAgent, A3CAgent, ReplayBuffer, Experience
from signal_fusion import (
    SignalFusionEngine, Signal, BayesianFusion,
    ConflictDetector, SignalValidator
)
from model_manager import ModelManager, ModelEvaluator, ModelSelector
from unified_model import UnifiedTradingModel


class TestLSTMModel(unittest.TestCase):
    """Test LSTM Time Series Predictor"""
    
    def setUp(self):
        self.device = torch.device('cpu')
        self.model = LSTMTimeSeriesPredictor(
            input_size=200,
            hidden_sizes=[64, 32, 16],
            num_classes=3
        ).to(self.device)
    
    def test_lstm_forward_pass(self):
        """Test LSTM forward pass"""
        batch_size = 32
        seq_length = 60
        input_size = 200
        
        X = torch.randn(batch_size, seq_length, input_size)
        logits, probs = self.model(X)
        
        self.assertEqual(logits.shape, (batch_size, 3))
        self.assertEqual(probs.shape, (batch_size, 3))
        self.assertTrue(torch.allclose(probs.sum(dim=1), torch.ones(batch_size)))
    
    def test_lstm_prediction(self):
        """Test LSTM prediction with confidence"""
        X = torch.randn(1, 60, 200)
        preds, confs, probs = self.model.predict_step(X)
        
        self.assertEqual(len(preds), 1)
        self.assertEqual(len(confs), 1)
        self.assertTrue(0 <= preds[0] <= 2)
        self.assertTrue(0.0 <= confs[0] <= 1.0)
    
    def test_lstm_multi_step(self):
        """Test multi-step prediction"""
        X = torch.randn(1, 60, 200)
        preds = self.model.multi_step_predict(X, steps=5)
        
        self.assertEqual(len(preds), 5)
        for pred in preds:
            self.assertTrue(0 <= pred <= 2)
    
    def test_lstm_training(self):
        """Test LSTM training"""
        X, y = create_synthetic_data(num_samples=100)
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=16)
        
        trainer = LSTMTrainer(self.model, device=self.device)
        metrics = trainer.train_epoch(loader)
        
        self.assertIn('loss', metrics)
        self.assertIn('accuracy', metrics)
        self.assertTrue(metrics['loss'] > 0)


class TestTransformerModel(unittest.TestCase):
    """Test Transformer Predictor"""
    
    def setUp(self):
        self.device = torch.device('cpu')
        self.model = TransformerPredictor(
            input_size=200,
            d_model=128,
            num_heads=4,
            num_layers=2,
            num_classes=3
        ).to(self.device)
    
    def test_transformer_forward_pass(self):
        """Test Transformer forward pass"""
        batch_size = 16
        seq_length = 60
        
        X = torch.randn(batch_size, seq_length, 200)
        logits, probs = self.model(X)
        
        self.assertEqual(logits.shape, (batch_size, 3))
        self.assertEqual(probs.shape, (batch_size, 3))
    
    def test_transformer_attention(self):
        """Test Transformer attention visualization"""
        X = torch.randn(1, 30, 200)
        result = self.model.predict_with_attention(X)
        
        self.assertIn('predictions', result)
        self.assertIn('probabilities', result)
        self.assertIn('attention_maps', result)
        self.assertEqual(len(result['attention_maps']), 2)  # 2 layers
    
    def test_transformer_training(self):
        """Test Transformer training"""
        X, y = create_synthetic_data(num_samples=100)
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=16)
        
        trainer = TransformerTrainer(self.model, device=self.device)
        metrics = trainer.train_epoch(loader)
        
        self.assertTrue(metrics['loss'] > 0)
        self.assertTrue(0.0 <= metrics['accuracy'] <= 1.0)


class TestCNNLSTMModel(unittest.TestCase):
    """Test CNN-LSTM Hybrid Model"""
    
    def setUp(self):
        self.device = torch.device('cpu')
        self.model = CNNLSTMPredictor(
            input_size=200,
            cnn_channels=32,
            lstm_hidden=16,
            num_classes=3
        ).to(self.device)
    
    def test_cnnlstm_forward(self):
        """Test CNN-LSTM forward pass"""
        X = torch.randn(16, 60, 200)
        logits, probs = self.model(X)
        
        self.assertEqual(logits.shape, (16, 3))
        self.assertEqual(probs.shape, (16, 3))
    
    def test_cnnlstm_feature_extraction(self):
        """Test feature extraction"""
        X = torch.randn(4, 60, 200)
        features = self.model.extract_features(X)
        
        self.assertEqual(features.shape[0], 4)
        self.assertTrue(features.shape[1] > 0)
    
    def test_cnnlstm_training(self):
        """Test training"""
        X, y = create_synthetic_data(num_samples=50)
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=8)
        
        trainer = CNNLSTMTrainer(self.model, device=self.device)
        metrics = trainer.train_epoch(loader)
        
        self.assertIn('loss', metrics)
        self.assertIn('accuracy', metrics)


class TestRLAgents(unittest.TestCase):
    """Test Reinforcement Learning Agents"""
    
    def setUp(self):
        self.device = torch.device('cpu')
        self.state_dim = 50
        self.action_dim = 3
    
    def test_ppo_agent_creation(self):
        """Test PPO agent initialization"""
        agent = PPOAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            device=self.device
        )
        self.assertIsNotNone(agent.policy_net)
        self.assertIsNotNone(agent.optimizer)
    
    def test_ppo_action_selection(self):
        """Test PPO action selection"""
        agent = PPOAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            device=self.device
        )
        state = np.random.randn(self.state_dim)
        action, log_prob = agent.select_action(state)
        
        self.assertTrue(0 <= action < self.action_dim)
        self.assertTrue(isinstance(log_prob, float))
    
    def test_dqn_agent(self):
        """Test DQN agent"""
        agent = DQNAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            device=self.device
        )
        
        state = np.random.randn(self.state_dim)
        action = agent.select_action(state, training=True)
        
        self.assertTrue(0 <= action < self.action_dim)
    
    def test_dqn_memory(self):
        """Test DQN experience replay"""
        agent = DQNAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            memory_size=100,
            device=self.device
        )
        
        # Add experiences
        for _ in range(10):
            exp = Experience(
                state=np.random.randn(self.state_dim),
                action=0,
                reward=1.0,
                next_state=np.random.randn(self.state_dim),
                done=False
            )
            agent.remember(exp)
        
        self.assertEqual(len(agent.memory), 10)
    
    def test_a3c_agent(self):
        """Test A3C agent"""
        agent = A3CAgent(
            state_dim=self.state_dim,
            action_dim=self.action_dim,
            num_workers=2,
            device=self.device
        )
        
        self.assertEqual(len(agent.workers), 2)
        self.assertIsNotNone(agent.global_network)


class TestSignalFusion(unittest.TestCase):
    """Test Signal Fusion Engine"""
    
    def setUp(self):
        self.engine = SignalFusionEngine(num_models=3)
    
    def test_signal_creation(self):
        """Test Signal object creation"""
        signal = Signal(
            model_name='lstm',
            prediction=0,
            confidence=0.8,
            timestamp=__import__('datetime').datetime.now()
        )
        self.assertEqual(signal.model_name, 'lstm')
        self.assertEqual(signal.prediction, 0)
        self.assertEqual(signal.confidence, 0.8)
    
    def test_bayesian_fusion(self):
        """Test Bayesian fusion"""
        fusion = BayesianFusion()
        signals = [
            Signal('model1', 0, 0.9, __import__('datetime').datetime.now()),
            Signal('model2', 0, 0.7, __import__('datetime').datetime.now()),
            Signal('model3', 1, 0.6, __import__('datetime').datetime.now())
        ]
        
        pred, conf, info = fusion.fuse(signals)
        self.assertTrue(0 <= pred <= 2)
        self.assertTrue(0.0 <= conf <= 1.0)
    
    def test_conflict_detection(self):
        """Test conflict detection"""
        signals = [
            Signal('m1', 0, 0.9, __import__('datetime').datetime.now()),
            Signal('m2', 0, 0.8, __import__('datetime').datetime.now()),
            Signal('m3', 2, 0.5, __import__('datetime').datetime.now())
        ]
        
        conflict = ConflictDetector.compute_conflict_score(signals)
        self.assertTrue(0.0 <= conflict <= 1.0)
    
    def test_signal_validation(self):
        """Test signal validation"""
        valid_signal = Signal('model', 0, 0.8, __import__('datetime').datetime.now())
        is_valid, msg = SignalValidator.validate_signal(valid_signal)
        self.assertTrue(is_valid)
        
        invalid_signal = Signal('model', 5, 0.8, __import__('datetime').datetime.now())
        is_valid, msg = SignalValidator.validate_signal(invalid_signal)
        self.assertFalse(is_valid)
    
    def test_fusion_engine(self):
        """Test full fusion engine"""
        signals = [
            Signal('lstm', 0, 0.85, __import__('datetime').datetime.now()),
            Signal('transformer', 0, 0.75, __import__('datetime').datetime.now()),
            Signal('cnn_lstm', 1, 0.65, __import__('datetime').datetime.now())
        ]
        
        result = self.engine.fuse_signals(signals)
        
        self.assertIn('prediction', result)
        self.assertIn('confidence', result)
        self.assertIn('conflict_score', result)


class TestModelManager(unittest.TestCase):
    """Test Model Manager and Evaluator"""
    
    def setUp(self):
        self.manager = ModelManager()
        self.evaluator = ModelEvaluator(num_classes=3)
    
    def test_model_registration(self):
        """Test model registration"""
        info = self.manager.register_model(
            name='test_lstm',
            model_type='lstm',
            input_dim=200,
            output_dim=3,
            hyperparameters={'hidden': 64}
        )
        
        self.assertEqual(info.name, 'test_lstm')
        self.assertEqual(info.model_type, 'lstm')
    
    def test_model_evaluation(self):
        """Test model evaluation"""
        y_true = np.array([0, 1, 0, 2, 1, 0, 2, 1])
        y_pred = np.array([0, 1, 0, 2, 1, 0, 2, 0])
        y_probs = np.random.rand(8, 3)
        y_probs = y_probs / y_probs.sum(axis=1, keepdims=True)
        
        metrics = self.evaluator.evaluate(y_true, y_pred, y_probs)
        
        self.assertTrue(0.0 <= metrics.accuracy <= 1.0)
        self.assertTrue(0.0 <= metrics.f1 <= 1.0)
    
    def test_model_comparison(self):
        """Test model comparison"""
        self.manager.register_model(
            'model_a', 'lstm', 200, 3, {'hidden': 64}
        )
        self.manager.register_model(
            'model_b', 'transformer', 200, 3, {'heads': 8}
        )
        
        comparison = self.manager.compare_models(['model_a', 'model_b'])
        self.assertEqual(len(comparison), 2)
    
    def test_model_export(self):
        """Test model config export"""
        self.manager.register_model(
            'export_test', 'lstm', 200, 3, {'param': 'value'}
        )
        
        config_json = self.manager.export_model_config('export_test')
        config = __import__('json').loads(config_json)
        
        self.assertEqual(config['name'], 'export_test')
        self.assertEqual(config['model_type'], 'lstm')


class TestUnifiedModel(unittest.TestCase):
    """Test Unified Trading Model"""
    
    def setUp(self):
        self.device = torch.device('cpu')
        self.unified = UnifiedTradingModel(device=self.device)
        
        # Create dummy models
        self.lstm = LSTMTimeSeriesPredictor(
            input_size=200, num_classes=3
        ).to(self.device)
        self.transformer = TransformerPredictor(
            input_size=200, d_model=128, num_classes=3
        ).to(self.device)
    
    def test_model_registration(self):
        """Test registering models"""
        self.unified.register_model('lstm', self.lstm, 'lstm', weight=0.6)
        self.unified.register_model('transformer', self.transformer, 'transformer', weight=0.4)
        
        self.assertEqual(len(self.unified.models), 2)
        self.assertEqual(self.unified.weights['lstm'], 0.6)
    
    def test_single_prediction(self):
        """Test single model prediction"""
        self.unified.register_model('lstm', self.lstm, 'lstm')
        
        X = torch.randn(1, 60, 200)
        pred, conf = self.unified.predict_single('lstm', X)
        
        self.assertTrue(0 <= pred <= 2)
        self.assertTrue(0.0 <= conf <= 1.0)
    
    def test_ensemble_prediction(self):
        """Test ensemble prediction"""
        self.unified.register_model('lstm', self.lstm, 'lstm', weight=0.6)
        self.unified.register_model('transformer', self.transformer, 'transformer', weight=0.4)
        
        X = torch.randn(1, 60, 200)
        pred, conf, metadata = self.unified.predict_ensemble(X)
        
        self.assertTrue(0 <= pred <= 2)
        self.assertTrue(0.0 <= conf <= 1.0)
        self.assertEqual(metadata['method'], 'weighted_vote')
    
    def test_unified_predict(self):
        """Test unified prediction interface"""
        self.unified.register_model('lstm', self.lstm, 'lstm')
        
        X = torch.randn(1, 60, 200)
        result = self.unified.predict(X, use_ensemble=False)
        
        self.assertTrue(0 <= result.prediction <= 2)
        self.assertTrue(0.0 <= result.confidence <= 1.0)
        self.assertTrue(0.0 <= result.risk_score <= 1.0)
    
    def test_model_deactivation(self):
        """Test model activation/deactivation"""
        self.unified.register_model('lstm', self.lstm, 'lstm')
        self.unified.deactivate_model('lstm')
        
        self.assertFalse(self.unified.models['lstm']['active'])
        
        self.unified.activate_model('lstm')
        self.assertTrue(self.unified.models['lstm']['active'])
    
    def test_feedback_update(self):
        """Test performance feedback"""
        self.unified.register_model('lstm', self.lstm, 'lstm')
        
        self.unified.update_feedback('lstm', prediction=0, actual=0)
        self.unified.update_feedback('lstm', prediction=1, actual=0)
        
        accuracies = self.unified.get_model_accuracies()
        self.assertEqual(accuracies['lstm'], 0.5)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete system"""
    
    def setUp(self):
        self.device = torch.device('cpu')
    
    def test_end_to_end_training(self):
        """Test end-to-end training pipeline"""
        # Create data
        X, y = create_synthetic_data(num_samples=100)
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.LongTensor(y)
        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=16)
        
        # Train LSTM
        model = LSTMTimeSeriesPredictor()
        trainer = LSTMTrainer(model, device=self.device)
        history = trainer.train_epoch(loader)
        
        self.assertTrue(history['loss'] > 0)
        self.assertTrue(0.0 <= history['accuracy'] <= 1.0)
    
    def test_complete_prediction_pipeline(self):
        """Test complete prediction pipeline"""
        unified = UnifiedTradingModel(device=self.device)
        
        lstm = LSTMTimeSeriesPredictor()
        transformer = TransformerPredictor()
        
        unified.register_model('lstm', lstm, 'lstm', weight=0.6)
        unified.register_model('transformer', transformer, 'transformer', weight=0.4)
        
        X = torch.randn(4, 60, 200)
        
        for i in range(4):
            x_sample = X[i:i+1]
            result = unified.predict(x_sample, use_ensemble=True)
            
            self.assertTrue(0 <= result.prediction <= 2)
            self.assertTrue(0.0 <= result.confidence <= 1.0)


def run_tests(verbose=2):
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLSTMModel))
    suite.addTests(loader.loadTestsFromTestCase(TestTransformerModel))
    suite.addTests(loader.loadTestsFromTestCase(TestCNNLSTMModel))
    suite.addTests(loader.loadTestsFromTestCase(TestRLAgents))
    suite.addTests(loader.loadTestsFromTestCase(TestSignalFusion))
    suite.addTests(loader.loadTestsFromTestCase(TestModelManager))
    suite.addTests(loader.loadTestsFromTestCase(TestUnifiedModel))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=verbose)
    result = runner.run(suite)
    
    return result


if __name__ == '__main__':
    result = run_tests(verbose=2)
    print(f"\n{'='*70}")
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success: {result.wasSuccessful()}")
    print(f"{'='*70}")
