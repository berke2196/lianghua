"""
完整交易引擎 - 整合所有模块
Complete Trading Engine - All Components Integrated
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np

# 导入所有模块
from algorithm_framework_core import (
    MarketMakingAlgorithm,
    StatisticalArbitrageAlgorithm,
    TrendFollowingAlgorithm,
    FundingRateArbitrageAlgorithm,
    TechnicalIndicatorStrategy,
    AlgorithmSignalFusion
)
from ai_signal_filter import AISignalFilter, MarketRegimeDetector, FalseSignalDetector
from kelly_sizing import KellySizing
from stop_loss import StopLossManager
from position_manager import PositionManager
from risk_monitor import RiskMonitor
from hyperliquid_api import HyperliquidAPI
from hyperliquid_websocket import HyperliquidWebSocket

logger = logging.getLogger(__name__)


class IntegratedTradingEngine:
    """
    完整的交易引擎 - 集成所有模块
    
    架构:
    1. 数据获取 (WebSocket)
    2. 算法信号生成 (5个算法)
    3. AI信号过滤 (质量评分)
    4. 风控检查 (Kelly + 止损)
    5. 订单执行
    6. 头寸管理
    """
    
    def __init__(self, config: Dict):
        """
        初始化交易引擎
        
        配置参数:
        {
            'capital': 100000,
            'trading_mode': 'sandbox',  # 沙箱/实盘
            'algorithms': {
                'market_making': True,
                'stat_arb': True,
                'trend_following': True,
                'funding_arb': True,
                'technical': True
            },
            'ai_filter_enabled': True,
            'risk_management': {
                'kelly_fraction': 0.15,
                'daily_loss_limit': 0.1,
                'max_leverage': 3.0
            }
        }
        """
        
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # ============ 初始化API和WebSocket ============
        self.exchange = HyperliquidAPI(
            sandbox_mode=(config['trading_mode'] == 'sandbox')
        )
        self.websocket = HyperliquidWebSocket(self.exchange)
        
        # ============ 初始化算法层 ============
        self.algorithms = self._initialize_algorithms()
        self.signal_fusion = AlgorithmSignalFusion()
        
        # ============ 初始化AI过滤层 ============
        self.ai_filter = AISignalFilter() if config.get('ai_filter_enabled', True) else None
        self.market_regime_detector = MarketRegimeDetector()
        
        # ============ 初始化风控层 ============
        self.kelly_sizing = KellySizing(
            conservative_factor=config['risk_management'].get('kelly_fraction', 0.15)
        )
        self.stop_loss = StopLossManager(
            daily_loss_limit=config['risk_management'].get('daily_loss_limit', 0.1)
        )
        self.position_manager = PositionManager(
            max_leverage=config['risk_management'].get('max_leverage', 3.0)
        )
        self.risk_monitor = RiskMonitor()
        
        # ============ 状态跟踪 ============
        self.open_positions = {}
        self.trade_history = []
        self.signal_history = []
        self.daily_pnl = 0
        self.session_start_time = datetime.now()
        
    def _initialize_algorithms(self) -> Dict:
        """初始化所有算法"""
        
        algorithms = {}
        algo_config = self.config.get('algorithms', {})
        
        if algo_config.get('market_making', True):
            algorithms['market_making'] = MarketMakingAlgorithm(self.config)
        
        if algo_config.get('stat_arb', True):
            algorithms['stat_arb'] = StatisticalArbitrageAlgorithm(self.config)
        
        if algo_config.get('trend_following', True):
            algorithms['trend_following'] = TrendFollowingAlgorithm(self.config)
        
        if algo_config.get('funding_arb', True):
            algorithms['funding_arb'] = FundingRateArbitrageAlgorithm(self.config)
        
        if algo_config.get('technical', True):
            algorithms['technical'] = TechnicalIndicatorStrategy(self.config)
        
        self.logger.info(f"✅ 初始化了 {len(algorithms)} 个交易算法")
        return algorithms
    
    async def start(self):
        """启动交易引擎"""
        
        self.logger.info("=" * 60)
        self.logger.info("🚀 启动 Hyperliquid AI Trader v2")
        self.logger.info("=" * 60)
        self.logger.info(f"📊 交易模式: {self.config['trading_mode']}")
        self.logger.info(f"💰 初始资金: ${self.config['capital']:,.0f}")
        self.logger.info(f"🤖 激活算法: {', '.join(self.algorithms.keys())}")
        self.logger.info(f"🧠 AI过滤: {'启用' if self.ai_filter else '禁用'}")
        self.logger.info("=" * 60)
        
        # 连接WebSocket
        await self.websocket.connect()
        
        # 启动主交易循环
        await self._trading_loop()
    
    async def _trading_loop(self):
        """
        主交易循环 (100Hz)
        
        流程:
        1. 获取市场数据 (WebSocket)
        2. 生成交易信号 (5个算法)
        3. 融合信号 (多数投票)
        4. AI过滤 (质量评分 > 65)
        5. 风控检查 (Kelly + 止损)
        6. 执行订单
        7. 管理头寸
        """
        
        iteration = 0
        
        while True:
            try:
                iteration += 1
                
                # ========== 1️⃣ 获取市场数据 ==========
                market_data = await self.websocket.get_latest_market_data()
                
                if not market_data:
                    await asyncio.sleep(0.01)  # 10ms
                    continue
                
                # ========== 2️⃣ 生成信号 (算法层) ==========
                signals = await self._generate_algorithm_signals(market_data)
                
                # ========== 3️⃣ 融合信号 ==========
                fused_signal = self.signal_fusion.fuse_signals(signals)
                
                # ========== 4️⃣ AI过滤 ==========
                if self.ai_filter:
                    filtered_signal = self.ai_filter.filter_signal(
                        fused_signal,
                        market_data
                    )
                    
                    # 只执行评分 > 65 的信号
                    if filtered_signal['final_score'] <= 65:
                        await asyncio.sleep(0.01)
                        continue
                    
                    final_signal = filtered_signal
                else:
                    # 如果禁用AI过滤，直接使用融合信号
                    final_signal = fused_signal
                
                # ========== 5️⃣ 风控检查 ==========
                can_execute = await self._risk_control_check(final_signal, market_data)
                
                if not can_execute:
                    await asyncio.sleep(0.01)
                    continue
                
                # ========== 6️⃣ 执行订单 ==========
                order_result = await self._execute_order(final_signal, market_data)
                
                if order_result:
                    # 记录交易
                    self.trade_history.append({
                        'timestamp': datetime.now(),
                        'iteration': iteration,
                        'signal': final_signal,
                        'order': order_result,
                        'market_data': market_data
                    })
                    
                    self.logger.info(
                        f"✅ 交易执行 | 信号:{final_signal['action']} | "
                        f"评分:{final_signal.get('final_score', 'N/A'):.1f} | "
                        f"数量:{order_result.get('quantity', 'N/A')}"
                    )
                
                # ========== 7️⃣ 管理头寸 ==========
                await self._manage_positions(market_data)
                
                # ========== 📊 定期日志 ==========
                if iteration % 1000 == 0:  # 每10秒 (100Hz * 10s)
                    await self._log_statistics()
                
                # 10ms执行一次 (100Hz)
                await asyncio.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"❌ 交易循环错误: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _generate_algorithm_signals(self, market_data: Dict) -> Dict:
        """
        生成所有算法的信号
        
        返回格式:
        {
            'market_making': signal,
            'stat_arb': signal,
            'trend_following': signal,
            'funding_arb': signal,
            'technical': signal
        }
        """
        
        signals = {}
        
        # 并行执行所有算法 (提高效率)
        if 'market_making' in self.algorithms:
            mm = self.algorithms['market_making']
            signals['market_making'] = mm.generate_quotes()
        
        if 'stat_arb' in self.algorithms:
            sa = self.algorithms['stat_arb']
            signals['stat_arb'] = sa.generate_signal()
        
        if 'trend_following' in self.algorithms:
            tf = self.algorithms['trend_following']
            signals['trend_following'] = tf.generate_signal()
        
        if 'funding_arb' in self.algorithms:
            fa = self.algorithms['funding_arb']
            signals['funding_arb'] = fa.generate_signal()
        
        if 'technical' in self.algorithms:
            ti = self.algorithms['technical']
            tech_signals = ti.generate_signals()
            signals['technical'] = tech_signals[0] if tech_signals else None
        
        return signals
    
    async def _risk_control_check(self, signal: Dict, market_data: Dict) -> bool:
        """
        风控检查 - 5层
        
        返回: True = 可以执行, False = 被风控阻止
        """
        
        # ❌ 检查1: 日亏损限制
        if self.stop_loss.check_daily_loss_limit(self.daily_pnl):
            self.logger.warning("⚠️  已达日亏损限制，停止交易")
            return False
        
        # ❌ 检查2: 清算风险
        liquidation_risk = self.risk_monitor.check_liquidation_risk()
        if liquidation_risk > 0.8:
            self.logger.warning(f"⚠️  清液风险过高 ({liquidation_risk:.1%})，停止交易")
            return False
        
        # ❌ 检查3: 最大杠杆
        current_leverage = self.position_manager.get_current_leverage()
        if current_leverage > self.config['risk_management']['max_leverage']:
            self.logger.warning(f"⚠️  杠杆过高 ({current_leverage:.1f}x)，停止交易")
            return False
        
        # ❌ 检查4: 市场异常
        market_regime = self.market_regime_detector.detect(market_data)
        if market_regime == "volatile" and signal.get('final_score', 0) < 75:
            self.logger.warning(f"⚠️  高波动市场，只执行高评分信号")
            return False
        
        # ✅ 所有风控检查通过
        return True
    
    async def _execute_order(self, signal: Dict, market_data: Dict) -> Optional[Dict]:
        """
        执行订单
        
        返回: 订单结果或None
        """
        
        try:
            action = signal.get('action', 'HOLD')
            
            if action == 'HOLD':
                return None
            
            # 计算仓位大小 (Kelly准则)
            position_size = self.kelly_sizing.calculate_dynamic_kelly(
                win_rate=self._get_historical_win_rate(),
                profit_loss_ratio=self._get_historical_profit_loss_ratio()
            )
            
            # 计算订单量
            current_price = market_data.get('price', 0)
            capital = self.config['capital']
            quantity = (capital * position_size) / current_price
            
            # 生成订单
            order = {
                'action': action,
                'quantity': quantity,
                'price': current_price,
                'timestamp': datetime.now(),
                'signal_score': signal.get('final_score', 0),
                'confidence': signal.get('confidence', 0)
            }
            
            # 发送订单到交易所
            result = await self.exchange.submit_order(
                symbol='BTC-USD',  # 示例
                side='BUY' if action in ['LONG', 'BUY'] else 'SELL',
                quantity=quantity,
                order_type='limit',
                price=current_price
            )
            
            if result:
                # 更新头寸
                self.position_manager.add_position(order)
                return result
            
            return None
        
        except Exception as e:
            self.logger.error(f"❌ 订单执行失败: {e}")
            return None
    
    async def _manage_positions(self, market_data: Dict):
        """
        管理开仓头寸
        
        操作:
        - 时间止损: 超过30秒
        - 利润锁定: 赚0.1%以上
        - 风险止损: 亏0.05%以上
        - 清算风险: 自动减仓
        """
        
        current_price = market_data.get('price', 0)
        
        for position_id, position in list(self.open_positions.items()):
            # 计算P&L
            pnl_ratio = (current_price - position['entry_price']) / position['entry_price']
            
            # 时间止损 (30秒)
            elapsed = (datetime.now() - position['open_time']).total_seconds()
            if elapsed > 30:
                await self.exchange.close_position(position_id)
                del self.open_positions[position_id]
                self.logger.info(f"⏱️  时间止损: {position_id}")
            
            # 利润锁定 (0.1%)
            elif pnl_ratio > 0.001:
                await self.exchange.close_position(position_id)
                del self.open_positions[position_id]
                self.logger.info(f"💰 利润锁定: {position_id} (PnL: +{pnl_ratio:.2%})")
            
            # 风险止损 (-0.05%)
            elif pnl_ratio < -0.0005:
                await self.exchange.close_position(position_id)
                del self.open_positions[position_id]
                self.logger.info(f"🚫 风险止损: {position_id} (PnL: {pnl_ratio:.2%})")
    
    async def _log_statistics(self):
        """定期输出统计信息"""
        
        elapsed = (datetime.now() - self.session_start_time).total_seconds()
        
        self.logger.info("=" * 60)
        self.logger.info("📊 交易统计")
        self.logger.info("=" * 60)
        self.logger.info(f"运行时间: {elapsed/3600:.1f} 小时")
        self.logger.info(f"总交易数: {len(self.trade_history)}")
        self.logger.info(f"开仓头数: {len(self.open_positions)}")
        self.logger.info(f"日收益: {self.daily_pnl:.2%}")
        self.logger.info(f"胜率: {self._get_win_rate():.1%}")
        self.logger.info(f"最大回撤: {self._get_max_drawdown():.1%}")
        self.logger.info("=" * 60)
    
    def _get_historical_win_rate(self) -> float:
        """获取历史胜率"""
        if not self.trade_history:
            return 0.5
        
        wins = sum(1 for t in self.trade_history if t.get('order', {}).get('pnl', 0) > 0)
        return wins / len(self.trade_history) if self.trade_history else 0.5
    
    def _get_historical_profit_loss_ratio(self) -> float:
        """获取历史收益/亏损比"""
        if not self.trade_history:
            return 1.0
        
        profitable_trades = [t for t in self.trade_history if t.get('order', {}).get('pnl', 0) > 0]
        losing_trades = [t for t in self.trade_history if t.get('order', {}).get('pnl', 0) <= 0]
        
        if not profitable_trades or not losing_trades:
            return 1.0
        
        avg_profit = sum(t.get('order', {}).get('pnl', 0) for t in profitable_trades) / len(profitable_trades)
        avg_loss = abs(sum(t.get('order', {}).get('pnl', 0) for t in losing_trades) / len(losing_trades))
        
        return avg_profit / avg_loss if avg_loss > 0 else 1.0
    
    def _get_win_rate(self) -> float:
        """计算胜率"""
        if not self.trade_history:
            return 0.0
        
        wins = sum(1 for t in self.trade_history if t.get('order', {}).get('pnl', 0) > 0)
        return wins / len(self.trade_history)
    
    def _get_max_drawdown(self) -> float:
        """计算最大回撤"""
        if not self.trade_history:
            return 0.0
        
        cumulative_pnl = 0
        peak = 0
        max_dd = 0
        
        for trade in self.trade_history:
            pnl = trade.get('order', {}).get('pnl', 0)
            cumulative_pnl += pnl
            
            if cumulative_pnl > peak:
                peak = cumulative_pnl
            
            drawdown = (cumulative_pnl - peak) / peak if peak > 0 else 0
            if drawdown < max_dd:
                max_dd = drawdown
        
        return max_dd
    
    async def stop(self):
        """停止交易引擎"""
        self.logger.info("🛑 停止交易引擎...")
        await self.websocket.disconnect()
        self.logger.info("✅ 交易引擎已停止")


# ============ 启动脚本 ============

async def main():
    """主函数"""
    
    # 配置
    config = {
        'capital': 100000,
        'trading_mode': 'sandbox',
        'algorithms': {
            'market_making': True,
            'stat_arb': True,
            'trend_following': True,
            'funding_arb': True,
            'technical': True
        },
        'ai_filter_enabled': True,
        'risk_management': {
            'kelly_fraction': 0.15,
            'daily_loss_limit': 0.1,
            'max_leverage': 3.0
        }
    }
    
    # 创建交易引擎
    engine = IntegratedTradingEngine(config)
    
    try:
        # 启动交易
        await engine.start()
    except KeyboardInterrupt:
        print("\n👋 用户中断")
    finally:
        await engine.stop()


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行
    asyncio.run(main())
