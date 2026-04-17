# API Documentation

Complete REST API reference for the trading system.

## Base URL

```
Production: https://api.trading.company.com/v1
Staging: https://staging-api.trading.company.com/v1
```

## Authentication

All API requests require authentication via JWT bearer token.

```bash
# Request
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" https://api.trading.company.com/v1/trades

# Response
HTTP/1.1 200 OK
Content-Type: application/json
```

## Rate Limiting

- **Standard**: 1000 requests per minute
- **Elevated**: 5000 requests per minute (on request)
- **Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field: amount",
    "details": {
      "field": "amount",
      "reason": "required"
    }
  },
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | Status | Description |
|------|--------|-------------|
| INVALID_REQUEST | 400 | Invalid request parameters |
| UNAUTHORIZED | 401 | Missing or invalid token |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| CONFLICT | 409 | Resource conflict |
| RATE_LIMITED | 429 | Rate limit exceeded |
| INTERNAL_ERROR | 500 | Server error |

---

## Endpoints

### Trading Endpoints

#### GET /trades

Retrieve trade history.

**Parameters**:
```
offset (optional): Default 0, max 10000
limit (optional): Default 100, max 1000
symbol (optional): Filter by symbol (e.g., "ETHUSD")
status (optional): Filter by status (open, closed, pending)
side (optional): Filter by side (buy, sell)
start_time (optional): Filter from timestamp
end_time (optional): Filter until timestamp
order (optional): Sort order (asc, desc) - default desc
```

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/trades?limit=50&status=closed" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example Response** (200):
```json
{
  "data": [
    {
      "id": "trade_abc123",
      "symbol": "ETHUSD",
      "side": "buy",
      "quantity": 10.5,
      "entry_price": 2100.50,
      "current_price": 2150.75,
      "pnl": 528.625,
      "pnl_percent": 2.38,
      "status": "open",
      "strategy": "trend_follow",
      "exchange": "hyperliquid",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z",
      "metadata": {
        "signal_strength": 0.85,
        "risk_score": 0.3
      }
    }
  ],
  "pagination": {
    "total": 1500,
    "offset": 0,
    "limit": 50,
    "has_more": true
  }
}
```

---

#### POST /trades/execute

Execute a new trade.

**Request Body**:
```json
{
  "symbol": "ETHUSD",
  "side": "buy",
  "quantity": 10.5,
  "price": 2100.50,
  "order_type": "limit",
  "strategy": "trend_follow",
  "exchange": "hyperliquid",
  "risk_limit": 1000,
  "timeout_seconds": 30,
  "metadata": {
    "signal_strength": 0.85,
    "confidence": 0.9
  }
}
```

**Validation Rules**:
- `symbol`: Required, valid exchange symbol
- `side`: Required, "buy" or "sell"
- `quantity`: Required, positive number, format = 2 decimals max
- `price`: Required for limit orders, positive number
- `order_type`: "limit" or "market"
- `strategy`: Required, registered strategy name

**Example Request**:
```bash
curl -X POST "https://api.trading.company.com/v1/trades/execute" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSD",
    "side": "buy",
    "quantity": 10.5,
    "price": 2100.50,
    "order_type": "limit",
    "strategy": "trend_follow",
    "exchange": "hyperliquid"
  }'
```

**Success Response** (201):
```json
{
  "data": {
    "trade_id": "trade_abc123",
    "status": "pending",
    "created_at": "2024-01-15T10:30:00Z",
    "message": "Trade order submitted successfully"
  }
}
```

**Error Response** (400):
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Insufficient balance for this trade",
    "details": {
      "required": 22050.50,
      "available": 15000.00
    }
  }
}
```

---

#### GET /trades/{trade_id}

Get details for a specific trade.

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/trades/trade_abc123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "id": "trade_abc123",
    "symbol": "ETHUSD",
    "side": "buy",
    "quantity": 10.5,
    "entry_price": 2100.50,
    "current_price": 2150.75,
    "pnl": 528.625,
    "status": "open",
    "orders": [
      {
        "order_id": "order_1",
        "quantity": 10.5,
        "price": 2100.50,
        "filled": 10.5,
        "status": "filled",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:35:00Z"
  }
}
```

---

#### POST /trades/{trade_id}/close

Close an open trade.

**Request Body**:
```json
{
  "close_price": 2150.75,
  "reason": "stop_loss"
}
```

**Example Request**:
```bash
curl -X POST "https://api.trading.company.com/v1/trades/trade_abc123/close" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "close_price": 2150.75,
    "reason": "manual"
  }'
```

**Response** (200):
```json
{
  "data": {
    "trade_id": "trade_abc123",
    "status": "closed",
    "exit_price": 2150.75,
    "pnl": 528.625,
    "pnl_percent": 2.38,
    "closed_at": "2024-01-15T10:40:00Z"
  }
}
```

---

### Positions Endpoints

#### GET /positions

Get current positions.

**Parameters**:
```
symbol (optional): Filter by symbol
status (optional): Filter by status (open, closed)
```

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/positions" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": [
    {
      "position_id": "pos_123",
      "symbol": "ETHUSD",
      "size": 10.5,
      "entry_price": 2100.50,
      "current_price": 2150.75,
      "unrealized_pnl": 528.625,
      "unrealized_pnl_percent": 2.38,
      "side": "long",
      "status": "open",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:35:00Z"
    }
  ],
  "summary": {
    "total_positions": 1,
    "total_value_usd": 22550.875,
    "total_unrealized_pnl": 528.625,
    "total_unrealized_pnl_percent": 2.38,
    "total_exposure_percent": 25.5
  }
}
```

---

#### POST /positions/reduce

Reduce position size.

**Request Body**:
```json
{
  "symbol": "ETHUSD",
  "reduction_percent": 50
}
```

**Response** (200):
```json
{
  "data": {
    "position_id": "pos_123",
    "new_size": 5.25,
    "reduction": 5.25,
    "reduction_value_usd": 11275.4375
  }
}
```

---

### Risk Endpoints

#### GET /risk/metrics

Get current risk metrics.

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/risk/metrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "total_exposure_percent": 25.5,
    "drawdown_percent": 5.2,
    "var_95_percent": 3.1,
    "var_99_percent": 5.8,
    "max_drawdown_percent": 8.7,
    "portfolio_volatility": 2.3,
    "sharpe_ratio": 1.85,
    "win_rate_percent": 58.5,
    "profit_factor": 2.1,
    "trades_today": 12,
    "trades_week": 87,
    "trades_month": 342
  }
}
```

---

#### GET /risk/var

Calculate Value at Risk.

**Parameters**:
```
confidence (optional): Default 95, values: 90, 95, 99
period_days (optional): Default 30, values: 7, 30, 90
```

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/risk/var?confidence=95&period_days=30" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "var_95": 3100.50,
    "var_99": 5800.25,
    "confidence": 95,
    "period_days": 30,
    "portfolio_value": 100000,
    "var_percent": 3.1
  }
}
```

---

### Metrics Endpoints

#### GET /metrics/pnl

Get P&L metrics.

**Parameters**:
```
period (optional): Default "today", values: today, week, month, all
```

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/metrics/pnl?period=today" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "pnl_today": 1250.50,
    "pnl_week": 5620.75,
    "pnl_month": 12450.25,
    "pnl_ytd": 45800.00,
    "pnl_all_time": 125450.50,
    "trades_today": 12,
    "win_rate_today": 66.67,
    "average_win": 185.50,
    "average_loss": -120.75,
    "largest_win": 520.25,
    "largest_loss": -350.00
  }
}
```

---

#### GET /metrics/performance

Get performance metrics.

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/metrics/performance" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "api_response_time_p50_ms": 45,
    "api_response_time_p95_ms": 250,
    "api_response_time_p99_ms": 850,
    "api_error_rate_percent": 0.05,
    "database_connections": 18,
    "cache_hit_rate_percent": 94.5,
    "memory_usage_mb": 625,
    "cpu_usage_percent": 35
  }
}
```

---

### Alerts Endpoints

#### GET /alerts

Get alerts.

**Parameters**:
```
severity (optional): Filter by severity (info, warning, error, critical)
limit (optional): Default 100, max 1000
offset (optional): Default 0
```

**Example Request**:
```bash
curl -X GET "https://api.trading.company.com/v1/alerts?severity=critical&limit=50" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": [
    {
      "alert_id": "alert_123",
      "title": "High Drawdown Detected",
      "message": "Drawdown exceeded 20% threshold",
      "severity": "critical",
      "tags": {
        "strategy": "trend_follow",
        "threshold": "20%"
      },
      "created_at": "2024-01-15T10:40:00Z",
      "acknowledged": false
    }
  ],
  "pagination": {
    "total": 5,
    "limit": 50,
    "offset": 0
  }
}
```

---

#### POST /alerts/{alert_id}/acknowledge

Acknowledge an alert.

**Example Request**:
```bash
curl -X POST "https://api.trading.company.com/v1/alerts/alert_123/acknowledge" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Response** (200):
```json
{
  "data": {
    "alert_id": "alert_123",
    "acknowledged": true,
    "acknowledged_at": "2024-01-15T10:42:00Z"
  }
}
```

---

### Health Endpoints

#### GET /health

Health check endpoint.

**Response** (200):
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:45:00Z",
  "version": "2.0.0"
}
```

---

#### GET /ready

Readiness probe.

**Response** (200):
```json
{
  "ready": true,
  "dependencies": {
    "database": "healthy",
    "redis": "healthy",
    "api": "healthy"
  }
}
```

---

## Webhooks

### Trade Execution Webhook

Sent when a trade is executed.

```json
{
  "event_type": "trade.executed",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "trade_id": "trade_abc123",
    "symbol": "ETHUSD",
    "side": "buy",
    "quantity": 10.5,
    "price": 2100.50,
    "status": "filled"
  }
}
```

### Alert Webhook

Sent when an alert is triggered.

```json
{
  "event_type": "alert.triggered",
  "timestamp": "2024-01-15T10:40:00Z",
  "data": {
    "alert_id": "alert_123",
    "title": "High Drawdown",
    "severity": "critical",
    "value": 22.5,
    "threshold": 20
  }
}
```

---

## Rate Limiting

Requests are limited to:
- **1000 requests per minute** for standard users
- **5000 requests per minute** for premium accounts
- **Unlimited** for internal services

When rate limited, receive:
```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705318800
```

---

## Pagination

List endpoints support pagination:

```json
{
  "data": [...],
  "pagination": {
    "total": 1500,
    "limit": 100,
    "offset": 0,
    "has_more": true,
    "next_offset": 100
  }
}
```

---

## Examples

### Complete Trading Example

```bash
# 1. Get current positions
curl -X GET "https://api.trading.company.com/v1/positions" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" | jq .

# 2. Check risk metrics
curl -X GET "https://api.trading.company.com/v1/risk/metrics" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" | jq .

# 3. Execute trade
curl -X POST "https://api.trading.company.com/v1/trades/execute" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "ETHUSD",
    "side": "buy",
    "quantity": 10,
    "price": 2100,
    "order_type": "limit",
    "strategy": "trend_follow",
    "exchange": "hyperliquid"
  }' | jq .

# 4. Monitor trade
curl -X GET "https://api.trading.company.com/v1/trades/trade_abc123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" | jq .

# 5. Close trade
curl -X POST "https://api.trading.company.com/v1/trades/trade_abc123/close" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "close_price": 2150,
    "reason": "manual"
  }' | jq .
```

---

## SDKs

- **Python**: `pip install trading-api-sdk`
- **JavaScript**: `npm install trading-api-sdk`
- **Go**: `go get github.com/company/trading-api-sdk`

---

## Support

- **Documentation**: https://docs.trading.company.com
- **Status Page**: https://status.trading.company.com
- **Issues**: support@trading.company.com
