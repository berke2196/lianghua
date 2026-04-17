import React, { useState } from 'react';

function RightPanel({ tradingState }) {
  const [orderType, setOrderType] = useState('buy');
  const [price, setPrice] = useState(45000);
  const [amount, setAmount] = useState(0.1);

  return (
    <div style={{
      width: '320px',
      background: 'rgba(15, 52, 96, 0.3)',
      borderLeft: '1px solid #0f3460',
      overflowY: 'auto',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '16px'
    }}>
      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          💰 账户信息
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
            <span style={{ color: '#aaa' }}>余额</span>
            <strong style={{ color: '#00d4ff' }}>${tradingState.balance.toFixed(2)}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
            <span style={{ color: '#aaa' }}>收益</span>
            <strong style={{ color: tradingState.pnl >= 0 ? '#00ff00' : '#ff0000' }}>
              ${tradingState.pnl.toFixed(2)}
            </strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
            <span style={{ color: '#aaa' }}>持仓数</span>
            <strong>{tradingState.positions.length}</strong>
          </div>
        </div>
      </div>

      <div style={{
        background: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid #0f3460',
        borderRadius: '8px',
        padding: '16px'
      }}>
        <h3 style={{ fontSize: '14px', marginBottom: '12px', color: '#00d4ff', textTransform: 'uppercase' }}>
          📊 下单
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <button
              onClick={() => setOrderType('buy')}
              style={{
                background: orderType === 'buy' ? '#00d4ff' : 'rgba(0, 212, 255, 0.1)',
                border: '1px solid #0f3460',
                color: orderType === 'buy' ? '#000' : '#fff',
                padding: '8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              买入
            </button>
            <button
              onClick={() => setOrderType('sell')}
              style={{
                background: orderType === 'sell' ? '#00d4ff' : 'rgba(0, 212, 255, 0.1)',
                border: '1px solid #0f3460',
                color: orderType === 'sell' ? '#000' : '#fff',
                padding: '8px',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '12px'
              }}
            >
              卖出
            </button>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', fontSize: '12px' }}>
            <span style={{ marginBottom: '4px', color: '#aaa' }}>价格</span>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(parseFloat(e.target.value))}
              style={{
                background: 'rgba(0, 0, 0, 0.5)',
                border: '1px solid #0f3460',
                color: '#fff',
                padding: '8px',
                borderRadius: '4px'
              }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', fontSize: '12px' }}>
            <span style={{ marginBottom: '4px', color: '#aaa' }}>数量</span>
            <input
              type="number"
              value={amount}
              step="0.01"
              onChange={(e) => setAmount(parseFloat(e.target.value))}
              style={{
                background: 'rgba(0, 0, 0, 0.5)',
                border: '1px solid #0f3460',
                color: '#fff',
                padding: '8px',
                borderRadius: '4px'
              }}
            />
          </label>

          <button style={{
            background: orderType === 'buy' ? '#00ff00' : '#ff0000',
            color: orderType === 'buy' ? '#000' : '#fff',
            padding: '10px',
            border: 'none',
            borderRadius: '4px',
            fontWeight: 'bold',
            cursor: 'pointer'
          }}>
            {orderType === 'buy' ? '🟢 买入' : '🔴 卖出'}
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
          📈 持仓
        </h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
          {tradingState.positions.length === 0 ? (
            <div style={{ textAlign: 'center', color: '#666', padding: '16px' }}>无持仓</div>
          ) : (
            tradingState.positions.map((pos, i) => (
              <div key={i} style={{
                display: 'flex',
                justifyContent: 'space-between',
                background: 'rgba(0, 0, 0, 0.5)',
                padding: '8px',
                borderRadius: '4px'
              }}>
                <span>{pos.symbol}</span>
                <span>{pos.amount}个</span>
                <span style={{ color: pos.pnl >= 0 ? '#00ff00' : '#ff0000' }}>{pos.pnl}%</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

export default RightPanel;
