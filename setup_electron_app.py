"""
Electron应用完整构建脚本
"""

import os
import subprocess
import sys
import json
from pathlib import Path

root = r"c:\Users\北神大帝\Desktop\塞子"
os.chdir(root)

print("\n" + "="*70)
print("🛠️  构建 Electron 交易应用")
print("="*70 + "\n")

# 1. 创建必要目录
print("[1/5] 创建目录结构...")
dirs = [
    "src/components",
    "src/styles",
    "public",
    "build"
]

for d in dirs:
    Path(os.path.join(root, d)).mkdir(parents=True, exist_ok=True)
    print(f"  ✅ {d}")

# 2. 创建React应用结构
print("\n[2/5] 创建React组件...")

# App.js
app_js = '''import React, { useState, useEffect } from 'react';
import './App.css';
import LeftToolbar from './components/LeftToolbar';
import TradingChart from './components/TradingChart';
import RightPanel from './components/RightPanel';
import TopBar from './components/TopBar';

function App() {
  const [tradingState, setTradingState] = useState({
    isRunning: false,
    balance: 10000,
    pnl: 0,
    positions: []
  });

  const [selectedSymbol, setSelectedSymbol] = useState('BTC');

  return (
    <div className="app-container">
      <TopBar balance={tradingState.balance} pnl={tradingState.pnl} isRunning={tradingState.isRunning} />
      <div className="main-content">
        <LeftToolbar selectedSymbol={selectedSymbol} onSymbolChange={setSelectedSymbol} isRunning={tradingState.isRunning} />
        <TradingChart symbol={selectedSymbol} />
        <RightPanel tradingState={tradingState} />
      </div>
    </div>
  );
}

export default App;
'''

with open('src/App.js', 'w', encoding='utf-8') as f:
    f.write(app_js)
print("  ✅ App.js")

# LeftToolbar.js
left_toolbar = '''import React, { useState } from 'react';
import '../styles/LeftToolbar.css';

function LeftToolbar({ selectedSymbol, onSymbolChange, isRunning }) {
  const symbols = ['BTC', 'ETH', 'SOL', 'ARB', 'XRP'];
  const [config, setConfig] = useState({
    strategy: 'mixed',
    leverage: 2,
    riskPerTrade: 1,
    maxPositions: 3
  });

  return (
    <div className="left-toolbar">
      <div className="toolbar-section">
        <h3>📊 币种选择</h3>
        <div className="symbol-list">
          {symbols.map(sym => (
            <button
              key={sym}
              className={`symbol-btn ${selectedSymbol === sym ? 'active' : ''}`}
              onClick={() => onSymbolChange(sym)}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      <div className="toolbar-section">
        <h3>🤖 算法配置</h3>
        <label>
          <span>策略</span>
          <select value={config.strategy} onChange={(e) => setConfig({...config, strategy: e.target.value})}>
            <option value="high_freq">高频交易</option>
            <option value="trend">趋势跟踪</option>
            <option value="mixed">混合策略</option>
            <option value="arbitrage">套利</option>
          </select>
        </label>
        <label>
          <span>杠杆</span>
          <input type="range" min="1" max="10" value={config.leverage} onChange={(e) => setConfig({...config, leverage: parseInt(e.target.value)})} />
          <span>{config.leverage}x</span>
        </label>
      </div>

      <div className="toolbar-section">
        <h3>🚀 控制</h3>
        <button className="btn btn-start" disabled={isRunning}>启动交易</button>
        <button className="btn btn-stop" disabled={!isRunning}>停止交易</button>
      </div>

      <div className="toolbar-section">
        <h3>📈 状态</h3>
        <div className={isRunning ? 'running' : 'stopped'}>
          {isRunning ? '🟢 运行中' : '🔴 已停止'}
        </div>
      </div>
    </div>
  );
}

export default LeftToolbar;
'''

with open('src/components/LeftToolbar.js', 'w', encoding='utf-8') as f:
    f.write(left_toolbar)
print("  ✅ LeftToolbar.js")

# TradingChart.js
trading_chart = '''import React, { useEffect, useState } from 'react';
import '../styles/TradingChart.css';

function TradingChart({ symbol }) {
  const [price, setPrice] = useState(45000);
  const [change, setChange] = useState(2.5);

  useEffect(() => {
    const timer = setInterval(() => {
      setPrice(prev => prev + (Math.random() - 0.5) * 100);
      setChange(prev => prev + (Math.random() - 0.5) * 0.2);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="trading-chart">
      <div className="chart-header">
        <h2>{symbol}/USDT</h2>
        <div className="price-info">
          <span className="price">${price.toFixed(2)}</span>
          <span className={`change ${change >= 0 ? 'positive' : 'negative'}`}>
            {change >= 0 ? '📈' : '📉'} {change.toFixed(2)}%
          </span>
        </div>
      </div>
      <div className="chart-canvas">
        <div className="chart-placeholder">
          K线图表 - {symbol}
          <br />
          <small>连接后显示实时数据</small>
        </div>
      </div>
    </div>
  );
}

export default TradingChart;
'''

with open('src/components/TradingChart.js', 'w', encoding='utf-8') as f:
    f.write(trading_chart)
print("  ✅ TradingChart.js")

# RightPanel.js
right_panel = '''import React, { useState } from 'react';
import '../styles/RightPanel.css';

function RightPanel({ tradingState }) {
  const [orderType, setOrderType] = useState('buy');
  const [price, setPrice] = useState(45000);
  const [amount, setAmount] = useState(0.1);

  return (
    <div className="right-panel">
      <div className="panel-section">
        <h3>💰 账户信息</h3>
        <div className="account-info">
          <div className="info-item">
            <span>余额</span>
            <strong>${tradingState.balance.toFixed(2)}</strong>
          </div>
          <div className="info-item">
            <span>收益</span>
            <strong className={tradingState.pnl >= 0 ? 'positive' : 'negative'}>
              ${tradingState.pnl.toFixed(2)}
            </strong>
          </div>
          <div className="info-item">
            <span>持仓数</span>
            <strong>{tradingState.positions.length}</strong>
          </div>
        </div>
      </div>

      <div className="panel-section">
        <h3>📊 下单</h3>
        <div className="order-form">
          <div className="order-type">
            <button className={orderType === 'buy' ? 'active' : ''} onClick={() => setOrderType('buy')}>买入</button>
            <button className={orderType === 'sell' ? 'active' : ''} onClick={() => setOrderType('sell')}>卖出</button>
          </div>

          <label>
            <span>价格</span>
            <input type="number" value={price} onChange={(e) => setPrice(parseFloat(e.target.value))} />
          </label>

          <label>
            <span>数量</span>
            <input type="number" value={amount} step="0.01" onChange={(e) => setAmount(parseFloat(e.target.value))} />
          </label>

          <button className={`order-btn ${orderType}`}>
            {orderType === 'buy' ? '🟢 买入' : '🔴 卖出'}
          </button>
        </div>
      </div>

      <div className="panel-section">
        <h3>📈 持仓</h3>
        <div className="positions">
          {tradingState.positions.length === 0 ? (
            <div className="empty">无持仓</div>
          ) : (
            tradingState.positions.map((pos, i) => (
              <div key={i} className="position-item">
                <span>{pos.symbol}</span>
                <span>{pos.amount}个</span>
                <span className={pos.pnl >= 0 ? 'positive' : 'negative'}>{pos.pnl}%</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default RightPanel;
'''

with open('src/components/RightPanel.js', 'w', encoding='utf-8') as f:
    f.write(right_panel)
print("  ✅ RightPanel.js")

# TopBar.js
top_bar = '''import React from 'react';
import '../styles/TopBar.css';

function TopBar({ balance, pnl, isRunning }) {
  return (
    <div className="top-bar">
      <div className="logo">🚀 Hyperliquid AI Trader v2</div>
      <div className="stats">
        <div className="stat">
          <span>账户余额</span>
          <strong>${balance.toFixed(2)}</strong>
        </div>
        <div className="stat">
          <span>收益</span>
          <strong className={pnl >= 0 ? 'positive' : 'negative'}>${pnl.toFixed(2)}</strong>
        </div>
        <div className="stat">
          <span>状态</span>
          <strong>{isRunning ? '🟢 交易中' : '🔴 已停止'}</strong>
        </div>
      </div>
    </div>
  );
}

export default TopBar;
'''

with open('src/components/TopBar.js', 'w', encoding='utf-8') as f:
    f.write(top_bar)
print("  ✅ TopBar.js")

# 3. 创建CSS样式
print("\n[3/5] 创建样式文件...")

app_css = '''* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: #1a1a2e;
  color: #fff;
}

.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

.main-content {
  display: flex;
  flex: 1;
  overflow: hidden;
}
'''

with open('src/App.css', 'w', encoding='utf-8') as f:
    f.write(app_css)
print("  ✅ App.css")

top_bar_css = '''.top-bar {
  background: rgba(0, 0, 0, 0.5);
  border-bottom: 1px solid #0f3460;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  backdrop-filter: blur(10px);
}

.logo {
  font-size: 18px;
  font-weight: bold;
  color: #00d4ff;
}

.stats {
  display: flex;
  gap: 40px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat span {
  font-size: 12px;
  color: #888;
  text-transform: uppercase;
}

.stat strong {
  font-size: 16px;
  margin-top: 4px;
}

.positive {
  color: #00ff00;
}

.negative {
  color: #ff0000;
}
'''

with open('src/styles/TopBar.css', 'w', encoding='utf-8') as f:
    f.write(top_bar_css)
print("  ✅ TopBar.css")

left_toolbar_css = '''.left-toolbar {
  width: 280px;
  background: rgba(15, 52, 96, 0.3);
  border-right: 1px solid #0f3460;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.toolbar-section {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid #0f3460;
  border-radius: 8px;
  padding: 16px;
}

.toolbar-section h3 {
  font-size: 14px;
  margin-bottom: 12px;
  color: #00d4ff;
  text-transform: uppercase;
}

.symbol-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.symbol-btn {
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid #0f3460;
  color: #fff;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: bold;
  transition: all 0.3s;
}

.symbol-btn:hover {
  background: rgba(0, 212, 255, 0.2);
}

.symbol-btn.active {
  background: #00d4ff;
  color: #000;
  border-color: #00d4ff;
}

label {
  display: flex;
  flex-direction: column;
  margin-bottom: 12px;
  font-size: 12px;
}

label span {
  margin-bottom: 4px;
  color: #aaa;
}

label input,
label select {
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid #0f3460;
  color: #fff;
  padding: 6px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.control-buttons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.btn {
  padding: 10px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: bold;
  transition: all 0.3s;
}

.btn-start {
  background: #00ff00;
  color: #000;
}

.btn-start:hover:not(.disabled) {
  transform: scale(1.05);
}

.btn-start.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-stop {
  background: #ff0000;
  color: #fff;
}

.btn-stop:hover:not(.disabled) {
  transform: scale(1.05);
}

.btn-stop.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.status-info {
  font-size: 12px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.running {
  color: #00ff00;
}

.stopped {
  color: #ff0000;
}
'''

with open('src/styles/LeftToolbar.css', 'w', encoding='utf-8') as f:
    f.write(left_toolbar_css)
print("  ✅ LeftToolbar.css")

trading_chart_css = '''.trading-chart {
  flex: 1;
  background: rgba(0, 0, 0, 0.3);
  border-left: 1px solid #0f3460;
  border-right: 1px solid #0f3460;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chart-header {
  background: rgba(0, 0, 0, 0.5);
  border-bottom: 1px solid #0f3460;
  padding: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-header h2 {
  font-size: 18px;
  color: #00d4ff;
}

.price-info {
  display: flex;
  gap: 20px;
  align-items: center;
}

.price {
  font-size: 20px;
  font-weight: bold;
}

.change {
  font-size: 16px;
}

.chart-canvas {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, rgba(15, 52, 96, 0.2), rgba(0, 0, 0, 0.2));
}

.chart-placeholder {
  text-align: center;
  color: #666;
  font-size: 18px;
}
'''

with open('src/styles/TradingChart.css', 'w', encoding='utf-8') as f:
    f.write(trading_chart_css)
print("  ✅ TradingChart.css")

right_panel_css = '''.right-panel {
  width: 320px;
  background: rgba(15, 52, 96, 0.3);
  border-left: 1px solid #0f3460;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-section {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid #0f3460;
  border-radius: 8px;
  padding: 16px;
}

.panel-section h3 {
  font-size: 14px;
  margin-bottom: 12px;
  color: #00d4ff;
  text-transform: uppercase;
}

.account-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
}

.info-item span {
  color: #aaa;
}

.info-item strong {
  color: #00d4ff;
}

.order-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.order-type {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.order-type button {
  background: rgba(0, 212, 255, 0.1);
  border: 1px solid #0f3460;
  color: #fff;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.3s;
}

.order-type button.active {
  background: #00d4ff;
  color: #000;
}

.order-form label {
  font-size: 12px;
}

.order-form input {
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid #0f3460;
  color: #fff;
  padding: 8px;
  border-radius: 4px;
}

.order-btn {
  padding: 10px;
  border: none;
  border-radius: 4px;
  font-weight: bold;
  cursor: pointer;
  transition: all 0.3s;
}

.order-btn.buy {
  background: #00ff00;
  color: #000;
}

.order-btn.buy:hover {
  transform: scale(1.05);
}

.order-btn.sell {
  background: #ff0000;
  color: #fff;
}

.order-btn.sell:hover {
  transform: scale(1.05);
}

.positions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
}

.empty {
  text-align: center;
  color: #666;
  padding: 16px;
}

.position-item {
  display: flex;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.5);
  padding: 8px;
  border-radius: 4px;
}
'''

with open('src/styles/RightPanel.css', 'w', encoding='utf-8') as f:
    f.write(right_panel_css)
print("  ✅ RightPanel.css")

# 4. 创建public目录文件
print("\n[4/5] 创建HTML和资源文件...")

index_html = '''<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="theme-color" content="#000000" />
    <meta name="description" content="Hyperliquid AI Trading System" />
    <title>Hyperliquid AI Trader v2</title>
    <style>
      body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
      #root { width: 100%; height: 100vh; }
    </style>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
'''

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(index_html)
print("  ✅ index.html")

# 5. 创建index.js
print("\n[5/5] 创建React入口文件...")

index_js = '''import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
'''

with open('src/index.js', 'w', encoding='utf-8') as f:
    f.write(index_js)
print("  ✅ index.js")

print("\n" + "="*70)
print("✅ Electron应用结构已创建！")
print("="*70)
print("\n接下来运行:")
print("  1. npm install")
print("  2. npm start")
print("\n" + "="*70 + "\n")
