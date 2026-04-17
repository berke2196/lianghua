"""
Reinforcement Learning Trading Agents
PPO, DQN, and A3C implementations for trading strategy learning.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from torch.distributions import Categorical
from torch.utils.data import DataLoader
import numpy as np
from collections import deque
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """Single RL experience"""
    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    log_prob: float = 0.0
    value: float = 0.0


class ReplayBuffer:
    """Prioritized experience replay buffer"""
    
    def __init__(self, capacity: int = 100000):
        self.capacity = capacity
        self.buffer = deque(maxlen=capacity)
        self.priorities = deque(maxlen=capacity)
    
    def add(self, experience: Experience, priority: float = 1.0):
        """Add experience with priority"""
        self.buffer.append(experience)
        self.priorities.append(priority)
    
    def sample(self, batch_size: int) -> List[Experience]:
        """Sample batch with prioritization"""
        if len(self.buffer) == 0:
            return []
        
        # Normalize priorities
        priorities = np.array(list(self.priorities), dtype=np.float32)
        priorities = priorities / priorities.sum()
        
        # Sample indices based on priorities
        indices = np.random.choice(
            len(self.buffer),
            size=min(batch_size, len(self.buffer)),
            p=priorities,
            replace=False
        )
        
        return [self.buffer[i] for i in indices]
    
    def __len__(self):
        return len(self.buffer)


class PolicyNetwork(nn.Module):
    """Actor network for policy gradient methods"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        hidden_dims: List[int] = None,
        dropout: float = 0.2
    ):
        super().__init__()
        
        if hidden_dims is None:
            hidden_dims = [256, 128]
        
        layers = []
        prev_dim = state_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        self.network = nn.Sequential(*layers)
        
        # Policy head (action distribution)
        self.policy_head = nn.Linear(prev_dim, action_dim)
        
        # Value head (state value)
        self.value_head = nn.Linear(prev_dim, 1)
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns policy logits and state value
        """
        features = self.network(state)
        action_logits = self.policy_head(features)
        state_value = self.value_head(features).squeeze(-1)
        return action_logits, state_value


class ValueNetwork(nn.Module):
    """Critic network for value-based methods"""
    
    def __init__(
        self,
        state_dim: int,
        hidden_dims: List[int] = None,
        dropout: float = 0.2
    ):
        super().__init__()
        
        if hidden_dims is None:
            hidden_dims = [256, 128]
        
        layers = []
        prev_dim = state_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim
        
        self.network = nn.Sequential(*layers)
        self.value_head = nn.Linear(prev_dim, 1)
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        features = self.network(state)
        return self.value_head(features).squeeze(-1)


class PPOAgent:
    """
    Proximal Policy Optimization Agent
    Actor-Critic architecture with clipped surrogate loss and GAE.
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        learning_rate: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_ratio: float = 0.2,
        entropy_coef: float = 0.01,
        value_coef: float = 0.5,
        max_grad_norm: float = 0.5,
        device: torch.device = torch.device('cpu')
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device
        
        # Hyperparameters
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_ratio = clip_ratio
        self.entropy_coef = entropy_coef
        self.value_coef = value_coef
        self.max_grad_norm = max_grad_norm
        
        # Networks
        self.policy_net = PolicyNetwork(state_dim, action_dim).to(device)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=learning_rate)
        
        # Experience storage
        self.experiences = []
    
    def select_action(
        self,
        state: np.ndarray,
        deterministic: bool = False
    ) -> Tuple[int, float]:
        """Select action based on policy"""
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            action_logits, value = self.policy_net(state_tensor)
        
        if deterministic:
            action = torch.argmax(action_logits, dim=1).item()
            log_prob = 0.0
        else:
            dist = Categorical(logits=action_logits)
            action = dist.sample().item()
            log_prob = dist.log_prob(torch.tensor(action, device=self.device)).item()
        
        return action, log_prob
    
    def compute_gae(
        self,
        rewards: List[float],
        values: List[float],
        dones: List[bool],
        next_value: float = 0.0
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute Generalized Advantage Estimation"""
        advantages = []
        gae = 0
        
        values = values + [next_value]
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_non_terminal = 1.0 if not dones[t] else 0.0
            else:
                next_non_terminal = 1.0
            
            delta = rewards[t] + self.gamma * values[t + 1] * next_non_terminal - values[t]
            gae = delta + self.gamma * self.gae_lambda * next_non_terminal * gae
            advantages.insert(0, gae)
        
        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = advantages + torch.FloatTensor(values[:-1]).to(self.device)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return advantages, returns
    
    def update(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        old_log_probs: torch.Tensor,
        advantages: torch.Tensor,
        returns: torch.Tensor,
        epochs: int = 3
    ):
        """PPO update step with clipped surrogate loss"""
        for _ in range(epochs):
            action_logits, values = self.policy_net(states)
            
            # New log probabilities
            dist = Categorical(logits=action_logits)
            new_log_probs = dist.log_prob(actions)
            
            # Probability ratio
            ratio = torch.exp(new_log_probs - old_log_probs)
            
            # Clipped surrogate loss
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            
            # Value loss
            value_loss = F.smooth_l1_loss(values, returns)
            
            # Entropy bonus
            entropy = dist.entropy().mean()
            
            # Total loss
            loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy
            
            # Optimization step
            self.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), self.max_grad_norm)
            self.optimizer.step()


class DQNAgent:
    """
    Deep Q-Network Agent
    Double DQN with dueling architecture and prioritized experience replay.
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        learning_rate: float = 1e-4,
        gamma: float = 0.99,
        epsilon: float = 1.0,
        epsilon_decay: float = 0.995,
        epsilon_min: float = 0.01,
        target_update_freq: int = 1000,
        memory_size: int = 100000,
        device: torch.device = torch.device('cpu')
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device
        
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_decay = epsilon_decay
        self.epsilon_min = epsilon_min
        self.target_update_freq = target_update_freq
        self.update_count = 0
        
        # Q-networks
        self.q_network = self._build_network().to(device)
        self.target_network = self._build_network().to(device)
        self.target_network.load_state_dict(self.q_network.state_dict())
        
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=learning_rate)
        self.criterion = nn.SmoothL1Loss()
        
        # Experience replay
        self.memory = ReplayBuffer(memory_size)
    
    def _build_network(self) -> nn.Module:
        """Build dueling DQN network"""
        return nn.Sequential(
            nn.Linear(self.state_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, self.action_dim + 1)  # +1 for advantage stream aggregation
        )
    
    def select_action(self, state: np.ndarray, training: bool = True) -> int:
        """Select action with epsilon-greedy policy"""
        if training and np.random.random() < self.epsilon:
            return np.random.randint(0, self.action_dim)
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self.q_network(state_tensor)
        
        return torch.argmax(q_values, dim=1).item()
    
    def update(self, batch_size: int = 32):
        """Update Q-network using prioritized replay"""
        if len(self.memory) < batch_size:
            return
        
        # Sample batch
        experiences = self.memory.sample(batch_size)
        
        states = torch.FloatTensor(np.array([e.state for e in experiences])).to(self.device)
        actions = torch.LongTensor([e.action for e in experiences]).to(self.device)
        rewards = torch.FloatTensor([e.reward for e in experiences]).to(self.device)
        next_states = torch.FloatTensor(np.array([e.next_state for e in experiences])).to(self.device)
        dones = torch.FloatTensor([1 - e.done for e in experiences]).to(self.device)
        
        # Double DQN update
        with torch.no_grad():
            next_actions = torch.argmax(self.q_network(next_states), dim=1)
            next_q_values = self.target_network(next_states).gather(1, next_actions.unsqueeze(1)).squeeze(1)
            target_q_values = rewards + self.gamma * next_q_values * dones
        
        current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1)).squeeze(1)
        
        loss = self.criterion(current_q_values, target_q_values)
        
        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 1.0)
        self.optimizer.step()
        
        # Update target network
        self.update_count += 1
        if self.update_count % self.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
        
        # Decay epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
    
    def remember(self, experience: Experience):
        """Store experience in replay buffer"""
        self.memory.add(experience)


class A3CWorker:
    """Worker for Asynchronous Advantage Actor-Critic"""
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        global_network: PolicyNetwork,
        learning_rate: float = 1e-4,
        gamma: float = 0.99,
        device: torch.device = torch.device('cpu')
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.device = device
        self.gamma = gamma
        
        # Local network (shared architecture)
        self.local_network = PolicyNetwork(state_dim, action_dim).to(device)
        self.global_network = global_network
        
        self.optimizer = optim.Adam(self.local_network.parameters(), lr=learning_rate)
    
    def compute_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        rewards: List[float],
        dones: List[bool]
    ) -> torch.Tensor:
        """Compute A3C loss"""
        action_logits, values = self.local_network(states)
        
        # Compute returns
        returns = []
        g_t = 0
        for t in reversed(range(len(rewards))):
            g_t = rewards[t] + self.gamma * g_t * (1 - dones[t])
            returns.insert(0, g_t)
        
        returns = torch.FloatTensor(returns).to(self.device)
        advantages = returns - values.detach()
        
        # Policy loss
        dist = Categorical(logits=action_logits)
        policy_loss = -(dist.log_prob(actions) * advantages).mean()
        
        # Value loss
        value_loss = F.smooth_l1_loss(values, returns)
        
        # Total loss
        loss = policy_loss + 0.5 * value_loss - 0.01 * dist.entropy().mean()
        
        return loss
    
    def update(self, loss: torch.Tensor):
        """Synchronous parameter update"""
        self.optimizer.zero_grad()
        loss.backward()
        
        # Sync gradients to global network
        for local_param, global_param in zip(
            self.local_network.parameters(),
            self.global_network.parameters()
        ):
            if global_param.grad is not None:
                global_param.grad += local_param.grad


class A3CAgent:
    """
    Asynchronous Advantage Actor-Critic Agent
    Multi-threaded parallel training with shared parameters.
    """
    
    def __init__(
        self,
        state_dim: int,
        action_dim: int,
        num_workers: int = 4,
        learning_rate: float = 1e-4,
        device: torch.device = torch.device('cpu')
    ):
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.num_workers = num_workers
        self.device = device
        
        # Global network (shared)
        self.global_network = PolicyNetwork(state_dim, action_dim).to(device)
        
        # Worker networks
        self.workers = [
            A3CWorker(state_dim, action_dim, self.global_network, learning_rate, device=device)
            for _ in range(num_workers)
        ]
    
    def select_action(self, state: np.ndarray, worker_id: int = 0) -> int:
        """Select action using worker network"""
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            action_logits, _ = self.workers[worker_id].local_network(state_tensor)
        
        dist = Categorical(logits=action_logits)
        action = dist.sample().item()
        
        return action
