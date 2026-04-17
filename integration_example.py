"""
风险管理系统 - 完整集成示例
展示如何将所有模块集成成完整的交易系统
"""

import numpy as np
from datetime import datetime, timedelta
import logging

# 导入所有模块
from kelly_sizing import KellyCalculator, ConservativenessLevel, KellyConfig
from stop_loss import ComprehensiveStopLossManager, StopLossConfig, Position
from position_manager import PositionManager, PositionMode
from order_optimizer import OrderOptimizer, OrderBook, ExecutionAlgorithm
from order_executor import OrderExecutor, OrderManager, Order, OrderSide, OrderType
from risk_monitor import RiskMonitor, RiskMetrics, AlertLevel
from recovery import RecoveryManager, FailureType
from risk_config import get_balanced_config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegratedTradingSystem:
    """完整的交易系统集成"""
    
    def __init__(self, initial_equity: float = 10000):
        """
        初始化系统
        
        Args:
            initial_equity: 初始资金
        """
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        
        # 加载配置
        self.config = get_balanced_config()
        
        # 初始化各个模块
        self.kelly = KellyCalculator(self.config.kelly)
        self.stop_loss = ComprehensiveStopLossManager(self.config.stop_loss)
        self.position_manager = PositionManager()
        self.order_optimizer = OrderOptimizer()
        self.order_executor = OrderExecutor()
        self.risk_monitor = RiskMonitor()
        self.recovery_manager = RecoveryManager()
        
        # 状态
        self.trading_active = True
        self.performance_log = []
        
        logger.info(f"Trading system initialized with ${initial_equity:.2f}")
    
    def process_market_data(self, 
                           symbol: str,
                           price: float,
                           bid_volume: float = 1000,
                           ask_volume: float = 1000):
        """
        处理市场数据
        
        Args:
            symbol: 交易品种
            price: 当前价格
            bid_volume: 买方总量
            ask_volume: 卖方总量
        """
        # 更新头寸价格
        self.position_manager.update_price(symbol, price)
        
        # 更新监控指标
        self._update_risk_metrics()
        
        # 检查止损
        self._check_stop_losses()
    
    def execute_trade(self,
                     symbol: str,
                     side: OrderSide,
                     quantity: float,
                     max_price: float = None,
                     time_limit_seconds: int = 300):
        """
        执行交易
        
        Args:
            symbol: 交易品种
            side: BUY/SELL
            quantity: 数量
            max_price: 最大价格 (LIMIT订单)
            time_limit_seconds: 时间限制
            
        Returns:
            success, order_id
        """
        if not self.trading_active:
            logger.warning("Trading is paused")
            return False, None
        
        # 1. Kelly计算确定头寸大小
        kelly_fraction, level = self.kelly.recommend_kelly()
        logger.info(f"Kelly recommendation: {kelly_fraction:.4f} ({level.name})")
        
        # 2. 计算头寸参数
        position_value = self.current_equity * kelly_fraction
        leverage = 2.0 if kelly_fraction > 0.1 else 1.0
        
        # 3. 检查头寸限制
        allowed, reason = self.position_manager.check_position_limits(
            symbol, quantity, self.current_equity
        )
        if not allowed:
            logger.error(f"Position limit check failed: {reason}")
            return False, None
        
        # 4. 打开头寸
        success, msg = self.position_manager.open_position(
            symbol=symbol,
            mode=PositionMode.LONG if side == OrderSide.BUY else PositionMode.SHORT,
            quantity=quantity,
            entry_price=max_price or 50000,  # 假设价格
            leverage=leverage,
            collateral_amount=position_value
        )
        
        if not success:
            logger.error(f"Failed to open position: {msg}")
            return False, None
        
        # 5. 订单优化
        ob = OrderBook(
            bids=[(50000, 1000)] * 5,
            asks=[(50001, 1000)] * 5,
            mid_price=50000,
            timestamp=datetime.now()
        )
        
        result = self.order_optimizer.optimize_execution(
            symbol, quantity, ob, time_limit_seconds=time_limit_seconds
        )
        
        logger.info(f"Execution algorithm: {result['algorithm']}")
        logger.info(f"Estimated slippage: {result['estimated_slippage']:.4f}")
        
        # 6. 提交订单
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=max_price or 50000
        )
        
        success, msg = self.order_executor.submit_order(order)
        
        if success:
            logger.info(f"Order submitted: {order.order_id}")
            return True, order.order_id
        else:
            logger.error(f"Order submission failed: {msg}")
            return False, None
    
    def simulate_fill(self, order_id: str, filled_qty: float, fill_price: float):
        """
        模拟订单成交
        
        Args:
            order_id: 订单ID
            filled_qty: 成交数量
            fill_price: 成交价格
        """
        success, msg = self.order_executor.fill_order(
            order_id, filled_qty, fill_price, is_partial=False
        )
        
        if success:
            logger.info(f"Order filled: {filled_qty} @ {fill_price}")
            
            # 更新权益
            pnl = filled_qty * (fill_price - 50000)  # 假设入场价
            self.current_equity += pnl
            
            logger.info(f"P&L: ${pnl:.2f}, New equity: ${self.current_equity:.2f}")
    
    def _update_risk_metrics(self):
        """更新风险指标"""
        metrics = self.position_manager.calculate_portfolio_metrics(
            self.current_equity
        )
        
        risk_metrics = RiskMetrics(
            timestamp=datetime.now(),
            account_equity=self.current_equity,
            used_margin=metrics.used_collateral,
            available_margin=metrics.available_collateral,
            margin_ratio=metrics.margin_ratio,
            total_pnl=metrics.total_unrealized_pnl,
            total_pnl_percent=metrics.total_roi,
            portfolio_leverage=metrics.portfolio_leverage,
            portfolio_heat=metrics.portfolio_heat,
            clearance_distance_percent=metrics.min_distance_to_liquidation,
            liquidation_risk=self.position_manager.estimate_liquidation_risk(
                self.current_equity
            ),
            system_latency_ms=2.0,  # 模拟延迟
            network_latency_ms=50.0,
            portfolio_correlation=0.3
        )
        
        self.risk_monitor.record_metrics(risk_metrics)
        
        # 异常检测
        anomalies = self.risk_monitor.detect_anomalies(risk_metrics)
        if anomalies:
            logger.warning(f"Anomalies detected: {len(anomalies)}")
            for alert in anomalies:
                logger.warning(f"  [{alert.level.value}] {alert.title}")
    
    def _check_stop_losses(self):
        """检查止损"""
        for symbol in self.position_manager.positions:
            should_close, reason = self.stop_loss.comprehensive_check(
                symbol,
                account_collateral=self.current_equity * 0.5,
                account_equity=self.current_equity
            )
            
            if should_close:
                logger.warning(f"Stop loss triggered for {symbol}: {reason}")
                self.position_manager.close_position(symbol, 49000)  # 平仓价格
    
    def get_trading_report(self) -> Dict:
        """生成交易报告"""
        metrics = self.position_manager.calculate_portfolio_metrics(
            self.current_equity
        )
        
        exec_summary = self.order_executor.execution_quality.get_execution_summary()
        risk_summary = self.risk_monitor.get_risk_summary()
        recovery_status = self.recovery_manager.get_recovery_status()
        
        return {
            'current_equity': self.current_equity,
            'pnl': self.current_equity - self.initial_equity,
            'pnl_percent': (self.current_equity - self.initial_equity) / self.initial_equity,
            'total_positions': metrics.total_positions,
            'portfolio_leverage': metrics.portfolio_leverage,
            'margin_ratio': metrics.margin_ratio,
            'liquidation_risk': self.position_manager.estimate_liquidation_risk(
                self.current_equity
            ),
            'execution_quality': exec_summary,
            'risk_metrics': risk_summary,
            'recovery_status': recovery_status,
            'timestamp': datetime.now()
        }
    
    def print_report(self):
        """打印交易报告"""
        report = self.get_trading_report()
        
        print("\n" + "=" * 60)
        print("TRADING SYSTEM REPORT")
        print("=" * 60)
        print(f"Initial Equity:      ${self.initial_equity:>10,.2f}")
        print(f"Current Equity:      ${report['current_equity']:>10,.2f}")
        print(f"P&L:                 ${report['pnl']:>10,.2f}")
        print(f"P&L %:               {report['pnl_percent']:>10.2%}")
        print(f"\nPositions:           {report['total_positions']:>10}")
        print(f"Portfolio Leverage:  {report['portfolio_leverage']:>10.2f}x")
        print(f"Margin Ratio:        {report['margin_ratio']:>10.2f}")
        print(f"Liquidation Risk:    {report['liquidation_risk']:>10.2%}")
        
        print(f"\nExecution Quality:")
        print(f"  Total Orders:      {report['execution_quality'].get('total_orders', 0):>8}")
        print(f"  Avg Slippage:      {report['execution_quality'].get('average_slippage', 0):>8.6f}")
        print(f"  Fill Rate:         {report['execution_quality'].get('fill_rate', 0):>8.2%}")
        
        print(f"\nRisk Status:")
        print(f"  Active Alerts:     {report['risk_metrics'].get('active_alerts', 0):>8}")
        print(f"  System Latency:    {report['risk_metrics'].get('system_latency_ms', 0):>8.1f}ms")
        print(f"  Network Latency:   {report['risk_metrics'].get('network_latency_ms', 0):>8.1f}ms")
        
        print(f"\nRecovery Status:     {report['recovery_status'].get('state'):>15}")
        print("=" * 60 + "\n")


def run_example():
    """运行完整示例"""
    logger.info("Starting integrated trading system example...")
    
    # 创建系统
    system = IntegratedTradingSystem(initial_equity=10000)
    
    # 模拟交易历史
    print("\n" + "=" * 60)
    print("SIMULATING TRADING ACTIVITY")
    print("=" * 60)
    
    # 1. 添加历史交易用于Kelly计算
    print("\n1. Building trading history for Kelly calculation...")
    for i in range(20):
        return_val = np.random.normal(0.01, 0.02)
        system.kelly.add_trade({'return': return_val})
    
    system.kelly.calculate_performance_metrics()
    kelly_frac, level = system.kelly.recommend_kelly()
    print(f"   Kelly recommendation: {kelly_frac:.4f} ({level.name})")
    
    # 2. 执行交易
    print("\n2. Executing trades...")
    success, order_id = system.execute_trade(
        symbol='BTC',
        side=OrderSide.BUY,
        quantity=1.0,
        max_price=50000,
        time_limit_seconds=300
    )
    
    if success:
        print(f"   ✅ Order placed: {order_id}")
        
        # 3. 模拟成交
        print("\n3. Simulating order fills...")
        system.simulate_fill(order_id, 1.0, 50100)  # 成交于50100
    
    # 4. 处理市场数据
    print("\n4. Processing market data...")
    system.process_market_data('BTC', 50200)
    
    # 5. 生成报告
    print("\n5. Generating report...")
    system.print_report()
    
    logger.info("Example completed successfully!")


def demo_kelly_sizing():
    """演示Kelly准则"""
    print("\n" + "=" * 60)
    print("DEMO: Kelly准则计算")
    print("=" * 60)
    
    calc = KellyCalculator()
    
    # 模拟交易
    print("\nSimulating 50 trades...")
    pnl_list = []
    for _ in range(50):
        pnl = np.random.normal(0.01, 0.02)
        pnl_list.append(pnl)
        calc.add_trade({'return': pnl})
    
    # 计算指标
    calc.calculate_performance_metrics()
    metrics = calc.performance_metrics
    
    print(f"\nPerformance Metrics:")
    print(f"  Win Rate:           {metrics['win_rate']:>8.2%}")
    print(f"  Avg Win:            {metrics['avg_win']:>8.4f}")
    print(f"  Avg Loss:           {metrics['avg_loss']:>8.4f}")
    print(f"  Sharpe Ratio:       {metrics['sharpe_ratio']:>8.2f}")
    print(f"  Max Drawdown:       {metrics['max_drawdown']:>8.4f}")
    
    # Kelly建议
    kelly, level = calc.recommend_kelly()
    print(f"\nKelly Recommendation:")
    print(f"  Kelly Fraction:     {kelly:>8.4f}")
    print(f"  Conservativeness:   {level.name:>15}")


def demo_stop_loss():
    """演示止损系统"""
    print("\n" + "=" * 60)
    print("DEMO: 三防线止损系统")
    print("=" * 60)
    
    config = StopLossConfig(
        single_trade_stop_loss=0.02,
        max_holding_time_minutes=60,
        consecutive_loss_threshold=3,
        daily_loss_limit=0.05
    )
    
    manager = ComprehensiveStopLossManager(config)
    
    # 创建头寸
    position = Position(
        symbol='BTC',
        size=1.0,
        entry_price=50000,
        current_price=49500  # -1%
    )
    
    manager.add_position(position)
    
    print("\nPosition created:")
    print(f"  Symbol:             BTC")
    print(f"  Size:               1.0")
    print(f"  Entry Price:        50000")
    print(f"  Current Price:      49500")
    print(f"  P&L %:              -1.00%")
    
    # 检查止损
    should_close, reason = manager.comprehensive_check(
        'BTC',
        account_collateral=10000,
        account_equity=10000
    )
    
    print(f"\nStop Loss Check:")
    print(f"  Should Close:       {should_close}")
    if reason:
        print(f"  Reason:             {reason}")
    else:
        print(f"  Status:             ✅ No stop loss triggered")


if __name__ == "__main__":
    # 运行演示
    demo_kelly_sizing()
    demo_stop_loss()
    run_example()
    
    print("\n✅ All examples completed!")
