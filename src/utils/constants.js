/**
 * Application constants and configuration
 */

// API Configuration
export const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000';
export const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:8000/ws/frontend';
export const API_TIMEOUT = parseInt(process.env.REACT_APP_API_TIMEOUT || 30000);

// Trading Constants
export const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT'];
export const STRATEGIES = ['multi', 'macd', 'rsi', 'bollinger', 'breakout', 'mm'];
export const HFT_MODES = ['conservative', 'balanced', 'aggressive'];

// Timeframes
export const TIMEFRAMES = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '30m': 1800,
  '1h': 3600,
  '4h': 14400,
  '1d': 86400,
};

// Trading Limits
export const MIN_LEVERAGE = 1;
export const MAX_LEVERAGE = 125;
export const MIN_TRADE_SIZE = 1;
export const MAX_TRADE_SIZE = 10000;

// Colors
export const COLORS = {
  primary: '#40c4ff',
  success: '#00e676',
  warning: '#ffd600',
  error: '#ff5252',
  info: '#2196f3',
  background: '#0a0e27',
  surface: '#1a1f3a',
  text: '#ffffff',
  textSecondary: '#b0bec5',
};

// Chart Options
export const CHART_OPTIONS = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: true,
      labels: {
        color: COLORS.text,
      },
    },
  },
  scales: {
    y: {
      ticks: {
        color: COLORS.textSecondary,
      },
      grid: {
        color: 'rgba(255,255,255,0.1)',
      },
    },
    x: {
      ticks: {
        color: COLORS.textSecondary,
      },
      grid: {
        color: 'rgba(255,255,255,0.1)',
      },
    },
  },
};

// Default Settings
export const DEFAULT_SETTINGS = {
  strategy: 'multi',
  symbol: 'BTCUSDT',
  leverage: 2,
  trade_size_usd: 10,
  min_confidence: 0.70,
  stop_loss_pct: 0.012,
  take_profit_pct: 0.028,
  enable_long: true,
  enable_short: true,
  max_open_positions: 3,
  max_daily_loss_usd: 50,
  hft_interval_ms: 500,
  hft_mode: 'balanced',
  ema_fast: 5,
  ema_slow: 20,
  ema_long: 60,
  macd_fast: 12,
  macd_slow: 26,
  macd_signal: 9,
  rsi_period: 14,
  rsi_oversold: 30,
  rsi_overbought: 70,
  bb_period: 20,
  bb_std: 2.0,
  breakout_period: 20,
  breakout_vol_mult: 1.5,
};

// API Endpoints
export const ENDPOINTS = {
  // Auth
  LOGIN: '/api/auth/login',
  LOGOUT: '/api/auth/logout',

  // Trading
  START_TRADING: '/api/trading/start',
  STOP_TRADING: '/api/trading/stop',
  TEST_ORDER: '/api/trading/test_order',
  CLOSE_POSITION: '/api/trading/close_position',
  CANCEL_ORDERS: '/api/trading/cancel_orders',

  // Status
  HEALTH: '/api/health',
  STATUS: '/api/trading/status',
  LOGS: '/api/trading/logs',
  INDICATORS: '/api/trading/indicators_all',

  // Settings
  GET_SETTINGS: '/api/settings',
  UPDATE_SETTINGS: '/api/settings',
  SYMBOL_SETTINGS: '/api/settings/symbol',

  // Market
  ORDERBOOK: '/api/market/orderbook',

  // WebSocket
  WS: '/ws/frontend',
};

// Message Types (WebSocket)
export const MESSAGE_TYPES = {
  ACCOUNT_UPDATE: 'account_update',
  PRICES: 'prices',
  ORDERBOOK: 'orderbook',
  SETTINGS_UPDATED: 'settings_updated',
  NEW_TRADE: 'new_trade',
  PERFORMANCE: 'performance',
  SIGNAL_UPDATE: 'signal_update',
  LOG: 'log',
  ALERT: 'alert',
  WS_STATUS: 'ws_status',
};

// Storage Keys
export const STORAGE_KEYS = {
  SETTINGS: 'trading_settings',
  LAST_LOGIN: 'last_login_user',
  THEME: 'theme_mode',
  NOTIFICATIONS: 'notifications_enabled',
};

// Notification Types
export const NOTIFICATION_TYPES = {
  SUCCESS: 'success',
  ERROR: 'error',
  WARNING: 'warning',
  INFO: 'info',
};
