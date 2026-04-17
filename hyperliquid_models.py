# Hyperliquid 数据模型定义
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from decimal import Decimal


class OrderStatus(str, Enum):
    """订单状态枚举"""
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL_FILLED = "partially_filled"
    REJECTED = "rejected"


class OrderType(str, Enum):
    """订单类型枚举"""
    LIMIT = "limit"
    MARKET = "market"
    STOP = "stop"
    TAKE_PROFIT = "take_profit"


class OrderSide(str, Enum):
    """订单方向枚举"""
    BUY = "buy"
    SELL = "sell"
    LONG = "long"
    SHORT = "short"


class PositionMode(str, Enum):
    """持仓模式枚举"""
    ONE_WAY = "one_way"
    HEDGE = "hedge"


@dataclass
class Candle:
    """K线数据模型"""
    timestamp: datetime  # 时间戳
    open: Decimal  # 开盘价
    high: Decimal  # 最高价
    low: Decimal  # 最低价
    close: Decimal  # 收盘价
    volume: Decimal  # 成交量(币)
    quote_asset_volume: Decimal  # 成交额(USDT)
    trade_count: int  # 成交笔数
    taker_buy_volume: Decimal = Decimal(0)  # 主动买入量


@dataclass
class Ticker:
    """行情数据模型"""
    symbol: str  # 交易对
    bid: Decimal  # 买价
    bid_size: Decimal  # 买价量
    ask: Decimal  # 卖价
    ask_size: Decimal  # 卖价量
    last_price: Decimal  # 最新价
    timestamp: datetime  # 时间戳
    mark_price: Optional[Decimal] = None  # 标记价格
    index_price: Optional[Decimal] = None  # 指数价格
    volume_24h: Decimal = Decimal(0)  # 24小时成交量
    high_24h: Decimal = Decimal(0)  # 24小时最高
    low_24h: Decimal = Decimal(0)  # 24小时最低
    change_24h: Decimal = Decimal(0)  # 24小时涨幅百分比


@dataclass
class OrderBook:
    """委托簿模型"""
    symbol: str  # 交易对
    bids: List[tuple[Decimal, Decimal]] = field(default_factory=list)  # [价格, 数量]
    asks: List[tuple[Decimal, Decimal]] = field(default_factory=list)  # [价格, 数量]
    timestamp: datetime = field(default_factory=datetime.utcnow)  # 时间戳
    seq_num: Optional[int] = None  # 序列号(用于排序)


@dataclass
class Order:
    """订单模型"""
    order_id: str  # 订单ID
    symbol: str  # 交易对
    side: OrderSide  # 买卖方向
    order_type: OrderType  # 订单类型
    price: Decimal  # 委托价格
    quantity: Decimal  # 委托数量
    filled: Decimal  # 已成交数量
    status: OrderStatus  # 订单状态
    timestamp: datetime  # 创建时间
    update_time: datetime = field(default_factory=datetime.utcnow)  # 更新时间
    client_order_id: Optional[str] = None  # 客户端订单ID
    stop_price: Optional[Decimal] = None  # 止损价
    reduce_only: bool = False  # 仅平仓
    post_only: bool = False  # 仅作为maker
    trigger_price: Optional[Decimal] = None  # 触发价格
    executed_value: Decimal = Decimal(0)  # 已成交金额
    average_price: Decimal = Decimal(0)  # 平均成交价
    fee_currency: Optional[str] = None  # 手续费币种
    fee: Decimal = Decimal(0)  # 手续费


@dataclass
class Position:
    """持仓模型"""
    symbol: str  # 交易对
    side: str  # 持仓方向 (LONG/SHORT/BOTH)
    size: Decimal  # 持仓数量
    entry_price: Decimal  # 开仓价格
    mark_price: Decimal  # 标记价格
    liquidation_price: Optional[Decimal] = None  # 强平价
    leverage: Decimal = Decimal(1)  # 杠杆
    unrealized_pnl: Decimal = Decimal(0)  # 未实现盈亏
    realized_pnl: Decimal = Decimal(0)  # 已实现盈亏
    margin: Decimal = Decimal(0)  # 保证金
    available_margin: Decimal = Decimal(0)  # 可用保证金
    percentage: Decimal = Decimal(0)  # 持仓比例百分比
    funding_rate: Decimal = Decimal(0)  # 资金费率
    timestamp: datetime = field(default_factory=datetime.utcnow)  # 时间戳


@dataclass
class Trade:
    """成交记录模型"""
    trade_id: str  # 成交ID
    order_id: str  # 订单ID
    symbol: str  # 交易对
    side: OrderSide  # 买卖方向
    price: Decimal  # 成交价
    quantity: Decimal  # 成交数量
    fee: Decimal  # 手续费
    fee_currency: str  # 手续费币种
    timestamp: datetime  # 成交时间
    is_buyer: bool = False  # 是否为主动买方
    is_maker: bool = False  # 是否为做市商
    quote_quantity: Decimal = Decimal(0)  # 成交金额


@dataclass
class FundingRate:
    """资金费率模型"""
    symbol: str  # 交易对
    funding_rate: Decimal  # 当前资金费率
    funding_time: datetime  # 资金费率时间
    next_funding_time: datetime  # 下次资金费率时间
    estimated_funding_rate: Optional[Decimal] = None  # 预计资金费率
    interval: int = 3600  # 费率间隔(秒)


@dataclass
class Account:
    """账户信息模型"""
    account_id: str  # 账户ID
    total_balance: Decimal  # 总资产
    available_balance: Decimal  # 可用资产
    locked_balance: Decimal  # 锁定资产
    margin_level: Optional[Decimal] = None  # 保证金水平
    account_equity: Optional[Decimal] = None  # 账户权益
    timestamp: datetime = field(default_factory=datetime.utcnow)  # 时间戳


@dataclass
class WebSocketMessage:
    """WebSocket消息模型"""
    channel: str  # 频道名称 (ticker/candle/orderbook/trade/funding)
    symbol: str  # 交易对
    data: Dict[str, Any]  # 消息数据
    timestamp: datetime = field(default_factory=datetime.utcnow)  # 接收时间


@dataclass
class SubscriptionConfig:
    """订阅配置模型"""
    symbols: List[str]  # 交易对列表
    channels: List[str]  # 订阅频道列表
    auto_reconnect: bool = True  # 自动重连
    reconnect_delay: int = 5  # 重连延迟(秒)
    heartbeat_interval: int = 30  # 心跳间隔(秒)
    max_retries: int = 10  # 最大重试次数
