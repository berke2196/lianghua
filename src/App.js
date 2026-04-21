import React, { useState, useEffect, useCallback, useRef } from 'react';
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import './App.css';

const _HOST   = process.env.REACT_APP_API_URL      || `${window.location.protocol}//${window.location.host}`;
const _WS_HOST = _HOST.replace(/^https/, 'wss').replace(/^http/, 'ws');
const _PREFIX  = process.env.REACT_APP_API_PREFIX   || '';

function API(path) { return _PREFIX ? `${_HOST}/${_PREFIX}${path}` : `${_HOST}${path}`; }
function WSU(path) { return _PREFIX ? `${_WS_HOST}/${_PREFIX}${path}` : `${_WS_HOST}${path}`; }

function authFetch(path, opts = {}) {
  const token = localStorage.getItem('jwt_token') || '';
  const headers = { ...(opts.headers || {}), ...(token ? { 'Authorization': `Bearer ${token}` } : {}) };
  return fetch(API(path), { ...opts, headers });
}

function App() {
  const [view, setView] = useState('auth');
  const viewRef = useRef('auth');
  const _setView = (v) => { viewRef.current = v; setView(v); };

  // 账号认证
  const [jwtToken, setJwtToken] = useState(() => localStorage.getItem('jwt_token') || '');
  const [authUser, setAuthUser] = useState(() => localStorage.getItem('auth_user') || '');
  const [authView, setAuthView] = useState('login'); // login | register | activate
  const [authForm, setAuthForm] = useState({ username:'', email:'', password:'', license_code:'' });
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState('');
  const [authSuccess, setAuthSuccess] = useState('');
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem('is_admin') === '1');

  // 管理后台
  const [changePwdTarget, setChangePwdTarget] = useState(''); // 当前要改密码的用户名
  const [changePwdVal, setChangePwdVal] = useState('');
  const [changePwdMsg, setChangePwdMsg] = useState('');
  const [adminGenCount, setAdminGenCount] = useState(1);
  const [adminGenDays, setAdminGenDays] = useState(30);
  const [adminGenLoading, setAdminGenLoading] = useState(false);
  const [adminNewCodes, setAdminNewCodes] = useState([]);
  const [adminUsers, setAdminUsers] = useState([]);
  const [adminLicenses, setAdminLicenses] = useState([]);
  const [adminTab, setAdminTab] = useState('gen'); // gen | users | licenses
  const [settingsTab, setSettingsTab] = useState('basic'); // basic | risk | symbols | advanced
  const [expandedSymbol, setExpandedSymbol] = useState(null); // 展开的币种推荐卡片

  // 连接
  const [backendOk, setBackendOk] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = useRef(null);

  // 登录表单
  const [loginForm, setLoginForm] = useState({ user: '', signer: '', private_key: '' });
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
  const [showScores, setShowScores] = useState(false);
  const [optResult, setOptResult] = useState(null);
  const [optLoading, setOptLoading] = useState(false);

  // 设置
  const [settings, setSettings] = useState({
    strategy: 'multi',
    symbol: 'BTCUSDT',
    leverage: 5,
    stop_loss_pct: 0.005,
    take_profit_pct: 0.008,
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
    // Risk
    max_open_positions: 3, max_daily_loss_usd: 50, max_position_usd: 500, max_trade_usd: 30,
    cancel_on_reverse: true, hft_interval_ms: 500,
    cooldown_secs: 60,
    hft_mode: 'balanced',  // balanced模式RR≥1.2，收支平衡起点
    active_symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
  });
  const [indicators, setIndicators] = useState(null);
  const [multiIndicators, setMultiIndicators] = useState({}); // {BTCUSDT: {...}, ETHUSDT: {...}}
  const multiIndicatorsRef = useRef({});                       // ref版，供WS/callback读取
  const [symbolSettings, setSymbolSettings] = useState({});   // 每币种独立参数
  const [activeSym, setActiveSym] = useState('BTCUSDT');      // 仪表盘当前查看的币种
  const activeSymRef = useRef('BTCUSDT');                      // WS回调里用ref，避免stale closure
  const switchActiveSym = useCallback((sym) => {
    activeSymRef.current = sym;
    setActiveSym(sym);
    const latest = multiIndicatorsRef.current[sym];
    if (latest) setIndicators(latest);
  }, []);
  const [liveLog, setLiveLog] = useState([]);
  const [balanceDelta, setBalanceDelta] = useState(0); // >0涨 <0跌 0无变化
  const [logAutoClean, setLogAutoClean] = useState(true); // 是否自动清空日志
  const [testOrdering, setTestOrdering] = useState(false);
  const [tgConfig, setTgConfig] = useState({ token: '', chat_id: '', token_set: false, enabled: false });
  const [tgSaving, setTgSaving] = useState(false);

  const [toast, setToast] = useState(null);

  const showToast = useCallback((msg, type = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  }, []);

  // ─── JWT 初始化：有 token 直接进登录页，并自动拉取已保存的地址 ───
  useEffect(() => {
    if (jwtToken && authUser) {
      _setView('login');
      // 自动拉取上次登录保存的 wallet/signer
      fetch(API('/api/auth/saved-credentials'), {
        headers: { 'Authorization': `Bearer ${jwtToken}` }
      }).then(r => r.json()).then(d => {
        if (d.ok && d.user) {
          setLoginForm(p => ({
            ...p,
            user: d.user,
            signer: d.signer || '',
            private_key: d.private_key || '',
          }));
        }
      }).catch(() => {});
    }
  }, []); // eslint-disable-line

  // ─── 账号注册 ───
  const handleRegister = async () => {
    setAuthLoading(true); setAuthError(''); setAuthSuccess('');
    try {
      const r = await fetch(API('/api/auth/register'), {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ username: authForm.username, email: authForm.email, password: authForm.password })
      });
      const d = await r.json();
      if (d.ok) { setAuthSuccess(d.msg); setAuthView('activate'); }
      else setAuthError(d.msg);
    } catch { setAuthError('网络错误，无法连接服务器'); }
    setAuthLoading(false);
  };

  // ─── 账号激活 ───
  const handleActivate = async () => {
    setAuthLoading(true); setAuthError(''); setAuthSuccess('');
    try {
      const r = await fetch(API('/api/auth/activate'), {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ username: authForm.username, license_code: authForm.license_code })
      });
      const d = await r.json();
      if (d.ok) { setAuthSuccess(d.msg + '，请登录'); setAuthView('login'); }
      else setAuthError(d.msg);
    } catch { setAuthError('网络错误，无法连接服务器'); }
    setAuthLoading(false);
  };

  // ─── 账号密码登录 → 拿 JWT ───
  const handlePasswordLogin = async () => {
    setAuthLoading(true); setAuthError(''); setAuthSuccess('');
    try {
      const r = await fetch(API('/api/auth/password-login'), {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ username: authForm.username, password: authForm.password })
      });
      const d = await r.json();
      if (d.ok) {
        setJwtToken(d.token);
        setAuthUser(d.username);
        setIsAdmin(!!d.is_admin);
        localStorage.setItem('jwt_token', d.token);
        localStorage.setItem('auth_user', d.username);
        localStorage.setItem('is_admin', d.is_admin ? '1' : '0');
        _setView('login');
      } else setAuthError(d.msg);
    } catch { setAuthError('网络错误，无法连接服务器'); }
    setAuthLoading(false);
  };

  // ─── 退出账号 ───
  const handleAccountLogout = () => {
    setJwtToken(''); setAuthUser(''); setIsAdmin(false);
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('auth_user');
    localStorage.removeItem('is_admin');
    _setView('auth');
  };

  // ─── 管理：生成授权码 ───
  const handleGenLicense = async () => {
    setAdminGenLoading(true); setAdminNewCodes([]);
    try {
      const r = await authFetch('/api/admin/generate-license', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ count: adminGenCount, days: adminGenDays })
      });
      const d = await r.json();
      if (d.ok) { setAdminNewCodes(d.codes); showToast(`✅ 生成 ${d.codes.length} 个授权码`, 'success'); }
      else showToast(`❌ ${d.msg || d.detail}`, 'error');
    } catch { showToast('网络错误', 'error'); }
    setAdminGenLoading(false);
  };

  // ─── 管理：加载用户/授权码列表 ───
  const loadAdminData = async (tab) => {
    if (!jwtToken) return;
    try {
      if (tab === 'users' || tab === 'all') {
        const r = await authFetch('/api/admin/users');
        const d = await r.json();
        if (d.ok) setAdminUsers(d.data);
      }
      if (tab === 'licenses' || tab === 'all') {
        const r = await authFetch('/api/admin/licenses');
        const d = await r.json();
        if (d.ok) setAdminLicenses(d.data);
      }
    } catch {}
  };

  // ─── 健康检查（同步 isTrading / logged_in 状态）───
  const isTradingRef = useRef(false);
  const healthFailRef = useRef(0); // 连续失败计数
  useEffect(() => { isTradingRef.current = isTrading; }, [isTrading]);
  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch(API('/api/health'), { signal: AbortSignal.timeout(4000) });
        if (r.ok) {
          healthFailRef.current = 0;
          setBackendOk(true);
        } else {
          healthFailRef.current += 1;
          if (healthFailRef.current >= 2) setBackendOk(false);
        }
      } catch {
        healthFailRef.current += 1;
        if (healthFailRef.current >= 2) setBackendOk(false);
      }
      // 同步用户状态（需要认证）
      if (account.logged_in) {
        try {
          const sr = await authFetch('/api/trading/status', { signal: AbortSignal.timeout(4000) });
          if (sr.ok) {
            const sd = await sr.json();
            if (!!sd.auto_trading !== isTradingRef.current) setIsTrading(!!sd.auto_trading);
          }
        } catch {}
      }
    };
    check();
    const t = setInterval(check, 5000);
    return () => clearInterval(t);
  }, [account.logged_in]);

  // ─── 指标通过 WS 实时接收（indicators_push），0延迟，无轮询 ───

  // ─── 日志定时自动清空（每5分钟） ───
  useEffect(() => {
    if (!logAutoClean) return;
    const t = setInterval(() => {
      setLiveLog(prev => prev.length > 0 ? [] : prev);
    }, 5 * 60 * 1000);
    return () => clearInterval(t);
  }, [logAutoClean]);

  const connectWS = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState < 2) return;
    const _tok = localStorage.getItem('jwt_token') || '';
    const ws = new WebSocket(WSU('/ws/frontend') + (_tok ? `?token=${encodeURIComponent(_tok)}` : ''));
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
            setAccount(prev => ({ ...prev, ...data }));
            if (data.performance) setPerf(data.performance);
            if (data.settings) {
              const { symbol_settings: ss, ...globalOnly } = data.settings;
              setSettings(prev => ({ ...prev, ...globalOnly }));
              if (ss) setSymbolSettings(ss);
            }
            if (data.trade_logs)  setTradeLogs(data.trade_logs);
            if (data.auto_trading != null) setIsTrading(data.auto_trading);
            if (data.market_prices) setPrices(prev => ({ ...prev, ...data.market_prices }));
            if (data.logged_in === true && viewRef.current === 'login') {
              _setView('dashboard');
            }
            break;
          case 'account_update':
            setAccount(prev => {
              const oldBal = prev.balance || 0;
              const newBal = data.balance != null ? data.balance : oldBal;
              const diff = newBal - oldBal;
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
            setPrices(prev => ({ ...prev, ...data }));
            break;
          case 'orderbook':
            setOrderbook({ bids: data.bids || [], asks: data.asks || [] });
            break;
          case 'settings_updated': {
            const { symbol_settings: ss2, ...globalOnly2 } = data;
            setSettings(prev => ({ ...prev, ...globalOnly2 }));
            if (ss2) setSymbolSettings(ss2);
            break;
          }
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
          case 'indicators_push': {
            const sym = data.symbol;
            if (!sym) break;
            multiIndicatorsRef.current = { ...multiIndicatorsRef.current, [sym]: data };
            setMultiIndicators(prev => ({ ...prev, [sym]: data }));
            if (sym === activeSymRef.current) setIndicators(data);
            // 信号触发时记录到日志（节流：同币种同方向5s内只记一次，余额<5U时不刷）
            const cur = data.current_signal || {};
            const fired = cur.side && cur.side !== 'HOLD';
            if (fired && !data.has_position && (account.available || 0) >= 5) {
              const sigKey = `${sym}_${cur.side}`;
              const lastSigTime = window._sigLogTs || {};
              const now = Date.now();
              if (!lastSigTime[sigKey] || now - lastSigTime[sigKey] >= 5000) {
                window._sigLogTs = { ...lastSigTime, [sigKey]: now };
                const newText = `⚡ ${sym.replace('USDT','')} ${cur.side} 置信:${((cur.confidence||0)*100).toFixed(1)}%`;
                setLiveLog(prev => {
                  if (prev[0]?.text === newText) return prev;
                  return [{ ts: new Date().toLocaleTimeString(), text: newText, level: 'info' }, ...prev.slice(0, 49)];
                });
              }
            }
            break;
          }
          case 'signal_update':
            break;
          case 'log':
            setLiveLog(prev => {
              const newEntry = { ts: data.ts||new Date().toLocaleTimeString(), text: data.text||'', level: data.level||'info' };
              if (prev[0]?.text === newEntry.text) return prev; // 去重
              return [newEntry, ...prev.slice(0, 49)]; // 最多50条
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
        const r = await authFetch('/api/trading/logs?limit=500');
        if (r.ok) {
          const d = await r.json();
          setTradeLogs(d.logs || []);
          if (d.performance) setPerf(d.performance);
        }
      } catch {}
    };
    const fetch_settings = async () => {
      try {
        const r = await authFetch('/api/trading/status');
        if (r.ok) {
          const d = await r.json();
          if (d.settings) {
            const { symbol_settings: ss3, ...globalOnly3 } = d.settings;
            setSettings(p => ({ ...p, ...globalOnly3 }));
            if (ss3) setSymbolSettings(ss3);
          }
        }
      } catch {}
    };
    fetch_logs();
    fetch_settings(); // 恢复后端settings含symbol_settings
    // 拉取Telegram配置
    authFetch('/api/telegram/config').then(r=>r.json()).then(d=>{
      if(d.ok) setTgConfig(d);
    }).catch(()=>{});
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
      const r = await authFetch('/api/auth/login', {
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
        // 重连 WS 以携带 token，使后端能识别用户
        if (wsRef.current) { try { wsRef.current.close(); } catch {} }
        setTimeout(connectWS, 300);
        const addr = d.wallet ? `${d.wallet.slice(0,8)}...${d.wallet.slice(-4)}` : '';
        showToast(`✅ AsterDex 登录成功！${addr} 余额: $${(d.balance || 0).toFixed(2)} USDT`, 'success');
        // 延迟拉取后端状态，同步 isTrading（后端登录后自动启动HFT）
        setTimeout(async () => {
          try {
            const hr = await authFetch('/api/trading/status');
            const hd = await hr.json();
            if (hd.auto_trading) setIsTrading(true);
          } catch {}
        }, 1500);
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
  const [closeConfirm, setCloseConfirm] = useState(null); // {symbol, size, entry, mark, side, fee, pnl}

  const closePosition = async (symbol) => {
    // 找到持仓数据计算手续费
    const pos = account.positions?.find(p => p.symbol === symbol);
    if (pos) {
      const entry = Number(pos.entry_price) || 0;
      const mark  = Number(pos.mark_price)  || 0;
      const size  = Number(pos.size)        || 0;
      const FEE_RATE = 0.0005;
      const fee   = size * (entry + mark) * FEE_RATE;
      const isLong = pos.side === 'LONG';
      const gross = isLong ? (mark - entry) * size : (entry - mark) * size;
      const net   = gross - fee;
      setCloseConfirm({ symbol, size, entry, mark, side: pos.side, fee, gross, net });
    } else {
      // 无本地数据直接平
      _doClosePosition(symbol);
    }
  };

  const _doClosePosition = async (symbol) => {
    setCloseConfirm(null);
    try {
      const r = await authFetch('/api/trading/close_position', {
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
      const r = await authFetch('/api/trading/cancel_orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol }),
      });
      const d = await r.json();
      if (d.ok) showToast(`✅ 已撤销 ${symbol} 挂单`, 'success');
      else showToast(`撤单失败: ${JSON.stringify(d.result||'')}`, 'error');
    } catch (e) { showToast(`撤单请求失败: ${e.message}`, 'error'); }
  };

  const handleLogout = async () => {
    await authFetch('/api/auth/logout', { method: 'POST' });
    setAccount({ logged_in: false, balance: 0, available: 0, positions: [], open_orders: [] });
    setIsTrading(false);
    setTradeLogs([]);
    setPerf({ total_trades: 0, wins: 0, losses: 0, total_pnl: 0, daily_pnl: 0, win_rate: 0 });
    setIndicators(null);
    setMultiIndicators({});
    multiIndicatorsRef.current = {};
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
      const { symbol_settings: _drop2, ...globalOnly2 } = settings;
      const payload = { ...globalOnly2, symbol_settings: symbolSettings };
      const sr = await authFetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
      if (!sr.ok) { showToast('❌ 设置保存失败，请重试', 'error'); return; }
      const r = await authFetch('/api/trading/start', { method: 'POST' });
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
      await authFetch('/api/trading/stop', { method: 'POST' });
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
      const r = await authFetch('/api/trading/test_order', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ symbol: settings.symbol, side }),
      });
      const d = await r.json();
      if (d.ok) {
        showToast(`✅ 测试${side}单成功: ${JSON.stringify(d.result).slice(0,80)}`, 'success');
        setLiveLog(prev => [{ ts: new Date().toLocaleTimeString(), text: `[测试下单] ${side} ${settings.symbol} -> ${JSON.stringify(d.result).slice(0,60)}`, level:'info' }, ...prev.slice(0, 49)]);
      } else {
        showToast(`❌ 下单失败: ${d.error}`, 'error');
        setLiveLog(prev => [{ ts: new Date().toLocaleTimeString(), text: `[错误] ${d.error}`, level:'error' }, ...prev.slice(0, 49)]);
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
      const { symbol_settings: _drop, ...globalOnly } = settings;
      const payload = { ...globalOnly, symbol_settings: symbolSettings };
      const r = await authFetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) { showToast(`❌ 保存失败 (HTTP ${r.status})`, 'error'); return; }
      const d = await r.json();
      if (d.ok) {
        showToast('✅ 设置已保存', 'success');
        const activeSet = new Set(settings.active_symbols || []);
        setMultiIndicators(prev => {
          const next = {};
          Object.keys(prev).forEach(k => { if (activeSet.has(k)) next[k] = prev[k]; });
          return next;
        });
      } else {
        showToast(`❌ 保存失败: ${d.error || '未知错误'}`, 'error');
      }
    } catch (e) {
      console.error('saveSettings error', e);
      showToast(`❌ 保存失败: ${e.message || '网络错误'}`, 'error');
    }
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

      {/* 手动平仓二次确认弹窗 */}
      {closeConfirm && (
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.7)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:'#1a1a2e',border:'1px solid rgba(255,45,120,0.5)',borderRadius:10,padding:28,minWidth:320,maxWidth:420,boxShadow:'0 0 40px rgba(255,45,120,0.25)'}}>
            <div style={{fontSize:16,fontWeight:700,color:'#fff',marginBottom:16}}>⚠️ 确认手动平仓</div>
            <div style={{fontSize:13,color:'rgba(255,255,255,0.75)',lineHeight:2,marginBottom:16}}>
              <div>币种：<b style={{color:'var(--cyan)'}}>{closeConfirm.symbol}</b></div>
              <div>方向：<b style={{color: closeConfirm.side==='LONG' ? 'var(--green)' : 'var(--pink)'}}>{closeConfirm.side==='LONG' ? '▲ 做多' : '▼ 做空'}</b></div>
              <div>数量：<b>{closeConfirm.size}</b></div>
              <div>开仓价：<b>${Number(closeConfirm.entry).toLocaleString()}</b></div>
              <div>当前价：<b>${Number(closeConfirm.mark).toLocaleString()}</b></div>
              <hr style={{border:'none',borderTop:'1px solid rgba(255,255,255,0.1)',margin:'8px 0'}}/>
              <div>毛利润：<b style={{color: closeConfirm.gross >= 0 ? 'var(--green)' : 'var(--pink)'}}>{closeConfirm.gross >= 0 ? '+' : ''}{closeConfirm.gross.toFixed(4)} USDT</b></div>
              <div>手续费：<b style={{color:'var(--pink)'}}>-{closeConfirm.fee.toFixed(4)} USDT</b></div>
              <div style={{fontSize:15,marginTop:4}}>净利润：<b style={{color: closeConfirm.net >= 0 ? '#00ff88' : '#ff3b3b', fontSize:17}}>{closeConfirm.net >= 0 ? '+' : ''}{closeConfirm.net.toFixed(4)} USDT</b></div>
            </div>
            <div style={{display:'flex',gap:10,marginTop:8}}>
              <button onClick={() => _doClosePosition(closeConfirm.symbol)}
                style={{flex:1,padding:'10px 0',background:'rgba(255,45,120,0.15)',border:'1px solid rgba(255,45,120,0.6)',color:'var(--pink)',borderRadius:6,cursor:'pointer',fontWeight:700,fontSize:13}}>
                确认平仓
              </button>
              <button onClick={() => setCloseConfirm(null)}
                style={{flex:1,padding:'10px 0',background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.2)',color:'rgba(255,255,255,0.7)',borderRadius:6,cursor:'pointer',fontSize:13}}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 顶部栏 */}
      <div className="header">
        <div className="header-left">
          <h2>◈ ASTERDEX HFT</h2>
          <div className="header-divider" />
          <div className="header-status">
            <span className={`dot ${backendOk ? 'green' : 'red'}`} />
            <span className="status-label">{backendOk ? 'API' : 'OFFLINE'}</span>
            <span className={`dot ${wsConnected ? 'green' : 'yellow'}`} />
            <span className="status-label">{wsConnected ? 'WS' : 'SYNC'}</span>
            {isTrading && <span className="badge badge-trading">⚡ LIVE</span>}
            {account.logged_in && <span className="badge badge-live">● CONNECTED</span>}
          </div>
        </div>
        <div className="header-status">
          {btcPrice > 0 && (
            <span className="price-label">BTC <span style={{opacity:0.5,fontSize:10,fontWeight:400}}>$</span>{Number(btcPrice).toLocaleString()}</span>
          )}
          {account.logged_in && (
            <>
              <span style={{color:'var(--text-dim)',fontSize:11}}>余额</span>
              <span style={{color:'var(--cyan)',fontWeight:800,fontFamily:'monospace',fontSize:13,textShadow:'0 0 10px rgba(0,245,255,0.5)'}}>${(account.balance||0).toFixed(2)}</span>
              <span style={{color:'var(--text-dim)',fontSize:11}}>可用</span>
              <span style={{color:'var(--text)',fontWeight:700,fontFamily:'monospace',fontSize:12}}>${(account.available||0).toFixed(2)}</span>
            </>
          )}
        </div>
      </div>

      <div className="main-content">
        {/* 侧边导航 */}
        <div className="sidebar-left">
          {!account.logged_in ? (
            <button className="nav-btn active">🔐 登录</button>
          ) : (
            <>
              <div className="sidebar-section-title">导航</div>
              <button className={`nav-btn ${view === 'dashboard' ? 'active' : ''}`} onClick={() => setView('dashboard')}>
                <span>📊</span> 仪表盘
              </button>
              <button className={`nav-btn ${view === 'analytics' ? 'active' : ''}`} onClick={() => setView('analytics')}>
                <span>📈</span> 性能分析
              </button>
              <button className={`nav-btn ${view === 'chart' ? 'active' : ''}`} onClick={() => setView('chart')}>
                <span>📉</span> 行情图表
              </button>
              <button className={`nav-btn ${view === 'positions' ? 'active' : ''}`} onClick={() => setView('positions')}>
                <span>📋</span> 持仓/挂单
                {(account.positions?.length > 0) && (
                  <span style={{marginLeft:'auto',background:'var(--green-dim)',color:'var(--green)',borderRadius:10,padding:'1px 6px',fontSize:10,fontWeight:700}}>
                    {account.positions.length}
                  </span>
                )}
              </button>
              <button className={`nav-btn ${view === 'logs' ? 'active' : ''}`} onClick={() => setView('logs')}>
                <span>📝</span> 交易记录
              </button>
              <button className={`nav-btn ${view === 'settings' ? 'active' : ''}`} onClick={() => setView('settings')}>
                <span>⚙️</span> 策略设置
              </button>

              <hr />
              <div className="sidebar-section-title">账户</div>
              <div className="metrics">
                <div className="metric-item">
                  <span className="metric-label">余额</span>
                  <span className="metric-value green" style={{textShadow:'0 0 8px rgba(0,245,255,0.4)'}}>${(account.balance||0).toFixed(2)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">可用</span>
                  <span className="metric-value">${(account.available||0).toFixed(2)}</span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">占用</span>
                  <span className="metric-value yellow">${Math.max(0,(account.balance||0)-(account.available||0)).toFixed(2)}</span>
                </div>
              </div>

              <hr />
              <div className="sidebar-section-title">绩效</div>
              {(() => {
                const _closedLogs = tradeLogs.filter(t => t.side === 'CLOSE');
                const _lWins   = _closedLogs.filter(t => t.pnl > 0).length;
                const _lLosses = _closedLogs.filter(t => t.pnl < 0).length;
                const _lClosed = _closedLogs.length;
                const _lWinRate = _lClosed > 0 ? parseFloat((_lWins / _lClosed * 100).toFixed(1)) : 0;
                return (
              <div className="metrics">
                <div className="metric-item">
                  <span className="metric-label">今日</span>
                  <span className={`metric-value ${(perf.daily_pnl||0)>=0?'green':'red'}`}>
                    {(perf.daily_pnl||0)>=0?'+':''}{(perf.daily_pnl||0).toFixed(2)}U
                  </span>
                </div>
                <div className="metric-item">
                  <span className="metric-label">累计</span>
                  <span className={`metric-value ${(perf.total_pnl||0)>=0?'green':'red'}`}>
                    {(perf.total_pnl||0)>=0?'+':''}{(perf.total_pnl||0).toFixed(2)}U
                  </span>
                </div>
                <div className="metric-item" style={{flexDirection:'column',alignItems:'stretch',gap:4}}>
                  <div style={{display:'flex',justifyContent:'space-between'}}>
                    <span className="metric-label">胜率</span>
                    <span className={`metric-value ${_lWinRate>=55?'green':_lWinRate>=40?'yellow':'red'}`}>
                      {_lWinRate}%
                    </span>
                  </div>
                  <div style={{height:3,background:'var(--bg4)',borderRadius:2,overflow:'hidden'}}>
                    <div style={{
                      height:'100%',
                      width:`${Math.min(_lWinRate,100)}%`,
                      background:_lWinRate>=55?'var(--green)':_lWinRate>=40?'var(--yellow)':'var(--red)',
                      borderRadius:2,transition:'width .6s ease'
                    }}/>
                  </div>
                  <div style={{fontSize:9,color:'var(--text-dim)',textAlign:'right'}}>
                    {_lWins}W / {_lLosses}L / {_lClosed}平仓
                  </div>
                </div>
              </div>
                );
              })()}

              <hr />
              <div style={{padding:'0 4px 6px'}}>
                <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer"
                  style={{fontSize:10,color:'var(--blue)',textDecoration:'none',display:'block',padding:'4px 6px',borderRadius:4,transition:'background .15s'}}
                  onMouseEnter={e=>e.target.style.background='var(--blue-dim)'}
                  onMouseLeave={e=>e.target.style.background='transparent'}
                >↗ AsterDex Pro</a>
                <a href="https://www.asterdex.com/en/user-center/api" target="_blank" rel="noopener noreferrer"
                  style={{fontSize:10,color:'var(--text-dim)',textDecoration:'none',display:'block',padding:'4px 6px',borderRadius:4,transition:'background .15s'}}
                  onMouseEnter={e=>e.target.style.background='var(--bg3)'}
                  onMouseLeave={e=>e.target.style.background='transparent'}
                >↗ API 管理</a>
              </div>
              {isAdmin && (
                <button className={`nav-btn ${view === 'admin' ? 'active' : ''}`}
                  onClick={() => { _setView('admin'); loadAdminData('all'); }}
                  style={{marginTop:4,background: view==='admin' ? 'rgba(255,180,0,0.12)' : undefined, borderColor: view==='admin' ? 'rgba(255,180,0,0.4)' : undefined, color:'#ffb400'}}>
                  <span>🛡️</span> 管理后台
                </button>
              )}
              <button className="nav-btn danger" onClick={handleLogout}>🚪 退出登录</button>
            </>
          )}
        </div>

        {/* 主内容 */}
        <div className="content-area">

          {/* ── 账号认证页（注册/登录/激活）── */}
          {view === 'auth' && (
            <div className="login-view">
              <div className="login-card">
                <div style={{textAlign:'center',marginBottom:24}}>
                  <div style={{fontSize:48,marginBottom:8,filter:'drop-shadow(0 0 16px rgba(0,245,255,0.6))'}}>◈</div>
                  <h2 style={{background:'linear-gradient(135deg,var(--cyan),var(--purple))',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',fontSize:22,fontWeight:900,letterSpacing:3}}>ASTERDEX HFT</h2>
                  <p style={{color:'var(--text-mid)',fontSize:13,marginTop:6}}>云端全自动量化交易中心</p>
                </div>

                {/* Tab 切换 */}
                <div style={{display:'flex',gap:4,marginBottom:20,background:'rgba(255,255,255,0.04)',borderRadius:8,padding:4}}>
                  {[['login','登录'],['register','注册'],['activate','激活']].map(([k,label])=>(
                    <button key={k} onClick={()=>{setAuthView(k);setAuthError('');setAuthSuccess('');}}
                      style={{flex:1,padding:'7px 0',borderRadius:6,border:'none',cursor:'pointer',fontSize:13,fontWeight:600,
                        background: authView===k ? 'linear-gradient(135deg,var(--cyan),var(--purple))' : 'transparent',
                        color: authView===k ? '#000' : 'var(--text-mid)',transition:'all .2s'}}>
                      {label}
                    </button>
                  ))}
                </div>

                {authError && <div className="alert alert-error" style={{marginBottom:12}}>{authError}</div>}
                {authSuccess && <div className="alert alert-success" style={{marginBottom:12,background:'rgba(0,245,100,0.1)',border:'1px solid rgba(0,245,100,0.3)',color:'#00f564',borderRadius:8,padding:'10px 14px'}}>{authSuccess}</div>}

                {authView === 'login' && (
                  <div className="login-form">
                    <div className="form-group">
                      <label>用户名</label>
                      <input type="text" placeholder="您的用户名" value={authForm.username}
                        onChange={e=>setAuthForm(p=>({...p,username:e.target.value}))} autoComplete="username"/>
                    </div>
                    <div className="form-group">
                      <label>密码</label>
                      <input type="password" placeholder="登录密码" value={authForm.password}
                        onChange={e=>setAuthForm(p=>({...p,password:e.target.value}))} autoComplete="current-password"
                        onKeyDown={e=>e.key==='Enter'&&handlePasswordLogin()}/>
                    </div>
                    <button className="btn-primary btn-large" onClick={handlePasswordLogin} disabled={authLoading} style={{marginTop:8}}>
                      {authLoading ? '⏳ 登录中...' : '🔑 登录'}
                    </button>
                  </div>
                )}

                {authView === 'register' && (
                  <div className="login-form">
                    <div className="form-group">
                      <label>用户名</label>
                      <input type="text" placeholder="设置用户名（字母数字）" value={authForm.username}
                        onChange={e=>setAuthForm(p=>({...p,username:e.target.value}))} autoComplete="username"/>
                    </div>
                    <div className="form-group">
                      <label>邮箱</label>
                      <input type="email" placeholder="您的邮箱" value={authForm.email}
                        onChange={e=>setAuthForm(p=>({...p,email:e.target.value}))} autoComplete="email"/>
                    </div>
                    <div className="form-group">
                      <label>密码</label>
                      <input type="password" placeholder="设置密码（8位以上）" value={authForm.password}
                        onChange={e=>setAuthForm(p=>({...p,password:e.target.value}))} autoComplete="new-password"/>
                    </div>
                    <button className="btn-primary btn-large" onClick={handleRegister} disabled={authLoading} style={{marginTop:8}}>
                      {authLoading ? '⏳ 注册中...' : '📝 注册账号'}
                    </button>
                  </div>
                )}

                {/* ── 联系客服 ── */}
                <div style={{marginTop:20,padding:'12px 14px',background:'rgba(0,245,255,0.04)',border:'1px solid rgba(0,245,255,0.15)',borderRadius:8}}>
                  <div style={{fontSize:12,color:'var(--text-mid)',marginBottom:6,fontWeight:600}}>📞 客服备用微信beishen/ 获取授权码</div>
                  <div style={{display:'flex',flexDirection:'column',gap:6,fontSize:12}}>
                    <a href="https://t.me/zuyuvip" target="_blank" rel="noopener noreferrer"
                      style={{color:'var(--cyan)',textDecoration:'none',display:'flex',alignItems:'center',gap:6}}>
                      <span style={{fontSize:14}}>✈️</span> 点击联系telegram客服@zuyuvip
                    </a>
                    <div style={{color:'var(--text-dim)',fontSize:11,marginTop:2}}>如需授权码、技术支持或账号问题，请联系以上方式</div>
                  </div>
                </div>

                {authView === 'activate' && (
                  <div className="login-form">
                    <div className="form-group">
                      <label>用户名</label>
                      <input type="text" placeholder="您的用户名" value={authForm.username}
                        onChange={e=>setAuthForm(p=>({...p,username:e.target.value}))}/>
                    </div>
                    <div className="form-group">
                      <label>授权码</label>
                      <input type="text" placeholder="格式: XXXXX-XXXXX-XXXXX-XXXXX" value={authForm.license_code}
                        onChange={e=>setAuthForm(p=>({...p,license_code:e.target.value.toUpperCase()}))}
                        style={{letterSpacing:2,fontFamily:'monospace'}}/>
                      <small style={{color:'var(--text-dim)',fontSize:11}}>联系管理员获取授权码</small>
                    </div>
                    <button className="btn-primary btn-large" onClick={handleActivate} disabled={authLoading} style={{marginTop:8}}>
                      {authLoading ? '⏳ 激活中...' : '🔓 激活账号'}
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* ── 私钥登录页 ── */}
          {view === 'login' && (
            <div className="login-view">
              <div className="login-card">
                <div style={{textAlign:'center',marginBottom:20}}>
                  <div style={{fontSize:48,marginBottom:8,filter:'drop-shadow(0 0 16px rgba(0,245,255,0.6))'}}>◈</div>
                  <h2 style={{background:'linear-gradient(135deg,var(--cyan),var(--purple))',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',fontSize:22,fontWeight:900,letterSpacing:3}}>ASTERDEX HFT</h2>
                  <p style={{color:'var(--text-mid)',fontSize:13,marginTop:6,letterSpacing:'0.5px'}}>连接 AsterDex 全自动高频交易</p>
                </div>

                {authUser && (
                  <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',background:'rgba(0,245,255,0.06)',border:'1px solid rgba(0,245,255,0.15)',borderRadius:8,padding:'8px 12px',marginBottom:14}}>
                    <span style={{color:'var(--cyan)',fontSize:13}}>👤 {authUser}</span>
                    <button onClick={handleAccountLogout} style={{background:'none',border:'none',color:'var(--text-dim)',cursor:'pointer',fontSize:12}}>退出账号</button>
                  </div>
                )}

                <div className="alert alert-info" style={{marginBottom:16,lineHeight:1.9}}>
                  <b>🔗 连接方式</b>：使用 AsterDex 专业 API V3 登录<br/>
                  <span style={{color:'var(--text-mid)',fontSize:12}}>主账户地址 + API钉包地址 + API钉包私钥 — 共三个字段</span>
                </div>

                <div className="login-form">
                  <div className="form-group">
                    <label style={{display:'flex',alignItems:'center',gap:6}}>
                      主账户地址 （主钉包）
                      {loginForm.user && <span style={{fontSize:10,color:'var(--cyan)',background:'rgba(0,245,255,0.1)',padding:'1px 6px',borderRadius:3}}>✓ 已自动填入</span>}
                    </label>
                    <input
                      type="text"
                      placeholder="您登录 AsterDex 时使用的主钉包地址"
                      value={loginForm.user}
                      onChange={e => setLoginForm(p => ({ ...p, user: e.target.value }))}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    <small style={{color:'var(--text-dim)',fontSize:11}}>即页面右上角显示的 0x6c...1B46 完整地址</small>
                  </div>
                  <div className="form-group">
                    <label style={{display:'flex',alignItems:'center',gap:6}}>
                      API 钉包地址 （Signer）
                      {loginForm.signer && <span style={{fontSize:10,color:'var(--cyan)',background:'rgba(0,245,255,0.1)',padding:'1px 6px',borderRadius:3}}>✓ 已自动填入</span>}
                    </label>
                    <input
                      type="text"
                      placeholder="专业API 页面列表里的 API 钉包地址"
                      value={loginForm.signer}
                      onChange={e => setLoginForm(p => ({ ...p, signer: e.target.value }))}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    <small style={{color:'var(--text-dim)',fontSize:11}}>如 0xa60a3f2348cbed90ecb6b99a1c6d948323792914</small>
                  </div>
                  <div className="form-group">
                    <label style={{display:'flex',alignItems:'center',gap:6}}>
                      API 钉包私钥 （Private Key）
                      {loginForm.private_key && <span style={{fontSize:10,color:'var(--cyan)',background:'rgba(0,245,255,0.1)',padding:'1px 6px',borderRadius:3}}>✓ 已自动填入</span>}
                    </label>
                    <input
                      type="password"
                      placeholder="创建钉包时页面上显示的「确认保存」那一行私钥"
                      value={loginForm.private_key}
                      onChange={e => setLoginForm(p => ({ ...p, private_key: e.target.value }))}
                      autoComplete="off"
                    />
                    <small style={{color:'var(--text-dim)',fontSize:11}}>如 0xd135c54789bf761b5e8659...</small>
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

                <div style={{marginTop:16,textAlign:'center',fontSize:12,color:'var(--text-dim)'}}>
                  <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer" style={{color:'var(--text-mid)',textDecoration:'none'}}>
                    ↗ AsterDex
                  </a>
                  <span style={{margin:'0 10px'}}>|</span>
                  <a href="https://docs.asterdex.com/for-developers/aster-api/api-documentation" target="_blank" rel="noopener noreferrer" style={{color:'var(--text-mid)',textDecoration:'none'}}>
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

              {/* ── 顶部全宽：多币种信号总览 ── */}
              {(settings.active_symbols||['BTCUSDT']).length > 0 && (
                <div className="card" style={{padding:12}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                      <h3 style={{margin:0,fontSize:13}}>🌐 多币种信号总览</h3>
                      <span style={{fontSize:10,color:'var(--text-dim)',letterSpacing:'0.5px'}}>点击切换币种实时更新</span>
                    </div>
                    <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(160px,1fr))',gap:8}}>
                      {(settings.active_symbols||['BTCUSDT']).map(sym=>{
                        const ind = multiIndicators[sym] || {};
                        const symLabel = sym.replace('USDT','');
                        const symColors = {
                          BTC:'#f7931a',ETH:'#627eea',SOL:'#9945ff',BNB:'#f3ba2f',
                          ARB:'#12aaff',AVAX:'#e84142',DOGE:'#c2a633',XRP:'#346aa9',
                          ADA:'#0033ad',DOT:'#e6007a',LTC:'#bfbbbb',LINK:'#2a5ada',
                          UNI:'#ff007a',ATOM:'#2e3148',NEAR:'#00c08b',APT:'#2dd8a3',
                          SUI:'#6fbcf0',OP:'#ff0420',INJ:'#00b2ff',TIA:'#7b2bf9',
                          SEI:'#9b59b6',WIF:'#c084fc',FET:'#1a9aef',RNDR:'#e8442b',
                        };
                        const color = symColors[symLabel] || 'var(--cyan)';
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
                          <div key={sym} onClick={()=>switchActiveSym(sym)} style={{
                            padding:'8px 10px',borderRadius:6,cursor:'pointer',
                            border:`1px solid ${isActive?color:(hasp?'rgba(191,95,255,0.3)':fired?'rgba(0,245,255,0.3)':blocked?'rgba(255,230,0,0.2)':'rgba(0,245,255,0.06)')}`,
                            background:isActive?`${color}15`:'rgba(0,245,255,0.01)',
                            transition:'all .2s',
                          }}>
                            {/* 标题行 */}
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:5}}>
                              <span style={{fontWeight:800,color,fontSize:12,letterSpacing:1}}>{symLabel}</span>
                              {hasp
                                ? <span style={{fontSize:9,padding:'1px 5px',background:'rgba(191,95,255,0.12)',border:'1px solid rgba(191,95,255,0.4)',color:'var(--purple)',borderRadius:3}}>持仓</span>
                                : fired
                                  ? <span style={{fontSize:9,padding:'1px 5px',background:'rgba(0,245,255,0.1)',border:'1px solid rgba(0,245,255,0.4)',color:'var(--cyan)',borderRadius:3}}>下单</span>
                                  : blocked
                                    ? <span style={{fontSize:9,padding:'1px 5px',background:'rgba(255,230,0,0.08)',border:'1px solid rgba(255,230,0,0.35)',color:'var(--yellow)',borderRadius:3}}>过滤</span>
                                    : <span style={{fontSize:9,color:'var(--text-dim)'}}>待机</span>}
                            </div>
                            {/* 做多进度条 */}
                            <div style={{marginBottom:3}}>
                              <div style={{display:'flex',justifyContent:'space-between',fontSize:9,marginBottom:1}}>
                                <span style={{color:curSide==='BUY'?'var(--cyan)':'rgba(0,245,255,0.4)'}}>▲ {bullPct}%</span>
                                {curSide==='BUY' && <span style={{color:'var(--cyan)',fontSize:8}}>▶</span>}
                              </div>
                              <div style={{height:3,background:'rgba(0,245,255,0.06)',borderRadius:2,overflow:'hidden'}}>
                                <div style={{height:'100%',width:`${bullPct}%`,background:curSide==='BUY'?'var(--cyan)':'rgba(0,245,255,0.3)',borderRadius:2,transition:'width .4s'}}/>
                              </div>
                            </div>
                            {/* 做空进度条 */}
                            <div style={{marginBottom:4}}>
                              <div style={{display:'flex',justifyContent:'space-between',fontSize:9,marginBottom:1}}>
                                <span style={{color:curSide==='SELL'?'var(--pink)':'rgba(255,45,120,0.4)'}}>▼ {bearPct}%</span>
                                {curSide==='SELL' && <span style={{color:'var(--pink)',fontSize:8}}>▶</span>}
                              </div>
                              <div style={{height:3,background:'rgba(255,45,120,0.06)',borderRadius:2,overflow:'hidden'}}>
                                <div style={{height:'100%',width:`${bearPct}%`,background:curSide==='SELL'?'var(--pink)':'rgba(255,45,120,0.3)',borderRadius:2,transition:'width .4s'}}/>
                              </div>
                            </div>
                            {/* 底部信息 */}
                            <div style={{display:'flex',justifyContent:'space-between',fontSize:9,color:'var(--text-dim)'}}>
                              <span>ADX <b style={{color:adx>=25?'var(--cyan)':adx>=20?'var(--yellow)':'var(--pink)'}}>{adx.toFixed(0)}</b></span>
                              <span style={{color:ms==='trending'?'rgba(0,245,255,0.5)':'rgba(255,45,120,0.5)'}}>{ms==='trending'?'趋势':'震荡'}</span>
                              {px > 0 && <span style={{color:'var(--text-dim)',fontFamily:'monospace'}}>${Number(px).toLocaleString()}</span>}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

              {/* ── 主体：左主栏 + 右侧栏 ── */}
              <div className="dashboard-body">
                <div className="dashboard-left">
                  <div className="dashboard-mid">

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
                          <span style={{color:'var(--text-dim)',fontSize:10}}>挂单占比</span>
                          <span className="red">卖出 {sellPct}%</span>
                        </div>
                        <div style={{height:8,borderRadius:4,overflow:'hidden',display:'flex'}}>
                          <div style={{width:`${buyPct}%`,background:'var(--cyan)',transition:'width .4s',boxShadow:'0 0 4px var(--cyan)'}} />
                          <div style={{width:`${sellPct}%`,background:'var(--pink)',transition:'width .4s',boxShadow:'0 0 4px var(--pink)'}} />
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* HFT 控制卡片 */}
                <div className="card control-card" style={{minWidth:0}}>
                  <h3>⚡ HFT 自动交易</h3>

                  {/* 多币种启动提示 */}
                  <div style={{marginBottom:8,padding:'6px 8px',background:'rgba(0,245,255,0.03)',borderRadius:5,border:'1px solid rgba(0,245,255,0.12)',fontSize:11}}>
                    <div style={{color:'var(--cyan)',fontWeight:700,marginBottom:4,letterSpacing:'0.5px'}}>◈ 同时交易币种</div>
                    <div style={{display:'flex',gap:4,flexWrap:'wrap'}}>
                      {(settings.active_symbols||[settings.symbol]).map(sym=>(
                        <span key={sym} style={{padding:'1px 7px',borderRadius:3,background:'rgba(0,245,255,0.08)',border:'1px solid rgba(0,245,255,0.3)',color:'var(--cyan)',fontSize:10,fontWeight:700,textShadow:'0 0 6px rgba(0,245,255,0.3)'}}>
                          {sym.replace('USDT','')}
                        </span>
                      ))}
                    </div>
                    <div style={{color:'var(--text-dim)',fontSize:10,marginTop:2}}>每个币种独立最多1单，止盈/止损后自动下一单</div>
                  </div>

                  {/* 币种选择（只从已启用的里选详细视图） */}
                  <div style={{display:'flex',gap:4,marginBottom:8,flexWrap:'wrap'}}>
                    {(settings.active_symbols||['BTCUSDT']).map(sym=>{
                      const symColors={
                        BTCUSDT:'#f7931a',ETHUSDT:'#627eea',SOLUSDT:'#9945ff',BNBUSDT:'#f3ba2f',
                        ARBUSDT:'#12aaff',AVAXUSDT:'#e84142',DOGEUSDT:'#c2a633',XRPUSDT:'#346aa9',
                        ADAUSDT:'#0033ad',DOTUSDT:'#e6007a',LTCUSDT:'#bfbbbb',LINKUSDT:'#2a5ada',
                        UNIUSDT:'#ff007a',ATOMUSDT:'#2e3148',NEARUSDT:'#00c08b',APTUSDT:'#2dd8a3',
                        SUIUSDT:'#6fbcf0',OPUSDT:'#ff0420',INJUSDT:'#00b2ff',TIAUSDT:'#7b2bf9',
                        SEIUSDT:'#9b59b6',WIFUSDT:'#c084fc',FETUSDT:'#1a9aef',RENDERUSDT:'#e8442b',
                      };
                      const color=symColors[sym]||'var(--cyan)';
                      const isActive=activeSym===sym;
                      return (
                        <button key={sym}
                          onClick={()=>{switchActiveSym(sym);setSettings(p=>({...p,symbol:sym}));}}
                          style={{padding:'3px 10px',fontSize:11,borderRadius:4,border:`1px solid ${isActive?color:'rgba(0,245,255,0.12)'}`,
                            background:isActive?`${color}18`:'transparent',
                            color:isActive?color:'var(--text-mid)',cursor:'pointer',fontWeight:isActive?700:400,transition:'all .15s'}}
                        >{sym.replace('USDT','')}</button>
                      );
                    })}
                  </div>

                  <div className="hft-status">
                    <div className={`status-indicator ${isTrading ? 'active' : 'idle'}`}>
                      {isTrading ? '⚡ 运行中' : '⏸ 已停止'}
                    </div>
                    <div style={{fontSize:11,color:'var(--cyan)',marginTop:4,letterSpacing:'0.5px'}}>◉ 实盘 · AsterDex · {settings.symbol}</div>
                    <div style={{fontSize:10,marginTop:3,color:settings.hft_mode==='turbo'?'var(--pink)':settings.hft_mode==='aggressive'?'#ff9800':settings.hft_mode==='conservative'?'var(--cyan)':'var(--yellow)',letterSpacing:'0.5px'}}>
                      {settings.hft_mode==='turbo'?'🚀 Turbo极速':settings.hft_mode==='aggressive'?'⚡ 激进模式':settings.hft_mode==='conservative'?'🛡️ 精准模式':'⚖️ 平衡模式'}
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

                    const borderColor = buyReady?'rgba(0,245,255,0.5)': sellReady?'rgba(255,45,120,0.5)': buyBlocked?'rgba(255,230,0,0.3)': sellBlocked?'rgba(255,45,120,0.2)':'rgba(0,245,255,0.08)';

                    return (
                      <div style={{background:'rgba(0,245,255,0.01)',border:`1px solid ${borderColor}`,borderRadius:6,padding:'10px 12px',margin:'6px 0',boxShadow:buyReady||sellReady?`0 0 20px ${borderColor}`:'none',transition:'all .3s'}}>

                        {/* 顶栏：策略名 + 状态 */}
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                          <span style={{fontSize:10,color:'var(--text-dim)',letterSpacing:'0.5px'}}><b style={{color:'var(--cyan)'}}>CRYPTO_HFT</b> · {indicators.bars||0}K</span>
                          {indicators.has_position
                            ? <span style={{fontSize:10,padding:'2px 8px',background:'rgba(191,95,255,0.12)',border:'1px solid rgba(191,95,255,0.5)',color:'var(--purple)',borderRadius:3,fontWeight:700,letterSpacing:'0.5px'}}>◈ 持仓中</span>
                            : fired
                              ? <span style={{fontSize:10,padding:'2px 8px',background:'rgba(0,245,255,0.1)',border:'1px solid rgba(0,245,255,0.6)',color:'var(--cyan)',borderRadius:3,fontWeight:700,letterSpacing:'0.5px',boxShadow:'0 0 10px rgba(0,245,255,0.2)'}}>▶ 下单触发</span>
                              : (buyBlocked||sellBlocked)
                                ? <span style={{fontSize:10,padding:'2px 8px',background:'rgba(255,230,0,0.08)',border:'1px solid rgba(255,230,0,0.4)',color:'var(--yellow)',borderRadius:3,fontWeight:700,letterSpacing:'0.5px'}}>⚠ 过滤</span>
                                : isTrading
                                  ? <span style={{fontSize:10,color:'var(--text-dim)',letterSpacing:'0.5px'}}>⏳ 扫描中</span>
                                  : <span style={{fontSize:10,color:'var(--text-dim)'}}>待启动</span>}
                        </div>

                        {/* 做多区 */}
                        <div style={{marginBottom:6}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:2}}>
                            <span style={{fontSize:11,color:'var(--cyan)',fontWeight:700,letterSpacing:'0.5px'}}>▲ BUY</span>
                            <span style={{fontSize:11,fontWeight:700,color:buyReady?'var(--cyan)':buyBlocked?'var(--yellow)':'var(--text-dim)'}}>
                              {bullPct}%
                              {buyReady
                                ? <span style={{fontSize:10,marginLeft:4,color:'var(--cyan)',textShadow:'0 0 6px rgba(0,245,255,0.8)'}}>▶ 触发!</span>
                                : buyBlocked && buyGap > 0
                                  ? <span style={{fontSize:10,marginLeft:4,color:'var(--yellow)'}}>差{buyGap}%</span>
                                  : buyBlocked
                                    ? <span style={{fontSize:10,marginLeft:4,color:'var(--yellow)'}}>过滤</span>
                                    : null}
                            </span>
                          </div>
                          <div style={{height:6,background:'rgba(0,245,255,0.06)',borderRadius:3,overflow:'hidden',position:'relative'}}>
                            <div style={{height:'100%',width:`${bullPct}%`,background:buyReady?'var(--cyan)':'rgba(0,245,255,0.35)',transition:'width .5s',borderRadius:3,boxShadow:buyReady?'0 0 8px var(--cyan)':'none'}}/>
                            <div style={{position:'absolute',top:0,left:`${thresh}%`,width:1,height:'100%',background:'var(--yellow)',opacity:0.8}}/>
                          </div>
                        </div>

                        {/* 做空区 */}
                        <div style={{marginBottom:8}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:2}}>
                            <span style={{fontSize:11,color:'var(--pink)',fontWeight:700,letterSpacing:'0.5px'}}>▼ SELL</span>
                            <span style={{fontSize:11,fontWeight:700,color:sellReady?'var(--pink)':sellBlocked?'var(--yellow)':'var(--text-dim)'}}>
                              {bearPct}%
                              {sellReady
                                ? <span style={{fontSize:10,marginLeft:4,color:'var(--pink)',textShadow:'0 0 6px rgba(255,45,120,0.8)'}}>▶ 触发!</span>
                                : sellBlocked && sellGap > 0
                                  ? <span style={{fontSize:10,marginLeft:4,color:'var(--yellow)'}}>差{sellGap}%</span>
                                  : sellBlocked
                                    ? <span style={{fontSize:10,marginLeft:4,color:'var(--yellow)'}}>过滤</span>
                                    : null}
                            </span>
                          </div>
                          <div style={{height:6,background:'rgba(255,45,120,0.06)',borderRadius:3,overflow:'hidden',position:'relative'}}>
                            <div style={{height:'100%',width:`${bearPct}%`,background:sellReady?'var(--pink)':'rgba(255,45,120,0.35)',transition:'width .5s',borderRadius:3,boxShadow:sellReady?'0 0 8px var(--pink)':'none'}}/>
                            <div style={{position:'absolute',top:0,left:`${thresh}%`,width:1,height:'100%',background:'var(--yellow)',opacity:0.8}}/>
                          </div>
                        </div>

                        {/* 市场状态栏 */}
                        {(() => {
                          const ms = indicators.market_state;
                          const adx = indicators.adx || 0;
                          const rr  = indicators.reward_risk || 0;
                          const isTrending = ms === 'trending';
                          return (
                            <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:6,padding:'4px 6px',background:isTrending?'rgba(0,245,255,0.04)':'rgba(255,45,120,0.04)',borderRadius:4,border:`1px solid ${isTrending?'rgba(0,245,255,0.18)':'rgba(255,45,120,0.18)'}`}}>
                              <span style={{fontSize:10,fontWeight:700,color:isTrending?'var(--cyan)':'var(--pink)',letterSpacing:'0.5px'}}>
                                {isTrending ? '◈ 趋势行情' : '⚠ 震荡降权'}
                              </span>
                              <span style={{fontSize:10,color:'var(--text-mid)'}}>ADX <b style={{color:adx>=20?'var(--cyan)':adx>=10?'var(--yellow)':'var(--pink)'}}>{adx.toFixed(1)}</b></span>
                              <span style={{fontSize:10,color:'var(--text-mid)'}}>盈亏比 <b style={{color:rr>=1.8?'var(--cyan)':'var(--pink)'}}>{rr.toFixed(2)}x</b></span>
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
                              <div style={{padding:'4px 8px',background:'rgba(255,230,0,0.06)',border:'1px solid rgba(255,230,0,0.25)',borderRadius:4,marginBottom:4,fontSize:10,color:'var(--yellow)',letterSpacing:'0.3px'}}>
                                ⚠ 未下单：{blockReason}
                              </div>
                              <div style={{padding:'4px 8px',background:'rgba(0,245,255,0.02)',borderRadius:4,marginBottom:6,fontSize:10,display:'flex',flexWrap:'wrap',gap:8,alignItems:'center',border:'1px solid rgba(0,245,255,0.08)'}}>
                                <span style={{color:'var(--text-dim)'}}>生效参数{hasCustParam?<span style={{color:'var(--yellow)',marginLeft:3}}>(独立)</span>:''}：</span>
                                <span>止损 <b style={{color:'var(--pink)'}}>{effSl.toFixed(2)}%</b></span>
                                <span>止盈 <b style={{color:'var(--cyan)'}}>{effTp.toFixed(2)}%</b></span>
                                <span>盈亏比 <b style={{color:rrOk?'var(--cyan)':'var(--pink)'}}>{effRr}x</b> <span style={{color:'var(--text-dim)'}}>需≥{modeRr}x</span></span>
                                {hasCustParam && (
                                  <button onClick={async()=>{
                                    const ns = {...symbolSettings}; delete ns[symKey];
                                    setSymbolSettings(ns);
                                    await authFetch('/api/settings/symbol',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:symKey,params:{stop_loss_pct:settings.stop_loss_pct,take_profit_pct:settings.take_profit_pct,leverage:settings.leverage,min_confidence:settings.min_confidence}})});
                                    showToast(`✅ 已重置 ${symKey} 为全局参数`,'success');
                                  }} style={{fontSize:9,padding:'2px 6px',background:'rgba(255,45,120,0.1)',border:'1px solid rgba(255,45,120,0.35)',color:'var(--pink)',borderRadius:3,cursor:'pointer'}}>
                                    🔄 重置为全局参数
                                  </button>
                                )}
                              </div>
                            </>
                          );
                        })()}

                        {/* 快速指标行 */}
                        <div style={{display:'flex',gap:10,fontSize:11,color:'var(--text-mid)',flexWrap:'wrap',paddingTop:6,borderTop:'1px solid rgba(0,245,255,0.08)'}}>
                          <span>RSI <b style={{color:indicators.rsi<35?'var(--cyan)':indicators.rsi>65?'var(--pink)':'var(--text)'}}>{Number(indicators.rsi||0).toFixed(1)}</b></span>
                          <span>MACD <b style={{color:(indicators.macd?.hist||0)>0?'var(--cyan)':'var(--pink)'}}>{Number(indicators.macd?.hist||0).toFixed(4)}</b></span>
                          <span>OBI <b style={{color:(indicators.ob_imbalance||0)>0?'var(--cyan)':'var(--pink)'}}>{((indicators.ob_imbalance||0)*100).toFixed(1)}%</b></span>
                          <span>ST <b style={{color:indicators.supertrend==='up'?'var(--cyan)':indicators.supertrend==='down'?'var(--pink)':'var(--text-mid)'}}>{indicators.supertrend||'--'}</b></span>
                        </div>

                        {/* 7维度评分条（可折叠）*/}
                        {Object.keys(scores).filter(k=>!k.startsWith('_')).length > 0 && (
                          <div style={{marginTop:8,paddingTop:6,borderTop:'1px solid rgba(0,245,255,0.08)'}}>
                            <div onClick={()=>setShowScores(p=>!p)}
                              style={{fontSize:9,color:'var(--text-dim)',marginBottom:4,letterSpacing:'1px',textTransform:'uppercase',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                              <span>◈ 7维度评分</span>
                              <span style={{fontSize:10}}>{showScores?'▲':'▼'}</span>
                            </div>
                            {showScores && [
                              ['supertrend','Supertrend',0.22],
                              ['ema','EMA三线',0.20],
                              ['macd','MACD',0.15],
                              ['rsi','RSI',0.15],
                              ['vwap','VWAP',0.12],
                              ['obi','OBI',0.11],
                              ['momentum','动量',0.05],
                            ].map(([key,label,wt])=>{
                              const v = scores[key] || 0;
                              const bar = Math.abs(v) * 50;
                              const isPos = v >= 0;
                              return (
                                <div key={key} style={{display:'flex',alignItems:'center',gap:5,marginBottom:2}}>
                                  <span style={{width:52,fontSize:9,color:'var(--text-dim)',flexShrink:0}}>{label}</span>
                                  <div style={{flex:1,height:4,background:'rgba(0,245,255,0.04)',borderRadius:2,position:'relative'}}>
                                    <div style={{position:'absolute',left:'50%',top:0,width:1,height:'100%',background:'rgba(0,245,255,0.15)'}}/>
                                    <div style={{
                                      position:'absolute',height:'100%',
                                      width:`${bar}%`,
                                      background:isPos?'var(--cyan)':'var(--pink)',
                                      boxShadow:isPos?'0 0 4px var(--cyan)':'0 0 4px var(--pink)',
                                      left:isPos?'50%':undefined,
                                      right:isPos?undefined:`${50-bar}%`,
                                      borderRadius:2,transition:'width .4s',
                                    }}/>
                                  </div>
                                  <span style={{width:30,fontSize:9,color:isPos&&v!==0?'var(--cyan)':v!==0?'var(--pink)':'var(--text-dim)',textAlign:'right',flexShrink:0}}>
                                    {v>0?'+':''}{v.toFixed(2)}
                                  </span>
                                  <span style={{width:24,fontSize:8,color:'var(--text-dim)',flexShrink:0}}>{(wt*100).toFixed(0)}%</span>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    );
                  })()}
                  {!indicators && (
                    <div style={{fontSize:11,color:'var(--text-dim)',textAlign:'center',padding:'12px 0',letterSpacing:'0.5px'}}>⏳ 等待K线数据...</div>
                  )}

                  <div className="control-btns">
                    <button className="btn-success btn-large" onClick={startTrading}
                      disabled={isTrading||tradingLoading||!account.logged_in||!backendOk}>
                      {tradingLoading?'⏳ 启动中...':'🚀 启动 HFT'}
                    </button>
                    <button className="btn-danger" onClick={stopTrading} disabled={!isTrading}>⏹️ 停止</button>
                    <button onClick={async()=>{
                      try{
                        const r = await authFetch('/api/trading/reset_daily',{method:'POST'});
                        const d = await r.json();
                        showToast(`🔄 ${d.message}`,'warn');
                      }catch(e){ showToast('重置失败: '+e.message,'error'); }
                    }} disabled={!account.logged_in}
                    title="手动重置今日亏损计数，解除日亏损熔断后可重新启动"
                    style={{fontSize:11,padding:'4px 8px',background:'rgba(255,165,0,0.12)',border:'1px solid rgba(255,165,0,0.4)',color:'#ffa500',borderRadius:4,cursor:'pointer',whiteSpace:'nowrap'}}>
                      🔄 重置日亏损
                    </button>
                  </div>
                  {perf.daily_pnl < -( settings.max_daily_loss_usd||50) && (
                    <div style={{marginTop:6,padding:'4px 8px',background:'rgba(255,45,120,0.1)',border:'1px solid rgba(255,45,120,0.4)',borderRadius:4,fontSize:11,color:'var(--pink)'}}>
                      ⛔ 日亏损熔断中 ${Math.abs(perf.daily_pnl||0).toFixed(2)} / 限额${settings.max_daily_loss_usd||50} — 点「重置日亏损」后可重新启动
                    </div>
                  )}

                  {/* 测试下单 */}
                  <div style={{marginTop:8,padding:'8px',background:'rgba(0,245,255,0.02)',border:'1px dashed rgba(0,245,255,0.15)',borderRadius:6}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                      <span style={{fontSize:10,color:'var(--text-mid)',letterSpacing:'0.5px'}}>◈ 测试下单</span>
                      <span style={{fontSize:12,color:'var(--yellow)',fontWeight:700}}>
                        现价 ${curPrice>0?Number(curPrice).toLocaleString():'--'}
                      </span>
                    </div>
                    <div style={{display:'flex',gap:6}}>
                      <button onClick={()=>testOrder('BUY')} disabled={testOrdering||!account.logged_in||curPrice<=0}
                        style={{flex:1,padding:'7px 4px',background:'rgba(0,245,255,0.08)',border:'1px solid rgba(0,245,255,0.4)',color:'var(--cyan)',borderRadius:4,cursor:'pointer',fontSize:12,lineHeight:1.3,letterSpacing:'0.5px',boxShadow:'0 0 8px rgba(0,245,255,0.1)'}}>
                        {testOrdering?'⏳...':<>▲ BUY<br/><span style={{fontSize:10,color:'var(--cyan)',opacity:0.7}}>@ ${curPrice>0?Number(curPrice).toLocaleString():'--'}</span></>}
                      </button>
                      <button onClick={()=>testOrder('SELL')} disabled={testOrdering||!account.logged_in||curPrice<=0}
                        style={{flex:1,padding:'7px 4px',background:'rgba(255,45,120,0.08)',border:'1px solid rgba(255,45,120,0.4)',color:'var(--pink)',borderRadius:4,cursor:'pointer',fontSize:12,lineHeight:1.3,letterSpacing:'0.5px',boxShadow:'0 0 8px rgba(255,45,120,0.1)'}}>
                        {testOrdering?'⏳...':<>▼ SELL<br/><span style={{fontSize:10,color:'var(--pink)',opacity:0.7}}>@ ${curPrice>0?Number(curPrice).toLocaleString():'--'}</span></>}
                      </button>
                    </div>
                  </div>

                  <div className="mini-stats">
                    <div>策略: <b style={{color:'var(--cyan)'}}>{indicators?.strategy || 'crypto_hft'}</b></div>
                    <div>交易数: <b>{perf.total_trades}</b></div>
                    <div>胜率: <b className={parseFloat(perf.win_rate)>=70?'green':''}>{perf.win_rate}%</b></div>
                    <div>盈亏: <b className={perf.total_pnl>=0?'green':'red'}>{perf.total_pnl>=0?'+':''}{(perf.total_pnl||0).toFixed(2)}</b></div>
                  </div>
                </div>

                  </div>{/* /dashboard-mid 结束 */}


                </div>{/* /dashboard-left */}

                {/* ── 右侧栏：账户 + 实时日志 + 每日图表 ── */}
                <div className="dashboard-right">

                  {/* 账户卡片 */}
                  <div className="card account-card">
                    <h3>💼 账户概览 <span className="badge badge-live" style={{marginLeft:8}}>实盘</span></h3>
                    <div className="stat-grid" style={{gridTemplateColumns:'1fr 1fr',gap:8}}>
                      <div className="stat">
                        <span className="stat-label">余额</span>
                        <span style={{display:'flex',alignItems:'center',gap:4}}>
                          <span className="stat-val green">${(account.balance||0).toFixed(2)}</span>
                          {balanceDelta !== 0 && (
                            <span style={{fontSize:10,fontWeight:700,color:balanceDelta>0?'var(--cyan)':'var(--pink)',animation:'fadeInUp .3s ease'}}>
                              {balanceDelta>0?'▲':'▼'}{Math.abs(balanceDelta).toFixed(2)}
                            </span>
                          )}
                        </span>
                      </div>
                      <div className="stat"><span className="stat-label">可用</span><span className="stat-val">${(account.available||0).toFixed(2)}</span></div>
                      <div className="stat"><span className="stat-label">占用</span><span className="stat-val yellow">${Math.max(0,(account.balance||0)-(account.available||0)).toFixed(2)}</span></div>
                      <div className="stat"><span className="stat-label">持仓数</span><span className="stat-val">{account.positions?.length||0}</span></div>
                      <div className="stat">
                        <span className="stat-label">今日盈亏</span>
                        <span className={`stat-val ${(perf.daily_pnl||0)>=0?'green':'red'}`}>
                          {(perf.daily_pnl||0)>=0?'+':''}{(perf.daily_pnl||0).toFixed(2)}
                          <span style={{fontSize:10,marginLeft:3,opacity:0.7}}>{perf.daily_pnl_pct !== undefined ? `(${perf.daily_pnl_pct>0?'+':''}${perf.daily_pnl_pct}%)` : ''}</span>
                        </span>
                      </div>
                      <div className="stat">
                        <span className="stat-label">累计盈亏</span>
                        <span className={`stat-val ${(perf.total_pnl||0)>=0?'green':'red'}`}>
                          {(perf.total_pnl||0)>=0?'+':''}{(perf.total_pnl||0).toFixed(2)}
                          <span style={{fontSize:10,marginLeft:3,opacity:0.7}}>{perf.total_pnl_pct !== undefined ? `(${perf.total_pnl_pct>0?'+':''}${perf.total_pnl_pct}%)` : ''}</span>
                        </span>
                      </div>
                    </div>
                    <div style={{marginTop:8,display:'flex',gap:8}}>
                      <a href="https://www.asterdex.com/en/trade/pro/futures/BTCUSDT" target="_blank" rel="noopener noreferrer" style={{color:'var(--purple)',textDecoration:'none',fontSize:10,padding:'2px 8px',border:'1px solid rgba(191,95,255,0.3)',borderRadius:3}} onMouseEnter={e=>e.target.style.background='rgba(191,95,255,0.1)'} onMouseLeave={e=>e.target.style.background='transparent'}>↗ AsterDex</a>
                      <a href="https://www.asterdex.com/en/user-center/api" target="_blank" rel="noopener noreferrer" style={{color:'var(--text-dim)',textDecoration:'none',fontSize:10,padding:'2px 8px',border:'1px solid rgba(0,245,255,0.1)',borderRadius:3}}>↗ API</a>
                    </div>
                  </div>

                  {/* 实时日志面板 */}
              <div className="card" style={{padding:'10px 12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
                  <div style={{display:'flex',alignItems:'center',gap:8}}>
                    <span style={{fontSize:12,fontWeight:700,color:'var(--text-mid)',letterSpacing:'0.5px'}}>◈ 实时日志</span>
                    <span style={{fontSize:10,padding:'1px 6px',background:'rgba(0,245,255,0.04)',border:'1px solid rgba(0,245,255,0.1)',borderRadius:3,color:'var(--text-dim)'}}>
                      {liveLog.length}/50
                    </span>
                    {isTrading && <span style={{width:6,height:6,borderRadius:'50%',background:'var(--cyan)',display:'inline-block',boxShadow:'0 0 6px var(--cyan)',animation:'pulse 1.5s infinite'}} />}
                  </div>
                  <div style={{display:'flex',alignItems:'center',gap:6}}>
                    <label style={{display:'flex',alignItems:'center',gap:4,fontSize:10,color:'var(--text-dim)',cursor:'pointer'}}>
                      <input type="checkbox" checked={logAutoClean} onChange={e=>setLogAutoClean(e.target.checked)}
                        style={{width:11,height:11,cursor:'pointer'}} />
                      5分钟自动清空
                    </label>
                    <button onClick={()=>setLiveLog([])} style={{
                      fontSize:10,padding:'2px 8px',background:'transparent',
                      border:'1px solid rgba(0,245,255,0.1)',color:'var(--text-dim)',borderRadius:3,cursor:'pointer'
                    }}>清空</button>
                  </div>
                </div>
                <div style={{height:160,overflowY:'auto',fontFamily:'monospace',fontSize:11,lineHeight:1.75,display:'flex',flexDirection:'column',gap:0}}>
                  {liveLog.length===0 && (
                    <div style={{color:'var(--text-dim)',padding:'30px 0',textAlign:'center',fontSize:11,letterSpacing:'0.5px'}}>
                      {isTrading ? '⏳ 等待交易信号...' : '▷ 启动 HFT 后显示实时日志'}
                    </div>
                  )}
                  {liveLog.map((l,i)=>{
                    const lv = l.level || 'info';
                    const textColor = lv==='error'?'var(--red)':lv==='warn'?'var(--yellow)':lv==='debug'?'var(--text-dim)':
                      l.text.includes('✅')||l.text.includes('止盈')||l.text.includes('⚡开仓')?'var(--green)':
                      l.text.includes('BUY')||l.text.includes('做多')?'#40d090':
                      l.text.includes('SELL')||l.text.includes('做空')?'#ff7070':'var(--text-mid)';
                    return (
                      <div key={i} style={{
                        display:'flex',gap:8,padding:'2px 4px',borderRadius:3,
                        background: i===0 ? `${textColor}12` : 'transparent',
                        borderLeft: i===0 ? `2px solid ${textColor}` : '2px solid transparent',
                      }}>
                        <span style={{color:'var(--text-dim)',flexShrink:0,fontSize:10,lineHeight:'1.7',fontFamily:'monospace'}}>{l.ts}</span>
                        <span style={{color:textColor,wordBreak:'break-word',fontSize:11}}>{l.text}</span>
                      </div>
                    );
                  })}
                </div>
              </div>

                  {/* 每日盈亏历史 */}
              {(() => {
                const dh = perf.daily_history || {};
                const days = Object.keys(dh).sort().slice(-14);
                if (days.length === 0) return null;
                const barData = days.map(d => ({
                  date: d.slice(5),
                  pnl:  parseFloat((dh[d].pnl || 0).toFixed(4)),
                  trades: dh[d].trades || 0,
                  wr: dh[d].trades > 0 ? Math.round((dh[d].wins||0)/dh[d].trades*100) : 0,
                }));
                return (
                  <div className="card" style={{padding:'12px 0 12px 12px'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10,paddingRight:12}}>
                      <h3 style={{margin:0,fontSize:13}}>📅 每日盈亏（最近{days.length}天）</h3>
                      <div style={{display:'flex',gap:12,fontSize:11}}>
                        <span style={{color:'var(--cyan)'}}>盈 {days.filter(d=>(dh[d].pnl||0)>0).length}天</span>
                        <span style={{color:'var(--pink)'}}>亏 {days.filter(d=>(dh[d].pnl||0)<0).length}天</span>
                      </div>
                    </div>
                    <ResponsiveContainer width="100%" height={100}>
                      <BarChart data={barData} margin={{top:2,right:16,left:0,bottom:0}} barCategoryGap="20%">
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,245,255,0.06)" vertical={false}/>
                        <XAxis dataKey="date" tick={{fill:'var(--text-dim)',fontSize:9}} tickLine={false} axisLine={false}/>
                        <YAxis hide/>
                        <Tooltip
                          contentStyle={{background:'var(--bg2)',border:'1px solid rgba(0,245,255,0.2)',borderRadius:6,fontSize:11}}
                          formatter={(v,n,p)=>[`${v>=0?'+':''}${v.toFixed(4)} U | ${p.payload.trades}笔 胜率${p.payload.wr}%`,'当日盈亏']}
                        />
                        <ReferenceLine y={0} stroke="rgba(0,245,255,0.15)"/>
                        <Bar dataKey="pnl" radius={[2,2,0,0]}
                          fill="var(--cyan)"
                          label={false}
                          isAnimationActive={false}
                          shape={(props) => {
                            const {x,y,width,height,value} = props;
                            const color = value >= 0 ? 'var(--cyan)' : 'var(--pink)';
                            return <rect x={x} y={y} width={width} height={Math.abs(height)||1} fill={color} rx={2} opacity={0.85}/>;
                          }}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                    <div style={{display:'flex',justifyContent:'space-between',marginTop:6,fontSize:10,color:'var(--text-dim)',borderTop:'1px solid rgba(0,245,255,0.08)',paddingTop:6,paddingRight:12}}>
                      <span>今日: <b style={{color:(perf.daily_pnl||0)>=0?'var(--cyan)':'var(--pink)'}}>{(perf.daily_pnl||0)>=0?'+':''}{(perf.daily_pnl||0).toFixed(4)} ({(perf.daily_pnl_pct||0).toFixed(2)}%)</b></span>
                      <span>累计: <b style={{color:(perf.total_pnl||0)>=0?'var(--cyan)':'var(--pink)'}}>{(perf.total_pnl||0)>=0?'+':''}{(perf.total_pnl||0).toFixed(2)} ({(perf.total_pnl_pct||0).toFixed(2)}%)</b></span>
                    </div>
                  </div>
                );
              })()}

                </div>{/* /dashboard-right */}
              </div>{/* /dashboard-body */}

              {/* ── 底部全宽：最近交易 ── */}
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

          {/* ── 性能分析页 ── */}
          {view === 'analytics' && account.logged_in && (() => {
            const closed = tradeLogs.filter(t => t.side === 'CLOSE' && t.pnl !== undefined);
            const totalTrades = closed.length;
            const winTrades = closed.filter(t => t.pnl > 0).length;
            const loseTrades = closed.filter(t => t.pnl < 0).length;
            const winRate = totalTrades > 0 ? (winTrades / totalTrades * 100).toFixed(1) : 0;
            const avgPnl = totalTrades > 0 ? (closed.reduce((s, t) => s + (t.pnl || 0), 0) / totalTrades).toFixed(4) : 0;
            const maxProfit = closed.length > 0 ? Math.max(...closed.map(t => t.pnl || 0)).toFixed(4) : 0;
            const maxLoss = closed.length > 0 ? Math.min(...closed.map(t => t.pnl || 0)).toFixed(4) : 0;

            // 计算累计收益曲线数据
            let cumsum = 0;
            const cumulativePnl = closed.map(t => {
              cumsum += t.pnl || 0;
              return cumsum.toFixed(4);
            });

            // 按币种统计
            const symbolStats = {};
            closed.forEach(t => {
              if (!symbolStats[t.symbol]) {
                symbolStats[t.symbol] = { wins: 0, losses: 0, pnl: 0, trades: 0 };
              }
              symbolStats[t.symbol].trades += 1;
              symbolStats[t.symbol].pnl += t.pnl || 0;
              if (t.pnl > 0) symbolStats[t.symbol].wins += 1;
              else if (t.pnl < 0) symbolStats[t.symbol].losses += 1;
            });

            return (
              <div className="analytics-view">
                <div className="card">
                  <h2>📊 性能分析与优化</h2>
                  <div style={{display:'flex',gap:10,marginBottom:12,flexWrap:'wrap'}}>
                    {[
                      {label:'今日盈亏', val:perf.daily_pnl||0, pct:perf.daily_pnl_pct},
                      {label:'累计盈亏', val:perf.total_pnl||0, pct:perf.total_pnl_pct},
                    ].map(c=>(
                      <div key={c.label} style={{flex:1,minWidth:120,background:'rgba(0,245,255,0.03)',border:`1px solid ${c.val>=0?'rgba(0,245,255,0.15)':'rgba(255,45,120,0.15)'}`,borderRadius:6,padding:'8px 14px'}}>
                        <div style={{fontSize:10,color:'var(--text-mid)',marginBottom:2}}>{c.label} <span style={{fontSize:9,opacity:0.5}}>(实时)</span></div>
                        <div style={{fontSize:18,fontWeight:700,color:c.val>=0?'var(--cyan)':'var(--pink)'}}>
                          {c.val>=0?'+':''}{c.val.toFixed(4)} U
                          {c.pct!==undefined && <span style={{fontSize:11,marginLeft:5,opacity:0.7}}>({c.pct>=0?'+':''}{c.pct}%)</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                  <p style={{color:'var(--text-mid)',fontSize:12,margin:'0 0 16px',letterSpacing:'0.5px'}}>基于 {totalTrades} 笔平仓交易</p>

                  {/* 核心指标 */}
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:12,marginBottom:20}}>
                    <div style={{background:'rgba(0,245,255,0.03)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)'}}>
                      <div style={{fontSize:11,color:'var(--text-mid)',marginBottom:4,letterSpacing:'0.5px'}}>总平仓</div>
                      <div style={{fontSize:22,fontWeight:700,color:'var(--cyan)',textShadow:'0 0 12px rgba(0,245,255,0.4)'}}>{totalTrades}</div>
                      <div style={{fontSize:10,color:'var(--text-dim)',marginTop:2}}>赢{winTrades} / 亏{loseTrades}</div>
                    </div>
                    <div style={{background:'rgba(0,245,255,0.03)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)'}}>
                      <div style={{fontSize:11,color:'var(--text-mid)',marginBottom:4,letterSpacing:'0.5px'}}>胜率</div>
                      <div style={{fontSize:22,fontWeight:700,color:parseFloat(winRate)>=55?'var(--cyan)':parseFloat(winRate)>=50?'var(--yellow)':'var(--pink)',textShadow:`0 0 12px ${parseFloat(winRate)>=55?'rgba(0,245,255,0.4)':parseFloat(winRate)>=50?'rgba(255,230,0,0.4)':'rgba(255,45,120,0.4)'}`}}>{winRate}%</div>
                      <div style={{fontSize:10,color:'var(--text-dim)',marginTop:2}}>目标 ≥55%</div>
                    </div>
                    <div style={{background:'rgba(0,245,255,0.03)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)'}}>
                      <div style={{fontSize:11,color:'var(--text-mid)',marginBottom:4,letterSpacing:'0.5px'}}>平均收益</div>
                      <div style={{fontSize:22,fontWeight:700,color:parseFloat(avgPnl)>=0?'var(--cyan)':'var(--pink)'}}>${avgPnl}</div>
                      <div style={{fontSize:10,color:'var(--text-dim)',marginTop:2}}>单笔</div>
                    </div>
                    <div style={{background:'rgba(0,245,255,0.03)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)'}}>
                      <div style={{fontSize:11,color:'var(--text-mid)',marginBottom:4,letterSpacing:'0.5px'}}>最大单笔</div>
                      <div style={{fontSize:22,fontWeight:700,color:'var(--cyan)'}}>+${maxProfit}</div>
                      <div style={{fontSize:10,color:'var(--text-dim)',marginTop:2}}>最大亏损 <span style={{color:'var(--pink)'}}>${maxLoss}</span></div>
                    </div>
                  </div>

                  {/* 收益曲线 */}
                  {totalTrades > 0 && (() => {
                    const chartData = closed.slice(-60).map((t, i) => ({
                      name: t.date ? `${t.date} ${t.time ? t.time.slice(0,5) : ''}` : (t.time ? t.time.slice(0,5) : `#${i+1}`),
                      cumPnl: parseFloat(cumulativePnl[closed.length > 60 ? closed.length - 60 + i : i]),
                      pnl: parseFloat((t.pnl||0).toFixed(4)),
                    }));
                    const lastVal = chartData.length ? chartData[chartData.length-1].cumPnl : 0;
                    return (
                      <div style={{background:'rgba(0,245,255,0.01)',padding:'12px 0 12px 12px',borderRadius:6,border:'1px solid rgba(0,245,255,0.1)',marginBottom:16}}>
                        <h3 style={{fontSize:13,marginTop:0,marginBottom:12,paddingRight:12}}>◈ 累计收益曲线
                          <span style={{float:'right',fontWeight:700,color:lastVal>=0?'var(--cyan)':'var(--pink)',fontSize:14,textShadow:`0 0 10px ${lastVal>=0?'rgba(0,245,255,0.5)':'rgba(255,45,120,0.5)'}`}}>
                            {lastVal>=0?'+':''}{lastVal.toFixed(2)} U
                          </span>
                        </h3>
                        <ResponsiveContainer width="100%" height={200}>
                          <AreaChart data={chartData} margin={{top:4,right:16,left:0,bottom:0}}>
                            <defs>
                              <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={lastVal>=0?'var(--cyan)':'var(--pink)'} stopOpacity={0.25}/>
                                <stop offset="95%" stopColor={lastVal>=0?'var(--cyan)':'var(--pink)'} stopOpacity={0}/>
                              </linearGradient>
                            </defs>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,245,255,0.06)"/>
                            <XAxis dataKey="name" tick={{fill:'var(--text-dim)',fontSize:9}} tickLine={false} axisLine={{stroke:'rgba(0,245,255,0.1)'}}/>
                            <YAxis tick={{fill:'var(--text-dim)',fontSize:9}} tickLine={false} axisLine={false} tickFormatter={v=>`${v>0?'+':''}${v.toFixed(1)}`}/>
                            <Tooltip
                              contentStyle={{background:'var(--bg2)',border:'1px solid rgba(0,245,255,0.2)',borderRadius:6,fontSize:11}}
                              labelStyle={{color:'var(--text-mid)'}}
                              formatter={(v,n)=>[`${v>=0?'+':''}${v.toFixed(4)} USDT`, n==='cumPnl'?'累计盈亏':'单笔盈亏']}
                            />
                            <ReferenceLine y={0} stroke="rgba(0,245,255,0.2)" strokeDasharray="4 4"/>
                            <Area type="monotone" dataKey="cumPnl" stroke={lastVal>=0?'var(--cyan)':'var(--pink)'}
                              strokeWidth={2} fill="url(#pnlGrad)" dot={false} activeDot={{r:4}}/>
                          </AreaChart>
                        </ResponsiveContainer>
                      </div>
                    );
                  })()}

                  {/* 币种分析 */}
                  <div style={{background:'rgba(0,245,255,0.01)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)',marginBottom:16}}>
                    <h3 style={{fontSize:13,marginTop:0,marginBottom:8,letterSpacing:'0.5px'}}>◈ 币种分析</h3>
                    <div style={{overflowX:'auto'}}>
                      <table style={{width:'100%',fontSize:12,borderCollapse:'collapse'}}>
                        <thead>
                          <tr style={{borderBottom:'1px solid rgba(0,245,255,0.12)',color:'var(--text-mid)',letterSpacing:'0.5px'}}>
                            <th style={{textAlign:'left',padding:6}}>币种</th>
                            <th style={{textAlign:'center',padding:6}}>交易</th>
                            <th style={{textAlign:'center',padding:6}}>胜</th>
                            <th style={{textAlign:'center',padding:6}}>亏</th>
                            <th style={{textAlign:'center',padding:6}}>胜率</th>
                            <th style={{textAlign:'right',padding:6}}>总收益</th>
                          </tr>
                        </thead>
                        <tbody>
                          {Object.entries(symbolStats).sort((a,b)=>b[1].pnl-a[1].pnl).map(([sym,stats])=>{
                            const wr = stats.trades > 0 ? (stats.wins/stats.trades*100).toFixed(1) : 0;
                            return (
                              <tr key={sym} style={{borderBottom:'1px solid rgba(0,245,255,0.05)',color:stats.pnl>=0?'var(--cyan)':'var(--pink)'}}>
                                <td style={{padding:6}}><strong>{sym}</strong></td>
                                <td style={{textAlign:'center',padding:6,color:'var(--text)'}}>{stats.trades}</td>
                                <td style={{textAlign:'center',padding:6,color:'var(--cyan)'}}>{stats.wins}</td>
                                <td style={{textAlign:'center',padding:6,color:'var(--pink)'}}>{stats.losses}</td>
                                <td style={{textAlign:'center',padding:6}}>{wr}%</td>
                                <td style={{textAlign:'right',padding:6,fontWeight:700}}>${stats.pnl.toFixed(2)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* 优化建议 */}
                  <div style={{background:'rgba(0,245,255,0.01)',padding:12,borderRadius:6,border:'1px solid rgba(0,245,255,0.1)'}}>
                    <h3 style={{fontSize:13,marginTop:0,marginBottom:8,letterSpacing:'0.5px'}}>◈ 优化建议</h3>
                    {totalTrades < 20 ? (
                      <div style={{fontSize:12,color:'var(--yellow)',padding:8,background:'rgba(255,230,0,0.06)',borderRadius:4,border:'1px solid rgba(255,230,0,0.2)'}}>⚠ 数据不足（{totalTrades}笔），建议收集≥20笔后再参考
                      </div>
                    ) : (
                      <div style={{fontSize:12,color:'var(--text-mid)',display:'flex',flexDirection:'column',gap:6}}>
                        {parseFloat(winRate) < 50 && (
                          <div style={{padding:8,background:'rgba(255,45,120,0.06)',border:'1px solid rgba(255,45,120,0.25)',borderRadius:4,color:'var(--pink)'}}>
                            ▼ 胜率偏低（{winRate}%）：
                            <br/>• 降低min_confidence (0.70→0.65)
                            <br/>• 增加止盈目标 (2.8%→3.5%)
                            <br/>• 检查ADX&gt;22过滤是否有效
                          </div>
                        )}
                        {parseFloat(winRate) >= 55 && (
                          <div style={{padding:8,background:'rgba(0,245,255,0.06)',border:'1px solid rgba(0,245,255,0.25)',borderRadius:4,color:'var(--cyan)'}}>
                            ◈ 胜率良好（{winRate}%）
                            <br/>• 可尝试提高杠杆或单笔金额
                            <br/>• 继续积累数据以验证稳定性
                          </div>
                        )}
                        {parseFloat(avgPnl) < 0.5 && parseFloat(avgPnl) > 0 && (
                          <div style={{padding:8,background:'rgba(191,95,255,0.06)',border:'1px solid rgba(191,95,255,0.25)',borderRadius:4,color:'var(--purple)'}}>
                            📊 平均收益偏小（${avgPnl}），考虑：
                            <br/>• 提高take_profit_pct目标
                            <br/>• 降低trade_size_usd防滑点
                          </div>
                        )}
                        <button
                          onClick={async()=>{
                            try {
                              const r = await authFetch('/api/optimize/run', {method:'POST'});
                              const d = await r.json();
                              if (d.best) {
                                showToast(`✅ 优化完成！最优: conf=${d.best.min_confidence} sl=${(d.best.stop_loss_pct*100).toFixed(1)}%`, 'success');
                                setOptResult(d);
                              }
                            } catch(e) { showToast('❌ 优化失败: '+e.message, 'error'); }
                          }}
                          style={{padding:8,marginTop:8,background:'rgba(0,245,255,0.06)',border:'1px solid rgba(0,245,255,0.3)',color:'var(--cyan)',borderRadius:4,cursor:'pointer',fontSize:12,fontWeight:700,letterSpacing:'0.5px'}}
                        >
                          🔬 运行参数网格优化
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* ── 持仓/挂单 ── */}
          {view === 'positions' && account.logged_in && (
            <div className="positions-view">
              <div className="card">
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                  <h3>📈 当前持仓（实时同步）</h3>
                  <div style={{display:'flex',gap:6}}>
                    {(account.positions?.length > 0
                      ? [...new Set(account.positions.map(p=>p.symbol))]
                      : [settings.symbol]
                    ).map(sym => (
                      <button key={sym} className="btn-danger" style={{width:'auto',padding:'4px 10px',fontSize:11}}
                        onClick={() => cancelOrders(sym)}>撤 {sym.replace('USDT','')} 挂单</button>
                    ))}
                  </div>
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
                          const tpDist = tp && mark ? ((tp - mark) / mark * 100 * (isLong ? 1 : -1)) : null;
                          const slDist = sl && mark ? ((mark - sl) / mark * 100 * (isLong ? 1 : -1)) : null;
                          const tpPct  = tp && entry && tp !== entry
                            ? Math.min(100, Math.max(0, isLong
                                ? (mark - entry) / (tp - entry) * 100
                                : (entry - mark) / (entry - tp) * 100))
                            : 0;
                          return (
                            <tr key={i} className={isLong ? 'row-long' : 'row-short'}>
                              <td><b>{p.symbol.replace('USDT','')}</b><span style={{color:'var(--text-dim)',fontSize:10}}>/U</span></td>
                              <td className={isLong ? 'green' : 'red'} style={{fontWeight:700}}>{isLong ? '▲ 做多' : '▼ 做空'}</td>
                              <td style={{color:'var(--cyan)',fontWeight:700}}>${p.entry_usd > 0 ? Number(p.entry_usd).toFixed(2) : (entry * p.size).toFixed(2)}</td>
                              <td>{p.size}</td>
                              <td>${Number(entry).toLocaleString()}</td>
                              <td>${Number(mark).toLocaleString()}</td>
                              <td className={p.unrealized_pnl >= 0 ? 'green' : 'red'} style={{fontWeight:700}}>
                                {p.unrealized_pnl >= 0 ? '+' : ''}{Number(p.unrealized_pnl).toFixed(4)}
                              </td>
                              <td>
                                {tp > 0 ? (
                                  <div>
                                    <div style={{color:'var(--cyan)',fontWeight:700,fontSize:12}}>${Number(tp).toLocaleString()}</div>
                                    <div style={{height:3,background:'rgba(0,245,255,0.06)',borderRadius:2,marginTop:2,width:60}}>
                                      <div style={{height:'100%',width:`${tpPct}%`,background:'var(--cyan)',borderRadius:2,transition:'width .5s'}}/>
                                    </div>
                                    {tpDist !== null && <div style={{fontSize:10,color: tpDist <= 0 ? 'var(--cyan)' : 'rgba(0,245,255,0.6)',marginTop:1,fontWeight: tpDist <= 0 ? 700 : 400}}>
                                      {tpDist <= 0 ? '✅ 已达到' : `还差 ${tpDist.toFixed(2)}%`}
                                    </div>}
                                  </div>
                                ) : <span style={{color:'var(--text-dim)'}}>--</span>}
                              </td>
                              <td>
                                {sl > 0 ? (
                                  <div>
                                    <div style={{color:'var(--pink)',fontWeight:700,fontSize:12}}>${Number(sl).toLocaleString()}</div>
                                    {slDist !== null && (
                                      <div style={{fontSize:10,color:'rgba(255,45,120,0.6)',marginTop:1}}>
                                        缓冲 {Math.abs(slDist).toFixed(2)}%
                                        {Math.abs(slDist) < 0.3 && <span style={{color:'var(--pink)',marginLeft:3}}>⚠ 接近</span>}
                                      </div>
                                    )}
                                  </div>
                                ) : <span style={{color:'var(--text-dim)'}}>--</span>}
                              </td>
                              <td>{p.leverage}x</td>
                              <td style={{color:'var(--text-dim)',fontSize:11}}>{p.open_time || '--'}</td>
                              <td>
                                <button className="btn-danger" style={{width:'auto',padding:'4px 10px',fontSize:11}}
                                  onClick={() => closePosition(p.symbol)}>手动平仓</button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
                <h3 style={{marginTop:24}}>📋 挂单</h3>
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
                    {label:'总记录', val: tradeLogs.length, color:'var(--cyan)'},
                    {label:'盈利笔', val: wins, color:'var(--cyan)'},
                    {label:'胜率',   val: closed>0?`${(wins/closed*100).toFixed(1)}%`:'--', color:'var(--yellow)'},
                    {label:'累计盈亏', val: `${totalPnl>=0?'+':''}${totalPnl.toFixed(2)} U`, color:totalPnl>=0?'var(--cyan)':'var(--pink)'},
                  ].map(c=>(
                    <div key={c.label} style={{flex:1,minWidth:90,background:'rgba(0,245,255,0.02)',border:'1px solid rgba(0,245,255,0.1)',borderRadius:6,padding:'8px 12px',textAlign:'center'}}>
                      <div style={{fontSize:10,color:'var(--text-mid)',marginBottom:2,letterSpacing:'0.5px'}}>{c.label}</div>
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
                          background:logFilter===k?'rgba(0,245,255,0.15)':'transparent',
                          color:logFilter===k?'var(--cyan)':'var(--text-mid)',
                          border:`1px solid ${logFilter===k?'rgba(0,245,255,0.5)':'rgba(0,245,255,0.1)'}`}}>
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
                      <div style={{display:'flex',gap:16,marginBottom:6,fontSize:11,color:'var(--text-dim)',padding:'4px 8px',background:'rgba(0,245,255,0.02)',borderRadius:4}}>
                        <span>本页 {pageLogs.length} 笔</span>
                        <span>手续费合计: <b style={{color:'var(--yellow)'}}>-${totalFee.toFixed(4)} USDT</b></span>
                        <span style={{color:'var(--text-dim)'}}>· 点击行查看明细</span>
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
                            const sideColor  = t.side==='BUY'?'var(--cyan)':t.side==='SELL'?'var(--pink)':'var(--yellow)';
                            const notional   = t.notional || (t.price * t.size) || 0;
                            const fee        = t.fee || notional * 0.0005;
                            const expanded   = expandedLog === (t.id || i);
                            return [
                              <tr key={t.id||i}
                                onClick={()=>setExpandedLog(expanded ? null : (t.id||i))}
                                style={{cursor:'pointer'}}
                                className={t.side==='BUY'?'row-buy':t.side==='SELL'?'row-sell':''}>
                                <td className="t-time" style={{color:'var(--text-dim)'}}>{t.time || t.ts}</td>
                                <td style={{color:sideColor,fontWeight:700}}>
                                  {sideZh[t.side] || t.side}
                                </td>
                                <td><b>{(t.symbol||'').replace('USDT','')}</b><span style={{color:'var(--text-dim)',fontSize:10}}>/U</span></td>
                                <td>${Number(t.price||0).toLocaleString()}</td>
                                <td style={{color:'var(--cyan)',fontWeight:700}}>
                                  ${notional > 0 ? notional.toFixed(2) : '--'}
                                </td>
                                <td>{t.size}</td>
                                <td style={{color:'var(--yellow)'}}>-${fee.toFixed(4)}</td>
                                <td style={{fontWeight:700,
                                  color:t.pnl>0?'var(--cyan)':t.pnl<0?'var(--pink)':'var(--text-dim)'}}>
                                  {isClose
                                    ? (t.pnl>=0?'+':'')+Number(t.pnl).toFixed(4)
                                    : '--'}
                                </td>
                                <td>{t.confidence ? `${(t.confidence*100).toFixed(0)}%` : '--'}</td>
                                <td style={{color:'var(--cyan)',fontSize:10}}>
                                  {stratName[t.strategy] || t.strategy || '--'}
                                </td>
                                <td>
                                  <span style={{fontSize:10,padding:'1px 5px',borderRadius:3,
                                    background:t.status==='filled'?'rgba(0,245,255,0.08)':t.status==='failed'?'rgba(255,45,120,0.08)':'rgba(255,230,0,0.08)',
                                    color:t.status==='filled'?'var(--cyan)':t.status==='failed'?'var(--pink)':'var(--yellow)',
                                    border:`1px solid ${t.status==='filled'?'rgba(0,245,255,0.35)':t.status==='failed'?'rgba(255,45,120,0.35)':'rgba(255,230,0,0.35)'}`}}>
                                    {t.status==='filled'?'成交':t.status==='failed'?'失败':'已发'}
                                  </span>
                                  <span style={{marginLeft:4,color:'var(--text-dim)',fontSize:10}}>{expanded?'▲':'▼'}</span>
                                </td>
                              </tr>,
                              expanded && (
                                <tr key={(t.id||i)+'_detail'} style={{background:'rgba(0,245,255,0.015)'}}>
                                  <td colSpan="11" style={{padding:'10px 16px'}}>
                                    <div style={{display:'flex',gap:24,flexWrap:'wrap',fontSize:11}}>
                                      <div>
                                        <div style={{color:'var(--text-mid)',marginBottom:2,letterSpacing:'0.5px'}}>◈ 交易详情</div>
                                        <div style={{color:'var(--text-dim)'}}>订单ID: <span style={{color:'var(--cyan)'}}>{t.result_raw||'--'}</span></div>
                                        <div style={{color:'var(--text-dim)'}}>策略: <span style={{color:'var(--cyan)'}}>{stratName[t.strategy]||t.strategy}</span></div>
                                        <div style={{color:'var(--text-dim)'}}>置信度: <span style={{color:'var(--yellow)'}}>{t.confidence?(t.confidence*100).toFixed(1)+'%':'--'}</span></div>
                                      </div>
                                      <div>
                                        <div style={{color:'var(--text-mid)',marginBottom:2,letterSpacing:'0.5px'}}>◈ 资金明细</div>
                                        <div style={{color:'var(--text-dim)'}}>成交金额: <span style={{color:'var(--cyan)'}}>${notional.toFixed(4)} USDT</span></div>
                                        <div style={{color:'var(--text-dim)'}}>手续费(0.05%): <span style={{color:'var(--yellow)'}}>-${fee.toFixed(6)} USDT</span></div>
                                        {isClose && <div style={{color:'var(--text-dim)'}}>平仓盈亏: <span style={{color:t.pnl>=0?'var(--cyan)':'var(--pink)',fontWeight:700}}>{t.pnl>=0?'+':''}{Number(t.pnl).toFixed(6)} USDT</span></div>}
                                        {isOpen  && (() => { const margin = (notional / (t.leverage||1)); return <div style={{color:'var(--text-dim)'}}>本次花费: <span style={{color:'var(--yellow)'}}>保证金 ${margin.toFixed(4)} + 手续费 ${fee.toFixed(4)}</span></div>; })()}
                                      </div>
                                      {isClose && t.pnl < 0 && (
                                        <div style={{background:'rgba(255,45,120,0.06)',border:'1px solid rgba(255,45,120,0.2)',borderRadius:4,padding:'6px 10px'}}>
                                          <div style={{color:'var(--pink)',fontWeight:700,marginBottom:2}}>⚠ 亏损分析</div>
                                          <div style={{color:'rgba(255,45,120,0.7)'}}>总亏损: {Number(t.pnl).toFixed(4)} USDT</div>
                                          <div style={{color:'var(--yellow)'}}>其中手续费: ${(fee*2).toFixed(4)} USDT</div>
                                        </div>
                                      )}
                                      {isClose && t.pnl > 0 && (
                                        <div style={{background:'rgba(0,245,255,0.06)',border:'1px solid rgba(0,245,255,0.2)',borderRadius:4,padding:'6px 10px'}}>
                                          <div style={{color:'var(--cyan)',fontWeight:700,marginBottom:2}}>◈ 本笔盈利</div>
                                          <div style={{color:'rgba(0,245,255,0.7)'}}>净盈利: +{Number(t.pnl).toFixed(4)} USDT</div>
                                          <div style={{color:'var(--yellow)'}}>已扣手续费: ${(fee*2).toFixed(4)} USDT</div>
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
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid rgba(0,245,255,0.15)',color:'var(--text-mid)',borderRadius:3,cursor:'pointer'}}>«</button>
                  <button onClick={()=>setLogPage(p=>Math.max(0,p-1))} disabled={logPage===0}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid rgba(0,245,255,0.15)',color:'var(--text-mid)',borderRadius:3,cursor:'pointer'}}>‹</button>
                  <span style={{color:'var(--text-mid)'}}>{logPage+1} / {pages}</span>
                  <button onClick={()=>setLogPage(p=>Math.min(pages-1,p+1))} disabled={logPage>=pages-1}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid rgba(0,245,255,0.15)',color:'var(--text-mid)',borderRadius:3,cursor:'pointer'}}>›</button>
                  <button onClick={()=>setLogPage(pages-1)} disabled={logPage>=pages-1}
                    style={{padding:'2px 8px',background:'transparent',border:'1px solid rgba(0,245,255,0.15)',color:'var(--text-mid)',borderRadius:3,cursor:'pointer'}}>»</button>
                </div>
              </div>
            );
          })()}

          {/* ── 策略设置 ── */}
          {view === 'settings' && account.logged_in && (
            <div className="settings-view">
              <h3>⚙️ HFT 策略设置</h3>
              {/* 设置子 Tab */}
              <div style={{display:'flex',gap:3,marginBottom:14,background:'rgba(0,245,255,0.03)',borderRadius:6,padding:'3px',border:'1px solid rgba(0,245,255,0.1)',width:'fit-content'}}>
                {[['basic','⚙️ 基础'],['risk','🛡️ 风控'],['symbols','🌐 币种'],['advanced','🔬 高级']].map(([k,l])=>(
                  <button key={k} onClick={()=>setSettingsTab(k)}
                    style={{padding:'5px 14px',borderRadius:4,border:'none',cursor:'pointer',fontSize:11,fontWeight:600,transition:'all .2s',
                      background:settingsTab===k?'rgba(0,245,255,0.15)':'transparent',
                      color:settingsTab===k?'var(--cyan)':'var(--text-mid)',
                      boxShadow:settingsTab===k?'0 0 8px rgba(0,245,255,0.2)':'none'}}>{l}</button>
                ))}
              </div>

              {/* ══ 基础 Tab ══ */}
              {settingsTab === 'basic' && (
              <div className="settings-form">
                <div className="form-row-2">
                  <div className="form-group">
                    <label>交易策略</label>
                    <select value={settings.strategy} onChange={e=>setSettings(p=>({...p,strategy:e.target.value}))}>
                      <option value="multi">🧠 多策略加权融合（推荐）</option>
                      <option value="crypto_hft">⚡ 加密货币高频专用</option>
                      <option value="ema_cross">📈 EMA三线交叉</option>
                      <option value="macd">📉 MACD 金死叉</option>
                      <option value="rsi">📊 RSI 超买超卖</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label>交易币种</label>
                    <select value={settings.symbol} onChange={e=>setSettings(p=>({...p,symbol:e.target.value}))}>
                      <option value="BTCUSDT">BTC/USDT</option>
                      <option value="ETHUSDT">ETH/USDT</option>
                      <option value="SOLUSDT">SOL/USDT</option>
                      <option value="ARBUSDT">ARB/USDT</option>
                      <option value="AVAXUSDT">AVAX/USDT</option>
                    </select>
                  </div>
                </div>

                {/* 下单量模式 */}
                <div className="form-group" style={{marginBottom:12}}>
                  <label style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                    <span>💰 下单量模式</span>
                    <span style={{fontSize:10,color:'var(--text-dim)'}}>
                      {settings.size_mode==='pct'
                        ? `余额${settings.size_pct||20}% × 杠杆${settings.leverage}x ≈ $${((account.available||0)*((settings.size_pct||20)/100)*settings.leverage).toFixed(1)}`
                        : `固定 $${settings.trade_size_usd} × 杠杆${settings.leverage}x = $${(settings.trade_size_usd*settings.leverage).toFixed(0)}`}
                    </span>
                  </label>
                  <div style={{display:'flex',gap:6,marginBottom:8}}>
                    {[['fixed','🔒 固定USD','每笔下固定金额'],['pct','📊 余额%','按余额百分比']].map(([v,l,desc])=>{
                      const act=(settings.size_mode||'fixed')===v;
                      return (
                        <button key={v} onClick={()=>setSettings(p=>({...p,size_mode:v}))}
                          style={{flex:1,padding:'6px',borderRadius:5,cursor:'pointer',textAlign:'center',
                            background:act?'rgba(255,230,0,0.08)':'transparent',
                            border:`2px solid ${act?'var(--yellow)':'rgba(0,245,255,0.12)'}`,
                            color:act?'var(--yellow)':'var(--text-mid)',transition:'all .2s'}}>
                          <div style={{fontWeight:700,fontSize:11}}>{l}</div>
                          <div style={{fontSize:9,marginTop:2,color:act?'rgba(255,230,0,0.6)':'var(--text-dim)'}}>{desc}</div>
                        </button>
                      );
                    })}
                  </div>
                  {(settings.size_mode||'fixed')==='fixed' ? (
                    <div style={{display:'flex',gap:6,alignItems:'center'}}>
                      <input type="number" min="1" max="1000" value={settings.trade_size_usd}
                        onChange={e=>setSettings(p=>({...p,trade_size_usd:+e.target.value}))} style={{flex:1}} />
                      <span style={{fontSize:10,color:'var(--text-dim)'}}>USD / 笔</span>
                    </div>
                  ) : (
                    <div style={{display:'flex',gap:6,alignItems:'center'}}>
                      <input type="range" min="5" max="50" value={settings.size_pct||20}
                        onChange={e=>setSettings(p=>({...p,size_pct:+e.target.value}))}
                        style={{flex:1,accentColor:'var(--yellow)'}} />
                      <span style={{fontSize:12,fontWeight:700,color:'var(--yellow)',minWidth:36}}>{settings.size_pct||20}%</span>
                    </div>
                  )}
                </div>

                {/* HFT 模式 */}
                <div className="form-group" style={{marginBottom:12}}>
                  <label style={{marginBottom:6,display:'block'}}>⚡ HFT交易模式</label>
                  <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                    {[
                      ['conservative','🛡️ 精准','var(--cyan)',['盈亏比≥1.8x','稳定首选']],
                      ['balanced','⚖️ 平衡','var(--yellow)',['盈亏比≥1.2x','推荐默认']],
                      ['aggressive','⚡ 激进','var(--purple)',['盈亏比≥0.3x','高频开仓']],
                      ['turbo','🚀 极速','var(--pink)',['盈亏比≥0.5x','翻倍冲榜']],
                    ].map(([val,label,color,lines])=>{
                      const active=settings.hft_mode===val;
                      return (
                        <button key={val} onClick={async()=>{
                          const next={...settings,hft_mode:val};
                          setSettings(next);
                          try{ await authFetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...next,symbol_settings:symbolSettings})}); showToast(`✅ 已切换到${label}模式`,'success'); }
                          catch{ showToast('模式切换失败','error'); }
                        }} style={{flex:'1 1 calc(25% - 6px)',minWidth:72,padding:'8px 4px',borderRadius:6,cursor:'pointer',textAlign:'center',
                          background:active?'rgba(0,245,255,0.06)':'transparent',
                          border:`2px solid ${active?color:'rgba(0,245,255,0.1)'}`,
                          color:active?color:'var(--text-mid)',transition:'all .2s'}}>
                          <div style={{fontWeight:700,fontSize:11,marginBottom:4}}>{label}</div>
                          {lines.map((l,i)=><div key={i} style={{fontSize:9,lineHeight:1.6,color:active?color:'var(--text-dim)'}}>{l}</div>)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="form-row-2">
                  <div className="form-group">
                    <label style={{display:'flex',justifyContent:'space-between'}}>
                      <span>最小置信度</span>
                      <span style={{color:'var(--cyan)',fontWeight:700}}>{(settings.min_confidence*100).toFixed(0)}%</span>
                    </label>
                    <input type="range" min="50" max="90" value={settings.min_confidence*100}
                      onChange={e=>setSettings(p=>({...p,min_confidence:+e.target.value/100}))}
                      style={{width:'100%',accentColor:'var(--cyan)'}} />
                  </div>
                  <div className="form-group">
                    <label>最大持仓 (USD)</label>
                    <input type="number" value={settings.max_position_usd}
                      onChange={e=>setSettings(p=>({...p,max_position_usd:+e.target.value}))} />
                  </div>
                  <div className="form-group">
                    <label>单笔最大 (USD)</label>
                    <input type="number" value={settings.max_trade_usd||30}
                      onChange={e=>setSettings(p=>({...p,max_trade_usd:+e.target.value}))} />
                  </div>
                </div>

                {settings.strategy==='ema_cross' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>EMA快线</label><input type="number" value={settings.ema_fast} onChange={e=>setSettings(p=>({...p,ema_fast:+e.target.value}))} /></div>
                    <div className="form-group"><label>EMA慢线</label><input type="number" value={settings.ema_slow} onChange={e=>setSettings(p=>({...p,ema_slow:+e.target.value}))} /></div>
                    <div className="form-group"><label>EMA长线</label><input type="number" value={settings.ema_long} onChange={e=>setSettings(p=>({...p,ema_long:+e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy==='macd' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>MACD快</label><input type="number" value={settings.macd_fast} onChange={e=>setSettings(p=>({...p,macd_fast:+e.target.value}))} /></div>
                    <div className="form-group"><label>MACD慢</label><input type="number" value={settings.macd_slow} onChange={e=>setSettings(p=>({...p,macd_slow:+e.target.value}))} /></div>
                    <div className="form-group"><label>Signal</label><input type="number" value={settings.macd_signal} onChange={e=>setSettings(p=>({...p,macd_signal:+e.target.value}))} /></div>
                  </div>
                )}
                {settings.strategy==='rsi' && (
                  <div className="form-row-2">
                    <div className="form-group"><label>RSI周期</label><input type="number" value={settings.rsi_period} onChange={e=>setSettings(p=>({...p,rsi_period:+e.target.value}))} /></div>
                    <div className="form-group"><label>超卖线</label><input type="number" value={settings.rsi_oversold} onChange={e=>setSettings(p=>({...p,rsi_oversold:+e.target.value}))} /></div>
                    <div className="form-group"><label>超买线</label><input type="number" value={settings.rsi_overbought} onChange={e=>setSettings(p=>({...p,rsi_overbought:+e.target.value}))} /></div>
                  </div>
                )}
                {(settings.strategy==='multi'||settings.strategy==='crypto_hft') && (
                  <div className="alert alert-info" style={{marginTop:6,fontSize:12}}>
                    💡 {settings.strategy==='multi'?'七维加权融合策略，建议置信度阈值 0.62+':'Supertrend+VWAP+订单簿微结构+RSI+MACD+HA确认'}
                  </div>
                )}

                <div className="form-actions">
                  <button className="btn-primary" onClick={saveSettings}>💾 保存并应用</button>
                </div>
              </div>
              )}

              {/* ══ 风控 Tab ══ */}
              {settingsTab === 'risk' && (
              <div className="settings-form">
                <div className="form-row checkboxes">
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.enable_long} onChange={e=>setSettings(p=>({...p,enable_long:e.target.checked}))} />
                    <span>📈 允许做多</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.enable_short} onChange={e=>setSettings(p=>({...p,enable_short:e.target.checked}))} />
                    <span>📉 允许做空</span>
                  </label>
                  <label className="checkbox-label">
                    <input type="checkbox" checked={settings.cancel_on_reverse} onChange={e=>setSettings(p=>({...p,cancel_on_reverse:e.target.checked}))} />
                    <span>↩️ 反向自动撤单</span>
                  </label>
                </div>

                <div className="form-row-2" style={{marginTop:8}}>
                  <div className="form-group"><label>最大持仓数</label><input type="number" value={settings.max_open_positions} onChange={e=>setSettings(p=>({...p,max_open_positions:+e.target.value}))} /></div>
                  <div className="form-group"><label>日亏损限额(USD)</label><input type="number" value={settings.max_daily_loss_usd} onChange={e=>setSettings(p=>({...p,max_daily_loss_usd:+e.target.value}))} /></div>
                  <div className="form-group"><label>HFT间隔(ms)</label><input type="number" value={settings.hft_interval_ms} onChange={e=>setSettings(p=>({...p,hft_interval_ms:+e.target.value}))} /></div>
                  <div className="form-group">
                    <label>平仓冷却(秒) <span style={{color:'var(--yellow)',fontSize:10}}>防反复横跳</span></label>
                    <input type="number" min="0" max="300" value={settings.cooldown_secs} onChange={e=>setSettings(p=>({...p,cooldown_secs:+e.target.value}))} />
                  </div>
                  <div className="form-group">
                    <label style={{display:'flex',justifyContent:'space-between'}}>
                      <span>🛡️ 插针保护(%)</span>
                      <span style={{fontSize:10,color:'var(--text-dim)'}}>偏离超过此值拒单</span>
                    </label>
                    <input type="number" step="0.1" min="0.1" max="5"
                      value={settings.spike_protection_pct??0.8}
                      onChange={e=>setSettings(p=>({...p,spike_protection_pct:+e.target.value}))} />
                  </div>
                </div>

                <div className="form-actions">
                  <button className="btn-primary" onClick={saveSettings}>💾 保存并应用</button>
                </div>
                <div className="alert alert-warn" style={{marginTop:12}}>
                  ⚠️ 实盘模式已启用，将使用真实资金进行自动交易。请确保风险参数正确。
                </div>
              </div>
              )}

              {/* ══ 币种 Tab ══ */}
              {settingsTab === 'symbols' && (
              <div className="settings-form">
                {/* 币种开关选择器 */}
                <div className="form-group" style={{marginBottom:14}}>
                  <label style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                    <span>🌐 同时交易币种 <span style={{fontSize:10,color:'var(--text-dim)'}}>(每个币种独立最多1单)</span></span>
                    <span style={{fontSize:10,color:'var(--cyan)'}}>已选 {(settings.active_symbols||[]).length} 个</span>
                  </label>
                  <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
                    {[
                      ['BTCUSDT','BTC','#f7931a'],['ETHUSDT','ETH','#627eea'],['SOLUSDT','SOL','#9945ff'],
                      ['BNBUSDT','BNB','#f3ba2f'],['ARBUSDT','ARB','#12aaff'],['AVAXUSDT','AVAX','#e84142'],
                      ['DOGEUSDT','DOGE','#c2a633'],['XRPUSDT','XRP','#346aa9'],['ADAUSDT','ADA','#0033ad'],
                      ['DOTUSDT','DOT','#e6007a'],['LTCUSDT','LTC','#bfbbbb'],['LINKUSDT','LINK','#2a5ada'],
                      ['UNIUSDT','UNI','#ff007a'],['ATOMUSDT','ATOM','#2e3148'],['NEARUSDT','NEAR','#00c08b'],
                      ['APTUSDT','APT','#2dd8a3'],['SUIUSDT','SUI','#6fbcf0'],['OPUSDT','OP','#ff0420'],
                      ['INJUSDT','INJ','#00b2ff'],['TIAUSDT','TIA','#7b2bf9'],['SEIUSDT','SEI','#9b59b6'],
                      ['WIFUSDT','WIF','#c084fc'],['FETUSDT','FET','#1a9aef'],['RENDERUSDT','RNDR','#e8442b'],
                    ].map(([sym,label,color])=>{
                      const active=(settings.active_symbols||[]).includes(sym);
                      return (
                        <button key={sym} onClick={async()=>{
                          const cur=settings.active_symbols||[];
                          const next=active?cur.filter(s=>s!==sym):[...cur,sym];
                          if(next.length===0) return;
                          const ns={...settings,active_symbols:next,symbol:next[0]};
                          setSettings(ns);
                          try{ await authFetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...ns,symbol_settings:symbolSettings})}); }catch{}
                        }} style={{padding:'4px 9px',borderRadius:4,cursor:'pointer',fontSize:11,fontWeight:700,
                          background:active?`${color}28`:'transparent',
                          border:`1.5px solid ${active?color:'rgba(0,245,255,0.1)'}`,
                          color:active?color:'var(--text-dim)',transition:'all .15s'}}>
                          {active?'✓ ':''}{label}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* 已启用币种的独立参数配置 */}
                {(()=>{
                  const SYM_COLOR = {
                    BTCUSDT:'#f7931a',ETHUSDT:'#627eea',SOLUSDT:'#9945ff',BNBUSDT:'#f3ba2f',
                    ARBUSDT:'#12aaff',AVAXUSDT:'#e84142',DOGEUSDT:'#c2a633',XRPUSDT:'#346aa9',
                    ADAUSDT:'#0033ad',DOTUSDT:'#e6007a',LTCUSDT:'#bfbbbb',LINKUSDT:'#2a5ada',
                    UNIUSDT:'#ff007a',ATOMUSDT:'#2e3148',NEARUSDT:'#00c08b',APTUSDT:'#2dd8a3',
                    SUIUSDT:'#6fbcf0',OPUSDT:'#ff0420',INJUSDT:'#00b2ff',TIAUSDT:'#7b2bf9',
                    SEIUSDT:'#9b59b6',WIFUSDT:'#c084fc',FETUSDT:'#1a9aef',RENDERUSDT:'#e8442b',
                  };
                  const activeSyms = settings.active_symbols || [];
                  if (!activeSyms.length) return null;
                  return (
                    <div style={{marginBottom:12}}>
                      <div style={{fontSize:11,color:'var(--cyan)',fontWeight:700,marginBottom:8}}>◈ 单币种独立参数设置</div>
                      <div style={{display:'flex',flexDirection:'column',gap:6}}>
                        {activeSyms.map(sym=>{
                          const color = SYM_COLOR[sym] || 'var(--cyan)';
                          const label = sym.replace('USDT','');
                          const cur = symbolSettings[sym] || {};
                          const hasCust = !!symbolSettings[sym];
                          const curTp   = cur.take_profit_pct  ?? 0.028;
                          const curSl   = cur.stop_loss_pct    ?? 0.012;
                          const curLev  = cur.leverage         ?? 3;
                          const curConf = cur.min_confidence   ?? 0.65;
                          return (
                            <div key={sym} style={{border:`1px solid ${color}44`,borderRadius:6,padding:'8px 10px',background:`${color}08`}}>
                              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:7}}>
                                <div style={{display:'flex',alignItems:'center',gap:6}}>
                                  <span style={{fontWeight:700,color,fontSize:12}}>{label}</span>
                                  {hasCust && <span style={{fontSize:9,padding:'1px 5px',background:`${color}22`,border:`1px solid ${color}55`,color,borderRadius:2}}>已自定义</span>}
                                </div>
                                <button onClick={async()=>{
                                  const params={take_profit_pct:curTp,stop_loss_pct:curSl,leverage:curLev,min_confidence:curConf};
                                  setSymbolSettings(p=>({...p,[sym]:params}));
                                  try{ await authFetch('/api/settings/symbol',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbol:sym,params})}); showToast(`✅ ${label} 已保存`,'success'); }
                                  catch{ showToast('保存失败','error'); }
                                }} style={{fontSize:10,padding:'3px 10px',borderRadius:3,border:`1px solid ${color}`,background:`${color}22`,color,cursor:'pointer'}}>💾 保存</button>
                              </div>
                              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr 1fr',gap:6}}>
                                {[
                                  {key:'take_profit_pct', label:'止盈 %',  val:curTp,   kc:'var(--cyan)',  step:0.1, min:0.1, max:10},
                                  {key:'stop_loss_pct',   label:'止损 %',  val:curSl,   kc:'var(--pink)',  step:0.1, min:0.1, max:5},
                                  {key:'leverage',        label:'杠杆 x',  val:curLev,  kc:'var(--yellow)',step:1,   min:1,   max:20},
                                  {key:'min_confidence',  label:'置信 %',  val:curConf, kc:'var(--purple)',step:1,   min:50,  max:90},
                                ].map(({key,label:kl,val,kc,step,min,max})=>(
                                  <div key={key}>
                                    <div style={{fontSize:9,color:'var(--text-dim)',marginBottom:2}}>{kl}</div>
                                    <input type="number" step={step} min={min} max={max}
                                      value={key==='min_confidence'?Math.round(val*100):key==='leverage'?val:parseFloat((val*100).toFixed(2))}
                                      onChange={e=>{
                                        let v=parseFloat(e.target.value); if(isNaN(v)) return;
                                        const stored=(key==='min_confidence'||key==='take_profit_pct'||key==='stop_loss_pct')?v/100:(key==='leverage'?v:v/100);
                                        setSymbolSettings(p=>({...p,[sym]:{...(p[sym]||{}),take_profit_pct:curTp,stop_loss_pct:curSl,leverage:curLev,min_confidence:curConf,[key]:stored}}));
                                      }}
                                      style={{width:'100%',padding:'3px 4px',background:'rgba(0,245,255,0.04)',border:`1px solid ${kc}55`,color:kc,borderRadius:3,fontSize:11,textAlign:'right'}} />
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

                <div className="form-actions">
                  <button className="btn-primary" onClick={saveSettings}>💾 保存并应用</button>
                </div>
              </div>
              )}

              {/* ══ 高级 Tab ══ */}
              {settingsTab === 'advanced' && (
              <div className="settings-form">
                {/* 自动迭代优化 */}
                <div className="card" style={{marginTop:0,padding:14}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10}}>
                    <h3 style={{margin:0,fontSize:13}}>🔬 自动参数迭代优化</h3>
                    <div style={{display:'flex',gap:8,alignItems:'center'}}>
                      {(()=>{
                        const closed=tradeLogs.filter(t=>t.side==='CLOSE').length;
                        return <span style={{fontSize:10,color:closed>=20?'var(--cyan)':'var(--text-dim)'}}>平仓数据 <b>{closed}</b>/20 {closed>=20?'◈ 可优化':'(积累中)'}</span>;
                      })()}
                      <button onClick={async()=>{
                        setOptLoading(true);
                        try{
                          const r=await authFetch('/api/optimize/run',{method:'POST'});
                          const d=await r.json();
                          setOptResult(d);
                          if(d.best) showToast('✅ 优化完成','success');
                          else showToast(d.error||'数据不足','warn');
                        }catch{ showToast('优化请求失败','error'); }
                        setOptLoading(false);
                      }} disabled={optLoading} style={{padding:'4px 12px',borderRadius:4,cursor:'pointer',fontSize:12,
                        background:optLoading?'transparent':'rgba(0,245,255,0.06)',border:'1px solid var(--cyan)',color:'var(--cyan)'}}>
                        {optLoading?'⏳ 分析中...':'▶ 立即优化'}
                      </button>
                    </div>
                  </div>
                  <div style={{fontSize:10,color:'var(--text-dim)',marginBottom:10,lineHeight:1.6}}>
                    系统每积累 <b style={{color:'var(--yellow)'}}>20笔平仓</b> 自动运行参数网格搜索，找出期望收益最高的组合。
                  </div>
                  {optResult&&optResult.best ? (
                    <div>
                      <div style={{background:'rgba(0,245,255,0.04)',border:'1px solid rgba(0,245,255,0.2)',borderRadius:6,padding:'8px 10px',marginBottom:8}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                          <span style={{fontSize:11,color:'var(--cyan)',fontWeight:700}}>◈ 最优参数组合</span>
                          <span style={{fontSize:10,color:'var(--text-dim)'}}>{optResult.optimized_at}</span>
                        </div>
                        <div style={{display:'flex',gap:16,fontSize:11,marginBottom:6,flexWrap:'wrap'}}>
                          <span>置信 <b style={{color:'var(--cyan)'}}>{Math.round(optResult.best.min_confidence*100)}%</b></span>
                          <span>止损 <b style={{color:'var(--pink)'}}>{(optResult.best.stop_loss_pct*100).toFixed(1)}%</b></span>
                          <span>止盈 <b style={{color:'var(--cyan)'}}>{(optResult.best.take_profit_pct*100).toFixed(1)}%</b></span>
                          {optResult.top5?.[0] && <span>训练胜率 <b style={{color:'var(--yellow)'}}>{optResult.top5[0].win_rate}%</b></span>}
                        </div>
                        <button onClick={async()=>{
                          try{
                            const r=await authFetch('/api/optimize/apply',{method:'POST'});
                            const d=await r.json();
                            if(d.ok){setSettings(p=>({...p,...d.applied}));showToast('✅ 最优参数已应用','success');}
                            else showToast(d.error||'应用失败','error');
                          }catch(e){showToast(`应用失败: ${e.message}`,'error');}
                        }} style={{width:'100%',padding:'6px',borderRadius:4,cursor:'pointer',fontSize:12,fontWeight:700,
                          background:'rgba(0,245,255,0.06)',border:'1px solid var(--cyan)',color:'var(--cyan)'}}>
                          🔁 应用最优参数
                        </button>
                      </div>
                      {optResult.top5?.length>1 && (
                        <table style={{width:'100%',borderCollapse:'collapse',fontSize:10}}>
                          <thead>
                            <tr style={{color:'var(--text-mid)'}}>
                              <td style={{padding:'2px 4px'}}>#</td>
                              <td>置信</td><td>止损</td><td>止盈</td>
                              <td style={{color:'var(--yellow)'}}>胜率</td>
                              <td style={{color:'var(--cyan)'}}>均盈亏</td>
                              <td>样本</td>
                            </tr>
                          </thead>
                          <tbody>
                            {optResult.top5.map((row,i)=>(
                              <tr key={i} style={{borderTop:'1px solid rgba(0,245,255,0.06)',color:i===0?'var(--cyan)':'var(--text-mid)'}}>
                                <td style={{padding:'3px 4px',color:'var(--text-dim)'}}>{i+1}</td>
                                <td>{Math.round(row.min_confidence*100)}%</td>
                                <td style={{color:'var(--pink)'}}>{(row.stop_loss_pct*100).toFixed(1)}%</td>
                                <td style={{color:'var(--cyan)'}}>{(row.take_profit_pct*100).toFixed(1)}%</td>
                                <td style={{color:row.win_rate>=55?'var(--cyan)':row.win_rate>=45?'var(--yellow)':'var(--pink)',fontWeight:700}}>{row.win_rate}%</td>
                                <td style={{color:row.avg_pnl>=0?'var(--cyan)':'var(--pink)'}}>{row.avg_pnl>=0?'+':''}{row.avg_pnl}</td>
                                <td style={{fontSize:9}}>{row.sample}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  ) : (
                    <div style={{textAlign:'center',padding:'20px 0',color:'var(--text-dim)',fontSize:11}}>
                      {optLoading?'⏳ 正在分析...':'暂无优化结果。积累20笔平仓后点击「立即优化」。'}
                    </div>
                  )}
                </div>

                {/* Telegram */}
                <div className="card" style={{marginTop:12,padding:14}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                    <h3 style={{margin:0,fontSize:13}}>📲 Telegram 通知配置</h3>
                    <span style={{fontSize:10,padding:'2px 8px',borderRadius:10,
                      background:tgConfig.enabled?'rgba(0,245,255,0.12)':'rgba(255,45,120,0.12)',
                      color:tgConfig.enabled?'var(--cyan)':'var(--pink)',
                      border:`1px solid ${tgConfig.enabled?'var(--cyan)':'var(--pink)'}`}}>
                      {tgConfig.enabled?'✅ 已启用':'❌ 未配置'}
                    </span>
                  </div>
                  <div style={{fontSize:10,color:'var(--text-dim)',marginBottom:12,lineHeight:1.6}}>
                    开仓/平仓/止损/余额告警实时推送。① 找 <code>@BotFather</code> 创建Bot拿Token &nbsp;② 找 <code>@userinfobot</code> 获取Chat ID
                  </div>
                  <div style={{display:'flex',flexDirection:'column',gap:8}}>
                    <div className="form-group" style={{marginBottom:0}}>
                      <label style={{fontSize:11,marginBottom:4,display:'block'}}>Bot Token</label>
                      <input type="text" placeholder={tgConfig.token_set?tgConfig.token:'填入 BotFather 给的 Token'}
                        value={tgConfig.token_set?'':tgConfig.token}
                        onChange={e=>setTgConfig(p=>({...p,token:e.target.value,token_set:false}))}
                        style={{width:'100%',fontFamily:'monospace',fontSize:11}} />
                    </div>
                    <div className="form-group" style={{marginBottom:0}}>
                      <label style={{fontSize:11,marginBottom:4,display:'block'}}>Chat ID</label>
                      <input type="text" placeholder="填入你的 Chat ID，如 -1003729962178"
                        value={tgConfig.chat_id}
                        onChange={e=>setTgConfig(p=>({...p,chat_id:e.target.value}))}
                        style={{width:'100%',fontFamily:'monospace',fontSize:11}} />
                    </div>
                    <div style={{display:'flex',gap:8,marginTop:4}}>
                      <button disabled={tgSaving} onClick={async()=>{
                        if(!tgConfig.token||!tgConfig.chat_id){showToast('Token和Chat ID不能为空','error');return;}
                        setTgSaving(true);
                        try{
                          const r=await authFetch('/api/telegram/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({token:tgConfig.token,chat_id:tgConfig.chat_id})});
                          const d=await r.json();
                          if(d.ok){setTgConfig(p=>({...p,token_set:true,enabled:true}));showToast('✅ Telegram配置已保存','success');}
                          else showToast(`❌ ${d.error}`,'error');
                        }catch(e){showToast(`保存失败: ${e.message}`,'error');}
                        finally{setTgSaving(false);}
                      }} style={{flex:1,padding:'7px',borderRadius:4,cursor:'pointer',fontSize:12,fontWeight:700,
                        background:'rgba(0,245,255,0.08)',border:'1px solid var(--cyan)',color:'var(--cyan)'}}>
                        {tgSaving?'保存中...':'💾 保存配置'}
                      </button>
                      <button onClick={async()=>{
                        try{
                          const r=await authFetch('/api/telegram/test',{method:'POST'});
                          const d=await r.json();
                          if(d.ok) showToast('📲 测试消息已发送','success');
                          else showToast(`❌ ${d.error}`,'error');
                        }catch(e){showToast(`请求失败: ${e.message}`,'error');}
                      }} style={{flex:1,padding:'7px',borderRadius:4,cursor:'pointer',fontSize:12,fontWeight:700,
                        background:'rgba(255,230,0,0.08)',border:'1px solid var(--yellow)',color:'var(--yellow)'}}>
                        📨 发送测试消息
                      </button>
                    </div>
                    <div style={{fontSize:10,color:'var(--text-dim)',marginTop:2}}>
                      通知内容：开仓📈 平仓✅/🔴 止损🔔 余额告警💸 熔断⛔ 心跳💓（每小时）
                    </div>
                  </div>
                </div>
              </div>
              )}
            </div>

          )}

          {/* ── 管理后台 ── */}
          {view === 'admin' && isAdmin && (
            <div style={{padding:24,maxWidth:900,margin:'0 auto'}}>
              <div style={{marginBottom:20,display:'flex',alignItems:'center',gap:12}}>
                <span style={{fontSize:22}}>🛡️</span>
                <h2 style={{background:'linear-gradient(135deg,#ffb400,#ff6b00)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent',backgroundClip:'text',fontSize:20,fontWeight:900,letterSpacing:2,margin:0}}>管理后台</h2>
              </div>

              {/* Tab */}
              <div style={{display:'flex',gap:4,marginBottom:20,background:'rgba(255,255,255,0.04)',borderRadius:8,padding:4,width:'fit-content'}}>
                {[['gen','生成授权码'],['licenses','授权码列表'],['users','用户列表']].map(([k,label])=>(
                  <button key={k} onClick={()=>{ setAdminTab(k); loadAdminData(k); }}
                    style={{padding:'7px 18px',borderRadius:6,border:'none',cursor:'pointer',fontSize:13,fontWeight:600,
                      background: adminTab===k ? 'linear-gradient(135deg,#ffb400,#ff6b00)' : 'transparent',
                      color: adminTab===k ? '#000' : 'rgba(255,255,255,0.5)',transition:'all .2s'}}>
                    {label}
                  </button>
                ))}
              </div>

              {/* ── 生成授权码 ── */}
              {adminTab === 'gen' && (
                <div style={{display:'flex',flexDirection:'column',gap:16}}>
                  <div style={{background:'rgba(255,180,0,0.06)',border:'1px solid rgba(255,180,0,0.2)',borderRadius:10,padding:20}}>
                    <div style={{fontWeight:700,color:'#ffb400',marginBottom:16,fontSize:15}}>批量生成授权码</div>
                    <div style={{display:'flex',gap:12,alignItems:'flex-end',flexWrap:'wrap'}}>
                      <div>
                        <div style={{fontSize:12,color:'rgba(255,255,255,0.5)',marginBottom:6}}>数量</div>
                        <input type="number" min="1" max="100" value={adminGenCount}
                          onChange={e=>setAdminGenCount(Math.min(100,Math.max(1,+e.target.value)))}
                          style={{width:80,padding:'8px 10px',background:'rgba(255,255,255,0.07)',border:'1px solid rgba(255,255,255,0.15)',borderRadius:6,color:'#fff',fontSize:14,textAlign:'center'}}/>
                      </div>
                      <div>
                        <div style={{fontSize:12,color:'rgba(255,255,255,0.5)',marginBottom:6}}>有效天数</div>
                        <select value={adminGenDays} onChange={e=>setAdminGenDays(+e.target.value)}
                          style={{padding:'8px 10px',background:'rgba(20,20,40,0.95)',border:'1px solid rgba(255,255,255,0.15)',borderRadius:6,color:'#fff',fontSize:13}}>
                          {[7,14,30,60,90,180,365].map(d=>(
                            <option key={d} value={d}>{d}天</option>
                          ))}
                        </select>
                      </div>
                      <button onClick={handleGenLicense} disabled={adminGenLoading}
                        style={{padding:'8px 24px',background:'linear-gradient(135deg,#ffb400,#ff6b00)',border:'none',borderRadius:6,color:'#000',fontWeight:700,fontSize:14,cursor:'pointer',opacity:adminGenLoading?.6:1}}>
                        {adminGenLoading ? '⏳ 生成中...' : '⚡ 生成'}
                      </button>
                    </div>
                  </div>

                  {adminNewCodes.length > 0 && (
                    <div style={{background:'rgba(0,245,100,0.06)',border:'1px solid rgba(0,245,100,0.2)',borderRadius:10,padding:20}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                        <span style={{fontWeight:700,color:'#00f564',fontSize:14}}>✅ 已生成 {adminNewCodes.length} 个授权码</span>
                        <button onClick={()=>{
                          navigator.clipboard.writeText(adminNewCodes.join('\n'));
                          showToast('已复制到剪贴板','success');
                        }} style={{padding:'4px 12px',background:'rgba(0,245,100,0.1)',border:'1px solid rgba(0,245,100,0.3)',borderRadius:4,color:'#00f564',cursor:'pointer',fontSize:12}}>
                          📋 全部复制
                        </button>
                      </div>
                      <div style={{display:'flex',flexDirection:'column',gap:6}}>
                        {adminNewCodes.map((code,i)=>(
                          <div key={i} style={{display:'flex',alignItems:'center',justifyContent:'space-between',background:'rgba(255,255,255,0.04)',borderRadius:6,padding:'8px 12px'}}>
                            <code style={{fontFamily:'monospace',fontSize:14,letterSpacing:2,color:'#e0e0e0'}}>{code}</code>
                            <button onClick={()=>{ navigator.clipboard.writeText(code); showToast('已复制','success'); }}
                              style={{background:'none',border:'none',color:'rgba(255,255,255,0.4)',cursor:'pointer',fontSize:16,padding:'0 4px'}}>📋</button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ── 授权码列表 ── */}
              {adminTab === 'licenses' && (
                <div>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                    <span style={{color:'rgba(255,255,255,0.5)',fontSize:13}}>共 {adminLicenses.length} 条</span>
                    <button onClick={()=>loadAdminData('licenses')} style={{padding:'4px 12px',background:'rgba(255,255,255,0.06)',border:'1px solid rgba(255,255,255,0.15)',borderRadius:4,color:'rgba(255,255,255,0.6)',cursor:'pointer',fontSize:12}}>刷新</button>
                  </div>
                  <div style={{overflowX:'auto'}}>
                    <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
                      <thead>
                        <tr style={{borderBottom:'1px solid rgba(255,255,255,0.1)'}}>
                          {['授权码','有效天数','状态','使用者','创建时间'].map(h=>(
                            <th key={h} style={{padding:'8px 12px',textAlign:'left',color:'rgba(255,255,255,0.4)',fontWeight:600,fontSize:11}}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {adminLicenses.map((lic,i)=>(
                          <tr key={i} style={{borderBottom:'1px solid rgba(255,255,255,0.05)',transition:'background .15s'}}
                            onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.03)'}
                            onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                            <td style={{padding:'8px 12px'}}>
                              <code style={{fontFamily:'monospace',fontSize:12,letterSpacing:1,color:'#e0e0e0'}}>{lic.code}</code>
                              <button onClick={()=>{ navigator.clipboard.writeText(lic.code); showToast('已复制','success'); }}
                                style={{background:'none',border:'none',color:'rgba(255,255,255,0.3)',cursor:'pointer',fontSize:12,marginLeft:6}}>📋</button>
                            </td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.6)'}}>{lic.days}天</td>
                            <td style={{padding:'8px 12px'}}>
                              <span style={{fontSize:11,padding:'2px 8px',borderRadius:10,
                                background: lic.used_by ? 'rgba(0,245,100,0.1)' : 'rgba(255,180,0,0.1)',
                                color: lic.used_by ? '#00f564' : '#ffb400',
                                border: `1px solid ${lic.used_by ? 'rgba(0,245,100,0.3)' : 'rgba(255,180,0,0.3)'}`}}>
                                {lic.used_by ? '已使用' : '未使用'}
                              </span>
                            </td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.5)'}}>{lic.username || '—'}</td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.4)',fontSize:11}}>{(lic.created_at||'').slice(0,16)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {adminLicenses.length === 0 && <div style={{textAlign:'center',padding:40,color:'rgba(255,255,255,0.3)'}}>暂无授权码</div>}
                  </div>
                </div>
              )}

              {/* ── 用户列表 ── */}
              {adminTab === 'users' && (
                <div>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:12}}>
                    <span style={{color:'rgba(255,255,255,0.5)',fontSize:13}}>共 {adminUsers.length} 位用户</span>
                    <button onClick={()=>loadAdminData('users')} style={{padding:'4px 12px',background:'rgba(255,255,255,0.06)',border:'1px solid rgba(255,255,255,0.15)',borderRadius:4,color:'rgba(255,255,255,0.6)',cursor:'pointer',fontSize:12}}>刷新</button>
                  </div>
                  <div style={{overflowX:'auto'}}>
                    <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
                      <thead>
                        <tr style={{borderBottom:'1px solid rgba(255,255,255,0.1)'}}>
                          {['用户名','邮箱','状态','到期时间','注册时间','操作'].map(h=>(
                            <th key={h} style={{padding:'8px 12px',textAlign:'left',color:'rgba(255,255,255,0.4)',fontWeight:600,fontSize:11}}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {adminUsers.map((u,i)=>(
                          <tr key={i} style={{borderBottom:'1px solid rgba(255,255,255,0.05)'}}
                            onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.03)'}
                            onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                            <td style={{padding:'8px 12px'}}>
                              <span style={{color:'#e0e0e0',fontWeight:600}}>{u.username}</span>
                              {u.is_admin ? <span style={{marginLeft:6,fontSize:10,padding:'1px 6px',borderRadius:8,background:'rgba(255,180,0,0.15)',color:'#ffb400',border:'1px solid rgba(255,180,0,0.3)'}}>管理员</span> : null}
                            </td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.5)',fontSize:12}}>{u.email}</td>
                            <td style={{padding:'8px 12px'}}>
                              <span style={{fontSize:11,padding:'2px 8px',borderRadius:10,
                                background: u.is_active ? 'rgba(0,245,100,0.1)' : 'rgba(255,45,120,0.1)',
                                color: u.is_active ? '#00f564' : '#ff2d78',
                                border: `1px solid ${u.is_active ? 'rgba(0,245,100,0.3)' : 'rgba(255,45,120,0.3)'}`}}>
                                {u.is_active ? '已激活' : '未激活'}
                              </span>
                            </td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.5)',fontSize:12}}>
                              {u.expires_at ? (
                                <span style={{color: new Date(u.expires_at) < new Date() ? '#ff2d78' : 'rgba(255,255,255,0.5)'}}>
                                  {u.expires_at.slice(0,10)}
                                </span>
                              ) : '—'}
                            </td>
                            <td style={{padding:'8px 12px',color:'rgba(255,255,255,0.4)',fontSize:11}}>{(u.created_at||'').slice(0,16)}</td>
                            <td style={{padding:'8px 12px'}}>
                              <button onClick={()=>{setChangePwdTarget(u.username);setChangePwdVal('');setChangePwdMsg('');}} style={{fontSize:11,padding:'2px 8px',borderRadius:3,background:'rgba(0,245,255,0.08)',border:'1px solid rgba(0,245,255,0.3)',color:'var(--cyan)',cursor:'pointer'}}>改密码</button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {adminUsers.length === 0 && <div style={{textAlign:'center',padding:40,color:'rgba(255,255,255,0.3)'}}>暂无用户</div>}
                  </div>
                </div>
              )}
            </div>
          )}

        </div>
      </div>

      {/* ── 改密码弹窗（全局浮层）── */}
      {changePwdTarget && (
        <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,background:'rgba(0,0,0,0.75)',zIndex:9999,display:'flex',alignItems:'center',justifyContent:'center'}}>
          <div style={{background:'#0d1117',border:'1px solid rgba(0,245,255,0.35)',borderRadius:12,padding:28,width:340,boxShadow:'0 0 40px rgba(0,245,255,0.1)'}}>
            <div style={{fontSize:15,fontWeight:700,color:'var(--cyan)',marginBottom:16}}>🔑 重置密码：{changePwdTarget}</div>
            <input type="password" placeholder="输入新密码（至少8位含字母和数字）" value={changePwdVal}
              onChange={e=>setChangePwdVal(e.target.value)}
              onKeyDown={e=>e.key==='Enter'&&e.target.click()}
              style={{width:'100%',padding:'8px 10px',borderRadius:6,border:'1px solid rgba(255,255,255,0.15)',background:'rgba(255,255,255,0.05)',color:'#fff',fontSize:13,marginBottom:10,boxSizing:'border-box'}}/>
            {changePwdMsg && <div style={{fontSize:12,marginBottom:10,color:changePwdMsg.startsWith('✅')?'#00f564':'#ff2d78'}}>{changePwdMsg}</div>}
            <div style={{display:'flex',gap:8}}>
              <button onClick={async()=>{
                if(!changePwdVal||changePwdVal.length<8){setChangePwdMsg('❌ 密码至少8位');return;}
                const r=await authFetch('/api/admin/change-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:changePwdTarget,new_password:changePwdVal})});
                const d=await r.json();
                setChangePwdMsg(d.ok?`✅ ${d.msg}`:`❌ ${d.msg}`);
                if(d.ok){setChangePwdVal('');setTimeout(()=>setChangePwdTarget(''),1200);}
              }} style={{flex:1,padding:'8px',borderRadius:6,background:'rgba(0,245,255,0.1)',border:'1px solid var(--cyan)',color:'var(--cyan)',cursor:'pointer',fontWeight:600,fontSize:13}}>确认重置</button>
              <button onClick={()=>{setChangePwdTarget('');setChangePwdMsg('');setChangePwdVal('');}} style={{flex:1,padding:'8px',borderRadius:6,background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.15)',color:'rgba(255,255,255,0.6)',cursor:'pointer',fontSize:13}}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
