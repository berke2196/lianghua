import React from 'react';

function TopBar({ balance, pnl, isRunning }) {
  return (
    <div style={{
      background: 'rgba(0, 0, 0, 0.5)',
      borderBottom: '1px solid #0f3460',
      padding: '12px 20px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      backdropFilter: 'blur(10px)'
    }}>
      <div style={{
        fontSize: '18px',
        fontWeight: 'bold',
        color: '#00d4ff'
      }}>
        🚀 Hyperliquid AI Trader v2
      </div>

      <div style={{
        display: 'flex',
        gap: '40px'
      }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: '#888', textTransform: 'uppercase' }}>账户余额</span>
          <strong style={{ fontSize: '16px', marginTop: '4px' }}>${balance.toFixed(2)}</strong>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: '#888', textTransform: 'uppercase' }}>收益</span>
          <strong style={{
            fontSize: '16px',
            marginTop: '4px',
            color: pnl >= 0 ? '#00ff00' : '#ff0000'
          }}>
            ${pnl.toFixed(2)}
          </strong>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: '#888', textTransform: 'uppercase' }}>状态</span>
          <strong style={{
            fontSize: '16px',
            marginTop: '4px',
            color: isRunning ? '#00ff00' : '#ff0000'
          }}>
            {isRunning ? '🟢 交易中' : '🔴 已停止'}
          </strong>
        </div>
      </div>
    </div>
  );
}

export default TopBar;
