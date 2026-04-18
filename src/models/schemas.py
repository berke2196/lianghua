"""
Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List


class LoginRequest(BaseModel):
    """Login request schema"""
    user: str = Field(..., description="Main account address")
    signer: str = Field(..., description="API signer address")
    private_key: str = Field(..., description="Private key for signing")

    @validator("user", "signer", "private_key")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()


class TradingSettings(BaseModel):
    """Trading settings schema"""
    strategy: str = "multi"
    symbol: str = "BTCUSDT"
    leverage: int = 2
    trade_size_usd: float = 10
    min_confidence: float = 0.62
    stop_loss_pct: float = 0.012
    take_profit_pct: float = 0.028
    enable_long: bool = True
    enable_short: bool = True
    max_open_positions: int = 3
    max_daily_loss_usd: float = 50
    hft_interval_ms: int = 500
    hft_mode: str = "balanced"


class TradeLog(BaseModel):
    """Trade log entry"""
    timestamp: str
    symbol: str
    side: str
    price: float
    size: float
    strategy: str
    confidence: float
    status: str
    pnl: Optional[float] = None


class AccountUpdate(BaseModel):
    """Account update message"""
    logged_in: bool
    balance: float
    available: float
    positions: List[Dict[str, Any]] = []
    open_orders: List[Dict[str, Any]] = []


class PerformanceMetrics(BaseModel):
    """Performance metrics"""
    total_trades: int
    wins: int
    losses: int
    total_pnl: float
    daily_pnl: float
    win_rate: float
    total_pnl_pct: float


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    backend: str = "ok"
    database: str = "ok"
    version: str = "1.0.0"
