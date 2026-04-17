# Hyperliquid API 配置文件
import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class HyperliquidConfig:
    """Hyperliquid配置类"""

    # API密钥
    api_key: str = os.getenv("HYPERLIQUID_API_KEY", "")
    api_secret: str = os.getenv("HYPERLIQUID_API_SECRET", "")

    # 连接配置
    testnet: bool = os.getenv("HYPERLIQUID_TESTNET", "false").lower() == "true"
    timeout: int = int(os.getenv("HYPERLIQUID_TIMEOUT", "30"))

    # WebSocket配置
    ws_reconnect: bool = os.getenv("HYPERLIQUID_WS_RECONNECT", "true").lower() == "true"
    ws_reconnect_delay: int = int(os.getenv("HYPERLIQUID_WS_RECONNECT_DELAY", "5"))
    ws_heartbeat: int = int(os.getenv("HYPERLIQUID_WS_HEARTBEAT", "30"))
    ws_max_retries: int = int(os.getenv("HYPERLIQUID_WS_MAX_RETRIES", "10"))
    ws_max_queue_size: int = int(os.getenv("HYPERLIQUID_WS_MAX_QUEUE_SIZE", "1000"))

    # 交易配置
    default_order_type: str = os.getenv("HYPERLIQUID_DEFAULT_ORDER_TYPE", "limit")
    enable_reduce_only: bool = (
        os.getenv("HYPERLIQUID_ENABLE_REDUCE_ONLY", "false").lower() == "true"
    )

    # 日志配置
    log_level: str = os.getenv("HYPERLIQUID_LOG_LEVEL", "INFO")
    log_file: Optional[str] = os.getenv("HYPERLIQUID_LOG_FILE", None)

    # API速率限制
    rate_limit_per_second: int = int(os.getenv("HYPERLIQUID_RATE_LIMIT", "100"))

    @classmethod
    def from_env(cls) -> "HyperliquidConfig":
        """从环境变量加载配置"""
        return cls()

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "testnet": self.testnet,
            "timeout": self.timeout,
            "ws_reconnect": self.ws_reconnect,
            "ws_reconnect_delay": self.ws_reconnect_delay,
            "ws_heartbeat": self.ws_heartbeat,
            "ws_max_retries": self.ws_max_retries,
            "ws_max_queue_size": self.ws_max_queue_size,
            "default_order_type": self.default_order_type,
            "enable_reduce_only": self.enable_reduce_only,
            "log_level": self.log_level,
            "log_file": self.log_file,
            "rate_limit_per_second": self.rate_limit_per_second,
        }


# 默认配置实例
default_config = HyperliquidConfig.from_env()
