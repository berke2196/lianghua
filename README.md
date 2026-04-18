# 🚀 AsterDex HFT Trader v5.0

**高频交易自动化平台** - 支持多币种、智能参数优化、实时监控

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![React](https://img.shields.io/badge/React-18.2-blue)
![Status](https://img.shields.io/badge/Status-Testing-yellow)

---

## 📋 目录
- [快速开始](#快速开始)
- [系统要求](#系统要求)
- [功能特性](#功能特性)
- [配置指南](#配置指南)
- [常见问题](#常见问题)
- [性能指标](#性能指标)

---

## 🚀 快速开始

### 1️⃣ 环境准备

```bash
# 克隆项目
git clone <repo-url>
cd 塞子

# 安装Python依赖
pip install -r requirements.txt

# 安装Node依赖
npm install

# 安装图表库
npm install recharts dayjs
```

### 2️⃣ 配置交易所认证

编辑 `config.py`：

```python
class Config:
    ASTER_BASE = "https://fapi.asterdex.com"  # 交易所API
    ASTER_WS = "wss://fstream.asterdex.com"   # WebSocket
    CORS_ORIGINS = ["http://localhost:3000"]  # 前端地址
```

### 3️⃣ 启动应用

```bash
# 终端1: 启动React前端
npm start
# 访问 http://localhost:3000

# 终端2: 启动FastAPI后端
python asterdex_backend.py
# 后端运行在 http://localhost:8000

# 或使用Electron桌面应用
npm run dev
```

### 4️⃣ 系统诊断

```bash
# 检查所有组件状态
curl http://localhost:8000/api/diagnostics | jq '.'

# 预期输出：
# {
#   "backend": { "logged_in": true, "auth_ready": "✅" },
#   "account": { "balance": 1000.00, "available": 950.00 },
#   "market": { "prices_count": 5, "klines_symbols": [...] }
# }
```

---

## 💻 系统要求

| 组件 | 最低版本 | 建议版本 |
|------|---------|--------|
| Python | 3.8 | 3.10+ |
| Node.js | 14 | 18+ |
| RAM | 2GB | 4GB+ |
| 网络 | 10Mbps | 100Mbps+ |

### 依赖包

- **Backend**: FastAPI, uvicorn, aiohttp, eth-account, pydantic
- **Frontend**: React 18, Ant Design 5, Recharts
- **Desktop**: Electron 27

---

## ✨ 功能特性

### 🎯 核心策略

- **7维度加权信号**
  - Supertrend (趋势)
  - EMA三线 (移动平均)
  - MACD (动量)
  - RSI (超买超卖)
  - VWAP (成交量加权)
  - OBI (订单簿不平衡)
  - Momentum (动量)

- **智能风控**
  - ✅ 止损/止盈
  - ✅ 移动止损 (ATR自适应)
  - ✅ 日亏损熔断
  - ✅ 仓位上限控制
  - ✅ 冷却期防反复

### 📊 自动优化

- **参数网格搜索** - 自动寻找最优参数
- **回测分析** - 历史数据验证
- **实时推荐** - 基于当前交易数据的优化建议

### 🖥️ 仪表板

- **实时交易** - 启停、参数调整、平仓
- **性能分析** - 胜率、盈亏、回撤曲线
- **币种监控** - 多币种并行监控
- **参数优化** - 可视化优化结果

### 🔐 安全性

- **EIP-712结构化签名** - 业界标准加密
- **私钥不落盘** - 仅存内存，不记录日志
- **CORS硬化** - 限制访问源
- **Electron隔离** - 预加载脚本隔离

---

## ⚙️ 配置指南

### 交易参数

```json
{
  "strategy": "crypto_hft",           // 策略名称
  "symbol": "BTCUSDT",                // 主要币种
  "active_symbols": ["BTCUSDT", "ETHUSDT"],  // 多币种
  
  // 仓位管理
  "leverage": 2,                      // 杠杆倍数 (1-20)
  "trade_size_usd": 10,               // 单笔下单金额
  "max_open_positions": 3,            // 最多持仓数
  
  // 信号过滤
  "min_confidence": 0.70,             // 最小置信度 (0.5-0.9)
  "hft_mode": "balanced",             // balanced/conservative/aggressive
  
  // 止损止盈
  "stop_loss_pct": 0.012,             // 止损 1.2%
  "take_profit_pct": 0.028,           // 止盈 2.8%
  
  // 风险控制
  "max_daily_loss_usd": 50,           // 日亏损熔断
  "cooldown_secs": 60,                // 平仓后冷却期
  "hft_interval_ms": 500              // 检查间隔
}
```

### 币种独立参数

```json
{
  "symbol_settings": {
    "BTCUSDT": {
      "leverage": 3,
      "min_confidence": 0.72,
      "take_profit_pct": 0.04
    },
    "ETHUSDT": {
      "leverage": 2,
      "min_confidence": 0.65,
      "take_profit_pct": 0.03
    }
  }
}
```

---

## 📈 API 文档

### 认证

```bash
POST /api/auth/login
Content-Type: application/json

{
  "user": "0x...",           // 主账户地址
  "signer": "0x...",         // API钉包地址
  "private_key": "0x..."     // API钉包私钥
}
```

### 交易控制

```bash
# 启动交易
POST /api/trading/start

# 停止交易
POST /api/trading/stop

# 获取状态
GET /api/trading/status

# 平仓
POST /api/trading/close_position
{ "symbol": "BTCUSDT" }

# 测试下单
POST /api/trading/test_order
{ "symbol": "BTCUSDT", "side": "BUY" }
```

### 分析与优化

```bash
# 诊断系统
GET /api/diagnostics

# 获取指标
GET /api/trading/indicators?symbol=BTCUSDT

# 运行优化
POST /api/optimize/run

# 获取优化建议
GET /api/strategy/recommendations

# 获取交易日志
GET /api/trading/logs?limit=500
```

### WebSocket

```javascript
// 连接
const ws = new WebSocket('ws://localhost:8000/ws/frontend');

// 监听消息
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: prices, orderbook, new_trade, account_update, etc.
};

// 心跳
setInterval(() => ws.send(JSON.stringify({type: 'ping'})), 30000);
```

---

## 🐛 常见问题

### Q1: 所有订单都是failed怎么办？

```
A: 按以下步骤诊断:
  1. curl http://localhost:8000/api/diagnostics
  2. 检查 auth_ready 是否为 ✅
  3. 查看后端日志: tail -50 logs/trading.log
  4. 尝试 /api/trading/test_order
  5. 验证私钥格式和账户设置
```

### Q2: 怎样提高胜率？

```
A: 参考 OPTIMIZATION_GUIDE.md 中的建议:
  - 降低 min_confidence (0.70 → 0.65)
  - 增加 take_profit_pct (2.8% → 3.5%)
  - 检查 ADX > 22 过滤是否生效
  - 运行参数优化 (/api/optimize/run)
```

### Q3: 如何进行多币种交易？

```
A: 配置 active_symbols:
  {
    "active_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    "max_open_positions": 3
  }
```

### Q4: 能否修改交易费率？

```
A: 交易费率由交易所决定 (Taker 0.05%)
   系统已在 _log_trade 中计算费用:
   fee = notional * 0.0005
```

---

## 📊 性能指标

### 期望目标

| 阶段 | 交易笔数 | 胜率目标 | 最大回撤 | 完成时间 |
|------|--------|--------|---------|---------|
| 测试 | 20 | >50% | <$50 | 2周 |
| 验证 | 100 | >55% | <$100 | 4周 |
| 稳定 | 500+ | >55% | <15% | 8周+ |

### 当前状态

```
交易笔数: 0 (需要修复交易执行)
胜率: N/A
总盈亏: $0
系统状态: 🟡 Testing
```

---

## 📚 文档

| 文件 | 内容 |
|------|------|
| [OPTIMIZATION_GUIDE.md](./OPTIMIZATION_GUIDE.md) | 完整的优化路线图和最佳实践 |
| [PROJECT_ASSESSMENT.md](./PROJECT_ASSESSMENT.md) | 项目评估报告和改进方案 |
| [config.py](./config.py) | 配置文件说明 |

---

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## ⚠️ 免责声明

**此项目仅用于教育目的，不构成投资建议。**

- 加密货币交易存在高风险
- 过去的性能不代表未来结果
- 在使用真实资金前，请充分理解风险
- 建议从小额测试开始

---

## 📞 支持

- 📧 Email: support@example.com
- 🐛 Issues: [GitHub Issues](https://github.com/...)
- 📖 Docs: [完整文档](./docs/)

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

**版本**: 5.0.0-beta  
**最后更新**: 2026年4月18日  
**状态**: 🟡 Testing Phase
