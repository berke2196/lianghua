import React, { useEffect, useState } from 'react';

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
    <div style={{
      flex: 1,
      background: 'rgba(0, 0, 0, 0.3)',
      borderLeft: '1px solid #0f3460',
      borderRight: '1px solid #0f3460',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden'
    }}>
      <div style={{
        background: 'rgba(0, 0, 0, 0.5)',
        borderBottom: '1px solid #0f3460',
        padding: '16px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ fontSize: '18px', color: '#00d4ff', margin: 0 }}>{symbol}/USDT</h2>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
          <span style={{ fontSize: '20px', fontWeight: 'bold' }}>${price.toFixed(2)}</span>
          <span style={{ fontSize: '16px', color: change >= 0 ? '#00ff00' : '#ff0000' }}>
            {change >= 0 ? '📈' : '📉'} {change.toFixed(2)}%
          </span>
        </div>
      </div>

      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'linear-gradient(135deg, rgba(15, 52, 96, 0.2), rgba(0, 0, 0, 0.2))'
      }}>
        <div style={{ textAlign: 'center', color: '#666', fontSize: '18px' }}>
          K线图表 - {symbol}
          <br />
          <small>连接后显示实时数据</small>
        </div>
      </div>
    </div>
  );
}

export default TradingChart;
