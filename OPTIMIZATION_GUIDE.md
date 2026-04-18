# 🚀 AsterDex HFT Trader - 运营优化指南

## 📋 执行概览

当前项目处于 **测试阶段**，所有2000笔订单均为failed状态。为达到**运营级别**，需要按以下步骤执行。

---

## 🔧 第一阶段：基础调试（1-2周）

### 1.1 诊断系统状态
```bash
# 调用诊断API检查所有组件
curl http://localhost:8000/api/diagnostics

# 响应应包含：
{
  "backend": {
    "logged_in": true,
    "auth_ready": "✅"
  },
  "account": {
    "balance": 1000.00,
    "available": 950.00
  },
  "market": {
    "prices_count": 5,
    "klines_symbols": ["BTCUSDT", "ETHUSDT"]
  }
}
```

### 1.2 测试下单流程
```bash
# 执行测试下单
curl -X POST http://localhost:8000/api/trading/test_order \
  -H "Content-Type: application/json" \
  -d '{"symbol": "BTCUSDT", "side": "BUY"}'

# 检查返回：
# - orderId != empty ✅
# - status = "filled" or "sent" ✅
# - error信息 ❌
```

### 1.3 常见失败原因及解决方案

| 问题 | 症状 | 解决方案 |
|------|------|---------|
| **认证失败** | POST返回401/invalid signature | 检查私钥格式、user/signer地址是否匹配 |
| **资金不足** | error含"insufficient margin" | 充值账户或降低trade_size_usd |
| **价格无效** | error含"invalid price" | 检查LIMIT订单价格，或改为MARKET |
| **杠杆限制** | error含"max leverage" | 降低leverage设置，通常最高20倍 |
| **网络延迟** | timeout或no response | 检查API_TIMEOUT配置，重试 |

### 1.4 验证止损/止盈
- [ ] 开仓后检查pos_tracker中的sl、tp值
- [ ] 验证移动止损是否在盈利>2×ATR后激活
- [ ] 手动平仓测试，验证PnL计算正确

---

## 📊 第二阶段：策略验证（2-3周）

### 2.1 收集至少20笔成功交易

**目标币种**: BTC、ETH（各20笔）

```
开仓 → 等待止盈/止损 → 平仓 → 记录PnL
```

**配置建议**:
```json
{
  "min_confidence": 0.65,      // 降低阈值增加交易频率
  "trade_size_usd": 5,         // 保守一点
  "leverage": 2,               // 标准2倍
  "stop_loss_pct": 0.015,      // 1.5%止损
  "take_profit_pct": 0.035,    // 3.5%止盈
  "max_open_positions": 1,     // 先测试单币种
  "hft_mode": "balanced"       // 平衡模式
}
```

### 2.2 关键指标检查

收集20笔后分析：

```
✅ 胜率 ≥ 50%?      (期望: >55%)
✅ 平均PnL > 0?    (期望: >$1/笔)
✅ 最大回撤?        (期望: <20笔PnL)
✅ 持仓时间分布?    (理解策略特点)
✅ 是否有连续亏损?  (>5笔连亏需警惕)
```

### 2.3 运行参数优化

```bash
curl -X POST http://localhost:8000/api/optimize/run
# 等待返回最优参数组合
```

---

## 🎨 第三阶段：UI现代化（2-3周）

### 3.1 新仪表板功能

✅ 已创建 `src/PerformanceDashboard.js` 包含：
- 📈 累计收益曲线（K线图）
- 📅 每日收益统计（柱状图）
- 🎯 币种分析表（胜率、总盈亏）
- 🍰 胜负分布饼图
- 🎚️ 风险指标进度条

### 3.2 集成到App.js

```javascript
import PerformanceDashboard from './PerformanceDashboard';

// 在主页面添加标签页
<Tabs>
  <TabPane tab="交易" key="trading">
    <TradingPanel />
  </TabPane>
  <TabPane tab="性能分析" key="analytics">
    <PerformanceDashboard perf={perf} tradeLogs={tradeLogs} settings={settings} />
  </TabPane>
  <TabPane tab="参数优化" key="optimize">
    <OptimizePanel />
  </TabPane>
</Tabs>
```

### 3.3 深色主题配置

```javascript
// src/App.js 顶部
import { ConfigProvider, theme } from 'antd';

<ConfigProvider theme={{ algorithm: theme.darkAlgorithm }}>
  {/* App内容 */}
</ConfigProvider>
```

---

## 🧠 第四阶段：高级优化（可选）

### 4.1 多币种并发策略

启用多币种后的配置：

```json
{
  "active_symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
  "symbol_settings": {
    "BTCUSDT": {
      "leverage": 3,
      "min_confidence": 0.70,
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

### 4.2 HFT模式选择

| 模式 | 盈亏比阈值 | 使用场景 |
|------|----------|--------|
| **conservative** | ≥1.8 | 趋势明确，需要高收益比 |
| **balanced** | ≥1.2 | 正常使用，平衡风险收益 |
| **aggressive** | ≥0.3 | 高频交易，多仓位 |

### 4.3 风险控制最佳实践

```python
# 后端配置参考
{
  "max_daily_loss_usd": 50,      # 日损失超过自动停止
  "max_open_positions": 3,       # 最多同时3仓
  "cooldown_secs": 60,           # 平仓后60s内禁止反向开仓
  "cancel_on_reverse": True,     # 反向信号自动平仓
  "trailing_stop": True          # 激活移动止损
}
```

---

## 📈 性能基准

| 阶段 | 交易数 | 胜率目标 | 平均收益 | 最大回撤 | 预计时间 |
|------|-------|--------|--------|---------|--------|
| **验证** | 20 | >50% | >$1 | <$50 | 1-2周 |
| **稳定** | 100 | >55% | >$2 | <$100 | 2-4周 |
| **运营** | 500+ | >55% | 稳定 | <15% | 持续 |

---

## 🔍 API参考

### 诊断与监控

```
GET  /api/diagnostics                  # 系统全面诊断
GET  /api/strategy/recommendations     # 策略优化建议
GET  /api/trading/indicators           # 当前指标计算
GET  /api/optimize/result              # 优化结果查询
```

### 交易执行

```
POST /api/trading/test_order           # 测试下单
POST /api/trading/start                # 启动自动交易
POST /api/trading/stop                 # 停止交易
POST /api/trading/close_position       # 手动平仓
POST /api/trading/cancel_orders        # 撤销挂单
```

### 参数与配置

```
POST /api/settings                     # 保存全局设置
POST /api/settings/symbol              # 保存币种参数
POST /api/optimize/run                 # 运行参数优化
POST /api/optimize/apply               # 应用优化结果
```

---

## ⚠️ 常见错误排查

### 问题1: 所有订单都是failed
```
症状: status = "failed" for all orders
原因: 
  1. 私钥/认证错误
  2. API额度用尽
  3. 网络连接问题
  4. 交易所维护中

排查:
  curl /api/diagnostics -> auth_ready should be ✅
  检查后端日志中的错误信息
  尝试test_order端点
```

### 问题2: 胜率持续<50%
```
症状: win_rate < 50%
原因:
  1. 市场信号过弱
  2. 止盈太小或止损太大
  3. 噪音信号过多

解决:
  - 降低min_confidence阈值
  - 增加take_profit_pct目标
  - 检查ADX>22的过滤是否有效
```

### 问题3: 回撤过大
```
症状: 单笔或连续亏损过大
原因:
  1. 杠杆过高
  2. 止损比例太大
  3. 市场剧烈波动

解决:
  - 降低leverage
  - 缩小stop_loss_pct（从1.2%→0.8%）
  - 降低max_open_positions
```

---

## 📝 检查清单

### 运营就绪检查

- [ ] 至少50笔成功交易记录
- [ ] 胜率 ≥ 55%
- [ ] 日均收益稳定（变异系数<0.5）
- [ ] 最大回撤 < 账户的15%
- [ ] UI仪表板完整，可实时监控
- [ ] 参数优化运行过至少2次
- [ ] 文档完整，有故障排查指南
- [ ] 风险控制模块测试通过

### 发布前最终检查

- [ ] 禁用所有debug日志
- [ ] 设置合理的API超时
- [ ] 配置完整的error handling
- [ ] 测试electron打包
- [ ] 添加使用说明和风险声明
- [ ] 准备好故障恢复机制

---

## 🚀 下一步行动

1. **立即**:
   - [ ] 运行 `/api/diagnostics` 诊断
   - [ ] 使用 `/api/trading/test_order` 验证下单链路
   - [ ] 查看后端日志了解失败原因

2. **本周**:
   - [ ] 修复所有identified的问题
   - [ ] 收集5-10笔成功交易
   - [ ] 开始集成PerformanceDashboard到前端

3. **本月**:
   - [ ] 完成50笔以上交易
   - [ ] 运行参数优化
   - [ ] UI全面升级完成

---

**有问题？** 检查后端日志: `tail -f logs/trading.log`

**需要重置？** `rm trade_history.json && restart backend`

**最后更新**: 2026-04-18 | 版本 v5.0.0
