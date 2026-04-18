import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';

/**
 * AsterDex HFT Auto Trader v5.0
 * - API Key + Secret Key 登录
 * - WebSocket 实时行情同步
 * - 真实账户余额/持仓
 * - HFT 自动交易控制
 */

const API_BASE = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws/frontend';

function App() {
  const [view, setView] = useState('login');
  const viewRef = useRef('login');
  const _setView = (v) => { viewRef.current = v; setView(v); };

  // 连接
  const [backendOk, setBackendOk] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  // 登录表单
  const [loginForm, setLoginForm] = useState({
    user: '',
    signer: '',
    private_key: '',
  });
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState('');

  // 账户数据（来自 WS 实时更新）
  const [account, setAccount] = useState({
    logged_in: false,
    balance: 0,
    available: 0,
    positions: [],
    open_orders: [],
  });

  // 行情
  const [prices, setPrices] = useState({});
  const [orderbook, setOrderbook] = useState({ bids: [], asks: [] });

  // 交易控制
  const [isTrading, setIsTrading] = useState(false);
  const [perf, setPerf] = useState({ total_trades: 0, wins: 0, losses: 0, total_pnl: 0, total_pnl_pct: 0, daily_pnl: 0, daily_pnl_pct: 0, win_rate: 0, daily_history: {} });
  const [tradeLogs, setTradeLogs] = useState([]);
  const [logFilter, setLogFilter] = useState('all');
  const [logPage,   setLogPage]   = useState(0);
  const [expandedLog, setExpandedLog] = useState(null);
  const [optResult, setOptResult] = useState(null);
  const [optLoading, setOptLoading] = useState(false);

  // 设置
  const [settings, setSettings] = useState({
    strategy: 'multi',
    symbol: 'BTCUSDT',
    leverage: 2,
    stop_loss_pct: 0.012,
    take_profit_pct: 0.028,
    enable_long: true,
    enable_short: true,
    trade_size_usd: 10,
    min_confidence: 0.70,
    // EMA
    ema_fast: 5, ema_slow: 20, ema_long: 60,
    // MACD
    macd_fast: 12, macd_slow: 26, macd_signal: 9,
    // RSI
    rsi_period: 14, rsi_oversold: 30, rsi_overbought: 70,
    // BB
    bb_period: 20, bb_std: 2.0,
    // Breakout
    breakout_period: 20, breakout_vol_mult: 1.5,
    // MM
    mm_spread_pct: 0.001, mm_order_size_usd: 5,
    // Risk
    max_open_positions: 3, max_daily_loss_usd: 50, max_position_usd: 500,
    cancel_on_reverse: true, hft_interval_ms: 500,
    cooldown_secs: 60,
    hft_mode: 'balanced',  // balanced模式RR≥1.2，收支平衡起点
    active_symbols: ['BTCUSDT'],
  });
  const [indicators, setIndicators] = useState(null);
  const [multiIndicators, setMultiIndicators] = useState({}); // {BTCUSDT: {...}, ETHUSDT: {...}}
  const [symbolSettings, setSymbolSettings] = useState({});   // 每币种独立参数
  const [activeSym, setActiveSym] = useState('BTCUSDT');      // 仪表盘当前查看的币种
  const [liveLog, setLiveLog] = useState([]);
  const [balanceDelta, setBalanceDelta] = useState(0); // >0涨 <0跌 0无变化
  const [logAutoClean, setLogAutoClean] = useState(true); // 是否自动清空日志
  const [testOrdering, setTestOrdering] = useState(false);

  const [toast, setToast] = useState(null);

  const showToast = useCallback((msg, type = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // ─── 健康检查 ───
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/health`);
        setBackendOk(r.ok);
      } catch { setBackendOk(false); }
    };
    check();
    const t = setInterval(check, 5000);
    return () => clearInterval(t);
  }, []);

  // ─── 指标轮询（登录后就启动）——单次请求indicators_all即可获得全部数据 ───
  useEffect(() => {
    if (!account.logged_in) return;
    const fetch_ind = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/trading/indicators_all`);
        if (!r.ok) return;
        const dAll = await r.json();
        const syms = dAll.symbols || {};
        setMultiIndicators(syms);
        // 当前选中币种的单独指标（直接从批量结果取）
        const d = syms[activeSym];
        if (d) {
          setIndicators(d);
          if (d.raw_signal && d.raw_signal.side !== 'HOLD' && !d.has_position) {
            const ts = new Date().toLocaleTimeString();
            const rs = d.raw_signal;
            const fired = d.current_signal?.side !== 'HOLD';
            setLiveLog(prev => {
              const last = prev[0]?.text || '';
              const newText = `[${activeSym.replace('USDT','')}/${rs.side}] 置信:${(rs.confidence*100).toFixed(1)}% RSI:${Number(d.rsi||0).toFixed(1)}${fired?' ⚡':''}`;
              if (last === newText) return prev;
              return [{ ts, text: newText }, ...prev.slice(0, 29)];
            });
          }
        }
      } catch {}
    };
    fetch_ind();
    const t = setInterval(fetch_ind, 1000);
    return () => clearInterval(t);
  }, [account.logged_in, activeSym, settings.active_symbols]);

  // ─── 日志定时自动清空（每5分钟） ───
  useEffect(() => {
    if (!logAutoClean) return;
    const t = setInterval(() => {
      setLiveLog(prev => prev.length > 0 ? [] : prev);
    }, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [logAutoClean, setLiveLog]);

  const connectWS = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState < 2) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      // 保活 ping
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }));
        else clearInterval(ping);
      }, 20000);
    };

    ws.onclose = () => {
      setWsConnected(false);
      setTimeout(connectWS, 3000);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (ev) => {
      try {
        const { type, data } = JSON.parse(ev.data);
        switch (type) {
          case 'init':
          case 'account_update':
            setAccount(prev => {
              const oldBal = prev.balance || 0;
              const newBal = data.balance != null ? data.balance : oldBal;
              const diff = newBal - oldBal;
              // oldBal>1 避免初始化时0→实际余额误触发动画
              if (Math.abs(diff) > 0.01 && oldBal > 1) {
                setBalanceDelta(diff);
                setTimeout(() => setBalanceDelta(0), 2500);
              }
              return { ...prev, ...data };
            });
            if (data.logged_in === true && viewRef.current === 'login') {
              _setView('dashboard');
            }
            break;
          case 'prices':
            setPrices(data);
            break;
          case 'orderbook':
            setOrderbook({ bids: data.bids || [], asks: data.asks || [] });
            break;
          case 'settings_updated':
            setSettings(prev => ({ ...prev, ...data }));
            if (data.symbol_settings) setSymbolSettings(data.symbol_settings);
            break;
          case 'new_trade':
            setTradeLogs(prev => [data, ...prev].slice(0, 500));
            break;
          case 'performance':
            setPerf(data);
            break;
          case 'opt_result':
            setOptResult(data);
            break;
          case 'trading_status':
            setIsTrading(data.active || false);
            break;
          case 'signal_update':
            // 同步 has_position 状态到 indicators
            setIndicators(prev => prev ? { ...prev, has_position: data.has_position } : prev);
            if (data.fired) {
              const ts = new Date().toLocaleTimeString();
              const newText = `⚡ 触发 ${data.side} ${data.symbol||''} 置信:${(data.confidence*100).toFixed(1)}%`;
              setLiveLog(prev => {
                if (prev[0]?.text === newText) return prev;
                return [{ ts, text: newText }, ...prev.slice(0, 29)];
              });
            }
            break;
          case 'log':
            setLiveLog(prev => {
              const newEntry = { ts: data.ts||new Date().toLocaleTimeString(), text: data.text||'' };
              if (prev[0]?.text === newEntry.text) return prev; // 去重
              return [newEntry, ...prev.slice(0, 29)]; // 最多30条
            });
            break;
          case 'alert':
            showToast(`⚠️ ${data.type}: ${JSON.stringify(data)}`, 'error');
            break;
          case 'ws_status':
            break;
          default:
            break;
        }
      } catch (e) {
        console.error('WS parse error', e);
      }
    };
  }, [showToast]);

  useEffect(() => {
    connectWS();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [connectWS]);

  // ─── 登录后拉取日志 + settings（含symbol_settings）───
  useEffect(() => {
    if (!account.logged_in) return;
    const fetch_logs = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/trading/logs?limit=500`);
        if (r.ok) {
          const d = await r.json();
          setTradeLogs(d.logs || []);
          if (d.performance) setPerf(d.performance);
        }
      } catch {}
    };
    const fetch_settings = async () => {
      try {
        const r = await fetch(`${API_BASE}/api/trading/status`);
        if (r.ok) {
          const d = await r.json();
          if (d.settings) {
            setSettings(p => ({ ...p, ...d.settings }));
            if (d.settings.symbol_settings) setSymbolSettings(d.settings.symbol_settings);
          }
        }
      } catch {}
    };
    fetch_logs();
    fetch_settings(); // 恢复后端settings含symbol_settings
  }, [account.logged_in]);

  // ─── 登录 ───
  const handleLogin = async () => {
    if (!loginForm.user.trim() || !loginForm.signer.trim() || !loginForm.private_key.trim()) {
      setLoginError('三个字段均不能为空');
      return;
    }
    setLoginLoading(true);
    setLoginError('');
    try {
      const r = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: loginForm.user.trim(), signer: loginForm.signer.trim(), private_key: loginForm.private_key.trim() }),
      });
      const d = await r.json();
      if (d.ok) {
        setAccount(prev => ({
          ...prev,
          logged_in: true,
          balance: d.balance || 0,
          available: d.available || 0,
          wallet: d.wallet || '',
          positions: d.positions || prev.positions,
          open_orders: d.open_orders || prev.open_orders,
        }));
        _setView('dashboard');
        const addr = d.wallet ? `${d.wallet.slice(0,8)}...${d.wallet.slice(-4)}` : '';
        showToast(`✅ AsterDex 登录成功！${addr} 余额: $${(d.balance || 0).toFixed(2)} USDT`, 'success');
      } else {
        setLoginError(d.error || '登录失败');
      }
    } catch (e) {
      setLoginError(`连接失败: ${e.message}，请确认后端已启动`);
    } finally {
      setLoginLoading(false);
    }
  };

  // ─── 手动操作 ───
  const closePosition = async (symbol) => {
    try {
      const r = await fetch(`${API_BASE}/api/trading/close_position`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      if (d.ok) showToast(`✅ 已平仓 ${symbol}`, 'success');
      else showToast(d.error || '平仓失败', 'error');
    } catch (e) { showToast(`平仓请求失败: ${e.message}`, 'error'); }
  };

  const cancelOrders = async (symbol) => {
    try {
      const r = await fetch(`${API_BASE}/api/trading/cancel_orders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      showToast(d.message || '已撤单', 'info');
    } catch (e) { showToast(`撤单请求失败: ${e.message}`, 'error'); }
  };

  const handleLogout = async () => {
    await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST' });
    setAccount({ logged_in: false, balance: 0, available: 0, positions: [], open_orders: [] });
    setIsTrading(false);
    setTradeLogs([]);
    setPerf({ total_trades: 0, wins: 0, losses: 0, total_pnl: 0, daily_pnl: 0, win_rate: 0 });
    setIndicators(null);
    setMultiIndicators({});
    setLiveLog([]);
    _setView('login');
    showToast('已登出', 'info');
  };

  // ─── 交易控制 ───
  const [tradingLoading, setTradingLoading] = useState(false);

  const startTrading = async () => {
    if (!account.logged_in) { showToast('❌ 请先登录账户', 'error'); return; }
    if (!backendOk) { showToast('❌ 后端未连接，请检查后端服务', 'error'); return; }
    setTradingLoading(true);
    try {
      const payload = { ...settings, symbol_settings: { ...symbolSettings, ...settings.symbol_settings } };
      await fetch(`${API_BASE}/api/settings`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
      const r = await fetch(`${API_BASE}/api/trading/start`, { method: 'POST' });
      const d = await r.json();
      if (d.ok) {
        setIsTrading(true);
        const stratZh = {multi:'多策略融合',crypto_hft:'加密高频',ema_cross:'EMA交叉',macd:'MACD',rsi:'RSI',bbands:'布林带',breakout:'突破',market_making:'做市商'};
        showToast(`🚀 HFT 已启动！🟢 实盘 | 币种: ${d.symbol} | 策略: ${stratZh[settings.strategy]||settings.strategy} | 置信阈值: ${(settings.min_confidence*100).toFixed(0)}%`, 'success');
      } else {
        showToast(`❌ 启动失败: ${d.error || '未知错误，请检查后端日志'}`, 'error');
      }
    } catch (e) {
      showToast(`❌ 网络错误: ${e.message}，请确认后端运行中`, 'error');
    } finally {
      setTradingLoading(false);
    }
  };

  const stopTrading = async () => {
    try {
      const r = await fetch(`${API_BASE}/api/trading/stop`, { method: 'POST' });
      const d = await r.json();
      setIsTrading(false);
      showToast(`⏹️ 交易已停止 | 本次共 ${perf.total_trades} 笔 | 胜率 ${perf.win_rate}%`, 'info');
    } catch (e) {
      showToast('⏹️ 停止指令已发送', 'info');
      setIsTrading(false);
    }
  };

  // 复制到剪贴板
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text).then(() => showToast('✅ 已复制到剪贴板', 'success')).catch(() => showToast('复制失败', 'error'));
  };

  // 测试下单
  const testOrder = async (side) => {
    setTestOrdering(true);
    try {
      const r = await fetch(`${API_BASE}/api/trading/test_order`, {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ symbol: settings.symbol, side }),
      });
      const d = await r.json();
      if (d.ok) {
        showToast(`✅ 测试${side}单成功: ${JSON.stringify(d.result).slice(0,80)}`, 'success');
        setLiveLog(prev => [{ ts: new Date().toLocaleTimeString(), text: `[测试下单] ${side} ${settings.symbol} -> ${JSON.stringify(d.result).slice(0,60)}` }, ...prev.slice(0, 29)]);
      } else {
        showToast(`❌ 下单失败: ${d.error}`, 'error');
        setLiveLog(prev => [{ ts: new Date().toLocaleTimeString(), text: `[错误] ${d.error}` }, ...prev.slice(0, 29)]);
      }
    } catch(e) {
      showToast(`请求失败: ${e.message}`, 'error');
    } finally {
      setTestOrdering(false);
    }
  };


  // ─── 保存设置 ───
  const saveSettings = async () => {
    try {
      const payload = { ...settings, symbol_settings: { ...symbolSettings, ...settings.symbol_settings } };
      const r = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const d = await r.json();
      if (d.ok) showToast('✅ 设置已保存', 'success');
      else showToast('保存失败', 'error');
    } catch (e) { showToast(`保存失败: ${e.message}`, 'error'); }
  };

  const btcPrice = prices['BTC'] || prices['BTCUSDT'] || 0;
  const symbol = settings.symbol;  // e.g. 'BTCUSDT'
  const symShort = symbol.replace('USDT','');
  const curPrice = prices[symShort] || prices[symbol] || 0;

  // ─── 渲染 ───
  return (
    <div className="app-container">
      {/* Toast */}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      {/* 顶部栏 */}
      <div className="header">
        <div className="header-left">
          <h2>⚡ AsterDex HFT Trader v5.0</h2>
        </div>
        <div className="header-status">
          <span className={`dot ${backendOk ? 'green' : 'red'}`} title="后端" />
          <span className="status-label">{backendOk ? '后端在线' : '后端离线'}</span>
          <span className={`dot ${wsConnected ? 'green' : 'yellow'}`} title="WS" />
          <span className="status-label">{wsConnected ? 'WS已连接' : 'WS重连中'}</span>
          {isTrading && <span className="badge badge-trading pulse">⚡ HFT运行中</span>}
          {account.logged_in && <span className="badge badge-live">✅ AsterDex 已连接</span>}
          {btcPrice > 0 && <span className="price-label">₿ ${Number(btcPrice).toLocaleString()}</span>}
        </div>
      </div>

      <div className="main-content">
        {/* 侧边导航 */}
        <div className="sidebar-left">
          {!account.logged_in ? (
            <button className="nav-btn active">🔐 登录</button>
          ) : (
            <>
              <button className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setView('dashboard')}>📊 仪表盘</button>
              <button className={`nav-btn ${view === 'chart' ? 'active' : ''}`} onClick={() => setView('chart')}>📈 行情图表</button>
              <button className={`nav-btn ${view === 'positions' ? 'active' : ''}`} onClick={() => setView('positions')}>📋 持仓/挂单</button>
              <button className={`nav-btn ${view === 'logs' ? 'active' : ''}`} onClick={() => setView('logs')}>📝 交易记录</button>
              <button className={`nav-btn ${view === 'settings' ? 'active' : ''}`} onClick={() => setView('settings')}>⚙️ 策略设置</button>
              <hr />
              <div className="metrics">
                <div className="metric-item">
                  <span className="metric-label">账户净值</span>
                  <span className="metric-value green">${(account.balance||0).toFixed(2)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">可用保证金</span>
                  <span className="metric-value">${(account.available||0).toFixed(2)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">保证金占用</span>
                  <span className="metric-value yellow">${Math.max(0, (account.balance || 0) - (account.available || 0)).toFixed(2)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">持仓数</span>
                  <span className="metric-value">{account.positions?.length || 0}</span>
                </div>
                <hr style={{borderColor:'#2a2a2a',margin:'4px 0'}}/>
                <div className="metric-item">
                  <span className="metric-label">今日盈亏</span>
                  <span className={`metric-value ${(perf.daily_pnl||0) >= 0 ? 'green' : 'red'}`}>
                    {(perf.daily_pnl||0) >= 0 ? '+' : ''}{(perf.daily_pnl||0).toFixed(2)}
                    <span style={{fontSize:9,marginLeft:3,opacity:0.7}}>
                      ({(perf.daily_pnl||0) >= 0 ? '+' : ''}{(perf.daily_pnl_pct||0).toFixed(2)}%)
                    </span>
                  </span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">历史盈亏</span>
                  <span className={`metric-value ${(perf.total_pnl||0) >= 0 ? 'green' : 'red'}`}>
                    {(perf.total_pnl||0) >= 0 ? '+' : ''}{(perf.total_pnl||0).toFixed(2)}
                    <span style={{fontSize:9,marginLeft:3,opacity:0.7}}>
                      ({(perf.total_pnl||0) >= 0 ? '+' : ''}{(perf.total_pnl_pct||0).toFixed(2)}%)
                    </span>
                  </span>
                </div>
                <div className="metric-item" style={{flexDirection:'column',alignItems:'flex-start',gap:2}}>
                  <div style={{display:'flex',justifyContent:'space-between',width:'100%'}}>
                    <span className="metric-label">胜率</span>
                    <span className={`metric-value ${parseFloat(perf.win_rate||0)>=55?'green':parseFloat(perf.win_rate||0)>=40?'yellow':'red'}`}>
                      {perf.win_rate||0}% <span style={{fontSize:9,color:'#555'}}>({perf.wins||0}W/{perf.losses||0}L)</span>
                    </span>
                  </div>
                  <div style={{width:'100%',height:4,background:'#1a1a1a',borderRadius:2,overflow:'hidden'}}>
                    <div style={{height:'100%',width:`${Math.min(perf.win_rate||0,100)}%`,background:parseFloat(perf.win_rate||0)>=55?'#00e676':parseFloat(perf.win_rate||0)>=40?'#ffd740':'#ff5252',borderRadius:2,transition:'width .5s'}}/>
                  </div>
                </div>
                <div className="metric-item">
                  <span className="metric-label">总交易</span>
                  <span className="metric-value">{perf.total_trades}</span>
                </div>
              </div>
              <hr style={{borderColor:'#2a2a2a'}}/>
              <div style={{padding:'0 4px 8px',fontSize:10,color:'#666'}}>
                <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer"
                  style={{fontSize:10,color:'#40c4ff',textDecoration:'none',display:'block',marginBottom:4}}>↗ AsterDex 交易</a>
                <a href="https://www.asterdex.com/en/user-center/api" target="_blank" rel="noopener noreferrer"
                  style={{fontSize:10,color:'#666',textDecoration:'none',display:'block',marginBottom:4}}>↗ API 管理</a>
              </div>
              <button className="nav-btn danger" onClick={handleLogout}>🚪 登出</button>
            </>
          )}
        </div>

        {/* 主内容 */}
        <div className="content-area">

          {/* ── 登录页 ── */}
          {view === 'login' && (
            <div className="login-view">
              <div className="login-card">
                <div style={{textAlign:'center',marginBottom:20}}>
                  <div style={{fontSize:48,marginBottom:8}}>⭐</div>
                  <h2 style={{color:'#00e676',fontSize:22}}>AsterDex HFT 自动交易系统</h2>
                  <p style={{color:'#888',fontSize:13,marginTop:6}}>连接您的 AsterDex 账户，全自动高频交易</p>
                </div>

                {!backendOk && (
                  <div className="alert alert-error" style={{marginBottom:14}}>
                    ⚠️ 后端未启动，请先运行 <code>python asterdex_backend.py</code>
                  </div>
                )}

                <div className="alert alert-info" style={{marginBottom:16,lineHeight:1.9}}>
                  <b>🔗 登录方式</b>：使用 AsterDex 专业 API V3 登录<br/>
                  <span style={{color:'#aaa',fontSize:12}}>主账户地址 + API钉包地址 + API钉包私钥 — 共三个字段</span>
                </div>

                <div className="login-form">
                  <div className="form-group">
                    <label>主账户地址 （主钉包）</label>
                    <input
                      type="text"
                      placeholder="您登录 AsterDex 时使用的主钉包地址"
                      value={loginForm.user}
                      onChange={e => setLoginForm(p => ({ ...p, user: e.target.value }))}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    <small style={{color:'#555',fontSize:11}}>即页面右上角显示的 0x6c...1B46 完整地址</small>
                  </div>
                  <div className="form-group">
                    <label>API 钉包地址 （Signer）</label>
                    <input
                      type="text"
                      placeholder="专业API 页面列表里的 API 钉包地址"
                      value={loginForm.signer}
                      onChange={e => setLoginForm(p => ({ ...p, signer: e.target.value }))}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    <small style={{color:'#555',fontSize:11}}>如 0xa60a3f2348cbed90ecb6b99a1c6d948323792914</small>
                  </div>
                  <div className="form-group">
                    <label>API 钉包私钥 （Private Key）</label>
                    <input
                      type="password"
                      placeholder="创建钉包时页面上显示的「确认保存」那一行私钥"
                      value={loginForm.private_key}
                      onChange={e => setLoginForm(p => ({ ...p, private_key: e.target.value }))}
                      autoComplete="off"
                    />
                    <small style={{color:'#555',fontSize:11}}>如 0xd135c54789bf761b5e8659...</small>
                  </div>
                </div>

                {loginError && <div className="alert alert-error" style={{marginTop:10}}>{loginError}</div>}

                <button
                  className="btn-primary btn-large"
                  onClick={handleLogin}
                  disabled={loginLoading || !backendOk}
                  style={{marginTop:16}}
                >
                  {loginLoading ? '⏳ 验证中...' : '🚀 连接 AsterDex'}
                </button>

                <div style={{marginTop:16,textAlign:'center',fontSize:12,color:'#555'}}>
                  <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer" style={{color:'#666',textDecoration:'none'}}>
                    ↗ 打开 AsterDex 网站
                  </a>
                  <span style={{margin:'0 10px'}}>|</span>
                  <a href="https://docs.asterdex.com/for-developers/aster-api/api-documentation" target="_blank" rel="noopener noreferrer" style={{color:'#666',textDecoration:'none'}}>
                    ↗ API 文档
                  </a>
                </div>
              </div>
            </div>
          )}

          {/* ── 行情图表 ── */}
          {view === 'chart' && account.logged_in && (() => {
            const tvSymMap = {
              'BTCUSDT':'BINANCE:BTCUSDT.P','ETHUSDT':'BINANCE:ETHUSDT.P',
              'SOLUSDT':'BINANCE:SOLUSDT.P','ARBUSDT':'BINANCE:ARBUSDT.P',
              'AVAXUSDT':'BINANCE:AVAXUSDT.P','BNBUSDT':'BINANCE:BNBUSDT.P',
            };
            const tvSym = tvSymMap[settings.symbol] || `BINANCE:${settings.symbol}.P`;
            const iframeSrc = `https://s.tradingview.com/widgetembed/?frameElementId=tv_chart&symbol=${encodeURIComponent(tvSym)}&interval=1&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=000000&studies=RSI%40tv-basicstudies%1FMACD%40tv-basicstudies&theme=dark&style=1&timezone=Asia%2FShanghai&withdateranges=1&hidevolume=0&locale=zh_CN`;
            return (
              <div className="chart-view">
                <div className="chart-toolbar">
                  <span className="chart-title">📈 实时K线图表 (TradingView)</span>
                  <div className="chart-sym-tabs">
                    {['BTCUSDT','ETHUSDT','SOLUSDT','ARBUSDT','AVAXUSDT'].map(sym => (
                      <button key={sym}
                        className={`sym-tab ${settings.symbol === sym ? 'active' : ''}`}
                        onClick={() => setSettings(p => ({ ...p, symbol: sym }))}>
                        {sym.replace('USDT','')}
                      </button>
                    ))}
                  </div>
                  <a href={`https://www.asterdex.com/zh-CN/trade/pro/futures/${settings.symbol}`}
                    target="_blank" rel="noopener noreferrer" className="chart-open-btn">↗️ AsterDex交易</a>
                </div>
                <iframe
                  key={settings.symbol}
                  src={iframeSrc}
                  title="TradingView Chart"
                  className="chart-iframe"
                  allowFullScreen
                  frameBorder="0"
                />
              </div>
            );
          })()}

          {/* ── 仓表盘 ── */}
          {view === 'dashboard' && account.logged_in && (
            <div className="dashboard-view">
              <div className="dashboard-top">
                {/* 账户卡片 */}
                <div className="card account-card">
                  <h3>💼 AsterDex 账户概览 <span className="badge badge-live" style={{marginLeft:8}}>实盘</span></h3>
                  <div className="stat-grid">
                    {/* 账户净值：带余额变动动画 */}
                    <div className="stat">
                      <span className="stat-label">账户净值</span>
                      <span style={{display:'flex',alignItems:'center',gap:5}}>
                        <span className="stat-val green" style={{transition:'color .3s'}}>${(account.balance||0).toFixed(2)}</span>
                        {balanceDelta !== 0 && (
                          <span style={{
                            fontSize:11,fontWeight:700,
                            color:balanceDelta>0?'#00e676':'#ff5252',
                            animation:'fadeInUp .3s ease',
                          }}>
                            {balanceDelta>0?'▲':'▼'}{Math.abs(balanceDelta).toFixed(2)}
                          </span>
                        )}
                      </span>
                    </div>
                    <div className="stat"><span className="stat-label">可用保证金</span><span className="stat-val">${(account.available||0).toFixed(2)}</span></div>
                    <div className="stat"><span className="stat-label">占用保证金</span><span className="stat-val yellow">${Math.max(0,(account.balance||0)-(account.available||0)).toFixed(2)}</span></div>
                    <div className="stat"><span className="stat-label">持仓数</span><span className="stat-val">{account.positions?.length||0} 个</span></div>
                    <div className="stat">
                      <span className="stat-label">今日盈亏</span>
                      <span className={`stat-val ${(perf.daily_pnl||0)>=0?'green':'red'}`}>
                        {(perf.daily_pnl||0)>=0?'+':''}{(perf.daily_pnl||0).toFixed(2)}
                        <span style={{fontSize:10,marginLeft:3,opacity:0.7}}>
                          {perf.daily_pnl_pct !== undefined ? `(${perf.daily_pnl_pct>0?'+':''}${perf.daily_pnl_pct}%)` : ''}
                        </span>
                      </span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">总盈亏</span>
                      <span className={`stat-val ${(perf.total_pnl||0)>=0?'green':'red'}`}>
                        {(perf.total_pnl||0)>=0?'+':''}{(perf.total_pnl||0).toFixed(2)}
                        <span style={{fontSize:10,marginLeft:3,opacity:0.7}}>
                          {perf.total_pnl_pct !== undefined ? `(${perf.total_pnl_pct>0?'+':''}${perf.total_pnl_pct}%)` : ''}
                        </span>
                      </span>
                    </div>
                  </div>
                  <div style={{marginTop:10,fontSize:11,color:'#666',display:'flex',gap:12}}>
                    <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer" style={{color:'#40c4ff',textDecoration:'none'}}>↗ AsterDex 交易页</a>
                    <a href="https://www.asterdex.com/en/user-center/api" target="_blank" rel="noopener noreferrer" style={{color:'#666',textDecoration:'none'}}>↗ API 管理</a>
                  </div>
                </div>

                {/* 多币种信号总览卡 */}
                {(settings.active_symbols||['BTCUSDT']).length > 0 && (
                  <div className="card" style={{padding:12,gridColumn:'1/-1'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                      <h3 style={{margin:0,fontSize:13}}>🌐 多币种信号总览</h3>
                      <span style={{fontSize:10,color:'#555'}}>点击卡片切换详细指标 · 实时更新</span>
                    </div>
                    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:8}}>
                      {(settings.active_symbols||['BTCUSDT']).map(sym=>{
                        const ind = multiIndicators[sym] || {};
                        const symLabel = sym.replace('USDT','');
                        const symColors = {BTC:'#f7931a',ETH:'#627eea',SOL:'#9945ff',ARB:'#28a0f0',AVAX:'#e84142'};
                        const color = symColors[symLabel] || '#40c4ff';
                        const raw    = ind.raw_signal   || {};
                        const curSig = ind.current_signal || {};
                        const scores = ind.scores || {};
                        const bullPct = Math.round((scores._bull || 0) * 100);
                        const bearPct = Math.round((scores._bear || 0) * 100);
                        const fired   = curSig.side && curSig.side !== 'HOLD';
                        const blocked = (raw.side && raw.side !== 'HOLD') && !fired;
                        const adx  = ind.adx || 0;
                        const ms   = ind.market_state;
                        const hasp = ind.has_position;
                        const px   = prices[symLabel] || 0;
                        const isActive = activeSym === sym;
                        const curSide  = curSig.side || 'HOLD';
                        return (
                          <div key={sym} onClick={()=>setActiveSym(sym)} style={{
                            padding:'8px 10px',borderRadius:6,cursor:'pointer',
                            border:`1px solid ${isActive?color:(hasp?'#40c4ff44':fired?'#00e67644':blocked?'#ffd74044':'#1a1a1a')}`,
                            background:isActive?`${color}11`:'#0a0a0a',
                            transition:'all .2s',
                          }}>
                            {/* 标题行 */}
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:5}}>
                              <span style={{fontWeight:700,color,fontSize:12}}>{symLabel}</span>
                              {hasp
                                ? <span style={{fontSize:9,padding:'1px 4px',background:'#40c4ff22',border:'1px solid #40c4ff55',color:'#40c4ff',borderRadius:2}}>持仓中</span>
                                : fired
                                  ? <span style={{fontSize:9,padding:'1px 4px',background:'#00e67622',border:'1px solid #00e67655',color:'#00e676',borderRadius:2}}>✅下单</span>
                                  : blocked
                                    ? <span style={{fontSize:9,padding:'1px 4px',background:'#ffd74022',border:'1px solid #ffd74055',color:'#ffd740',borderRadius:2}}>⚠️过滤</span>
                                    : <span style={{fontSize:9,color:'#333'}}>待机</span>}
                            </div>
                            {/* 做多进度条 */}
                            <div style={{marginBottom:3}}>
                              <div style={{display:'flex',justifyContent:'space-between',fontSize:9,marginBottom:1}}>
                                <span style={{color:curSide==='BUY'?'#00e676':'#00e67688'}}>▲ 多 {bullPct}%</span>
                                {curSide==='BUY' && <span style={{color:'#00e676',fontSize:8}}>▶</span>}
                              </div>
                              <div style={{height:4,background:'#111',borderRadius:2,overflow:'hidden'}}>
                                <div style={{height:'100%',width:`${bullPct}%`,background:curSide==='BUY'?'#00e676':'#00e67666',borderRadius:2,transition:'width .4s'}}/>
                              </div>
                            </div>
                            {/* 做空进度条 */}
                            <div style={{marginBottom:4}}>
                              <div style={{display:'flex',justifyContent:'space-between',fontSize:9,marginBottom:1}}>
                                <span style={{color:curSide==='SELL'?'#ff5252':'#ff525288'}}>▼ 空 {bearPct}%</span>
                                {curSide==='SELL' && <span style={{color:'#ff5252',fontSize:8}}>▶</span>}
                              </div>
                              <div style={{height:4,background:'#111',borderRadius:2,overflow:'hidden'}}>
                                <div style={{height:'100%',width:`${bearPct}%`,background:curSide==='SELL'?'#ff5252':'#ff525288',borderRadius:2,transition:'width .4s'}}/>
                              </div>
                            </div>
                            {/* 底部信息 */}
                            <div style={{display:'flex',justifyContent:'space-between',fontSize:9,color:'#444'}}>
                              <span>ADX <b style={{color:adx>=25?'#00e676':adx>=20?'#ffd740':'#ff5252'}}>{adx.toFixed(0)}</b></span>
                              <span style={{color:ms==='trending'?'#00e67677':'#ff525277'}}>{ms==='trending'?'趋势':'震荡'}</span>
                              {px > 0 && <span style={{color:'#333'}}>${Number(px).toLocaleString()}</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* 行情卡片 */}
                <div className="card market-card">
                  <h3>📊 {symbol} 实时行情</h3>
                  <div className="price-display">${curPrice > 0 ? Number(curPrice).toLocaleString() : '加载中...'}</div>
                  <div className="ob-mini">
                    <div className="ob-side asks">
                      {orderbook.asks.slice(0, 3).reverse().map((a, i) => (
                        <div key={i} className="ob-row">
                          <span className="red">{a.px || a[0]}</span>
                          <span>{a.sz || a[1]}</span>
                        </div>
                      ))}
                    </div>
                    <div className="ob-mid">${curPrice > 0 ? Number(curPrice).toLocaleString() : '-'}</div>
                    <div className="ob-side bids">
                      {orderbook.bids.slice(0, 3).map((b, i) => (
                        <div key={i} className="ob-row">
                          <span className="green">{b.px || b[0]}</span>
                          <span>{b.sz || b[1]}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  {/* 买卖占比 */}
                  {(() => {
                    const bidVol = orderbook.bids.slice(0,10).reduce((s,b)=>s+parseFloat(b.sz||b[1]||0),0);
                    const askVol = orderbook.asks.slice(0,10).reduce((s,a)=>s+parseFloat(a.sz||a[1]||0),0);
                    const total  = bidVol + askVol || 1;
                    const buyPct = (bidVol/total*100).toFixed(1);
                    const sellPct= (askVol/total*100).toFixed(1);
                    return (
                      <div style={{marginTop:10}}>
                        <div style={{display:'flex',justifyContent:'space-between',fontSize:11,marginBottom:4}}>
                          <span className="green">买入 {buyPct}%</span>
                          <span style={{color:'#888',fontSize:10}}>挂单占比（前10档）</span>
                          <span className="red">卖出 {sellPct}%</span>
                        </div>
                        <div style={{height:8,borderRadius:4,overflow:'hidden',display:'flex'}}>
                          <div style={{width:`${buyPct}%`,background:'#00e676',transition:'width .4s'}} />
                          <div style={{width:`${sellPct}%`,background:'#ff5252',transition:'width .4s'}} />
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* HFT 控制卡片 */}
                <div className="card control-card">
                  <h3>⚡ HFT 自动交易</h3>

                  {/* 多币种启动提示 */}
                  <div style={{marginBottom:8,padding:'5px 8px',background:'#0a1020',borderRadius:5,border:'1px solid #1a2040',fontSize:11}}>
                    <div style={{color:'#40c4ff',fontWeight:700,marginBottom:3}}>🌐 同时交易币种（到策略设置里勾选）</div>
                    <div style={{display:'flex',gap:4,flexWrap:'wrap'}}>
                      {(settings.active_symbols||[settings.symbol]).map(sym=>(
                        <span key={sym} style={{padding:'1px 7px',borderRadius:3,background:'#00e67622',border:'1px solid #00e67666',color:'#00e676',fontSize:10,fontWeight:700}}>
                          {sym.replace('USDT','')}
                        </span>
                      ))}
                    </div>
                    <div style={{color:'#333',fontSize:10,marginTop:2}}>每个币种独立最多1单，止盈/止损后自动进入下一单</div>
                  </div>

                  {/* 币种选择（只从已启用的里选详细视图） */}
                  <div style={{display:'flex',gap:4,marginBottom:8,flexWrap:'wrap'}}>
                    {(settings.active_symbols||['BTCUSDT']).map(sym=>{
                      const symColors={BTCUSDT:'#f7931a',ETHUSDT:'#627eea',SOLUSDT:'#9945ff',ARBUSDT:'#28a0f0',AVAXUSDT:'#e84142'};
                      const color=symColors[sym]||'#40c4ff';
                      const isActive=activeSym===sym;
                      return (
                        <button key={sym}
                          onClick={()=>{setActiveSym(sym);setSettings(p=>({...p,symbol:sym}));}}
                          style={{padding:'3px 10px',fontSize:11,borderRadius:4,border:`1px solid ${isActive?color:'#333'}`,
                            background:isActive?`${color}22`:'transparent',
                            color:isActive?color:'#555',cursor:'pointer',fontWeight:isActive?700:400}}
                        >{sym.replace('USDT','')}</button>
                      );
                    })}
                  </div>

                  <div className="hft-status">
                    <div className={`status-indicator ${isTrading ? 'active' : 'idle'}`}>
                      {isTrading ? '⚡ 运行中' : '⏸ 已停止'}
                    </div>
                    <div style={{fontSize:11,color:'#00e676',marginTop:4}}>🟢 实盘交易 · AsterDex · {settings.symbol}</div>
                    <div style={{fontSize:10,marginTop:3,color: settings.hft_mode==='aggressive'?'#ff5252':settings.hft_mode==='conservative'?'#00e676':'#ffd740'}}>
                      {settings.hft_mode==='aggressive'?'⚡ 激进模式':settings.hft_mode==='conservative'?'🛡️ 精准模式':'⚖️ 平衡模式'}
                    </div>
                  </div>

                  {/* 当前信号 + 双向置信度 */}
                  {indicators && (() => {
                    const raw     = indicators.raw_signal || {};
                    const cur     = indicators.current_signal || {};
                    const minConf = indicators.min_confidence || 0.55;
                    const rawConf = raw.confidence || 0;
                    const rawSide = raw.side || 'HOLD';
                    const curSide = cur.side || 'HOLD';
                    const blockReason = cur.block_reason || '';
                    const fired   = curSide !== 'HOLD';        // 真正会下单
                    const rawFired = rawSide !== 'HOLD';       // 原始信号存在但可能被过滤
                    const scores  = indicators.scores || {};

                    // 直接用后端算好的多空占比
                    const bullPct = Math.round((scores._bull || 0) * 100);
                    const bearPct = Math.round((scores._bear || 0) * 100);
                    const thresh  = Math.round(minConf * 100);

                    // 真正触发下单状态
                    const buyReady  = curSide === 'BUY';
                    const sellReady = curSide === 'SELL';
                    // 原始信号存在但被过滤
                    const buyBlocked  = rawSide === 'BUY'  && !buyReady;
                    const sellBlocked = rawSide === 'SELL' && !sellReady;
                    const buyGap    = !buyReady  && rawSide === 'BUY'  ? Math.max(0, thresh - bullPct) : 0;
                    const sellGap   = !sellReady && rawSide === 'SELL' ? Math.max(0, thresh - bearPct) : 0;

                    const borderColor = buyReady?'#00e676': sellReady?'#ff5252': buyBlocked?'#ffd74066': sellBlocked?'#ff525244':'#222';

                    return (
                      <div style={{background:'#080808',border:`1px solid ${borderColor}`,borderRadius:8,padding:'10px 12px',margin:'6px 0'}}>

                        {/* 顶栏：策略名 + 状态 */}
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                          <span style={{fontSize:10,color:'#555'}}>⚡ <b style={{color:'#40c4ff'}}>CRYPTO_HFT</b> · {indicators.bars||0}根K线</span>
                          {indicators.has_position
                            ? <span style={{fontSize:10,padding:'2px 7px',background:'#40c4ff22',border:'1px solid #40c4ff',color:'#40c4ff',borderRadius:3,fontWeight:700}}>📊 持仓中·等待止盈/止损</span>
                            : fired
                              ? <span style={{fontSize:10,padding:'2px 7px',background:'#00e67633',border:'1px solid #00e676',color:'#00e676',borderRadius:3,fontWeight:700}}>✅ 信号触发·正在下单</span>
                              : (buyBlocked||sellBlocked)
                                ? <span style={{fontSize:10,padding:'2px 7px',background:'#ffd74022',border:'1px solid #ffd740',color:'#ffd740',borderRadius:3,fontWeight:700}}>⚠️ 信号存在·被过滤</span>
                                : isTrading
                                  ? <span style={{fontSize:10,color:'#555'}}>⏳ 等待信号...</span>
                                  : <span style={{fontSize:10,color:'#444'}}>HFT未启动</span>}
                        </div>

                        {/* 做多区 */}
                        <div style={{marginBottom:6}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:2}}>
                            <span style={{fontSize:11,color:'#00e676',fontWeight:700}}>📈 做多 BUY</span>
                            <span style={{fontSize:11,fontWeight:700,color:buyReady?'#00e676':buyBlocked?'#ffd740':'#444'}}>
                              {bullPct}%
                              {buyReady
                                ? <span style={{fontSize:10,marginLeft:4,color:'#00e676'}}>✅ 下单中!</span>
                                : buyBlocked && buyGap > 0
                                  ? <span style={{fontSize:10,marginLeft:4,color:'#ffd740'}}>还差{buyGap}%→{thresh}%</span>
                                  : buyBlocked
                                    ? <span style={{fontSize:10,marginLeft:4,color:'#ff9800'}}>被过滤</span>
                                    : null}
                            </span>
                          </div>
                          <div style={{height:8,background:'#111',borderRadius:4,overflow:'hidden',position:'relative'}}>
                            <div style={{height:'100%',width:`${bullPct}%`,background:buyReady?'#00e676':'#00e67655',transition:'width .5s',borderRadius:4}}/>
                            {/* 触发阈值竖线 */}
                            <div style={{position:'absolute',top:0,left:`${thresh}%`,width:2,height:'100%',background:'#ffd740',opacity:0.9}}/>
                          </div>
                        </div>

                        {/* 做空区 */}
                        <div style={{marginBottom:8}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:2}}>
                            <span style={{fontSize:11,color:'#ff5252',fontWeight:700}}>▼ 做空 SELL</span>
                            <span style={{fontSize:11,fontWeight:700,color:sellReady?'#ff5252':sellBlocked?'#ffd740':'#555'}}>
                              {bearPct}%
                              {sellReady
                                ? <span style={{fontSize:10,marginLeft:4,color:'#ff5252'}}>✅ 下单中!</span>
                                : sellBlocked && sellGap > 0
                                  ? <span style={{fontSize:10,marginLeft:4,color:'#ffd740'}}>还差{sellGap}%→{thresh}%</span>
                                  : sellBlocked
                                    ? <span style={{fontSize:10,marginLeft:4,color:'#ff9800'}}>被过滤</span>
                                    : null}
                            </span>
                          </div>
                          <div style={{height:8,background:'#111',borderRadius:4,overflow:'hidden',position:'relative'}}>
                            <div style={{height:'100%',width:`${bearPct}%`,background:sellReady?'#ff5252':'#ff5252aa',transition:'width .5s',borderRadius:4}}/>
                            <div style={{position:'absolute',top:0,left:`${thresh}%`,width:2,height:'100%',background:'#ffd740',opacity:0.9}}/>
                          </div>
                        </div>

                        {/* 市场状态栏 */}
                        {(() => {
                          const ms = indicators.market_state;
                          const adx = indicators.adx || 0;
                          const rr  = indicators.reward_risk || 0;
                          const isTrending = ms === 'trending';
                          return (
                            <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:6,padding:'4px 6px',background:isTrending?'#00e67611':'#ff525211',borderRadius:4,border:`1px solid ${isTrending?'#00e67633':'#ff525233'}`}}>
                              <span style={{fontSize:10,fontWeight:700,color:isTrending?'#00e676':'#ff5252'}}>
                                {isTrending ? '📈 趋势行情·可交易' : '⚠️ 低趋势·置信降权60%'}
                              </span>
                              <span style={{fontSize:10,color:'#888'}}>ADX <b style={{color:adx>=20?'#00e676':adx>=10?'#ffd740':'#ff5252'}}>{adx.toFixed(1)}</b></span>
                              <span style={{fontSize:10,color:'#888'}}>盈亏比 <b style={{color:rr>=1.8?'#00e676':'#ff5252'}}>{rr.toFixed(2)}x</b></span>
                            </div>
                          );
                        })()}

                        {/* 过滤原因提示 + 实际生效参数 */}
                        {blockReason && !fired && (() => {
                          const symKey = activeSym; // e.g. BTCUSDT
                          const hasCustParam = !!(symbolSettings[symKey] && (symbolSettings[symKey].stop_loss_pct || symbolSettings[symKey].take_profit_pct));
                          const effSl = (symbolSettings[symKey]?.stop_loss_pct ?? settings.stop_loss_pct) * 100;
                          const effTp = (symbolSettings[symKey]?.take_profit_pct ?? settings.take_profit_pct) * 100;
                          const effRr = ((effTp/100 - 0.001) / (effSl/100 + 0.001)).toFixed(2);
                          const modeRr = settings.hft_mode==='aggressive'?0.3:settings.hft_mode==='conservative'?1.8:1.2;
                          const rrOk = parseFloat(effRr) >= modeRr;
                          return (
                            <>
                              <div style={{padding:'4px 8px',background:'#ff980011',border:'1px solid #ff980033',borderRadius:4,marginBottom:4,fontSize:10,color:'#ff9800'}}>
                                🚫 未下单原因：{blockReason}
                              </div>
                              <div style={{padding:'4px 8px',background:'#ffffff08',borderRadius:4,marginBottom:6,fontSize:10,display:'flex',flexWrap:'wrap',gap:8,alignItems:'center'}}>
                                <span style={{color:'#555'}}>实际生效参数{hasCustParam?<span style={{color:'#ffd740',marginLeft:3}}>(独立配置)</span>:''}：</span>
                                <span>止损 <b style={{color:'#ff5252'}}>{effSl.toFixed(2)}%</b></span>
                                <span>止盈 <b style={{color:'#00e676'}}>{effTp.toFixed(2)}%</b></span>
                                <span>盈亏比 <b style={{color:rrOk?'#00e676':'#ff5252'}}>{effRr}x</b> <span style={{color:'#555'}}>需≥{modeRr}x</span></span>
                                {hasCustParam && (
                                  <button onClick={async()=>{
                                    const ns = {...symbolSettings}; delete ns[symKey];
                                    setSymbolSettings(ns);
                                    await fetch(`${API_BASE}/api/settings/symbol`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:symKey,params:{stop_loss_pct:settings.stop_loss_pct,take_profit_pct:settings.take_profit_pct,leverage:settings.leverage,min_confidence:settings.min_confidence}})});
                                    showToast(`✅ 已重置 ${symKey} 为全局参数`,'success');
                                  }} style={{fontSize:9,padding:'2px 6px',background:'#ff525222',border:'1px solid #ff525266',color:'#ff5252',borderRadius:3,cursor:'pointer'}}>
                                    🔄 重置为全局参数
                                  </button>
                                )}
                              </div>
                            </>
                          );
                        })()}

                        {/* 快速指标行 */}
                        <div style={{display:'flex',gap:10,fontSize:11,color:'#888',flexWrap:'wrap',paddingTop:6,borderTop:'1px solid #1a1a1a'}}>
                          <span>RSI <b style={{color:indicators.rsi<35?'#00e676':indicators.rsi>65?'#ff5252':'#aaa'}}>{Number(indicators.rsi||0).toFixed(1)}</b></span>
                          <span>MACD <b style={{color:(indicators.macd?.hist||0)>0?'#00e676':'#ff5252'}}>{Number(indicators.macd?.hist||0).toFixed(4)}</b></span>
                          <span>OBI <b style={{color:(indicators.ob_imbalance||0)>0?'#00e676':'#ff5252'}}>{((indicators.ob_imbalance||0)*100).toFixed(1)}%</b></span>
                          <span>ST <b style={{color:indicators.supertrend==='up'?'#00e676':indicators.supertrend==='down'?'#ff5252':'#888'}}>{indicators.supertrend||'--'}</b></span>
                        </div>

                        {/* 7维度评分条 */}
                        {Object.keys(scores).filter(k=>!k.startsWith('_')).length > 0 && (
                          <div style={{marginTop:8,paddingTop:6,borderTop:'1px solid #1a1a1a'}}>
                            <div style={{fontSize:9,color:'#333',marginBottom:4}}>📊 7维度评分（绿=看多 红=看空）</div>
                            {[
                              ['supertrend','Supertrend',0.22],
                              ['ema','EMA三线',0.20],
                              ['macd','MACD',0.15],
                              ['rsi','RSI',0.15],
                              ['vwap','VWAP',0.12],
                              ['obi','OBI',0.11],
                              ['momentum','动量',0.05],
                            ].map(([key,label,wt])=>{
                              const v = scores[key] || 0;
                              const bar = Math.abs(v) * 50; // 最大50%宽度（中线两侧各50%）
                              const isPos = v >= 0;
                              return (
                                <div key={key} style={{display:'flex',alignItems:'center',gap:5,marginBottom:2}}>
                                  <span style={{width:52,fontSize:9,color:'#444',flexShrink:0}}>{label}</span>
                                  <div style={{flex:1,height:5,background:'#0d0d0d',borderRadius:2,position:'relative'}}>
                                    <div style={{position:'absolute',left:'50%',top:0,width:1,height:'100%',background:'#222'}}/>
                                    <div style={{
                                      position:'absolute',height:'100%',
                                      width:`${bar}%`,
                                      background:isPos?'#00e676':'#ff5252',
                                      left:isPos?'50%':undefined,
                                      right:isPos?undefined:`${50-bar}%`,
                                      borderRadius:2,transition:'width .4s',
                                    }}/>
                                  </div>
                                  <span style={{width:30,fontSize:9,color:isPos&&v!==0?'#00e676':v!==0?'#ff5252':'#444',textAlign:'right',flexShrink:0}}>
                                    {v>0?'+':''}{v.toFixed(2)}
                                  </span>
                                  <span style={{width:24,fontSize:8,color:'#333',flexShrink:0}}>{(wt*100).toFixed(0)}%</span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                  {!indicators && (
                    <div style={{fontSize:11,color:'#555',textAlign:'center',padding:'12px 0'}}>⏳ 等待K线数据（需65根，约2分钟）...</div>
                  )}

                  <div className="control-btns">
                    <button className="btn-success btn-large" onClick={startTrading}
                      disabled={isTrading||tradingLoading||!account.logged_in||!backendOk}>
                      {tradingLoading?'⏳ 启动中...':'🚀 启动 HFT'}
                    </button>
                    <button className="btn-danger" onClick={stopTrading} disabled={!isTrading}>⏹️ 停止</button>
                  </div>

                  {/* 测试下单 */}
                  <div style={{marginTop:8,padding:'8px',background:'#0a1a0a',border:'1px dashed #2a4a2a',borderRadius:6}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                      <span style={{fontSize:10,color:'#888'}}>🧪 市价真实下单测试</span>
                      <span style={{fontSize:12,color:'#ffd740',fontWeight:700}}>
                        现价 ${curPrice>0?Number(curPrice).toLocaleString():'--'}
                      </span>
                    </div>
                    <div style={{display:'flex',gap:6}}>
                      <button onClick={()=>testOrder('BUY')} disabled={testOrdering||!account.logged_in||curPrice<=0}
                        style={{flex:1,padding:'7px 4px',background:'#00e67622',border:'1px solid #00e676',color:'#00e676',borderRadius:4,cursor:'pointer',fontSize:12,lineHeight:1.3}}>
                        {testOrdering?'⏳...':<>🟢 市价买入<br/><span style={{fontSize:10,color:'#00a854'}}>@ ${curPrice>0?Number(curPrice).toLocaleString():'--'}</span></>}
                      </button>
                      <button onClick={()=>testOrder('SELL')} disabled={testOrdering||!account.logged_in||curPrice<=0}
                        style={{flex:1,padding:'7px 4px',background:'#ff525222',border:'1px solid #ff5252',color:'#ff5252',borderRadius:4,cursor:'pointer',fontSize:12,lineHeight:1.3}}>
                        {testOrdering?'⏳...':<>🔴 市价卖出<br/><span style={{fontSize:10,color:'#cc3333'}}>@ ${curPrice>0?Number(curPrice).toLocaleString():'--'}</span></>}
                      </button>
                    </div>
                  </div>

                  <div className="mini-stats">
                    <div>策略: <b style={{color:'#40c4ff'}}>{indicators?.strategy || 'crypto_hft'}</b></div>
                    <div>交易数: <b>{perf.total_trades}</b></div>
                    <div>胜率: <b className={parseFloat(perf.win_rate)>=70?'green':''}>{perf.win_rate}%</b></div>
                    <div>盈亏: <b className={perf.total_pnl>=0?'green':'red'}>{perf.total_pnl>=0?'+':''}{(perf.total_pnl||0).toFixed(2)}</b></div>
                  </div>
                </div>
              </div>

              {/* 指标面板（紧凑版，7维度已在HFT控制卡中显示）*/}
              {indicators && indicators.ready && (
                <div className="card indicators-card">
                  <h3 style={{fontSize:12,marginBottom:6}}>📊 实时指标 [CRYPTO_HFT] — {indicators.bars}根K线</h3>
                  <div style={{display:'flex',gap:16,flexWrap:'wrap',fontSize:11}}>
                    <span>EMA <b>F:{Number(indicators.ema?.fast||0).toFixed(1)}</b> S:{Number(indicators.ema?.slow||0).toFixed(1)} L:{Number(indicators.ema?.long||0).toFixed(1)}</span>
                    <span>MACD <b className={(indicators.macd?.hist||0)>0?'green':'red'}>H:{Number(indicators.macd?.hist||0).toFixed(4)}</b></span>
                    <span>RSI <b className={indicators.rsi<30?'green':indicators.rsi>70?'red':''}>{Number(indicators.rsi||0).toFixed(1)}</b></span>
                    <span>OBI <b className={(indicators.ob_imbalance||0)>0?'green':'red'}>{((indicators.ob_imbalance||0)*100).toFixed(1)}%</b></span>
                    <span>ST <b style={{color:indicators.supertrend==='up'?'#00e676':indicators.supertrend==='down'?'#ff5252':'#888'}}>{indicators.supertrend||'--'}</b></span>
                    <span>信号 <b className={indicators.raw_signal?.side==='BUY'?'green':indicators.raw_signal?.side==='SELL'?'red':''}>{indicators.raw_signal?.side||'HOLD'}</b></span>
                  </div>
                </div>
              )}

              {/* 实时日志面板 */}
              <div className="card" style={{padding:'10px 12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                  <div style={{display:'flex',alignItems:'center',gap:8}}>
                    <span style={{fontSize:12,fontWeight:700,color:'#7d8fa3'}}>📋 实时日志</span>
                    <span style={{fontSize:10,padding:'1px 6px',background:'#1c222c',border:'1px solid #1e2530',borderRadius:3,color:'#556070'}}>
                      {liveLog.length}/30
                    </span>
                    {isTrading && <span style={{width:6,height:6,borderRadius:'50%',background:'#00e676',display:'inline-block',boxShadow:'0 0 6px #00e676',animation:'pulse 1.5s infinite'}} />}
                  </div>
                  <div style={{display:'flex',alignItems:'center',gap:6}}>
                    <label style={{display:'flex',alignItems:'center',gap:4,fontSize:10,color:'#556070',cursor:'pointer'}}>
                      <input type="checkbox" checked={logAutoClean} onChange={e=>setLogAutoClean(e.target.checked)}
                        style={{width:11,height:11,cursor:'pointer'}} />
                      5分钟自动清空
                    </label>
                    <button onClick={()=>setLiveLog([])} style={{
                      fontSize:10,padding:'2px 8px',background:'transparent',
                      border:'1px solid #1e2530',color:'#556070',borderRadius:3,cursor:'pointer'
                    }}>清空</button>
                  </div>
                </div>
                <div style={{height:160,overflowY:'auto',fontFamily:'monospace',fontSize:11,lineHeight:1.75,display:'flex',flexDirection:'column',gap:0}}>
                  {liveLog.length===0 && (
                    <div style={{color:'#2a3040',padding:'30px 0',textAlign:'center',fontSize:11}}>
                      {isTrading ? '⏳ 等待交易信号...' : '▷ 启动 HFT 后显示实时日志'}
                    </div>
                  )}
                  {liveLog.map((l,i)=>{
                    const isOk  = l.text.includes('✅') || l.text.includes('止盈');
                    const isBuy = l.text.includes('BUY') || l.text.includes('做多');
                    const isSell= l.text.includes('SELL') || l.text.includes('做空');
                    const isErr = l.text.includes('❌') || l.text.includes('失败') || l.text.includes('错误');
                    const isWarn= l.text.includes('⚠️') || l.text.includes('冷却') || l.text.includes('💸') || l.text.includes('止损');
                    const isFire= l.text.includes('⚡');
                    const textColor = isErr?'#ff5252':isOk?'#00e676':isFire?'#ffd740':isWarn?'#ffab40':isBuy?'#40e090':isSell?'#ff7070':'#4a5a6a';
                    return (
                      <div key={i} style={{
                        display:'flex',gap:8,padding:'1px 4px',borderRadius:3,
                        background: i===0 && (isOk||isErr||isFire) ? `${textColor}0d` : 'transparent',
                      }}>
                        <span style={{color:'#2a3a4a',flexShrink:0,fontSize:10,lineHeight:'1.75'}}>{l.ts}</span>
                        <span style={{color:textColor,wordBreak:'break-word'}}>{l.text}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 每日盈亏历史 */}
              {(() => {
                const dh = perf.daily_history || {};
                const days = Object.keys(dh).sort().slice(-14); // 最近14天
                if (days.length === 0) return null;
                const maxAbs = Math.max(...days.map(d => Math.abs(dh[d].pnl || 0)), 0.01);
                return (
                  <div className="card" style={{padding:12}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
                      <h3 style={{margin:0,fontSize:13}}>📅 每日盈亏历史（最近{days.length}天）</h3>
                      <div style={{display:'flex',gap:12,fontSize:11}}>
                        <span style={{color:'#00e676'}}>盈利天: {days.filter(d=>(dh[d].pnl||0)>0).length}</span>
                        <span style={{color:'#ff5252'}}>亏损天: {days.filter(d=>(dh[d].pnl||0)<0).length}</span>
                      </div>
                    </div>
                    <div style={{display:'flex',gap:3,alignItems:'flex-end',height:80}}>
                      {days.map(d => {
                        const p = dh[d].pnl || 0;
                        const pct = dh[d].pnl_pct || 0;
                        const barH = Math.round(Math.abs(p) / maxAbs * 70);
                        const isPos = p >= 0;
                        const trades = dh[d].trades || 0;
                        const wr = trades > 0 ? Math.round((dh[d].wins||0)/trades*100) : 0;
                        return (
                          <div key={d} style={{flex:1,display:'flex',flexDirection:'column',alignItems:'center',gap:2}} title={`${d}\n盈亏: ${p>=0?'+':''}${p.toFixed(4)} USDT (${pct>=0?'+':''}${pct.toFixed(2)}%)\n交易: ${trades}笔 胜率: ${wr}%`}>
                            <span style={{fontSize:8,color:isPos?'#00e676':'#ff5252',lineHeight:1}}>
                              {pct>=0?'+':''}{pct.toFixed(1)}%
                            </span>
                            <div style={{width:'100%',height:barH,background:isPos?'#00e676':'#ff5252',borderRadius:'2px 2px 0 0',minHeight:2,opacity:0.85}}/>
                            <span style={{fontSize:7,color:'#444',lineHeight:1}}>{d.slice(5)}</span>
                          </div>
                        );
                      })}
                    </div>
                    <div style={{display:'flex',justifyContent:'space-between',marginTop:8,fontSize:10,color:'#555',borderTop:'1px solid #1a1a1a',paddingTop:6}}>
                      <span>今日: <b style={{color:(perf.daily_pnl||0)>=0?'#00e676':'#ff5252'}}>{(perf.daily_pnl||0)>=0?'+':''}{(perf.daily_pnl||0).toFixed(4)} ({(perf.daily_pnl_pct||0).toFixed(2)}%)</b></span>
                      <span>历史总计: <b style={{color:(perf.total_pnl||0)>=0?'#00e676':'#ff5252'}}>{(perf.total_pnl||0)>=0?'+':''}{(perf.total_pnl||0).toFixed(4)} ({(perf.total_pnl_pct||0).toFixed(2)}%)</b></span>
                    </div>
                  </div>
                );
              })()}

              {/* 最近交易 */}
              <div className="card recent-trades-card">
                <h3>🔄 最新交易记录 ({tradeLogs.length})</h3>
                <div className="trades-mini">
                  {tradeLogs.slice(0, 8).map((t, i) => (
                    <div key={t.id || i} className={`trade-row ${t.side === 'BUY' ? 'buy' : 'sell'}`}>
                      <span className="t-time">{t.time || t.ts}</span>
                      <span className={`t-side ${t.side === 'BUY' ? 'green' : 'red'}`}>{t.side}</span>
                      <span className="t-sym">{(t.symbol||'').replace('USDT','')}</span>
                      <span className="t-price">${Number(t.price).toLocaleString()}</span>
                      <span className="t-size">{t.size}</span>
                      <span className={`t-pnl ${t.pnl > 0 ? 'green' : t.pnl < 0 ? 'red' : ''}`}>{t.side === 'CLOSE' ? (t.pnl >= 0 ? '+' : '') + (t.pnl || 0).toFixed(2) : '--'}</span>
                    </div>
                  ))}
                  {tradeLogs.length === 0 && <div className="no-data">暂无交易记录，启动 HFT 后开始记录</div>}
                </div>
              </div>
            </div>
          )}

          {/* ── 持仓页 ── */}
          {view === 'positions' && account.logged_in && (
            <div className="positions-view">
              <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12}}>
                <h3>📈 当前持仓（实时同步）</h3>
                <button className="btn-danger" style={{width:'auto',padding:'6px 14px'}} onClick={() => cancelOrders(settings.symbol)}>撤销 {settings.symbol} 挂单</button>
              </div>
              {account.positions.length === 0 ? (
                <div className="empty-state">暂无持仓</div>
              ) : (
                <div className="positions-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>币种</th><th>方向</th><th>买入USD</th><th>数量</th>
                        <th>开仓价</th><th>标记价</th><th>未实现盈亏</th>
                        <th>🎯 止盈价</th><th>🛡️ 止损价</th>
                        <th>杠杆</th><th>开仓时间</th><th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {account.positions.map((p, i) => {
                        const mark   = Number(p.mark_price)  || 0;
                        const entry  = Number(p.entry_price) || 0;
                        const tp     = Number(p.tp_price)    || 0;
                        const sl     = Number(p.sl_price)    || 0;
                        const isLong = p.side === 'LONG';

                        // 距止盈/止损百分比
                        const tpDist = tp && mark ? ((tp - mark) / mark * 100 * (isLong ? 1 : -1)) : null;
                        const slDist = sl && mark ? ((mark - sl) / mark * 100 * (isLong ? 1 : -1)) : null;

                        // 进度：当前价在开仓→止盈区间的位置
                        const tpPct = tp && entry && tp !== entry
                          ? Math.min(100, Math.max(0,
                              isLong
                                ? (mark - entry) / (tp - entry) * 100
                                : (entry - mark) / (entry - tp) * 100
                            ))
                          : 0;

                        return (
                          <tr key={i} className={isLong ? 'row-long' : 'row-short'}>
                            <td><b>{p.symbol.replace('USDT','')}</b><span style={{color:'#555',fontSize:10}}>/USDT</span></td>
                            <td className={isLong ? 'green' : 'red'} style={{fontWeight:700}}>
                              {isLong ? '▲ 做多' : '▼ 做空'}
                            </td>
                            <td style={{color:'#40c4ff',fontWeight:700}}>
                              ${p.entry_usd > 0 ? Number(p.entry_usd).toFixed(2) : (entry * p.size).toFixed(2)}
                            </td>
                            <td>{p.size}</td>
                            <td>${Number(entry).toLocaleString()}</td>
                            <td>${Number(mark).toLocaleString()}</td>
                            <td className={p.unrealized_pnl >= 0 ? 'green' : 'red'} style={{fontWeight:700}}>
                              {p.unrealized_pnl >= 0 ? '+' : ''}{Number(p.unrealized_pnl).toFixed(4)}
                            </td>

                            {/* 止盈价 + 进度条 + 距离% */}
                            <td>
                              {tp > 0 ? (
                                <div>
                                  <div style={{color:'#00e676',fontWeight:700,fontSize:12}}>
                                    ${Number(tp).toLocaleString()}
                                  </div>
                                  <div style={{height:3,background:'#111',borderRadius:2,marginTop:2,width:60}}>
                                    <div style={{height:'100%',width:`${tpPct}%`,background:'#00e676',borderRadius:2,transition:'width .5s'}}/>
                                  </div>
                                  {tpDist !== null && (
                                    <div style={{fontSize:10,color:'#00e67699',marginTop:1}}>
                                      还差 {Math.abs(tpDist).toFixed(2)}%
                                    </div>
                                  )}
                                </div>
                              ) : <span style={{color:'#444'}}>--</span>}
                            </td>

                            {/* 止损价 + 距离% */}
                            <td>
                              {sl > 0 ? (
                                <div>
                                  <div style={{color:'#ff5252',fontWeight:700,fontSize:12}}>
                                    ${Number(sl).toLocaleString()}
                                  </div>
                                  {slDist !== null && (
                                    <div style={{fontSize:10,color:'#ff525299',marginTop:1}}>
                                      缓冲 {Math.abs(slDist).toFixed(2)}%
                                      {Math.abs(slDist) < 0.3 && <span style={{color:'#ff5252',marginLeft:3}}>⚠️ 接近</span>}
                                    </div>
                                  )}
                                </div>
                              ) : <span style={{color:'#444'}}>--</span>}
                            </td>

                            <td>{p.leverage}x</td>
                            <td style={{color:'#555',fontSize:11}}>{p.open_time || '--'}</td>
                            <td>
                              <button className="btn-danger"
                                style={{width:'auto',padding:'4px 10px',fontSize:11}}
                                onClick={() => closePosition(p.symbol)}>手动平仓</button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              <h3 style={{ marginTop: 24 }}>📋 挂单</h3>
              {account.open_orders.length === 0 ? (
                <div className="empty-state">暂无挂单</div>
              ) : (
                <table className="data-table">
                  <thead><tr><th>币种</th><th>方向</th><th>价格</th><th>数量</th></tr></thead>
                  <tbody>
                    {account.open_orders.map((o, i) => (
                      <tr key={i}>
                        <td>{o.symbol}</td>
                        <td className={o.side === 'BUY' ? 'green' : 'red'}>{o.side}</td>
                        <td>${o.price}</td>
                        <td>{o.size}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* ── 交易记录 ── */}
          {view === 'logs' && account.logged_in && (() => {
            const PAGE_SIZE = 20;
            const filtered = tradeLogs.filter(t =>
              logFilter === 'all'    ? true :
              logFilter === 'buy'    ? t.side === 'BUY' :
              logFilter === 'sell'   ? t.side === 'SELL' :
              logFilter === 'close'  ? t.side === 'CLOSE' : true
            );
            const pages   = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
            const pageLogs= filtered.slice(logPage * PAGE_SIZE, (logPage + 1) * PAGE_SIZE);
            const closedLogs = tradeLogs.filter(t=>t.side==='CLOSE');
            const totalPnl= closedLogs.reduce((s,t)=>s+(t.pnl||0), 0);
            const wins    = closedLogs.filter(t=>t.pnl>0).length;
            const closed  = closedLogs.length;
            return (
              <div className="logs-view">
                {/* 统计卡片行 */}
                <div style={{display:'flex',gap:10,marginBottom:12,flexWrap:'wrap'}}>
                  {[
                    {label:'总记录', val: tradeLogs.length, color:'#40c4ff'},
                    {label:'盈利笔', val: wins, color:'#00e676'},
                    {label:'胜率',   val: closed>0?`${(wins/closed*100).toFixed(1)}%`:'--', color:'#ffd740'},
                    {label:'累计盈亏', val: `${totalPnl>=0?'+':''}${totalPnl.toFixed(2)} U`, color:totalPnl>=0?'#00e676':'#ff5252'},
                  ].map(c=>(
                    <div key={c.label} style={{flex:1,minWidth:90,background:'#111',border:'1px solid #1e1e1e',borderRadius:6,padding:'8px 12px',textAlign:'center'}}>
                      <div style={{fontSize:10,color:'#666',marginBottom:2}}>{c.label}</div>
                      <div style={{fontSize:18,fontWeight:700,color:c.color}}>{c.val}</div>
                    </div>
                  ))}
                </div>

                {/* 筛选 + 标题 */}
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                  <h3 style={{margin:0,fontSize:14}}>📝 交易历史 ({filtered.length} 条)</h3>
                  <div style={{display:'flex',gap:4}}>
                    {[['all','全部'],['buy','买入开多'],['sell','卖出开空'],['close','平仓']].map(([k,l])=>(
                      <button key={k} onClick={()=>{setLogFilter(k);setLogPage(0);}}
                        style={{padding:'2px 8px',fontSize:11,borderRadius:3,cursor:'pointer',
                          background:logFilter===k?'#40c4ff':'transparent',
                          color:logFilter===k?'#000':'#888',
                          border:`1px solid ${logFilter===k?'#40c4ff':'#333'}`}}>
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 策略名中文映射 */}
                {(() => {
                  const stratName = {
                    crypto_hft:   '加密高频策略',
                    multi:        '多策略融合',
                    ema_cross:    'EMA三线交叉',
                    macd:         'MACD金死叉',
                    rsi:          'RSI超买超卖',
                    bbands:       '布林带策略',
                    breakout:     '突破策略',
                    market_making:'做市商策略',
                    reverse_signal:'反向平仓',
                    STOP_LOSS:    '止损平仓',
                    TAKE_PROFIT:  '止盈平仓',
                    CLOSE:        '手动平仓',
                  };
                  const sideZh = { BUY:'买入开多', SELL:'卖出开空', CLOSE:'平仓卖出' };
                  const totalFee = pageLogs.reduce((s,t)=>s+(t.fee||0),0);
                  return (
                    <div className="logs-table-container">
                      {/* 本页手续费汇总 */}
                      <div style={{display:'flex',gap:16,marginBottom:6,fontSize:11,color:'#555',padding:'4px 8px',background:'#0a0a0a',borderRadius:4}}>
                        <span>本页 {pageLogs.length} 笔</span>
                        <span>手续费合计: <b style={{color:'#ff9800'}}>-${totalFee.toFixed(4)} USDT</b></span>
                        <span style={{color:'#444'}}>· 点击行查看明细</span>
                      </div>
                      <table className="data-table logs-table">
                        <thead>
                          <tr>
                            <th>时间</th><th>方向</th><th>币种</th><th>成交价</th>
                            <th>买入金额</th><th>数量</th><th>手续费</th>
                            <th>盈亏</th><th>置信度</th><th>策略</th><th>状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {pageLogs.length === 0 && (
                            <tr><td colSpan="11" className="no-data">暂无记录</td></tr>
                          )}
                          {pageLogs.map((t, i) => {
                            const isOpen     = t.side === 'BUY' || t.side === 'SELL';
                            const isClose    = t.side === 'CLOSE';
                            const sideColor  = t.side==='BUY'?'#00e676':t.side==='SELL'?'#ff5252':'#ffd740';
                            const notional   = t.notional || (t.price * t.size) || 0;
                            const fee        = t.fee || notional * 0.0005;
                            const expanded   = expandedLog === (t.id || i);
                            return [
                              <tr key={t.id||i}
                                onClick={()=>setExpandedLog(expanded ? null : (t.id||i))}
                                style={{cursor:'pointer'}}
                                className={t.side==='BUY'?'row-buy':t.side==='SELL'?'row-sell':''}>
                                <td className="t-time" style={{color:'#555'}}>{t.time || t.ts}</td>
                                <td style={{color:sideColor,fontWeight:700}}>
                                  {sideZh[t.side] || t.side}
                                </td>
                                <td><b>{(t.symbol||'').replace('USDT','')}</b><span style={{color:'#555',fontSize:10}}>/U</span></td>
                                <td>${Number(t.price||0).toLocaleString()}</td>
                                <td style={{color:'#40c4ff',fontWeight:700}}>
                                  ${notional > 0 ? notional.toFixed(2) : '--'}
                                </td>
                                <td>{t.size}</td>
                                <td style={{color:'#ff9800'}}>-${fee.toFixed(4)}</td>
                                <td style={{fontWeight:700,
                                  color:t.pnl>0?'#00e676':t.pnl<0?'#ff5252':'#444'}}>
                                  {isClose
                                    ? (t.pnl>=0?'+':'')+Number(t.pnl).toFixed(4)
                                    : '--'}
                                </td>
                                <td>{t.confidence ? `${(t.confidence*100).toFixed(0)}%` : '--'}</td>
                                <td style={{color:'#40c4ff',fontSize:10}}>
                                  {stratName[t.strategy] || t.strategy || '--'}
                                </td>
                                <td>
                                  <span style={{fontSize:10,padding:'1px 5px',borderRadius:3,
                                    background:t.status==='filled'?'#00e67622':t.status==='failed'?'#ff525222':'#ffd74022',
                                    color:t.status==='filled'?'#00e676':t.status==='failed'?'#ff5252':'#ffd740',
                                    border:`1px solid ${t.status==='filled'?'#00e676':t.status==='failed'?'#ff5252':'#ffd740'}`}}>
                                    {t.status==='filled'?'成交':t.status==='failed'?'失败':'已发'}
                                  </span>
                                  <span style={{marginLeft:4,color:'#333',fontSize:10}}>{expanded?'▲':'▼'}</span>
                                </td>
                              </tr>,
                              expanded && (
                                <tr key={(t.id||i)+'_detail'} style={{background:'#060606'}}>
                                  <td colSpan="11" style={{padding:'10px 16px'}}>
                                    <div style={{display:'flex',gap:24,flexWrap:'wrap',fontSize:11}}>
                                      <div>
                                        <div style={{color:'#444',marginBottom:2}}>📋 交易详情</div>
                                        <div style={{color:'#555'}}>订单ID: <span style={{color:'#40c4ff'}}>{t.result_raw||'--'}</span></div>
                                        <div style={{color:'#555'}}>策略: <span style={{color:'#40c4ff'}}>{stratName[t.strategy]||t.strategy}</span></div>
                                        <div style={{color:'#555'}}>置信度: <span style={{color:'#ffd740'}}>{t.confidence?(t.confidence*100).toFixed(1)+'%':'--'}</span></div>
                                      </div>
                                      <div>
                                        <div style={{color:'#444',marginBottom:2}}>💰 资金明细</div>
                                        <div style={{color:'#555'}}>成交金额: <span style={{color:'#40c4ff'}}>${notional.toFixed(4)} USDT</span></div>
                                        <div style={{color:'#555'}}>手续费(0.05%): <span style={{color:'#ff9800'}}>-${fee.toFixed(6)} USDT</span></div>
                                        {isClose && <div style={{color:'#555'}}>平仓盈亏(扣费后): <span style={{color:t.pnl>=0?'#00e676':'#ff5252',fontWeight:700}}>{t.pnl>=0?'+':''}{Number(t.pnl).toFixed(6)} USDT</span></div>}
                                        {isOpen  && (() => { const margin = (notional / (t.leverage||1)); return <div style={{color:'#555'}}>本次花费: <span style={{color:'#ff9800'}}>保证金 ${margin.toFixed(4)} + 手续费 ${fee.toFixed(4)} USDT</span></div>; })()}
                                      </div>
                                      {isClose && t.pnl < 0 && (
                                        <div style={{background:'#ff525211',border:'1px solid #ff525233',borderRadius:4,padding:'6px 10px'}}>
                                          <div style={{color:'#ff5252',fontWeight:700,marginBottom:2}}>⚠️ 本笔亏损分析</div>
                                          <div style={{color:'#ff525299'}}>总亏损: {Number(t.pnl).toFixed(4)} USDT</div>
                                          <div style={{color:'#ff9800'}}>其中手续费: ${(fee*2).toFixed(4)} USDT (开+平)</div>
                                        </div>
                                      )}
                                      {isClose && t.pnl > 0 && (
                                        <div style={{background:'#00e67611',border:'1px solid #00e67633',borderRadius:4,padding:'6px 10px'}}>
                                          <div style={{color:'#00e676',fontWeight:700,marginBottom:2}}>✅ 本笔盈利</div>
                                          <div style={{color:'#00e67699'}}>净盈利: +{Number(t.pnl).toFixed(4)} USDT</div>
                                          <div style={{color:'#ff9800'}}>已扣手续费: ${(fee*2).toFixed(4)} USDT</div>
                                        </div>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              )
                            ];
                          })}
                        </tbody>
                      </table>
                    </div>
                  );
                })()}

                {/* 分页 */}
                <div style={{display:'flex',justifyContent:'center',alignItems:'center',gap:8,marginTop:10,fontSize:12}}>
                  <button onClick={()=>setLogPage(0)} disabled={logPage===0}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid #333',color:'#888',borderRadius:3,cursor:'pointer'}}>«</button>
                  <button onClick={()=>setLogPage(p=>Math.max(0,p-1))} disabled={logPage===0}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid #333',color:'#888',borderRadius:3,cursor:'pointer'}}>‹</button>
                  <span style={{color:'#666'}}>{logPage+1} / {pages}</span>
                  <button onClick={()=>setLogPage(p=>Math.min(pages-1,p+1))} disabled={logPage>=pages-1}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid #333',color:'#888',borderRadius:3,cursor:'pointer'}}>›</button>
                  <button onClick={()=>setLogPage(pages-1)} disabled={logPage>=pages-1}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid #333',color:'#888',borderRadius:3,cursor:'pointer'}}>»</button>
                </div>
              </div>
            );
          })()}

          {/* ── 策略设置 ── */}
          {view === 'settings' && account.logged_in && (
            <div className="settings-view">
              <h3>⚙️ HFT 策略设置</h3>
              <div className="settings-form">
                <div className="form-row-2">
                  <div className="form-group">
                    <label>交易策略</label>
                    <select value={settings.strategy} onChange={e => {
                      const s = e.target.value;
                      // 选策略时自动填入推荐置信度
                      const recConf = {multi:0.62,crypto_hft:0.62,ema_cross:0.58,macd:0.60,rsi:0.60,bbands:0.58,breakout:0.60,market_making:0.55};
                      setSettings(p => ({ ...p, strategy: s, min_confidence: recConf[s] || 0.60 }));
                    }}>
                      <option value="multi">🧠 多策略加权融合（推荐，目标胜率70%+）</option>
                      <option value="crypto_hft">⚡ 加密货币高频专用（Supertrend+VWAP+微结构）</option>
                      <option value="ema_cross">📈 EMA三线交叉 + HA趋势过滤</option>
                      <option value="macd">📉 MACD 金死叉</option>
                      <option value="rsi">📊 RSI 超买超卖</option>
                      <option value="bbands">🔵 布林带 回归/突破</option>
                      <option value="breakout">🔼 N周期高低点突破 + 成交量</option>
                      <option value="market_making">🎯 做市商 双边挂单</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>交易币种</label>
                    <select value={settings.symbol} onChange={e => setSettings(p => ({ ...p, symbol: e.target.value }))}>
                      <option value="BTCUSDT">BTC/USDT</option>
                      <option value="ETHUSDT">ETH/USDT</option>
                      <option value="SOLUSDT">SOL/USDT</option>
                      <option value="ARBUSDT">ARB/USDT</option>
                      <option value="AVAXUSDT">AVAX/USDT</option>
                    </select>
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label>每笔交易金额 (USD)</label>
                    <input type="number" min="1" value={settings.trade_size_usd}
                      onChange={e => setSettings(p => ({ ...p, trade_size_usd: +e.target.value }))} />
                  </div>
                </div>

                {/* HFT交易模式选择 */}
                <div className="form-group" style={{marginBottom:12}}>
                  <label style={{marginBottom:6,display:'block'}}>⚡ HFT交易模式</label>
                  <div style={{display:'flex',gap:6}}>
                    {[
                      ['conservative','🛡️ 精准','#00e676',['盈亏比≥ 1.8x','震荡打折 40%','开单少但精准']],
                      ['balanced',   '⚖️ 平衡','#ffd740',['盈亏比≥ 1.2x','震荡打折 20%','推荐默认设置']],
                      ['aggressive', '⚡ 激进','#ff5252',['盈亏比≥ 0.3x','震荡不打折', '高频快进快出']],
                    ].map(([val, label, color, lines]) => {
                      const active = settings.hft_mode === val;
                      return (
                        <button key={val} onClick={async()=>{
                          const next = {...settings, hft_mode:val};
                          setSettings(next);
                          try{
                            await fetch(`${API_BASE}/api/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...next,symbol_settings:{...symbolSettings,...next.symbol_settings}})});
                            showToast(`✅ 已切换到${label}模式（即时生效）`,'success');
                          }catch{showToast('模式切换失败，请手动保存设置','error');}
                        }}
                          style={{flex:1,padding:'8px 6px',borderRadius:6,cursor:'pointer',textAlign:'center',
                            background:active?`${color}22`:'transparent',
                            border:`2px solid ${active?color:'#222'}`,
                            color:active?color:'#444',
                            transition:'all .2s'}}>
                          <div style={{fontWeight:700,fontSize:12,marginBottom:4}}>{label}</div>
                          {lines.map((l,i)=><div key={i} style={{fontSize:9,lineHeight:1.6,color:active?color:'#333'}}>{l}</div>)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <span>最小置信度</span>
                      <span style={{color: settings.min_confidence>=0.70?'#00e676':settings.min_confidence>=0.62?'#ffd740':'#ff5252',fontWeight:700,fontSize:13}}>
                        {(settings.min_confidence*100).toFixed(0)}%
                        {settings.min_confidence>=0.70?' 🟢 高精准':settings.min_confidence>=0.62?' 🟡 平衡':' 🔴 高频次'}
                      </span>
                    </label>
                    <input type="range" min="50" max="90" value={settings.min_confidence * 100}
                      onChange={e => setSettings(p => ({ ...p, min_confidence: +e.target.value / 100 }))}
                      style={{width:'100%',accentColor: settings.min_confidence>=0.70?'#00e676':settings.min_confidence>=0.62?'#ffd740':'#ff5252'}} />
                    {/* 快选档位 */}
                    <div style={{display:'flex',gap:4,marginTop:4,flexWrap:'wrap'}}>
                      {[
                        [55,'55%','🔴 极高频'],
                        [60,'60%','🔴 高频'],
                        [62,'62%','⭐ 推荐'],
                        [68,'68%','🟡 稳健'],
                        [75,'75%','🟢 高精准'],
                      ].map(([v,label,desc])=>(
                        <button key={v} onClick={()=>setSettings(p=>({...p,min_confidence:v/100}))}
                          style={{flex:1,padding:'3px 2px',fontSize:9,borderRadius:3,cursor:'pointer',textAlign:'center',
                            background:Math.round(settings.min_confidence*100)===v?'#ffd74033':'transparent',
                            border:`1px solid ${Math.round(settings.min_confidence*100)===v?'#ffd740':'#222'}`,
                            color:Math.round(settings.min_confidence*100)===v?'#ffd740':'#555'}}>
                          <div style={{fontWeight:700}}>{label}</div>
                          <div style={{fontSize:8,marginTop:1}}>{desc}</div>
                        </button>
                      ))}
                    </div>
                    {/* 当前策略推荐说明 */}
                    {(() => {
                      const rec = {multi:62,crypto_hft:62,ema_cross:58,macd:60,rsi:60,bbands:58,breakout:60,market_making:55};
                      const cur = Math.round(settings.min_confidence*100);
                      const recommended = rec[settings.strategy] || 62;
                      return cur !== recommended ? (
                        <div style={{marginTop:4,fontSize:10,color:'#ffd740',padding:'3px 6px',background:'#ffd74011',borderRadius:3,border:'1px solid #ffd74033'}}>
                          ⚠️ 当前策略推荐置信度为 <b>{recommended}%</b>，
                          <button onClick={()=>setSettings(p=>({...p,min_confidence:recommended/100}))}
                            style={{background:'transparent',border:'none',color:'#40c4ff',cursor:'pointer',fontSize:10,padding:'0 2px'}}>[点此自动设置]</button>
                        </div>
                      ) : (
                        <div style={{marginTop:4,fontSize:10,color:'#00e676'}}>✅ 已是当前策略最优置信度</div>
                      );
                    })()}
                  </div>
                  <div className="form-group">
                    <label>最大持仓 (USD)</label>
                    <input type="number" value={settings.max_position_usd}
                      onChange={e => setSettings(p => ({ ...p, max_position_usd: +e.target.value }))} />
                  </div>
                </div>

                {/* 策略参数展开 */}
                {settings.strategy === 'ema_cross' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>EMA快线</label><input type="number" value={settings.ema_fast} onChange={e => setSettings(p => ({...p, ema_fast: +e.target.value}))} /></div>
                    <div className="form-group"><label>EMA慢线</label><input type="number" value={settings.ema_slow} onChange={e => setSettings(p => ({...p, ema_slow: +e.target.value}))} /></div>
                    <div className="form-group"><label>EMA长线</label><input type="number" value={settings.ema_long} onChange={e => setSettings(p => ({...p, ema_long: +e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy === 'macd' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>MACD快</label><input type="number" value={settings.macd_fast} onChange={e => setSettings(p => ({...p, macd_fast: +e.target.value}))} /></div>
                    <div className="form-group"><label>MACD慢</label><input type="number" value={settings.macd_slow} onChange={e => setSettings(p => ({...p, macd_slow: +e.target.value}))} /></div>
                    <div className="form-group"><label>Signal</label><input type="number" value={settings.macd_signal} onChange={e => setSettings(p => ({...p, macd_signal: +e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy === 'rsi' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>RSI周期</label><input type="number" value={settings.rsi_period} onChange={e => setSettings(p => ({...p, rsi_period: +e.target.value}))} /></div>
                    <div className="form-group"><label>超卖线</label><input type="number" value={settings.rsi_oversold} onChange={e => setSettings(p => ({...p, rsi_oversold: +e.target.value}))} /></div>
                    <div className="form-group"><label>超买线</label><input type="number" value={settings.rsi_overbought} onChange={e => setSettings(p => ({...p, rsi_overbought: +e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy === 'bbands' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>BB周期</label><input type="number" value={settings.bb_period} onChange={e => setSettings(p => ({...p, bb_period: +e.target.value}))} /></div>
                    <div className="form-group"><label>BB倍数</label><input type="number" step="0.1" value={settings.bb_std} onChange={e => setSettings(p => ({...p, bb_std: +e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy === 'breakout' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>突破周期</label><input type="number" value={settings.breakout_period} onChange={e => setSettings(p => ({...p, breakout_period: +e.target.value}))} /></div>
                    <div className="form-group"><label>成交量倍数</label><input type="number" step="0.1" value={settings.breakout_vol_mult} onChange={e => setSettings(p => ({...p, breakout_vol_mult: +e.target.value}))} /></div>
                  </div>
                )}
                {(settings.strategy === 'multi' || settings.strategy === 'crypto_hft') && (
                  <div className="alert alert-info" style={{marginTop:6,fontSize:12}}>
                    💡 <b>当前策略说明</b>:
                    {settings.strategy === 'multi' ? ' 七维加权融合：crypto_hft(40%) + EMA(20%) + MACD(15%) + BBands(10%) + RSI(8%) + 突破(7%)。主策略信号必须存在且至少2个子策略方向一致才下单。建议置信度阈值 0.62+。' : ' Supertrend趋势过滤 + VWAP偏离分析 + 订单簿微结构 + RSI位置 + MACD动能 + Heikin Ashi确认。逆趋势硬封锁检测。'}
                  </div>
                )}
                {settings.strategy === 'market_making' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>价差(%)</label><input type="number" step="0.0001" value={settings.mm_spread_pct} onChange={e => setSettings(p => ({...p, mm_spread_pct: +e.target.value}))} /></div>
                    <div className="form-group"><label>单笔USD</label><input type="number" value={settings.mm_order_size_usd} onChange={e => setSettings(p => ({...p, mm_order_size_usd: +e.target.value}))} /></div>
                  </div>
                )}

                {/* 推荐策略卡片（按币种，支持独立参数配置） */}
                {(()=>{
                  const RECS = [
                    {sym:'BTCUSDT',label:'BTC',color:'#f7931a',icon:'₿',
                     tp:0.028,sl:0.012,lev:3,conf:0.65,
                     winRate:'62%',reason:'流动性最强，Supertrend+EMA趋势行情高度可靠，ADX过滤震荡效果好'},
                    {sym:'ETHUSDT',label:'ETH',color:'#627eea',icon:'Ξ',
                     tp:0.032,sl:0.014,lev:2,conf:0.63,
                     winRate:'59%',reason:'波动率适中，VWAP偏离+订单簿信号配合好，趋势跟随首选'},
                    {sym:'SOLUSDT',label:'SOL',color:'#9945ff',icon:'◎',
                     tp:0.040,sl:0.018,lev:2,conf:0.66,
                     winRate:'55%',reason:'波动较大，需更宽止盈止损，ADX阈值建议调高至25+'},
                    {sym:'ARBUSDT',label:'ARB',color:'#28a0f0',icon:'△',
                     tp:0.035,sl:0.015,lev:2,conf:0.67,
                     winRate:'52%',reason:'流动性较弱，信号噪音大，需更高置信度阈值'},
                    {sym:'AVAXUSDT',label:'AVAX',color:'#e84142',icon:'▲',
                     tp:0.038,sl:0.016,lev:2,conf:0.65,
                     winRate:'54%',reason:'与BTC高相关，趋势行情表现好，建议跟随BTC方向'},
                  ];
                  return (
                    <div style={{marginBottom:14}}>
                      <div style={{fontSize:11,color:'#40c4ff',fontWeight:700,marginBottom:8}}>🎯 各币种推荐策略 · 独立参数配置</div>
                      <div style={{display:'flex',flexDirection:'column',gap:6}}>
                        {RECS.map(({sym,label,color,icon,tp,sl,lev,conf,winRate,reason})=>{
                          const isActive = (settings.active_symbols||[]).includes(sym);
                          // 当前该币种保存的独立参数（优先用symbolSettings，否则推荐值）
                          const cur = symbolSettings[sym] || {};
                          const curTp   = cur.take_profit_pct ?? tp;
                          const curSl   = cur.stop_loss_pct   ?? sl;
                          const curLev  = cur.leverage        ?? lev;
                          const curConf = cur.min_confidence  ?? conf;
                          const hasCust = !!symbolSettings[sym];
                          return (
                            <div key={sym} style={{
                              border:`1px solid ${isActive?color:'#1e1e1e'}`,borderRadius:6,
                              background:isActive?`${color}08`:'#080808',padding:'8px 10px',
                            }}>
                              {/* 头部 */}
                              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:4}}>
                                <div style={{display:'flex',alignItems:'center',gap:6}}>
                                  <span style={{fontWeight:700,color,fontSize:12}}>{icon} {label}</span>
                                  {hasCust && <span style={{fontSize:9,padding:'1px 5px',background:`${color}22`,border:`1px solid ${color}44`,color,borderRadius:2}}>已自定义</span>}
                                  {!isActive && <span style={{fontSize:9,color:'#333'}}>未启用</span>}
                                </div>
                                <div style={{display:'flex',gap:5,alignItems:'center'}}>
                                  <span style={{fontSize:10,color:'#666'}}>参考胜率 <b style={{color:parseInt(winRate)>=60?'#00e676':parseInt(winRate)>=55?'#ffd740':'#ff9800'}}>{winRate}</b></span>
                                  <button onClick={async()=>{
                                    const params={take_profit_pct:curTp,stop_loss_pct:curSl,leverage:curLev,min_confidence:curConf};
                                    setSymbolSettings(p=>({...p,[sym]:params}));
                                    try{
                                      await fetch(`${API_BASE}/api/settings/symbol`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:sym,params})});
                                      showToast(`✅ ${label} 独立参数已保存`,'success');
                                    }catch{ showToast('保存失败','error'); }
                                  }} style={{fontSize:10,padding:'2px 8px',borderRadius:3,
                                    border:`1px solid ${color}`,background:`${color}22`,color,cursor:'pointer'}}>
                                    💾 保存到{label}
                                  </button>
                                </div>
                              </div>
                              {/* 理由 */}
                              <div style={{fontSize:10,color:'#444',marginBottom:6}}>{reason}</div>
                              {/* 可编辑参数行 */}
                              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr 1fr',gap:6}}>
                                {[
                                  {key:'take_profit_pct',label:'止盈%',val:curTp,color:'#00e676',step:0.1,min:0.1,max:10},
                                  {key:'stop_loss_pct',  label:'止损%',val:curSl, color:'#ff5252',step:0.1,min:0.1,max:5},
                                  {key:'leverage',       label:'杠杆x',val:curLev, color:'#ffd740',step:1,  min:1,  max:10},
                                  {key:'min_confidence', label:'置信%',val:curConf,color:'#40c4ff',step:1,  min:50, max:90},
                                ].map(({key,label:kl,val,color:kc,step,min,max})=>(
                                  <div key={key}>
                                    <div style={{fontSize:9,color:'#555',marginBottom:2}}>{kl}</div>
                                    <input type="number" step={step} min={min} max={max}
                                      value={key==='min_confidence'?Math.round(val*100):key==='leverage'?val:parseFloat((val*100).toFixed(2))}
                                      onChange={e=>{
                                        let v = parseFloat(e.target.value);
                                        if(isNaN(v)) return;
                                        const stored = (key==='min_confidence'||key==='take_profit_pct'||key==='stop_loss_pct') ? v/100 : (key==='leverage' ? v : v/100);
                                        setSymbolSettings(p=>({...p,[sym]:{...(p[sym]||{}),take_profit_pct:curTp,stop_loss_pct:curSl,leverage:curLev,min_confidence:curConf,[key]:stored}}));
                                      }}
                                      style={{width:'100%',padding:'3px 4px',background:'#111',border:`1px solid ${kc}44`,
                                        color:kc,borderRadius:3,fontSize:11,textAlign:'right'}}
                                    />
                                  </div>
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()}

                {/* 多币种同时交易 */}
                <div className="form-group" style={{marginBottom:12}}>
                  <label style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                    <span>🌐 同时交易币种 <span style={{fontSize:10,color:'#555'}}>(每个币种独立最多1单)</span></span>
                    <span style={{fontSize:10,color:'#40c4ff'}}>
                      已选 {(settings.active_symbols||[]).length} 个 · 最大持仓 {settings.max_open_positions} 单
                    </span>
                  </label>
                  <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                    {[
                      ['BTCUSDT','BTC','#f7931a'],
                      ['ETHUSDT','ETH','#627eea'],
                      ['SOLUSDT','SOL','#9945ff'],
                      ['ARBUSDT','ARB','#2d374b'],
                      ['AVAXUSDT','AVAX','#e84142'],
                    ].map(([sym,label,color])=>{
                      const active = (settings.active_symbols||[]).includes(sym);
                      return (
                        <button key={sym} onClick={async()=>{
                          const cur = settings.active_symbols||[];
                          const next = active ? cur.filter(s=>s!==sym) : [...cur,sym];
                          if(next.length===0) return;
                          const nextSettings = {...settings, active_symbols:next, symbol:next[0]};
                          setSettings(nextSettings);
                          try{
                            await fetch(`${API_BASE}/api/settings`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...nextSettings,symbol_settings:{...symbolSettings,...nextSettings.symbol_settings}})});
                          }catch{}
                        }} style={{
                          padding:'5px 12px',borderRadius:5,cursor:'pointer',fontSize:12,fontWeight:700,
                          background: active?`${color}22`:'transparent',
                          border:`2px solid ${active?color:'#333'}`,
                          color: active?color:'#555',
                          transition:'all .2s',
                        }}>
                          {active?'✓ ':''}{label}
                        </button>
                      );
                    })}
                  </div>
                  <div style={{marginTop:5,fontSize:10,color:'#444'}}>
                    💡 勾选多个币种后，HFT会同时监控并各自独立下单，每个币种同时只持1单，止盈/止损后自动进入下一单
                  </div>
                </div>

                <div className="form-row checkboxes">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.enable_long}
                      onChange={e => setSettings(p => ({ ...p, enable_long: e.target.checked }))} />
                    <span>📈 允许做多</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.enable_short}
                      onChange={e => setSettings(p => ({ ...p, enable_short: e.target.checked }))} />
                    <span>📉 允许做空</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.cancel_on_reverse}
                      onChange={e => setSettings(p => ({ ...p, cancel_on_reverse: e.target.checked }))} />
                    <span>↩️ 反向自动撤单</span>
                  </label>
                </div>

                <div className="form-row-2" style={{marginTop:8}}>
                  <div className="form-group"><label>最大持仓数</label><input type="number" value={settings.max_open_positions} onChange={e => setSettings(p => ({...p, max_open_positions: +e.target.value}))} /></div>
                  <div className="form-group"><label>日亏损限额(USD)</label><input type="number" value={settings.max_daily_loss_usd} onChange={e => setSettings(p => ({...p, max_daily_loss_usd: +e.target.value}))} /></div>
                  <div className="form-group"><label>HFT间隔(ms)</label><input type="number" value={settings.hft_interval_ms} onChange={e => setSettings(p => ({...p, hft_interval_ms: +e.target.value}))} /></div>
                  <div className="form-group">
                    <label>平仓冷却(秒) <span style={{color:'#ff9800',fontSize:10}}>防反复横跳</span></label>
                    <input type="number" min="0" max="300" value={settings.cooldown_secs} onChange={e => setSettings(p => ({...p, cooldown_secs: +e.target.value}))} />
                  </div>
                </div>

                <div className="form-actions">
                  <button className="btn-primary" onClick={saveSettings}>💾 保存并应用</button>
                </div>

                <div className="alert alert-warn" style={{marginTop:12}}>
                  ⚠️ 实盘模式已启用，将使用真实资金进行自动交易。请确保风险参数正确。
                </div>
              </div>

              {/* ── 自动迭代优化面板 ── */}
              <div className="card" style={{marginTop:16,padding:14}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
                  <h3 style={{margin:0,fontSize:13}}>🔬 自动参数迭代优化</h3>
                  <div style={{display:'flex',gap:8,alignItems:'center'}}>
                    {(() => {
                      const closed = tradeLogs.filter(t=>t.side==='CLOSE').length;
                      const need = 20;
                      return (
                        <span style={{fontSize:10,color:closed>=need?'#00e676':'#888'}}>
                          平仓数据 <b>{closed}</b>/{need} {closed>=need?'✅ 可优化':'(积累中)'}
                        </span>
                      );
                    })()}
                    <button onClick={async()=>{
                      setOptLoading(true);
                      try {
                        const r = await fetch(`${API_BASE}/api/optimize/run`,{method:'POST'});
                        const d = await r.json();
                        setOptResult(d);
                        if(d.best) showToast('✅ 优化完成，发现更优参数组合','success');
                        else showToast(d.error||'数据不足，请积累更多交易记录','warn');
                      } catch(e){ showToast('优化请求失败','error'); }
                      setOptLoading(false);
                    }} disabled={optLoading} style={{
                      padding:'4px 12px',borderRadius:4,cursor:'pointer',fontSize:12,
                      background:optLoading?'#1a1a1a':'#40c4ff22',
                      border:'1px solid #40c4ff',color:'#40c4ff',
                    }}>{optLoading?'⏳ 分析中...':'▶ 立即优化'}</button>
                  </div>
                </div>

                <div style={{fontSize:10,color:'#555',marginBottom:10,lineHeight:1.6}}>
                  系统每积累 <b style={{color:'#ffd740'}}>20笔平仓</b> 自动运行一次参数网格搜索（置信度×止损×止盈 共150种组合），
                  找出历史期望收益最高的参数组合，点击「应用」后立即生效。
                </div>

                {optResult && optResult.best ? (
                  <div>
                    <div style={{background:'#00e67611',border:'1px solid #00e67633',borderRadius:6,padding:'8px 10px',marginBottom:8}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                        <span style={{fontSize:11,color:'#00e676',fontWeight:700}}>🏆 最优参数组合</span>
                        <span style={{fontSize:10,color:'#555'}}>优化时间: {optResult.optimized_at}</span>
                      </div>
                      <div style={{display:'flex',gap:16,fontSize:11,marginBottom:8}}>
                        <span>置信阈值 <b style={{color:'#40c4ff'}}>{Math.round(optResult.best.min_confidence*100)}%</b></span>
                        <span>止损 <b style={{color:'#ff5252'}}>{(optResult.best.stop_loss_pct*100).toFixed(1)}%</b></span>
                        <span>止盈 <b style={{color:'#00e676'}}>{(optResult.best.take_profit_pct*100).toFixed(1)}%</b></span>
                        {optResult.top5?.[0] && <>
                          <span>预期胜率 <b style={{color:'#ffd740'}}>{optResult.top5[0].win_rate}%</b></span>
                          <span>样本 <b>{optResult.top5[0].sample}笔</b></span>
                        </>}
                      </div>
                      <button onClick={async()=>{
                        try {
                          const r = await fetch(`${API_BASE}/api/optimize/apply`,{method:'POST'});
                          const d = await r.json();
                          if(d.ok){ setSettings(p=>({...p,...d.applied})); showToast('✅ 最优参数已应用','success'); }
                          else showToast(d.error||'应用失败','error');
                        } catch(e){ showToast(`应用失败: ${e.message}`,'error'); }
                      }} style={{
                        width:'100%',padding:'6px',borderRadius:4,cursor:'pointer',fontSize:12,fontWeight:700,
                        background:'#00e67622',border:'1px solid #00e676',color:'#00e676',
                      }}>🔁 应用最优参数到当前策略</button>
                    </div>

                    {/* Top5 参数组合 */}
                    {optResult.top5?.length > 1 && (
                      <div>
                        <div style={{fontSize:10,color:'#555',marginBottom:4}}>Top 5 参数组合（按期望收益排序）</div>
                        <table style={{width:'100%',borderCollapse:'collapse',fontSize:10}}>
                          <thead>
                            <tr style={{color:'#444'}}>
                              <td style={{padding:'2px 4px'}}>#</td>
                              <td>置信</td><td>止损</td><td>止盈</td>
                              <td style={{color:'#ffd740'}}>胜率</td>
                              <td style={{color:'#00e676'}}>均盈亏</td>
                              <td>样本</td>
                              <td>盈亏比</td>
                            </tr>
                          </thead>
                          <tbody>
                            {optResult.top5.map((row,i)=>(
                              <tr key={i} style={{borderTop:'1px solid #111',color:i===0?'#00e676':'#666'}}>
                                <td style={{padding:'3px 4px',color:'#555'}}>{i+1}</td>
                                <td>{Math.round(row.min_confidence*100)}%</td>
                                <td style={{color:'#ff5252'}}>{(row.stop_loss_pct*100).toFixed(1)}%</td>
                                <td style={{color:'#00e676'}}>{(row.take_profit_pct*100).toFixed(1)}%</td>
                                <td style={{color:row.win_rate>=55?'#00e676':row.win_rate>=45?'#ffd740':'#ff5252',fontWeight:700}}>{row.win_rate}%</td>
                                <td style={{color:row.avg_pnl>=0?'#00e676':'#ff5252'}}>{row.avg_pnl>=0?'+':''}{row.avg_pnl}</td>
                                <td>{row.sample}</td>
                                <td>{row.rr}x</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : (
                  <div style={{textAlign:'center',padding:'20px 0',color:'#333',fontSize:11}}>
                    {optLoading ? '⏳ 正在分析历史数据...' : '暂无优化结果。积累20笔平仓后点击「立即优化」或等待自动触发。'}
                  </div>
                )}
              </div>
            </div>

          )}

        </div>
      </div>
    </div>
  );
}

export default App;
