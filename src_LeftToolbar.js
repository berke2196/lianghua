import React, { useState } from 'react';

function LeftToolbar({ selectedSymbol, onSymbolChange, isRunning }) {
  const symbols = ['BTC', 'ETH', 'SOL', 'ARB', 'XRP'];
  const [config, setConfig] = useState({
    strategy: 'mixed',
    leverage: 2,
    riskPerTrade: 1,
    maxPositions: 3
  });

  return (
    <div style={{
      width: '280px',
      background: 'rgba(15, 52, 96, 0.3)',
      borderRight: '1px solid #0f3460',
      overflowY: 'auto',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '20px'
    }}>
      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          📊 币种选择
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
          {symbols.map(sym => (
            <button
              key={sym}
              onClick={() => onSymbolChange(sym)}
              style={{
                background: selectedSymbol === sym ? '#00d4ff' : 'rgba(0, 212, 255, 0.1)',
                border: '1px solid #0f3460',
                color: selectedSymbol === sym ? '#000' : '#fff',
                padding: '8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 'bold',
                transition: 'all 0.3s'
              }}
            >
              {sym}
            </button>
          ))}
        </div>
      </div>

      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          🤖 算法配置
        </h3>
        <label style={{ display: 'flex', flexDirection: 'column', marginBottom: '12px', fontSize: '12px' }}>
          <span style={{ marginBottom: '4px', color: '#aaa' }}>策略</span>
          <select style={{
            background: 'rgba(0, 0, 0, 0.5)',
            border: '1px solid #0f3460',
            color: '#fff',
            padding: '6px 8px',
            borderRadius: '4px'
          }}>
            <option>高频交易</option>
            <option>趋势跟踪</option>
            <option>混合策略</option>
            <option>套利</option>
          </select>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', marginBottom: '12px', fontSize: '12px' }}>
          <span style={{ marginBottom: '4px', color: '#aaa' }}>杠杆倍数</span>
          <input type="range" min="1" max="10" defaultValue="2" style={{ marginBottom: '4px' }} />
          <span>{config.leverage}x</span>
        </label>
      </div>

      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          🚀 控制
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button style={{
            background: '#00ff00',
            color: '#000',
            padding: '10px',
            border: 'none',
            borderRadius: '4px',
            cursor: isRunning ? 'not-allowed' : 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
            opacity: isRunning ? 0.5 : 1
          }} disabled={isRunning}>
            启动交易
          </button>
          <button style={{
            background: '#ff0000',
            color: '#fff',
            padding: '10px',
            border: 'none',
            borderRadius: '4px',
            cursor: !isRunning ? 'not-allowed' : 'pointer',
            fontSize: '12px',
            fontWeight: 'bold',
            opacity: !isRunning ? 0.5 : 1
          }} disabled={!isRunning}>
            停止交易
          </button>
        </div>
      </div>

      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          📈 状态
        </h3>
        <div style={{ color: isRunning ? '#00ff00' : '#ff0000' }}>
          {isRunning ? '🟢 运行中' : '🔴 已停止'}
        </div>
      </div>
    </div>
  );
}

export default LeftToolbar;
