"""
参数优化模块 - 支持多种优化算法
包括：网格搜索、贝叶斯优化、遗传算法、粒子群、模拟退火
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Callable, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class OptimizationMethod(Enum):
    """优化方法"""
    GRID_SEARCH = "grid_search"
    BAYESIAN = "bayesian"
    GENETIC = "genetic"
    PSO = "pso"
    SIMULATED_ANNEALING = "simulated_annealing"
    RANDOM_SEARCH = "random_search"


@dataclass
class ParameterSpace:
    """参数空间定义"""
    name: str
    min_value: float
    max_value: float
    step: Optional[float] = None
    values: Optional[List[Any]] = None  # 离散值


@dataclass
class OptimizationResult:
    """优化结果"""
    method: OptimizationMethod
    best_params: Dict[str, Any]
    best_score: float
    optimization_history: List[Dict] = field(default_factory=list)
    total_evaluations: int = 0
    elapsed_time: float = 0
    convergence_info: Dict = field(default_factory=dict)


class BaseOptimizer(ABC):
    """优化器基类"""
    
    def __init__(self, 
                 objective_func: Callable,
                 parameter_spaces: List[ParameterSpace],
                 max_iterations: int = 100,
                 maximize: bool = True):
        """
        初始化优化器
        
        Args:
            objective_func: 目标函数
            parameter_spaces: 参数空间列表
            max_iterations: 最大迭代次数
            maximize: 是否最大化
        """
        self.objective_func = objective_func
        self.parameter_spaces = parameter_spaces
        self.max_iterations = max_iterations
        self.maximize = maximize
        
        self.history = []
        self.best_score = -np.inf if maximize else np.inf
        self.best_params = None
    
    @abstractmethod
    def optimize(self) -> OptimizationResult:
        """执行优化"""
        pass
    
    def evaluate(self, params: Dict[str, Any]) -> float:
        """评估参数"""
        try:
            score = self.objective_func(params)
            self.history.append({
                'params': params,
                'score': score,
                'iteration': len(self.history)
            })
            
            # 更新最优解
            if self.maximize:
                if score > self.best_score:
                    self.best_score = score
                    self.best_params = params
            else:
                if score < self.best_score:
                    self.best_score = score
                    self.best_params = params
            
            return score
        except Exception as e:
            logger.error(f"Error evaluating parameters {params}: {e}")
            return -np.inf if self.maximize else np.inf


class GridSearchOptimizer(BaseOptimizer):
    """网格搜索优化"""
    
    def optimize(self) -> OptimizationResult:
        """执行网格搜索"""
        logger.info("Starting grid search optimization")
        
        # 生成参数网格
        param_grids = []
        for space in self.parameter_spaces:
            if space.values is not None:
                # 离散值
                param_grids.append((space.name, space.values))
            else:
                # 连续值
                if space.step is None:
                    n_steps = 10
                    step = (space.max_value - space.min_value) / n_steps
                else:
                    step = space.step
                
                values = np.arange(space.min_value, space.max_value + step, step)
                param_grids.append((space.name, values))
        
        # 生成所有参数组合
        from itertools import product
        param_names = [name for name, _ in param_grids]
        param_value_lists = [values for _, values in param_grids]
        
        total_combinations = np.prod([len(v) for v in param_value_lists])
        logger.info(f"Total combinations: {total_combinations}")
        
        # 评估所有组合
        for i, param_values in enumerate(product(*param_value_lists)):
            if i >= self.max_iterations:
                break
            
            params = dict(zip(param_names, param_values))
            score = self.evaluate(params)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Evaluated {i + 1}/{min(self.max_iterations, total_combinations)}: "
                           f"score={score:.6f}")
        
        return OptimizationResult(
            method=OptimizationMethod.GRID_SEARCH,
            best_params=self.best_params,
            best_score=self.best_score,
            optimization_history=self.history,
            total_evaluations=len(self.history)
        )


class RandomSearchOptimizer(BaseOptimizer):
    """随机搜索优化"""
    
    def optimize(self) -> OptimizationResult:
        """执行随机搜索"""
        logger.info("Starting random search optimization")
        
        for i in range(self.max_iterations):
            # 随机生成参数
            params = {}
            for space in self.parameter_spaces:
                if space.values is not None:
                    params[space.name] = np.random.choice(space.values)
                else:
                    params[space.name] = np.random.uniform(space.min_value, space.max_value)
            
            score = self.evaluate(params)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Iteration {i + 1}/{self.max_iterations}: score={score:.6f}")
        
        return OptimizationResult(
            method=OptimizationMethod.RANDOM_SEARCH,
            best_params=self.best_params,
            best_score=self.best_score,
            optimization_history=self.history,
            total_evaluations=len(self.history)
        )


class GeneticOptimizer(BaseOptimizer):
    """遗传算法优化"""
    
    def __init__(self,
                 objective_func: Callable,
                 parameter_spaces: List[ParameterSpace],
                 max_iterations: int = 100,
                 maximize: bool = True,
                 population_size: int = 50,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.8):
        """初始化遗传算法优化器"""
        super().__init__(objective_func, parameter_spaces, max_iterations, maximize)
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
    
    def optimize(self) -> OptimizationResult:
        """执行遗传算法"""
        logger.info("Starting genetic algorithm optimization")
        
        # 初始化种群
        population = self._initialize_population()
        fitness_scores = [self.evaluate(self._dict_from_individual(ind)) 
                         for ind in population]
        
        for generation in range(self.max_iterations):
            # 选择
            selected = self._selection(population, fitness_scores)
            
            # 交叉
            offspring = self._crossover(selected)
            
            # 变异
            mutated = [self._mutate(ind) for ind in offspring]
            
            # 评估新个体
            new_fitness = [self.evaluate(self._dict_from_individual(ind)) 
                          for ind in mutated]
            
            # 合并并选择最佳
            combined_pop = population + mutated
            combined_fitness = fitness_scores + new_fitness
            
            sorted_indices = np.argsort(combined_fitness)
            if not self.maximize:
                sorted_indices = sorted_indices[::-1]
            
            population = [combined_pop[i] for i in sorted_indices[:self.population_size]]
            fitness_scores = [combined_fitness[i] for i in sorted_indices[:self.population_size]]
            
            if (generation + 1) % 10 == 0:
                logger.info(f"Generation {generation + 1}/{self.max_iterations}: "
                           f"best_score={self.best_score:.6f}")
        
        return OptimizationResult(
            method=OptimizationMethod.GENETIC,
            best_params=self.best_params,
            best_score=self.best_score,
            optimization_history=self.history,
            total_evaluations=len(self.history)
        )
    
    def _initialize_population(self) -> List[np.ndarray]:
        """初始化种群"""
        population = []
        for _ in range(self.population_size):
            individual = np.array([
                np.random.uniform(space.min_value, space.max_value)
                for space in self.parameter_spaces
            ])
            population.append(individual)
        return population
    
    def _dict_from_individual(self, individual: np.ndarray) -> Dict[str, Any]:
        """从个体转换为参数字典"""
        return {
            space.name: individual[i]
            for i, space in enumerate(self.parameter_spaces)
        }
    
    def _selection(self, population: List, fitness_scores: List) -> List:
        """锦标赛选择"""
        selected = []
        for _ in range(len(population)):
            tournament_indices = np.random.choice(len(population), size=3, replace=False)
            if self.maximize:
                winner_idx = max(tournament_indices, key=lambda i: fitness_scores[i])
            else:
                winner_idx = min(tournament_indices, key=lambda i: fitness_scores[i])
            selected.append(population[winner_idx])
        return selected
    
    def _crossover(self, population: List) -> List:
        """单点交叉"""
        offspring = []
        for i in range(0, len(population) - 1, 2):
            if np.random.rand() < self.crossover_rate:
                crossover_point = np.random.randint(len(population[i]))
                child1 = np.concatenate([population[i][:crossover_point],
                                        population[i+1][crossover_point:]])
                child2 = np.concatenate([population[i+1][:crossover_point],
                                        population[i][crossover_point:]])
                offspring.extend([child1, child2])
            else:
                offspring.extend([population[i], population[i+1]])
        return offspring
    
    def _mutate(self, individual: np.ndarray) -> np.ndarray:
        """高斯变异"""
        mutated = individual.copy()
        for i in range(len(mutated)):
            if np.random.rand() < self.mutation_rate:
                sigma = (self.parameter_spaces[i].max_value - 
                        self.parameter_spaces[i].min_value) * 0.1
                mutated[i] += np.random.normal(0, sigma)
                mutated[i] = np.clip(mutated[i],
                                    self.parameter_spaces[i].min_value,
                                    self.parameter_spaces[i].max_value)
        return mutated


class PSOOptimizer(BaseOptimizer):
    """粒子群算法优化"""
    
    def __init__(self,
                 objective_func: Callable,
                 parameter_spaces: List[ParameterSpace],
                 max_iterations: int = 100,
                 maximize: bool = True,
                 num_particles: int = 50,
                 w: float = 0.7,
                 c1: float = 1.5,
                 c2: float = 1.5):
        """初始化PSO优化器"""
        super().__init__(objective_func, parameter_spaces, max_iterations, maximize)
        self.num_particles = num_particles
        self.w = w  # 惯性权重
        self.c1 = c1  # 认知参数
        self.c2 = c2  # 社会参数
    
    def optimize(self) -> OptimizationResult:
        """执行粒子群算法"""
        logger.info("Starting PSO optimization")
        
        # 初始化粒子
        n_dims = len(self.parameter_spaces)
        positions = np.array([
            np.array([np.random.uniform(space.min_value, space.max_value)
                     for space in self.parameter_spaces])
            for _ in range(self.num_particles)
        ])
        
        velocities = np.random.uniform(-1, 1, (self.num_particles, n_dims))
        
        # 初始化最优解
        fitness = np.array([self.evaluate(self._dict_from_position(pos)) 
                           for pos in positions])
        
        pbest_positions = positions.copy()
        pbest_fitness = fitness.copy()
        
        gbest_idx = np.argmax(fitness) if self.maximize else np.argmin(fitness)
        gbest_position = positions[gbest_idx].copy()
        gbest_fitness = fitness[gbest_idx]
        
        # 迭代
        for iteration in range(self.max_iterations):
            for i in range(self.num_particles):
                # 更新速度
                r1 = np.random.rand(n_dims)
                r2 = np.random.rand(n_dims)
                
                velocities[i] = (self.w * velocities[i] +
                               self.c1 * r1 * (pbest_positions[i] - positions[i]) +
                               self.c2 * r2 * (gbest_position - positions[i]))
                
                # 更新位置
                positions[i] += velocities[i]
                
                # 限制在范围内
                for j, space in enumerate(self.parameter_spaces):
                    positions[i][j] = np.clip(positions[i][j],
                                             space.min_value,
                                             space.max_value)
                
                # 评估
                fitness[i] = self.evaluate(self._dict_from_position(positions[i]))
                
                # 更新个体最优
                if self.maximize:
                    if fitness[i] > pbest_fitness[i]:
                        pbest_positions[i] = positions[i].copy()
                        pbest_fitness[i] = fitness[i]
                else:
                    if fitness[i] < pbest_fitness[i]:
                        pbest_positions[i] = positions[i].copy()
                        pbest_fitness[i] = fitness[i]
                
                # 更新全局最优
                if self.maximize:
                    if fitness[i] > gbest_fitness:
                        gbest_position = positions[i].copy()
                        gbest_fitness = fitness[i]
                else:
                    if fitness[i] < gbest_fitness:
                        gbest_position = positions[i].copy()
                        gbest_fitness = fitness[i]
            
            if (iteration + 1) % 10 == 0:
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}: "
                           f"best_score={self.best_score:.6f}")
        
        return OptimizationResult(
            method=OptimizationMethod.PSO,
            best_params=self.best_params,
            best_score=self.best_score,
            optimization_history=self.history,
            total_evaluations=len(self.history)
        )
    
    def _dict_from_position(self, position: np.ndarray) -> Dict[str, Any]:
        """从位置转换为参数字典"""
        return {
            space.name: position[i]
            for i, space in enumerate(self.parameter_spaces)
        }


class SimulatedAnnealingOptimizer(BaseOptimizer):
    """模拟退火优化"""
    
    def __init__(self,
                 objective_func: Callable,
                 parameter_spaces: List[ParameterSpace],
                 max_iterations: int = 100,
                 maximize: bool = True,
                 initial_temp: float = 1.0,
                 cooling_rate: float = 0.95):
        """初始化模拟退火优化器"""
        super().__init__(objective_func, parameter_spaces, max_iterations, maximize)
        self.initial_temp = initial_temp
        self.cooling_rate = cooling_rate
    
    def optimize(self) -> OptimizationResult:
        """执行模拟退火"""
        logger.info("Starting simulated annealing optimization")
        
        # 初始解
        current_solution = np.array([
            np.random.uniform(space.min_value, space.max_value)
            for space in self.parameter_spaces
        ])
        
        current_score = self.evaluate(self._dict_from_solution(current_solution))
        
        temperature = self.initial_temp
        
        for iteration in range(self.max_iterations):
            # 生成邻近解
            neighbor = current_solution.copy()
            for i, space in enumerate(self.parameter_spaces):
                delta = (space.max_value - space.min_value) * 0.05
                neighbor[i] += np.random.normal(0, delta)
                neighbor[i] = np.clip(neighbor[i],
                                     space.min_value,
                                     space.max_value)
            
            neighbor_score = self.evaluate(self._dict_from_solution(neighbor))
            
            # 接受准则
            delta_E = neighbor_score - current_score
            if self.maximize:
                accept_prob = 1.0 if delta_E > 0 else np.exp(delta_E / temperature)
            else:
                accept_prob = 1.0 if delta_E < 0 else np.exp(-delta_E / temperature)
            
            if np.random.rand() < accept_prob:
                current_solution = neighbor
                current_score = neighbor_score
            
            # 降温
            temperature *= self.cooling_rate
            
            if (iteration + 1) % 10 == 0:
                logger.info(f"Iteration {iteration + 1}/{self.max_iterations}: "
                           f"best_score={self.best_score:.6f}, T={temperature:.4f}")
        
        return OptimizationResult(
            method=OptimizationMethod.SIMULATED_ANNEALING,
            best_params=self.best_params,
            best_score=self.best_score,
            optimization_history=self.history,
            total_evaluations=len(self.history)
        )
    
    def _dict_from_solution(self, solution: np.ndarray) -> Dict[str, Any]:
        """从解转换为参数字典"""
        return {
            space.name: solution[i]
            for i, space in enumerate(self.parameter_spaces)
        }


class ParameterOptimizer:
    """参数优化器统一接口"""
    
    def __init__(self, 
                 objective_func: Callable,
                 parameter_spaces: List[ParameterSpace],
                 max_iterations: int = 100,
                 maximize: bool = True):
        """初始化优化器"""
        self.objective_func = objective_func
        self.parameter_spaces = parameter_spaces
        self.max_iterations = max_iterations
        self.maximize = maximize
    
    def optimize(self,
                method: OptimizationMethod = OptimizationMethod.BAYESIAN,
                **kwargs) -> OptimizationResult:
        """
        执行优化
        
        Args:
            method: 优化方法
            **kwargs: 方法特定参数
        
        Returns:
            优化结果
        """
        logger.info(f"Starting optimization with method: {method}")
        
        if method == OptimizationMethod.GRID_SEARCH:
            optimizer = GridSearchOptimizer(
                self.objective_func,
                self.parameter_spaces,
                self.max_iterations,
                self.maximize
            )
        elif method == OptimizationMethod.RANDOM_SEARCH:
            optimizer = RandomSearchOptimizer(
                self.objective_func,
                self.parameter_spaces,
                self.max_iterations,
                self.maximize
            )
        elif method == OptimizationMethod.GENETIC:
            optimizer = GeneticOptimizer(
                self.objective_func,
                self.parameter_spaces,
                self.max_iterations,
                self.maximize,
                **kwargs
            )
        elif method == OptimizationMethod.PSO:
            optimizer = PSOOptimizer(
                self.objective_func,
                self.parameter_spaces,
                self.max_iterations,
                self.maximize,
                **kwargs
            )
        elif method == OptimizationMethod.SIMULATED_ANNEALING:
            optimizer = SimulatedAnnealingOptimizer(
                self.objective_func,
                self.parameter_spaces,
                self.max_iterations,
                self.maximize,
                **kwargs
            )
        else:
            raise ValueError(f"Unknown optimization method: {method}")
        
        return optimizer.optimize()


__all__ = [
    'ParameterOptimizer',
    'OptimizationMethod',
    'ParameterSpace',
    'OptimizationResult',
]
