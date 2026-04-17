"""
Complete Examples for Deep Learning Trading Models
Demonstrates all major use cases and workflows.
"""

import torch
import numpy as np
from torch.utils.data import DataLoader, TensorDataset
from datetime import datetime, timedelta
import json

# Import all modules
from lstm_model import LSTMTimeSeriesPredictor, LSTMTrainer, create_synthetic_data
from transformer_model import TransformerPredictor, TransformerTrainer
from cnn_lstm_model import CNNLSTMPredictor, CNNLSTMTrainer
from rl_agent import PPOAgent, DQNAgent, A3CAgent
from signal_fusion import SignalFusionEngine, Signal
from model_manager import ModelManager, ModelEvaluator, OnlineLearner
from unified_model import UnifiedTradingModel


# ============================================================================
# Example 1: Single Model Training (LSTM)
# ============================================================================

def example_1_lstm_training():
    """Train and evaluate LSTM model"""
    print("\n" + "="*70)
    print("EXAMPLE 1: LSTM Training")
    print("="*70)
    
    # Create synthetic data
    X, y = create_synthetic_data(num_samples=500)
    
    # Split into train/val
    split_idx = int(0.8 * len(X))
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    # Create data loaders
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train))
    val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.LongTensor(y_val))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)
    
    # Create and train model
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = LSTMTimeSeriesPredictor(input_size=200)
    trainer = LSTMTrainer(model, device=device, learning_rate=0.001)
    
    print("Training LSTM model...")
    history = trainer.fit(
        train_loader, val_loader,
        epochs=20,
        patience=5,
        verbose=True
    )
    
    # Print results
    print(f"\nTraining Results:")
    print(f"  Final Train Loss: {history['train_loss'][-1]:.4f}")
    print(f"  Final Val Loss: {history['val_loss'][-1]:.4f}")
    print(f"  Final Train Acc: {history['train_acc'][-1]:.4f}")
    print(f"  Final Val Acc: {history['val_acc'][-1]:.4f}")
    
    return model, trainer


# ============================================================================
# Example 2: Ensemble Prediction
# ============================================================================

def example_2_ensemble_prediction():
    """Create ensemble of multiple models"""
    print("\n" + "="*70)
    print("EXAMPLE 2: Ensemble Prediction")
    print("="*70)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Create unified model
    unified = UnifiedTradingModel(device=device)
    
    # Create and register models
    lstm = LSTMTimeSeriesPredictor()
    transformer = TransformerPredictor(d_model=128, num_heads=4, num_layers=2)
    cnn_lstm = CNNLSTMPredictor()
    
    unified.register_model('lstm', lstm, 'lstm', weight=0.5)
    unified.register_model('transformer', transformer, 'transformer', weight=0.3)
    unified.register_model('cnn_lstm', cnn_lstm, 'cnn_lstm', weight=0.2)
    
    print(f"Registered {len(unified.models)} models in ensemble")
    
    # Make predictions
    X = torch.randn(8, 60, 200)  # 8 samples
    
    predictions = []
    for i in range(len(X)):
        x_sample = X[i:i+1]
        result = unified.predict(x_sample, use_ensemble=True)
        
        direction = ['Up', 'Down', 'Sideways'][result.prediction]
        predictions.append({
            'sample': i,
            'direction': direction,
            'confidence': f"{result.confidence:.2%}",
            'risk_score': f"{result.risk_score:.2f}"
        })
    
    print("\nPredictions:")
    for pred in predictions:
        print(f"  Sample {pred['sample']}: {pred['direction']} " +
              f"(Conf: {pred['confidence']}, Risk: {pred['risk_score']})")
    
    return unified, predictions


# ============================================================================
# Example 3: Cross-Validation
# ============================================================================

def example_3_cross_validation():
    """Perform K-fold cross-validation"""
    print("\n" + "="*70)
    print("EXAMPLE 3: Cross-Validation")
    print("="*70)
    
    # Create synthetic data
    X, y = create_synthetic_data(num_samples=300)
    
    # Create evaluator
    evaluator = ModelEvaluator(num_classes=3)
    
    # Perform 5-fold CV
    print("Performing 5-fold cross-validation...")
    
    def create_lstm_model():
        return LSTMTimeSeriesPredictor()
    
    cv_results = evaluator.cross_validate(
        X, y,
        model_fn=create_lstm_model,
        n_splits=5,
        verbose=True
    )
    
    print(f"\nCross-Validation Results:")
    print(f"  Mean Accuracy: {cv_results['mean_accuracy']:.4f} ± {cv_results['std_accuracy']:.4f}")
    print(f"  Mean F1 Score: {cv_results['mean_f1']:.4f} ± {cv_results['std_f1']:.4f}")
    print(f"  Number of Folds: {cv_results['num_folds']}")
    
    return cv_results


# ============================================================================
# Example 4: Signal Fusion
# ============================================================================

def example_4_signal_fusion():
    """Demonstrate signal fusion from multiple models"""
    print("\n" + "="*70)
    print("EXAMPLE 4: Signal Fusion")
    print("="*70)
    
    # Create fusion engine
    engine = SignalFusionEngine(num_models=5)
    
    # Create multiple signals from different models
    signals = [
        Signal('lstm', prediction=0, confidence=0.85, timestamp=datetime.now()),
        Signal('transformer', prediction=0, confidence=0.78, timestamp=datetime.now()),
        Signal('cnn_lstm', prediction=1, confidence=0.65, timestamp=datetime.now()),
        Signal('ppo_agent', prediction=0, confidence=0.72, timestamp=datetime.now()),
        Signal('dqn_agent', prediction=0, confidence=0.80, timestamp=datetime.now())
    ]
    
    print("\nIndividual Signals:")
    for i, sig in enumerate(signals):
        direction = ['Up', 'Down', 'Sideways'][sig.prediction]
        print(f"  {i+1}. {sig.model_name}: {direction} (Confidence: {sig.confidence:.2%})")
    
    # Fuse signals
    fusion_result = engine.fuse_signals(signals)
    
    direction = ['Up', 'Down', 'Sideways'][fusion_result['prediction']]
    print(f"\nFused Result:")
    print(f"  Direction: {direction}")
    print(f"  Confidence: {fusion_result['confidence']:.2%}")
    print(f"  Risk-Adjusted Confidence: {fusion_result['risk_adjusted_confidence']:.2%}")
    print(f"  Conflict Score: {fusion_result['conflict_score']:.2f}")
    print(f"  Number of Signals: {fusion_result['num_signals']}")
    
    return fusion_result


# ============================================================================
# Example 5: Online Learning
# ============================================================================

def example_5_online_learning():
    """Demonstrate online/incremental learning"""
    print("\n" + "="*70)
    print("EXAMPLE 5: Online Learning")
    print("="*70)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Create initial model
    model = LSTMTimeSeriesPredictor()
    learner = OnlineLearner(model, batch_size=16, learning_rate=1e-4)
    
    print("Simulating continuous learning from data stream...")
    
    # Simulate data stream with 5 batches
    losses = []
    for batch_num in range(5):
        X_batch = np.random.randn(16, 60, 200).astype(np.float32)
        y_batch = np.random.randint(0, 3, 16)
        
        loss = learner.learn_batch(X_batch, y_batch, device)
        losses.append(loss)
        
        print(f"  Batch {batch_num+1}: Loss = {loss:.4f}")
    
    print(f"\nOnline Learning Summary:")
    print(f"  Initial Loss: {losses[0]:.4f}")
    print(f"  Final Loss: {losses[-1]:.4f}")
    print(f"  Loss Improvement: {(losses[0] - losses[-1]) / losses[0] * 100:.1f}%")
    
    return model, losses


# ============================================================================
# Example 6: Model Comparison and A/B Testing
# ============================================================================

def example_6_model_comparison():
    """Compare and A/B test models"""
    print("\n" + "="*70)
    print("EXAMPLE 6: Model Comparison & A/B Testing")
    print("="*70)
    
    # Create manager
    manager = ModelManager()
    evaluator = ModelEvaluator()
    
    # Register models
    manager.register_model('lstm', 'lstm', 200, 3, {'hidden': 64})
    manager.register_model('transformer', 'transformer', 200, 3, {'heads': 8})
    manager.register_model('cnn_lstm', 'cnn_lstm', 200, 3, {'channels': 32})
    
    # Create synthetic predictions
    np.random.seed(42)
    y_true = np.random.randint(0, 3, 100)
    
    # LSTM predictions (slightly better)
    y_lstm = y_true.copy()
    y_lstm[np.random.rand(100) < 0.35] = np.random.randint(0, 3, np.sum(np.random.rand(100) < 0.35))
    
    # Transformer predictions (best)
    y_transformer = y_true.copy()
    y_transformer[np.random.rand(100) < 0.32] = np.random.randint(0, 3, np.sum(np.random.rand(100) < 0.32))
    
    # CNN-LSTM predictions
    y_cnn_lstm = y_true.copy()
    y_cnn_lstm[np.random.rand(100) < 0.37] = np.random.randint(0, 3, np.sum(np.random.rand(100) < 0.37))
    
    # Evaluate models
    manager.evaluate_model('lstm', y_true, y_lstm)
    manager.evaluate_model('transformer', y_true, y_transformer)
    manager.evaluate_model('cnn_lstm', y_true, y_cnn_lstm)
    
    # Compare
    comparison = manager.compare_models(['lstm', 'transformer', 'cnn_lstm'])
    
    print("\nModel Comparison:")
    for model_name, metrics in comparison.items():
        print(f"\n  {model_name.upper()}:")
        print(f"    Type: {metrics['type']}")
        print(f"    Accuracy: {metrics['accuracy']:.4f}")
        print(f"    F1 Score: {metrics['f1']:.4f}")
        print(f"    Precision: {metrics['precision']:.4f}")
        print(f"    Recall: {metrics['recall']:.4f}")
    
    # A/B test
    ab_result = manager.perform_ab_test(
        'lstm', 'transformer',
        np.random.randn(50, 60, 200),
        y_true[:50],
        y_lstm[:50],
        y_transformer[:50]
    )
    
    print(f"\n\nA/B Test Results:")
    print(f"  Model A (lstm): {ab_result['accuracy_a']:.4f}")
    print(f"  Model B (transformer): {ab_result['accuracy_b']:.4f}")
    print(f"  Winner: {ab_result['winner']}")
    print(f"  Improvement: {ab_result['improvement']:.2f}%")
    
    return manager, comparison, ab_result


# ============================================================================
# Example 7: Reinforcement Learning Agent
# ============================================================================

def example_7_rl_agent():
    """Demonstrate RL agent training"""
    print("\n" + "="*70)
    print("EXAMPLE 7: Reinforcement Learning Agent")
    print("="*70)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Create PPO agent
    agent = PPOAgent(
        state_dim=50,
        action_dim=3,
        learning_rate=3e-4,
        device=device
    )
    
    print("Simulating PPO agent trading...")
    
    # Simulate trading episodes
    episode_rewards = []
    for episode in range(5):
        state = np.random.randn(50)
        episode_reward = 0
        
        for step in range(10):
            # Agent selects action
            action, log_prob = agent.select_action(state)
            
            # Simulate environment
            reward = np.random.randn() + (0.1 if action == 0 else -0.1)
            next_state = np.random.randn(50)
            
            episode_reward += reward
            state = next_state
        
        episode_rewards.append(episode_reward)
        print(f"  Episode {episode+1}: Reward = {episode_reward:.2f}")
    
    print(f"\nPPO Agent Summary:")
    print(f"  Average Episode Reward: {np.mean(episode_rewards):.2f}")
    print(f"  Std Dev: {np.std(episode_rewards):.2f}")
    
    return agent, episode_rewards


# ============================================================================
# Example 8: Complete Trading Pipeline
# ============================================================================

def example_8_complete_pipeline():
    """Full end-to-end trading prediction pipeline"""
    print("\n" + "="*70)
    print("EXAMPLE 8: Complete Trading Pipeline")
    print("="*70)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    # Step 1: Create data
    print("\nStep 1: Preparing data...")
    X_train, y_train = create_synthetic_data(num_samples=400)
    X_test, y_test = create_synthetic_data(num_samples=100)
    
    # Step 2: Train models
    print("Step 2: Training models...")
    
    lstm = LSTMTimeSeriesPredictor()
    transformer = TransformerPredictor(d_model=128, num_heads=4, num_layers=2)
    
    # Prepare data loaders
    train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.LongTensor(y_train))
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    test_dataset = TensorDataset(torch.FloatTensor(X_test), torch.LongTensor(y_test))
    test_loader = DataLoader(test_dataset, batch_size=32)
    
    # Train LSTM
    lstm_trainer = LSTMTrainer(lstm, device=device)
    lstm_trainer.train_epoch(train_loader)
    
    # Train Transformer
    transformer_trainer = TransformerTrainer(transformer, device=device)
    transformer_trainer.train_epoch(train_loader)
    
    # Step 3: Create ensemble
    print("Step 3: Creating ensemble...")
    unified = UnifiedTradingModel(device=device)
    unified.register_model('lstm', lstm, 'lstm', weight=0.5)
    unified.register_model('transformer', transformer, 'transformer', weight=0.5)
    
    # Step 4: Make predictions
    print("Step 4: Making predictions on test set...")
    
    correct_predictions = 0
    total_predictions = 0
    predictions_log = []
    
    for X_batch, y_batch in test_loader:
        for i in range(len(X_batch)):
            x_sample = X_batch[i:i+1]
            result = unified.predict(x_sample, use_ensemble=True)
            
            # Log prediction
            predictions_log.append({
                'true': y_batch[i].item(),
                'predicted': result.prediction,
                'confidence': float(result.confidence),
                'risk_score': float(result.risk_score)
            })
            
            if result.prediction == y_batch[i].item():
                correct_predictions += 1
            total_predictions += 1
    
    # Step 5: Evaluate
    print("Step 5: Evaluating results...")
    
    accuracy = correct_predictions / total_predictions
    print(f"\nFinal Results:")
    print(f"  Overall Accuracy: {accuracy:.2%}")
    print(f"  Correct Predictions: {correct_predictions}/{total_predictions}")
    print(f"  Number of Models: {len(unified.models)}")
    
    model_accuracies = unified.get_model_accuracies()
    print(f"\n  Individual Model Accuracies:")
    for model_name, acc in model_accuracies.items():
        print(f"    {model_name}: {acc:.2%}")
    
    return unified, predictions_log, accuracy


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Run all examples"""
    print("\n" + "="*70)
    print("DEEP LEARNING TRADING MODELS - COMPLETE EXAMPLES")
    print("="*70)
    
    try:
        # Run examples
        model1, trainer1 = example_1_lstm_training()
        unified, preds = example_2_ensemble_prediction()
        cv_results = example_3_cross_validation()
        fusion_result = example_4_signal_fusion()
        model_online, losses = example_5_online_learning()
        manager, comparison, ab_result = example_6_model_comparison()
        agent, rewards = example_7_rl_agent()
        unified_final, pred_log, final_accuracy = example_8_complete_pipeline()
        
        # Summary
        print("\n" + "="*70)
        print("EXECUTION SUMMARY")
        print("="*70)
        print("\nAll examples completed successfully!")
        print("\nResults:")
        print(f"  Example 1 (LSTM): Training completed")
        print(f"  Example 2 (Ensemble): {len(preds)} predictions made")
        print(f"  Example 3 (CV): Mean accuracy: {cv_results['mean_accuracy']:.4f}")
        print(f"  Example 4 (Fusion): Fused prediction direction: {fusion_result['prediction']}")
        print(f"  Example 5 (Online): Loss reduced by {(losses[0] - losses[-1]) / losses[0] * 100:.1f}%")
        print(f"  Example 6 (AB Test): {ab_result['winner']} is better")
        print(f"  Example 7 (RL): Average reward: {np.mean(rewards):.2f}")
        print(f"  Example 8 (Full): Final accuracy: {final_accuracy:.2%}")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
