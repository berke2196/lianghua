"""
Configuration management for AsterDex HFT Trading System
Handles environment variables, defaults, and configuration validation
"""

import os
from typing import Optional, Dict, Any
from functools import lru_cache

# ─────────────────────────────────────────────
# Environment Variables with Defaults
# ─────────────────────────────────────────────

class Config:
    """Configuration singleton - loads from environment with sensible defaults"""

    # Backend API Configuration
    ASTER_BASE = os.getenv("BACKEND_ASTER_BASE", "https://fapi.asterdex.com")
    ASTER_WS = os.getenv("BACKEND_ASTER_WS", "wss://fstream.asterdex.com")

    # Server Configuration
    HOST = os.getenv("BACKEND_HOST", "localhost")
    PORT = int(os.getenv("BACKEND_PORT", 8000))
    RELOAD = os.getenv("BACKEND_RELOAD", "False").lower() == "true"

    # Security Configuration
    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000,http://127.0.0.1:8000"
    ).split(",")
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    CORS_HEADERS = ["Content-Type", "Authorization"]

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/trading.log")

    # Data Persistence
    HISTORY_FILE = os.getenv("HISTORY_FILE", "trade_history.db")
    BACKUP_DIR = os.getenv("BACKUP_DIR", "backups/")

    # Trading Defaults
    DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", 2))
    DEFAULT_TRADE_SIZE_USD = float(os.getenv("DEFAULT_TRADE_SIZE_USD", 10))
    DEFAULT_STOP_LOSS_PCT = float(os.getenv("DEFAULT_STOP_LOSS_PCT", 0.012))
    DEFAULT_TAKE_PROFIT_PCT = float(os.getenv("DEFAULT_TAKE_PROFIT_PCT", 0.028))
    MAX_DAILY_LOSS_USD = float(os.getenv("MAX_DAILY_LOSS_USD", 50))
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 3))

    # API Timeouts (seconds)
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", 10))
    WEBSOCKET_TIMEOUT = int(os.getenv("WEBSOCKET_TIMEOUT", 30))

    # Feature Flags
    ENABLE_PAPER_TRADING = os.getenv("ENABLE_PAPER_TRADING", "False").lower() == "true"
    ENABLE_BACKTESTING = os.getenv("ENABLE_BACKTESTING", "False").lower() == "true"

    @classmethod
    def validate(cls) -> bool:
        """Validate configuration values"""
        try:
            assert cls.PORT > 0 and cls.PORT < 65535, "Invalid port number"
            assert len(cls.CORS_ORIGINS) > 0, "CORS origins must not be empty"
            assert cls.API_TIMEOUT > 0, "API timeout must be positive"
            assert cls.DEFAULT_LEVERAGE > 0, "Leverage must be positive"
            return True
        except AssertionError as e:
            print(f"❌ Configuration validation failed: {e}")
            return False

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "backend": {
                "aster_base": cls.ASTER_BASE,
                "aster_ws": cls.ASTER_WS,
                "host": cls.HOST,
                "port": cls.PORT,
            },
            "security": {
                "cors_origins": cls.CORS_ORIGINS,
                "cors_methods": cls.CORS_METHODS,
            },
            "trading": {
                "default_leverage": cls.DEFAULT_LEVERAGE,
                "default_trade_size_usd": cls.DEFAULT_TRADE_SIZE_USD,
                "max_daily_loss_usd": cls.MAX_DAILY_LOSS_USD,
                "max_open_positions": cls.MAX_OPEN_POSITIONS,
            },
            "logging": {
                "level": cls.LOG_LEVEL,
                "file": cls.LOG_FILE,
            }
        }


# ─────────────────────────────────────────────
# Configuration Validation on Import
# ─────────────────────────────────────────────

if not Config.validate():
    print("⚠️ Configuration validation failed. Please check your environment variables.")
