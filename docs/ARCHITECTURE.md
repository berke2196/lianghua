# AsterDex HFT Trading System - Architecture

## Overview

AsterDex HFT Trading System is a high-frequency trading platform consisting of:
- **Backend**: Python FastAPI with async/await for optimal performance
- **Frontend**: React with modern hooks and component architecture  
- **Desktop**: Electron wrapper for native cross-platform application

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Desktop (Electron)                        │
│                   electron-main.js (94L)                     │
│                 + preload.js (Security IPC)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
           ┌─────────────┴─────────────┐
           ▼                            ▼
    ┌─────────────────┐        ┌────────────────────┐
    │ React Frontend  │        │ Python Backend     │
    │   (2,036L)      │◄──────►│   (1,823L)         │
    │   + Components  │ HTTP + │   + Async Tasks    │
    │   + Hooks       │ WebSocket  + Trading Engine │
    │   + Utils       │        │   + Market Data    │
    └─────────────────┘        └────────────────────┘
            │                           │
            │                           │
            ▼                           ▼
    ┌──────────────┐        ┌────────────────────┐
    │ localStorage │        │  AsterDex API v3   │
    │   (Client)   │        │  (EIP-712 signed)  │
    └──────────────┘        └────────────────────┘
                                    │
                                    ▼
                            ┌──────────────┐
                            │  Trade Data  │
                            │ (JSON store) │
                            └──────────────┘
```

## Backend Architecture

### Directory Structure

```
src/
├── models/
│   ├── trading_state.py       # TradingState, PositionTracker
│   ├── schemas.py             # Pydantic request/response models
│   └── __init__.py
├── api/
│   ├── auth.py               # Authentication endpoints
│   ├── trading.py            # Trading operations
│   ├── market.py             # Market data endpoints
│   ├── settings.py           # Configuration endpoints
│   ├── websocket.py          # WebSocket handlers
│   └── __init__.py
├── trading/
│   ├── engine.py             # HFT trading engine
│   ├── strategies.py         # Trading strategies
│   ├── indicators.py         # Technical indicators
│   ├── orders.py             # Order management
│   └── __init__.py
├── market/
│   ├── client.py             # AsterDex API client
│   ├── websocket.py          # Market data streams
│   ├── klines.py             # K-line data management
│   └── __init__.py
├── storage/
│   ├── history.py            # Trade persistence
│   └── __init__.py
└── utils/
    ├── logging.py            # Structured logging
    ├── security.py           # Key management
    ├── helpers.py            # Utility functions
    └── __init__.py
```

### Key Components

#### 1. TradingState (models/trading_state.py)
Global state management for:
- Authentication status
- Account balance and positions
- Market prices and orderbooks
- Active trading tasks
- Trading settings and performance metrics

```python
class TradingState:
    logged_in: bool
    user: str              # Main account
    balance: float
    positions: List[Dict]
    settings: Dict         # Trading parameters
    trade_logs: List[Dict] # History
```

#### 2. Async Task Management
Concurrent operations for:
- **account_sync_loop()**: Real-time balance/position updates (10s interval)
- **market_ws_loop()**: Market data via WebSocket
- **market_poll_loop()**: Fallback polling (if WS fails)
- **kline_refresh_loop()**: K-line data updates
- **hft_trading_loop()**: Main trading logic (100-500ms)

#### 3. Authentication
- EIP-712 structured signatures for signing
- Secure key storage with auto-expiration (1 hour)
- Private key cleared after logout
- Nonce-based replay attack prevention

#### 4. Trading Engine (trading/engine.py)
- 7-dimensional signal fusion:
  - Supertrend, EMA, MACD, RSI, VWAP, OBI, Momentum
- Multi-symbol support
- Risk management rules
- Position sizing
- Stop-loss/take-profit management

### API Endpoints (18 total)

| Category | Endpoint | Method |
|----------|----------|--------|
| Auth | `/api/auth/login` | POST |
| Auth | `/api/auth/logout` | POST |
| Trading | `/api/trading/start` | POST |
| Trading | `/api/trading/stop` | POST |
| Trading | `/api/trading/test_order` | POST |
| Market | `/api/market/orderbook` | GET |
| Status | `/api/health` | GET |
| Status | `/api/trading/status` | GET |
| Settings | `/api/settings` | GET/POST |
| WebSocket | `/ws/frontend` | WS |

## Frontend Architecture

### Component Structure

```
src/
├── components/
│   ├── ErrorBoundary.js         # Error handling
│   ├── LoginForm.js              # Authentication UI
│   ├── Dashboard.js              # Main trading view
│   ├── TradingControls.js        # Trading operations
│   ├── SettingsPanel.js          # Configuration
│   ├── TradeHistory.js           # Trade logs
│   ├── MarketData.js             # Price/chart display
│   └── PerformanceMetrics.js     # Stats visualization
├── hooks/
│   ├── useWebSocket.js           # WebSocket management
│   ├── useApi.js                 # HTTP requests
│   ├── useTrading.js             # Trading state
│   └── useSettings.js            # Settings management
├── context/
│   ├── TradingContext.js         # Global trading state
│   └── SettingsContext.js        # Settings state
├── utils/
│   ├── constants.js              # App constants
│   ├── helpers.js                # Utility functions
│   └── api.js                    # API client
├── styles/
│   ├── variables.css             # Theme variables
│   └── components.css            # Component styles
└── App.js                         # Root component
```

### Custom Hooks

#### useWebSocket
- Automatic reconnection with exponential backoff
- Message parsing and error handling
- Heartbeat/ping management

```javascript
const { connected, send } = useWebSocket(url, onMessage);
```

#### useApi
- HTTP request management
- Loading and error states
- Request retries

```javascript
const { request, loading, error } = useApi(baseUrl);
await request('/api/endpoint', { method: 'POST' });
```

#### useLocalStorage
- Persistent client-side state
- Automatic JSON serialization

```javascript
const [value, setValue] = useLocalStorage('key', initialValue);
```

### State Management

Uses React Context + Hooks (Zustand available for future enhancement):

```javascript
<TradingProvider>
  <SettingsProvider>
    <App />
  </SettingsProvider>
</TradingProvider>
```

## Data Flow

### Trading Flow
1. **Login** → User provides credentials
2. **Authenticate** → Backend validates with AsterDex
3. **Initialize** → Fetch balance, positions, open orders
4. **Market Stream** → WebSocket connects for real-time prices
5. **Signals** → Technical indicators generate trading signals
6. **Validation** → Risk management rules check trade viability
7. **Execution** → Order sent to exchange
8. **Monitoring** → Track position, update PnL
9. **Exit** → Stop-loss or take-profit triggered

### Real-time Updates
All data flows via WebSocket to ensure low-latency updates:

```python
{
  "type": "account_update",
  "data": {
    "balance": 1000,
    "positions": [...],
    "open_orders": [...]
  }
}
```

## Security Architecture

### Private Key Management
1. Received via HTTPS POST only
2. Stored in SecureKeyStore with auto-expiration
3. Used only for signing via context manager
4. Cleared explicitly on logout
5. Never logged or printed

### Authentication Flow
```
Client credentials
    ↓
HTTPS POST to /api/auth/login
    ↓
Backend validates with exchange API
    ↓
SecureKeyStore activation (1 hour TTL)
    ↓
WebSocket connection authorized
    ↓
Trading begins
```

### CORS Configuration
- **Allowed Origins**: `http://localhost:3000`, `http://localhost:8000`
- **Allowed Methods**: GET, POST, PUT, DELETE, OPTIONS
- **Allowed Headers**: Content-Type, Authorization
- Production: Configure via environment variables

### Electron Security
- Context isolation enabled
- Node integration disabled
- Sandbox enabled
- Web security enabled
- Secure preload.js bridge for IPC

## Performance Optimizations

1. **Connection Pooling**: Reused aiohttp.ClientSession
2. **Async I/O**: Non-blocking market data processing
3. **Per-Symbol Locks**: Prevents concurrent position conflicts
4. **WebSocket Broadcasting**: Efficient multi-client updates
5. **Debouncing**: UI updates throttled to 1 second
6. **Memoization**: React component optimization

## Deployment Architecture

### Development
```
localhost:3000  (React dev server)
localhost:8000  (FastAPI backend)
```

### Production
```
Docker containers:
- backend: FastAPI on port 8000
- frontend: Nginx serving static assets
- Optional: PostgreSQL for persistent storage
```

### Environment Variables
```
BACKEND_ASTER_BASE=https://fapi.asterdex.com
BACKEND_ASTER_WS=wss://fstream.asterdex.com
CORS_ORIGINS=https://yourdomain.com
LOG_LEVEL=INFO
```

## Scalability Considerations

1. **Horizontal Scaling**: Multiple backend instances behind load balancer
2. **Database**: Current JSON storage → Migrate to SQLite/PostgreSQL
3. **Caching**: Redis for price cache and session storage
4. **Message Queue**: Kafka for trade execution pipeline
5. **Monitoring**: Prometheus + Grafana for metrics

## Error Handling

- **Backend**: Custom exception hierarchy with proper HTTP status codes
- **Frontend**: Error boundaries for React errors + API error recovery
- **Network**: Automatic reconnection with exponential backoff
- **Trading**: Stop trading on API errors, alert user

## Testing Strategy

- **Backend**: pytest with 80%+ coverage
- **Frontend**: Jest + React Testing Library
- **E2E**: Selenium for full workflow testing
- **Security**: OWASP ZAP for vulnerability scanning

---

**Last Updated**: 2024  
**Version**: 2.0.0  
**Status**: Production-ready
