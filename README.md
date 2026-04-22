# 极客v99量化交易

> 🤖 基于 AsterDex 永续合约的全自动量化高频交易系统  
> **多策略信号融合 · 智能参数优化 · 实时风控 · 多用户SaaS**

[![Version](https://img.shields.io/badge/version-5.0.0-blue?style=flat-square)](https://github.com/berke2196/lianghua/releases)
[![Python](https://img.shields.io/badge/python-3.10+-green?style=flat-square)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square)](https://reactjs.org)
[![License](https://img.shields.io/badge/license-Private-red?style=flat-square)]()

---

## ✨ 核心功能

### 🧠 多维信号引擎
- **7大技术指标**加权融合：Supertrend · EMA三线 · MACD · RSI · VWAP · OBI订单簿 · 动量
- **Supertrend 硬性过滤**：趋势相反时强制压低置信度
- **均值回归模式**：震荡行情自动切换 OBI+RSI+VWAP 策略
- 四种 HFT 模式：`精准` / `平衡` / `激进` / `极速`

### 📊 智能参数优化（回测模块）
- **网格搜索**：自动测试 96 组参数组合（止损4×止盈4×置信3×模式2）
- **TOP3推荐**：按综合评分（盈利因子×胜率−最大回撤）排名
- **一键应用**：推荐参数直接写入策略，无需手动调整
- **无未来函数**：逐根K线切片模拟，防止数据泄露

### 🛡️ 实时风控
- 日亏损熔断（`daily_loss_limit`）
- 盈亏比动态校验
- 并发锁防止重复开仓
- 熔断器机制（连续失败5次自动切断30s）
- Guardian 平仓守护（防止重复平仓）

### 👥 多用户 SaaS
- JWT 认证 + Token 黑名单登出
- 授权码注册激活系统
- 管理后台：生成码 / 用户管理 / 延期 / 封禁 / 踢下线
- 每用户独立交易状态、设置、日志完全隔离

### 📱 其他
- Telegram 实时推送（开仓/平仓/风控报警）
- WebSocket 实时行情、指标、日志推送
- 自动参数优化（20笔平仓后触发，训练/验证集防过拟合）
- 多币种并发交易，每币种独立参数

---

## 🏗️ 技术栈

**后端**
- [FastAPI](https://fastapi.tiangolo.com) + uvicorn（ASGI异步框架）
- SQLite（多用户数据持久化）
- aiohttp（异步HTTP请求 AsterDex API）
- slowapi（请求限流防爆破）
- eth-account（以太坊钱包签名）
- cryptography（私钥Fernet加密）

**前端**
- React 18（hooks + 函数组件）
- recharts（K线/权益曲线图表）
- WebSocket（实时数据推送）

**部署**
- GitHub Pages（前端静态托管，域名 xb1.me）
- VPS + Nginx 反向代理 + Let's Encrypt SSL（后端）
- systemd 进程守护

---

## 📦 版本历史

### v5.0.0（2025.04）
- ✅ 新增**智能参数优化**：96组网格搜索 + TOP3推荐 + 一键应用
- ✅ 回测引擎迁移至线程池（`run_in_executor`），不再阻塞事件循环
- ✅ 修复回测强平 PnL 计算逻辑
- ✅ 新增 `/api/backtest/optimize` 和 `/api/backtest/apply` 接口
- ✅ 前端回测Tab重构：智能优化为主界面，普通回测折叠展示

### v4.x（2025.03）
- 多用户SaaS架构（JWT + 授权码系统）
- 管理后台（用户管理、延期、封禁、踢下线）
- 每用户独立交易状态完全隔离
- 熔断器机制 + Guardian平仓守护

### v3.x（2025.02）
- 7维度信号引擎（Supertrend/EMA/MACD/RSI/VWAP/OBI/动量）
- 四种HFT模式（精准/平衡/激进/极速）
- 日亏损熔断 + 盈亏比动态校验
- Telegram 实时通知

### v2.x（2025.01）
- 多币种并发交易
- WebSocket 实时行情推送
- 自动参数优化（历史平仓数据驱动）

### v1.x（2024.12）
- 基础单币种 HFT 框架
- AsterDex API 对接（永续合约开平仓）

---

## ⚠️ 免责声明

本项目仅供学习研究使用。量化交易存在亏损风险，使用本软件产生的任何损失由用户自行承担。

---

## � 联系 & 使用授权

本系统为**私有商业软件**，需授权码激活后方可使用。  
如需购买授权或了解详情，请联系作者。
