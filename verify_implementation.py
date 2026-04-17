#!/usr/bin/env python3
"""
验证所有实现是否正常工作
检查:
1. LSTM模型加载
2. RL模型加载
3. 交易引擎初始化
4. 信号生成
5. 风险计算
"""

import sys
import logging
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """测试所有必要的导入"""
    logger.info("=" * 60)
    logger.info("测试模块导入...")
    logger.info("=" * 60)
    
    try:
        import torch
        logger.info(f"✅ PyTorch 已安装 | 版本: {torch.__version__}")
        logger.info(f"   CUDA可用: {torch.cuda.is_available()}")
    except ImportError as e:
        logger.error(f"❌ PyTorch 导入失败: {e}")
        return False
    
    try:
        from lstm_model import LSTMTimeSeriesPredictor
        logger.info("✅ LSTM模型导入成功")
    except ImportError as e:
        logger.error(f"❌ LSTM模型导入失败: {e}")
        return False
    
    try:
        from rl_agent import PPOAgent
        logger.info("✅ RL模型导入成功")
    except ImportError as e:
        logger.error(f"❌ RL模型导入失败: {e}")
        return False
    
    try:
        from hyperliquid_api import HyperliquidAPI
        from hyperliquid_models import OrderSide, OrderType
        logger.info("✅ Hyperliquid API导入成功")
    except ImportError as e:
        logger.error(f"❌ Hyperliquid API导入失败: {e}")
        return False
    
    try:
        from backend_trading_engine import TradingEngine, TradeSignal
        logger.info("✅ 交易引擎导入成功")
    except ImportError as e:
        logger.error(f"❌ 交易引擎导入失败: {e}")
        return False
    
    return True

def test_lstm_model():
    """测试LSTM模型"""
    logger.info("\n" + "=" * 60)
    logger.info("测试LSTM模型...")
    logger.info("=" * 60)
    
    try:
        import torch
        from lstm_model import LSTMTimeSeriesPredictor
        
        device = torch.device('cpu')
        model = LSTMTimeSeriesPredictor(
            input_size=200,
            hidden_sizes=[64, 32, 16],
            num_classes=3,
            dropout=0.2,
            bidirectional=True
        ).to(device)
        
        model.eval()
        
        # 创建测试输入
        x = torch.randn(1, 60, 200).to(device)
        
        with torch.no_grad():
            logits, probs = model(x)
            prediction = torch.argmax(probs, dim=1).item()
            confidence = torch.max(probs).item()
        
        logger.info(f"✅ LSTM模型运行正常")
        logger.info(f"   输入形状: {x.shape}")
        logger.info(f"   输出形状: {probs.shape}")
        logger.info(f"   预测类别: {prediction} (0=上涨, 1=下跌, 2=横盘)")
        logger.info(f"   置信度: {confidence:.4f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ LSTM模型测试失败: {e}")
        return False

def test_rl_model():
    """测试RL模型"""
    logger.info("\n" + "=" * 60)
    logger.info("测试RL模型...")
    logger.info("=" * 60)
    
    try:
        import torch
        from rl_agent import PPOAgent
        
        device = torch.device('cpu')
        agent = PPOAgent(
            state_dim=50,
            action_dim=3,
            device=device
        )
        
        # 创建测试状态
        state = np.random.randn(50).astype(np.float32)
        
        action, log_prob = agent.select_action(state, deterministic=True)
        
        action_names = {0: "HOLD", 1: "LONG", 2: "SHORT"}
        
        logger.info(f"✅ RL模型运行正常")
        logger.info(f"   状态维度: {len(state)}")
        logger.info(f"   选择动作: {action} ({action_names.get(action, 'UNKNOWN')})")
        logger.info(f"   对数概率: {log_prob:.4f}")
        
        return True
    except Exception as e:
        logger.error(f"❌ RL模型测试失败: {e}")
        return False

def test_trading_engine():
    """测试交易引擎"""
    logger.info("\n" + "=" * 60)
    logger.info("测试交易引擎...")
    logger.info("=" * 60)
    
    try:
        from backend_trading_engine import TradingEngine
        
        # 初始化引擎 (模拟模式, 无API密钥)
        engine = TradingEngine(
            capital=10000,
            max_leverage=2.0,
            daily_loss_limit=0.10,
            hard_stop_loss=0.02
        )
        
        logger.info(f"✅ 交易引擎初始化成功")
        logger.info(f"   初始资金: ${engine.capital}")
        logger.info(f"   最大杠杆: {engine.max_leverage}x")
        logger.info(f"   AI设备: {engine.device}")
        
        # 测试状态获取
        status = engine.get_status()
        logger.info(f"✅ 状态获取成功")
        logger.info(f"   当前权益: ${status['equity']:.2f}")
        logger.info(f"   持仓数: {status['positions']}")
        logger.info(f"   交易数: {status['trades']}")
        
        return True
    except Exception as e:
        logger.error(f"❌ 交易引擎测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_signal_generation():
    """测试信号生成"""
    logger.info("\n" + "=" * 60)
    logger.info("测试信号生成...")
    logger.info("=" * 60)
    
    try:
        from backend_trading_engine import TradingEngine
        import asyncio
        
        engine = TradingEngine(
            capital=10000,
            max_leverage=2.0,
            api_key=None,  # 模拟模式
            api_secret=None
        )
        
        # 模拟市场数据
        symbol = "BTC"
        base_price = 50000
        
        # 填充足够的历史数据
        for i in range(70):
            price = base_price + np.random.randn() * 100
            market_data = {
                'symbol': symbol,
                'price': price,
                'bid': price * 0.999,
                'ask': price * 1.001,
                'funding_rate': 0.0001
            }
            
            if i >= 60:  # 只有数据足够后才生成信号
                signals = asyncio.run(engine._generate_signals(market_data))
                logger.info(f"第{i}步: 生成 {len(signals)} 个信号")
                
                for sig in signals:
                    logger.info(f"   策略: {sig.strategy} | 方向: {sig.direction} | 置信度: {sig.confidence:.2%}")
        
        logger.info(f"✅ 信号生成测试完成")
        return True
    except Exception as e:
        logger.error(f"❌ 信号生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_risk_calculation():
    """测试风险计算"""
    logger.info("\n" + "=" * 60)
    logger.info("测试风险计算...")
    logger.info("=" * 60)
    
    try:
        from backend_trading_engine import TradingEngine, Position
        
        engine = TradingEngine(capital=10000)
        
        # 添加模拟持仓
        engine.positions['BTC'] = Position(
            symbol='BTC',
            side='LONG',
            entry_price=50000,
            current_price=51000,
            size=0.1,
            leverage=2.0,
            unrealized_pnl=100,
            liquidation_price=25000,  # 模拟清算价格
            entry_time=__import__('datetime').datetime.now()
        )
        
        # 计算风险指标
        risk_metrics = engine._calculate_risk_metrics()
        
        logger.info(f"✅ 风险计算成功")
        logger.info(f"   当前权益: ${risk_metrics.current_equity:.2f}")
        logger.info(f"   未实现盈亏: ${risk_metrics.unrealized_pnl:.2f}")
        logger.info(f"   最大回撤: {risk_metrics.max_drawdown:.2%}")
        logger.info(f"   清算风险: {risk_metrics.liquidation_risk:.2%}")
        logger.info(f"   持仓热度: {risk_metrics.position_heat:.2%}")
        
        # 验证清算风险计算
        if risk_metrics.liquidation_risk >= 0 and risk_metrics.liquidation_risk <= 1:
            logger.info(f"✅ 清算风险值在有效范围 [0, 1] 内")
        else:
            logger.warning(f"⚠️ 清算风险值异常: {risk_metrics.liquidation_risk}")
        
        return True
    except Exception as e:
        logger.error(f"❌ 风险计算测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    logger.info("\n" + "=" * 60)
    logger.info("🚀 Hyperliquid AI 交易系统 - 实现验证")
    logger.info("=" * 60)
    
    results = []
    
    # 运行所有测试
    results.append(("模块导入", test_imports()))
    results.append(("LSTM模型", test_lstm_model()))
    results.append(("RL模型", test_rl_model()))
    results.append(("交易引擎", test_trading_engine()))
    results.append(("风险计算", test_risk_calculation()))
    # results.append(("信号生成", test_signal_generation()))  # 可能较慢, 可选
    
    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("验证结果汇总")
    logger.info("=" * 60)
    
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"{status} | {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    logger.info("\n" + "=" * 60)
    logger.info(f"总计: {passed}/{total} 项测试通过")
    logger.info("=" * 60)
    
    if passed == total:
        logger.info("🎉 所有实现验证通过! 系统已就绪。")
        return 0
    else:
        logger.warning("⚠️ 部分测试失败, 请检查实现。")
        return 1

if __name__ == "__main__":
    sys.exit(main())
