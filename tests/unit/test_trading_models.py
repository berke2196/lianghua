"""
Unit tests for trading models
"""

import pytest
from datetime import datetime
from src.models.trading_state import TradingState, PositionTracker


class TestTradingState:
    """Test TradingState class"""

    def test_initialization(self):
        """Test TradingState initialization"""
        state = TradingState()
        assert state.logged_in == False
        assert state.user == ""
        assert state.balance == 0.0
        assert len(state.settings) > 0

    def test_default_settings(self):
        """Test default settings are properly initialized"""
        state = TradingState()
        assert state.settings['leverage'] == 2
        assert state.settings['strategy'] == 'multi'
        assert state.settings['enable_long'] == True
        assert state.settings['enable_short'] == True

    def test_reset_state(self):
        """Test state reset functionality"""
        state = TradingState()
        state.logged_in = True
        state.user = "test_user"
        state.balance = 1000.0

        state.reset()

        assert state.logged_in == False
        assert state.user == ""
        assert state.balance == 0.0

    def test_get_summary(self):
        """Test get_summary returns safe-to-log state"""
        state = TradingState()
        state.logged_in = True
        state.user = "test_user_very_long"
        state.balance = 500.0

        summary = state.get_summary()

        assert summary['logged_in'] == True
        assert summary['balance'] == 500.0
        assert len(summary['user']) < len(state.user)  # Should be truncated


class TestPositionTracker:
    """Test PositionTracker class"""

    def test_initialization(self):
        """Test PositionTracker initialization"""
        tracker = PositionTracker()
        assert len(tracker.entries) == 0
        assert len(tracker.closed) == 0

    def test_add_entry(self):
        """Test adding position entry"""
        tracker = PositionTracker()
        tracker.add_entry("BTCUSDT", "LONG", 45000.0, 0.1)

        assert "BTCUSDT" in tracker.entries
        assert len(tracker.entries["BTCUSDT"]) == 1

        entry = tracker.entries["BTCUSDT"][0]
        assert entry.symbol == "BTCUSDT"
        assert entry.side == "LONG"
        assert entry.entry_price == 45000.0
        assert entry.qty == 0.1

    def test_calculate_pnl_long(self):
        """Test PnL calculation for long position"""
        tracker = PositionTracker()
        tracker.add_entry("BTCUSDT", "LONG", 45000.0, 0.1)

        pnl = tracker.calculate_pnl("BTCUSDT", 46000.0, "LONG")
        expected_pnl = (46000.0 - 45000.0) * 0.1
        assert abs(pnl - expected_pnl) < 0.01

    def test_calculate_pnl_short(self):
        """Test PnL calculation for short position"""
        tracker = PositionTracker()
        tracker.add_entry("ETHUSDT", "SHORT", 2500.0, 1.0)

        pnl = tracker.calculate_pnl("ETHUSDT", 2400.0, "SHORT")
        expected_pnl = (2500.0 - 2400.0) * 1.0
        assert abs(pnl - expected_pnl) < 0.01

    def test_close_position_profit(self):
        """Test closing position with profit"""
        tracker = PositionTracker()
        tracker.add_entry("BTCUSDT", "LONG", 45000.0, 0.1)

        pnl = tracker.close_position("BTCUSDT", 46000.0)
        expected_pnl = (46000.0 - 45000.0) * 0.1

        assert abs(pnl - expected_pnl) < 0.01
        assert "BTCUSDT" not in tracker.entries
        assert len(tracker.closed) == 1

    def test_close_position_loss(self):
        """Test closing position with loss"""
        tracker = PositionTracker()
        tracker.add_entry("ETHUSDT", "LONG", 2500.0, 1.0)

        pnl = tracker.close_position("ETHUSDT", 2400.0)
        expected_pnl = (2400.0 - 2500.0) * 1.0

        assert abs(pnl - expected_pnl) < 0.01
        assert pnl < 0  # Should be negative

    def test_multiple_entries(self):
        """Test handling multiple entries for same symbol"""
        tracker = PositionTracker()
        tracker.add_entry("BTCUSDT", "LONG", 45000.0, 0.1)
        tracker.add_entry("BTCUSDT", "LONG", 45500.0, 0.05)

        assert len(tracker.entries["BTCUSDT"]) == 2

        summary = tracker.get_position_summary("BTCUSDT")
        assert summary['open'] == True
        assert summary['entries'] == 2

    def test_update_peak_price(self):
        """Test peak price tracking"""
        tracker = PositionTracker()
        tracker.add_entry("BTCUSDT", "LONG", 45000.0, 0.1)

        entry = tracker.entries["BTCUSDT"][0]
        assert entry.peak_price == 45000.0

        tracker.update_prices("BTCUSDT", 46000.0)
        assert entry.peak_price == 46000.0

        tracker.update_prices("BTCUSDT", 45500.0)
        assert entry.peak_price == 46000.0  # Should not decrease


@pytest.mark.parametrize("side,entry_price,current_price,expected_pnl", [
    ("LONG", 100, 110, 10),
    ("LONG", 100, 90, -10),
    ("SHORT", 100, 90, 10),
    ("SHORT", 100, 110, -10),
])
def test_pnl_calculation_parametrized(side, entry_price, current_price, expected_pnl):
    """Test PnL calculation with different scenarios"""
    tracker = PositionTracker()
    tracker.add_entry("TEST", side, entry_price, 1.0)

    pnl = tracker.calculate_pnl("TEST", current_price, side)
    assert abs(pnl - expected_pnl) < 0.01
