"""
Trading state models - Core data structures for the trading system
"""

from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TradingState:
    """Global state management for the trading system"""

    def __init__(self):
        self.logged_in: bool = False
        self.user: str = ""        # Main account address
        self.signer: str = ""      # API signer address

        # Account data
        self.balance: float = 0.0
        self.available: float = 0.0
        self.positions: List[Dict] = []
        self.open_orders: List[Dict] = []

        # Market data
        self.market_prices: Dict[str, float] = {}
        self.orderbooks: Dict[str, Dict] = {}
        self.recent_trades_data: Dict[str, List] = {}

        # Trading tasks
        self.auto_trading: bool = False
        self.trading_task: Optional[object] = None
        self.ws_task: Optional[object] = None
        self.account_sync_task: Optional[object] = None
        self.kline_task: Optional[object] = None

        # Trading settings
        self.settings: Dict = self._default_settings()

        # Performance metrics
        self.perf: Dict = self._default_perf()

        # Trade logs
        self.trade_logs: List[Dict] = []

    @staticmethod
    def _default_settings() -> Dict:
        """Get default trading settings"""
        return {
            "strategy": "multi",
            "symbol": "BTCUSDT",
            "leverage": 2,
            "trade_size_usd": 10,
            "min_confidence": 0.62,
            "stop_loss_pct": 0.012,
            "take_profit_pct": 0.028,
            "enable_long": True,
            "enable_short": True,
            "max_open_positions": 3,
            "max_daily_loss_usd": 50,
            "cancel_on_reverse": True,
            "hft_interval_ms": 500,
            "hft_mode": "balanced",
            # EMA
            "ema_fast": 5,
            "ema_slow": 20,
            "ema_long": 60,
            # MACD
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            # RSI
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
            # Bollinger Bands
            "bb_period": 20,
            "bb_std": 2.0,
            # Breakout
            "breakout_period": 20,
            "breakout_vol_mult": 1.5,
            # Active symbols
            "active_symbols": ["BTCUSDT"],
            "symbol_settings": {},
        }

    @staticmethod
    def _default_perf() -> Dict:
        """Get default performance metrics"""
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0,
            "daily_pnl": 0.0,
            "win_rate": 0,
            "total_pnl_pct": 0.0,
            "daily_pnl_pct": 0.0,
            "daily_history": {},
        }

    def reset(self):
        """Reset to logged-out state"""
        self.logged_in = False
        self.user = ""
        self.signer = ""
        self.balance = 0.0
        self.available = 0.0
        self.positions = []
        self.open_orders = []
        logger.info("✅ Trading state reset")

    def get_summary(self) -> Dict:
        """Get safe-to-log summary of current state"""
        return {
            "logged_in": self.logged_in,
            "user": self.user[:10] + "..." if self.user else "",
            "balance": self.balance,
            "positions_count": len(self.positions),
            "orders_count": len(self.open_orders),
            "trading": self.auto_trading,
        }


class PositionTracker:
    """Track open and closed positions with PnL calculations"""

    class Entry:
        """Position entry record"""
        def __init__(self, symbol: str, side: str, price: float, qty: float):
            self.symbol = symbol
            self.side = side  # LONG or SHORT
            self.entry_price = price
            self.qty = qty
            self.entry_cost = price * qty
            self.closed_pnl = 0.0
            self.peak_price = price
            self.lowest_price = price

    def __init__(self):
        self.entries: Dict[str, List] = {}
        self.closed: List[Dict] = []

    def add_entry(self, symbol: str, side: str, price: float, qty: float):
        """Add new position entry"""
        if symbol not in self.entries:
            self.entries[symbol] = []

        entry = self.Entry(symbol, side, price, qty)
        self.entries[symbol].append(entry)
        logger.debug(f"📍 Position entry added: {symbol} {side} @ {price}")

    def update_prices(self, symbol: str, current_price: float):
        """Update peak/lowest prices for PnL tracking"""
        if symbol not in self.entries:
            return

        for entry in self.entries[symbol]:
            entry.peak_price = max(entry.peak_price, current_price)
            entry.lowest_price = min(entry.lowest_price, current_price)

    def calculate_pnl(self, symbol: str, current_price: float, side: str) -> float:
        """Calculate current PnL for a position"""
        if symbol not in self.entries:
            return 0.0

        total_pnl = 0.0
        for entry in self.entries[symbol]:
            if entry.side == side:
                if side == "LONG":
                    pnl = (current_price - entry.entry_price) * entry.qty
                else:  # SHORT
                    pnl = (entry.entry_price - current_price) * entry.qty
                total_pnl += pnl

        return total_pnl

    def close_position(self, symbol: str, exit_price: float) -> float:
        """Close all entries for a symbol and return PnL"""
        if symbol not in self.entries:
            return 0.0

        total_pnl = 0.0
        for entry in self.entries[symbol]:
            if entry.side == "LONG":
                pnl = (exit_price - entry.entry_price) * entry.qty
            else:  # SHORT
                pnl = (entry.entry_price - exit_price) * entry.qty

            total_pnl += pnl
            entry.closed_pnl = pnl

        # Move to closed and clear entries
        self.closed.extend(self.entries[symbol])
        del self.entries[symbol]

        logger.info(f"✅ Position closed: {symbol}, PnL: {total_pnl:.2f}")
        return total_pnl

    def get_position_summary(self, symbol: str) -> Dict:
        """Get summary of current position"""
        if symbol not in self.entries or not self.entries[symbol]:
            return {"symbol": symbol, "open": False}

        entries = self.entries[symbol]
        total_qty = sum(e.qty for e in entries)
        avg_price = sum(e.entry_price * e.qty for e in entries) / total_qty if total_qty > 0 else 0

        return {
            "symbol": symbol,
            "open": True,
            "side": entries[0].side,
            "qty": total_qty,
            "avg_entry": avg_price,
            "entries": len(entries),
        }
