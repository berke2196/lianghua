import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

/**
 * Hyperliquid AI 交易系统 v3.0
 * 完整的桌面应用 - Electron + React
 * 内嵌 Hyperliquid 交易界面 + 自动登录检测
 */

function App() {
  const [currentView, setCurrentView] = useState('trading');
  const [isConnected, setIsConnected] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [isAutoTrading, setIsAutoTrading] = useState(false);
  const [loginPromptVisible, setLoginPromptVisible] = useState(true);
  const [tradingStats, setTradingStats] = useState({
    trades: 0,
    wins: 0,
    win_rate: 0,
    total_pnl: 0,
    sharpe_ratio: 0,
    daily_pnl: 0
  });
  const [accountInfo, setAccountInfo] = useState({
    balance: 0,
    available: 0,
    positions: []
  });
  const [logs, setLogs] = useState([]);
  const [aiStatus, setAiStatus] = useState({
    lstm: false,
    rl: false,
    websocket: false
  });

  // 添加日志
  const addLog = useCallback((message, type = 'info') => {
    const timestamp = new Date().toLocaleTimeString();
    setLogs(prev => [{ time: timestamp, message, type }, ...prev].slice(0, 50));
  }, []);

  // 连接后端并获取状态
  useEffect(() => {
    const connectToBackend = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/trading/status');
        if (response.ok) {
          const data = await response.json();
          setIsConnected(true);
          setIsAutoTrading(data.status === 'running');
          setAiStatus({
            lstm: data.ai_models?.lstm || false,
            rl: data.ai_models?.rl || false,
            websocket: data.websocket?.connected || false
          });
        }
      } catch (error) {
        setIsConnected(false);
        setIsAutoTrading(false);
      }
    };

    connectToBackend();
    const interval = setInterval(connectToBackend, 3000);
    return () => clearInterval(interval);
  }, []);

  // 获取交易统计
  useEffect(() => {
    const fetchStats = async () => {
      if (!isConnected) return;
      try {
        const response = await fetch('http://localhost:8000/api/hft_performance');
        if (response.ok) {
          const data = await response.json();
          if (data.metrics) {
            setTradingStats(data.metrics);
          }
        }
      } catch (error) {
        console.error('获取统计数据失败:', error);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, [isConnected]);

  // 模拟检测iframe登录状态 (通过后端轮询)
  useEffect(() => {
    const checkLoginStatus = async () => {
      if (!isConnected || isLoggedIn) return;
      
      try {
        // 检查是否有账户数据返回
        const response = await fetch('http://localhost:8000/api/account/info');
        if (response.ok) {
          const data = await response.json();
          if (data.balance > 0 || data.positions?.length > 0) {
            setIsLoggedIn(true);
            setLoginPromptVisible(false);
            addLog('✅ 检测到Hyperliquid登录状态，账户已就绪', 'success');
          }
        }
      } catch (error) {
        // 忽略错误
      }
    };

    const interval = setInterval(checkLoginStatus, 5000);
    return () => clearInterval(interval);
  }, [isConnected, isLoggedIn, addLog]);

  // 启动自动交易
  const startAutoTrading = async () => {
    if (!isConnected) {
      addLog('❌ 后端未连接，无法启动交易', 'error');
      return;
    }
    
    addLog('🚀 正在启动AI自动交易...', 'info');
    
    try {
      const response = await fetch('http://localhost:8000/api/trading/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          mode: 'iframe_embedded',
          auto_detect_login: true 
        })
      });
      
      if (response.ok) {
        setIsAutoTrading(true);
        addLog('✅ AI自动交易已启动', 'success');
        addLog('🧠 LSTM + RL 模型已激活', 'info');
      } else {
        addLog('❌ 启动交易失败', 'error');
      }
    } catch (error) {
      addLog(`❌ 启动失败: ${error.message}`, 'error');
    }
  };

  // 停止自动交易
  const stopAutoTrading = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/trading/stop', {
        method: 'POST'
      });
      
      if (response.ok) {
        setIsAutoTrading(false);
        addLog('⏹️ AI自动交易已停止', 'warning');
      }
    } catch (error) {
      addLog(`❌ 停止失败: ${error.message}`, 'error');
    }
  };

  // 手动标记已登录
  const confirmLoggedIn = () => {
    setIsLoggedIn(true);
    setLoginPromptVisible(false);
    addLog('✅ 用户确认已登录Hyperliquid', 'success');
    
    // 可选：自动启动交易
    setTimeout(() => {
      startAutoTrading();
    }, 1000);
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      margin: 0,
      padding: 0,
      background: '#0a0a0a',
      fontFamily: 'Arial, sans-serif',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{
        padding: '10px 15px',
        background: '#1a1a1a',
        borderBottom: '1px solid #333',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h2 style={{ margin: 0, color: '#00ff00', fontSize: '16px' }}>
          📈 Hyperliquid AI 交易系统 v3.0
        </h2>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          {/* AI模型状态 */}
          <div style={{ display: 'flex', gap: '8px', fontSize: '11px' }}>
            <span style={{ color: aiStatus.lstm ? '#00ff00' : '#666' }}>
              🧠 LSTM {aiStatus.lstm ? 'ON' : 'OFF'}
            </span>
            <span style={{ color: aiStatus.rl ? '#00ff00' : '#666' }}>
              🎯 RL {aiStatus.rl ? 'ON' : 'OFF'}
            </span>
            <span style={{ color: aiStatus.websocket ? '#00ff00' : '#666' }}>
              📡 WS {aiStatus.websocket ? 'ON' : 'OFF'}
            </span>
          </div>
          
          <div style={{ 
            fontSize: '12px', 
            color: isConnected ? '#00ff00' : '#ff0000',
            padding: '4px 8px',
            background: isConnected ? '#003300' : '#330000',
            borderRadius: '4px'
          }}>
            {isConnected ? '✅ 后端已连接' : '❌ 后端离线'}
          </div>
          
          {isAutoTrading && (
            <div style={{
              fontSize: '12px',
              color: '#00ff00',
              padding: '4px 8px',
              background: '#003300',
              borderRadius: '4px',
              animation: 'pulse 1s infinite'
            }}>
              ⚡ 自动交易中
            </div>
          )}
        </div>
      </div>

      <div style={{
        flex: 1,
        display: 'flex',
        gap: '10px',
        padding: '10px'
      }}>
        <div style={{
          width: '180px',
          background: '#1a1a1a',
          borderRadius: '4px',
          padding: '15px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <h3 style={{ color: '#00ff00', marginTop: 0, fontSize: '14px' }}>🎮 菜单</h3>
          
          <button onClick={() => setCurrentView('trading')} style={{
            padding: '10px',
            background: currentView === 'trading' ? '#00ff00' : '#333',
            color: currentView === 'trading' ? '#000' : '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '12px'
          }}>
            📊 交易面板
          </button>

          <button onClick={() => setCurrentView('dashboard')} style={{
            padding: '10px',
            background: currentView === 'dashboard' ? '#00ff00' : '#333',
            color: currentView === 'dashboard' ? '#000' : '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '12px'
          }}>
            📈 性能数据
          </button>

          <button onClick={() => setCurrentView('settings')} style={{
            padding: '10px',
            background: currentView === 'settings' ? '#00ff00' : '#333',
            color: currentView === 'settings' ? '#000' : '#fff',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: 'bold',
            fontSize: '12px'
          }}>
            ⚙️ 设置
          </button>

          <hr style={{ borderColor: '#333', margin: '10px 0' }} />

          <h4 style={{ color: '#00ff00', fontSize: '12px', marginBottom: '8px' }}>📊 指标</h4>
          <div style={{ fontSize: '11px', color: '#fff', lineHeight: '1.8' }}>
            <p style={{ margin: '4px 0' }}>交易数: <span style={{ color: '#00ff00' }}>{tradingStats.trades || 0}</span></p>
            <p style={{ margin: '4px 0' }}>胜率: <span style={{ color: '#00ff00' }}>{tradingStats.win_rate || 0}%</span></p>
            <p style={{ margin: '4px 0' }}>盈亏: <span style={{ color: '#00ff00' }}>${tradingStats.total_pnl || 0}</span></p>
          </div>

          <hr style={{ borderColor: '#333', margin: '10px 0' }} />

          {/* 交易日志 */}
          <h4 style={{ color: '#00ff00', fontSize: '12px', marginBottom: '8px' }}>📝 交易日志</h4>
          <div style={{
            flex: 1,
            background: '#0a0a0a',
            borderRadius: '4px',
            padding: '8px',
            overflow: 'auto',
            fontSize: '10px',
            fontFamily: 'monospace'
          }}>
            {logs.length === 0 ? (
              <p style={{ color: '#666', margin: 0 }}>等待交易...</p>
            ) : (
              logs.map((log, idx) => (
                <div key={idx} style={{
                  marginBottom: '4px',
                  color: log.type === 'error' ? '#ff6666' : 
                         log.type === 'success' ? '#66ff66' : 
                         log.type === 'warning' ? '#ffaa00' : '#aaa'
                }}>
                  <span style={{ color: '#666' }}>[{log.time}]</span> {log.message}
                </div>
              ))
            )}
          </div>
        </div>

        <div style={{
          flex: 1,
          background: '#1a1a1a',
          borderRadius: '4px',
          padding: '15px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          {currentView === 'trading' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '10px'
              }}>
                <h3 style={{ color: '#00ff00', margin: 0 }}>💰 Hyperliquid 交易界面</h3>
                {isLoggedIn && (
                  <span style={{ color: '#00ff00', fontSize: '12px' }}>
                    ✅ 已登录
                  </span>
                )}
              </div>
              
              <div style={{
                flex: 1,
                background: '#0a0a0a',
                border: isLoggedIn ? '2px solid #00ff00' : '2px solid #ffaa00',
                borderRadius: '4px',
                overflow: 'hidden',
                position: 'relative'
              }}>
                <iframe
                  src="https://app.hyperliquid.xyz/trade"
                  style={{
                    width: '100%',
                    height: '100%',
                    border: 'none',
                    background: '#fff'
                  }}
                  title="Hyperliquid Trading"
                />
                
                {/* 登录提示层 */}
                {loginPromptVisible && (
                  <div style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.85)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 100
                  }}>
                    <div style={{
                      background: '#1a1a1a',
                      padding: '30px 40px',
                      borderRadius: '8px',
                      border: '2px solid #ffaa00',
                      textAlign: 'center',
                      maxWidth: '400px'
                    }}>
                      <h3 style={{ color: '#ffaa00', marginTop: 0 }}>
                        🔐 请先登录 Hyperliquid
                      </h3>
                      <p style={{ color: '#fff', fontSize: '14px', lineHeight: '1.6' }}>
                        请在中间的网页中登录您的Hyperliquid账户<br/>
                        登录完成后点击下方按钮启动自动交易
                      </p>
                      <button
                        onClick={confirmLoggedIn}
                        style={{
                          marginTop: '20px',
                          padding: '12px 30px',
                          background: '#00ff00',
                          color: '#000',
                          border: 'none',
                          borderRadius: '4px',
                          fontSize: '14px',
                          fontWeight: 'bold',
                          cursor: 'pointer'
                        }}
                      >
                        ✅ 我已登录，启动AI交易
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {currentView === 'dashboard' && (
            <div>
              <h3 style={{ color: '#00ff00', marginTop: 0 }}>📊 性能数据板</h3>
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr 1fr',
                gap: '15px',
                marginTop: '15px'
              }}>
                <div style={{
                  background: '#0a0a0a',
                  padding: '20px',
                  borderRadius: '4px',
                  border: '1px solid #00ff00'
                }}>
                  <div style={{ color: '#00ff00', fontSize: '12px' }}>交易数</div>
                  <div style={{ color: '#fff', fontSize: '28px', fontWeight: 'bold' }}>
                    {tradingStats.trades || 0}
                  </div>
                </div>
                <div style={{
                  background: '#0a0a0a',
                  padding: '20px',
                  borderRadius: '4px',
                  border: '1px solid #00ff00'
                }}>
                  <div style={{ color: '#00ff00', fontSize: '12px' }}>胜率</div>
                  <div style={{ color: '#fff', fontSize: '28px', fontWeight: 'bold' }}>
                    {typeof tradingStats.win_rate === 'string' 
                      ? tradingStats.win_rate 
                      : (tradingStats.win_rate || 0)}%
                  </div>
                </div>
                <div style={{
                  background: '#0a0a0a',
                  padding: '20px',
                  borderRadius: '4px',
                  border: '1px solid #00ff00'
                }}>
                  <div style={{ color: '#00ff00', fontSize: '12px' }}>总盈亏</div>
                  <div style={{ color: '#fff', fontSize: '28px', fontWeight: 'bold' }}>
                    ${tradingStats.total_pnl || 0}
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentView === 'settings' && (
            <div>
              <h3 style={{ color: '#00ff00', marginTop: 0 }}>⚙️ 系统设置</h3>
              <div style={{
                background: '#0a0a0a',
                padding: '20px',
                borderRadius: '4px',
                border: '1px solid #333',
                marginTop: '15px'
              }}>
                <div style={{ color: '#fff', marginBottom: '15px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                    <input type="checkbox" defaultChecked style={{ marginRight: '10px' }} />
                    启用高频交易 (1-5ms 检测)
                  </label>
                </div>
                <div style={{ color: '#fff', marginBottom: '15px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
                    <input type="checkbox" defaultChecked style={{ marginRight: '10px' }} />
                    启用 AI 信号过滤 (7维度)
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        <div style={{
          width: '220px',
          background: '#1a1a1a',
          borderRadius: '4px',
          padding: '15px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h4 style={{ color: '#00ff00', marginTop: 0, fontSize: '14px' }}>💼 账户</h4>
          <div style={{
            background: '#0a0a0a',
            padding: '12px',
            borderRadius: '4px',
            fontSize: '11px',
            color: '#fff',
            marginBottom: '15px',
            flex: 1
          }}>
            <p style={{ margin: '6px 0' }}>
              <span style={{ color: '#00ff00' }}>余额:</span> $10,000
            </p>
            <p style={{ margin: '6px 0' }}>
              <span style={{ color: '#00ff00' }}>可用:</span> $10,000
            </p>
            <hr style={{ borderColor: '#333', margin: '10px 0' }} />
            <h4 style={{ color: '#00ff00', fontSize: '11px', marginTop: '10px' }}>实时统计</h4>
            <p style={{ margin: '6px 0' }}>
              <span style={{ color: '#00ff00' }}>今日交易:</span> {tradingStats.trades || 0}
            </p>
            <p style={{ margin: '6px 0' }}>
              <span style={{ color: '#00ff00' }}>盈亏:</span> ${tradingStats.total_pnl || 0}
            </p>
          </div>

          <button 
            onClick={startAutoTrading}
            disabled={!isLoggedIn || isAutoTrading}
            style={{
              padding: '10px',
              background: (!isLoggedIn || isAutoTrading) ? '#333' : '#00ff00',
              color: (!isLoggedIn || isAutoTrading) ? '#666' : '#000',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 'bold',
              cursor: (!isLoggedIn || isAutoTrading) ? 'not-allowed' : 'pointer',
              marginBottom: '8px',
              fontSize: '12px'
            }}
          >
            {isAutoTrading ? '⚡ 交易中' : (isLoggedIn ? '🚀 开始交易' : '🔒 请先登录')}
          </button>

          <button 
            onClick={stopAutoTrading}
            disabled={!isAutoTrading}
            style={{
              padding: '10px',
              background: isAutoTrading ? '#ff0000' : '#333',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              fontWeight: 'bold',
              cursor: isAutoTrading ? 'pointer' : 'not-allowed',
              fontSize: '12px'
            }}
          >
            ⏹️ 停止交易
          </button>

          <button
            onClick={() => setLoginPromptVisible(true)}
            style={{
              padding: '8px',
              background: '#333',
              color: '#00ff00',
              border: '1px solid #00ff00',
              borderRadius: '4px',
              fontSize: '11px',
              cursor: 'pointer',
              marginTop: '8px'
            }}
          >
            🔄 重新检测登录
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
