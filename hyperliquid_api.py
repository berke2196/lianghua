# Hyperliquid REST API 封装
import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
from datetime import datetime, timedelta

import aiohttp
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from hyperliquid_models import (
    Account,
    Candle,
    Order,
    OrderBook,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Ticker,
    Trade,
    FundingRate,
)


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HyperliquidAPIError(Exception):
    """Hyperliquid API异常基类"""

    pass


class HyperliquidAuthError(HyperliquidAPIError):
    """认证异常"""

    pass


class HyperliquidNetworkError(HyperliquidAPIError):
    """网络异常"""

    pass


class HyperliquidTimeoutError(HyperliquidAPIError):
    """超时异常"""

    pass


class HyperliquidRateLimitError(HyperliquidAPIError):
    """速率限制异常"""

    pass


class HyperliquidAPI:
    """Hyperliquid REST API封装"""

    # API端点
    API_BASE_URL = "https://api.hyperliquid.xyz"
    API_TESTNET_URL = "https://api-testnet.hyperliquid.xyz"

    # 重试配置
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # 秒
    BACKOFF_FACTOR = 2
    TIMEOUT = 30  # 秒

    # 速率限制
    RATE_LIMIT_PER_SECOND = 100
    RATE_LIMIT_WINDOW = 60  # 秒

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False,
        timeout: int = 30,
    ):
        """
        初始化Hyperliquid API客户端

        Args:
            api_key: API密钥
            api_secret: API密钥
            testnet: 是否使用测试网
            timeout: 请求超时时间(秒)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.timeout = timeout
        self.base_url = self.API_TESTNET_URL if testnet else self.API_BASE_URL

        # 初始化会话
        self.session = self._create_session()

        # 速率限制跟踪
        self._request_times: List[float] = []
        self._lock = asyncio.Lock()

    def _create_session(self) -> requests.Session:
        """创建带重试策略的会话"""
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=self.BACKOFF_FACTOR,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _sign_request(self, data: Dict[str, Any]) -> str:
        """
        签署请求

        Args:
            data: 请求数据

        Returns:
            签名
        """
        message = json.dumps(data)
        signature = hmac.new(
            self.api_secret.encode(), message.encode(), hashlib.sha256
        ).hexdigest()
        return signature

    def _get_headers(self, signature: str) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "HAPI-KEY": self.api_key,
            "HAPI-SIGN": signature,
            "HAPI-TIME": str(int(time.time() * 1000)),
        }

    async def _apply_rate_limit(self) -> None:
        """应用速率限制"""
        async with self._lock:
            now = time.time()
            # 移除超出窗口的请求记录
            self._request_times = [
                t for t in self._request_times if now - t < self.RATE_LIMIT_WINDOW
            ]

            # 检查是否超过速率限制
            if len(self._request_times) >= self.RATE_LIMIT_PER_SECOND:
                wait_time = (
                    self.RATE_LIMIT_WINDOW
                    - (now - self._request_times[0])
                )
                if wait_time > 0:
                    logger.warning(f"触发速率限制，等待 {wait_time:.2f} 秒")
                    await asyncio.sleep(wait_time)

            self._request_times.append(now)

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        public: bool = True,
    ) -> Dict[str, Any]:
        """
        发送HTTP请求

        Args:
            method: HTTP方法 (GET, POST)
            endpoint: API端点
            data: 请求数据
            public: 是否为公开API

        Returns:
            响应数据

        Raises:
            HyperliquidAPIError: API错误
        """
        url = f"{self.base_url}{endpoint}"

        # 非公开接口需要签名
        if not public:
            if not data:
                data = {}
            signature = self._sign_request(data)
            headers = self._get_headers(signature)
        else:
            headers = {"Content-Type": "application/json"}

        try:
            if method.upper() == "GET":
                response = self.session.get(
                    url, params=data, headers=headers, timeout=self.timeout
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url, json=data, headers=headers, timeout=self.timeout
                )
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise HyperliquidTimeoutError(f"请求超时: {endpoint}")
        except requests.exceptions.ConnectionError:
            raise HyperliquidNetworkError(f"网络错误: {endpoint}")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise HyperliquidAuthError("认证失败，请检查API密钥")
            elif response.status_code == 429:
                raise HyperliquidRateLimitError("请求过于频繁，请稍后再试")
            else:
                raise HyperliquidAPIError(f"HTTP错误 {response.status_code}: {e}")
        except Exception as e:
            raise HyperliquidAPIError(f"请求失败: {str(e)}")

    # ========== 公开接口 ==========

    def get_ticker(self, symbol: str) -> Ticker:
        """
        获取行情数据

        Args:
            symbol: 交易对 (e.g., "BTC-USD")

        Returns:
            Ticker对象
        """
        endpoint = "/info"
        data = {"type": "ticker", "coin": symbol}

        response = self._request("GET", endpoint, data, public=True)

        try:
            return Ticker(
                symbol=symbol,
                bid=Decimal(response.get("bid", 0)),
                bid_size=Decimal(response.get("bidSz", 0)),
                ask=Decimal(response.get("ask", 0)),
                ask_size=Decimal(response.get("askSz", 0)),
                last_price=Decimal(response.get("mid", 0)),
                timestamp=datetime.fromtimestamp(
                    response.get("time", 0) / 1000
                ),
                mark_price=Decimal(response.get("markPx", 0)),
                volume_24h=Decimal(response.get("volume24h", 0)),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"解析Ticker数据失败: {str(e)}")

    def get_orderbook(self, symbol: str, depth: int = 20) -> OrderBook:
        """
        获取委托簿

        Args:
            symbol: 交易对
            depth: 深度 (20, 100)

        Returns:
            OrderBook对象
        """
        endpoint = "/info"
        data = {"type": "orderBook", "coin": symbol}

        response = self._request("GET", endpoint, data, public=True)

        try:
            bids = [
                (Decimal(b[0]), Decimal(b[1])) for b in response.get("bids", [])
            ][:depth]
            asks = [
                (Decimal(a[0]), Decimal(a[1])) for a in response.get("asks", [])
            ][:depth]

            return OrderBook(
                symbol=symbol,
                bids=bids,
                asks=asks,
                timestamp=datetime.fromtimestamp(response.get("time", 0) / 1000),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"解析OrderBook数据失败: {str(e)}")

    def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> List[Candle]:
        """
        获取K线数据

        Args:
            symbol: 交易对
            interval: 时间间隔 (1m, 5m, 15m, 1h, 4h, 1d)
            limit: 返回数量

        Returns:
            Candle列表
        """
        # Hyperliquid使用毫秒时间戳
        endpoint = "/info"
        data = {"type": "candle", "coin": symbol, "interval": interval}

        response = self._request("GET", endpoint, data, public=True)

        candles = []
        try:
            for candle_data in response:
                candle = Candle(
                    timestamp=datetime.fromtimestamp(candle_data[0] / 1000),
                    open=Decimal(candle_data[1]),
                    high=Decimal(candle_data[2]),
                    low=Decimal(candle_data[3]),
                    close=Decimal(candle_data[4]),
                    volume=Decimal(candle_data[5]),
                    quote_asset_volume=Decimal(candle_data[6]),
                    trade_count=int(candle_data[7]),
                )
                candles.append(candle)
        except (KeyError, ValueError, IndexError, TypeError) as e:
            raise HyperliquidAPIError(f"解析K线数据失败: {str(e)}")

        return candles

    def get_funding_rates(self, symbol: str) -> FundingRate:
        """
        获取资金费率

        Args:
            symbol: 交易对

        Returns:
            FundingRate对象
        """
        endpoint = "/info"
        data = {"type": "fundingRate", "coin": symbol}

        response = self._request("GET", endpoint, data, public=True)

        try:
            now = datetime.utcnow()
            return FundingRate(
                symbol=symbol,
                funding_rate=Decimal(response.get("fundingRate", 0)),
                funding_time=now,
                next_funding_time=now + timedelta(hours=8),
                estimated_funding_rate=Decimal(
                    response.get("estimatedFundingRate", 0)
                ),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"解析资金费率数据失败: {str(e)}")

    # ========== 私有接口 ==========

    def get_account_info(self) -> Account:
        """
        获取账户信息

        Returns:
            Account对象
        """
        endpoint = "/account"
        data = {"method": "getAccountInfo"}

        response = self._request("POST", endpoint, data, public=False)

        try:
            return Account(
                account_id=response.get("user", {}).get("userId", ""),
                total_balance=Decimal(response.get("total_balance", 0)),
                available_balance=Decimal(response.get("available_balance", 0)),
                locked_balance=Decimal(response.get("locked_balance", 0)),
                margin_level=Decimal(response.get("margin_level", 0)),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"解析账户信息失败: {str(e)}")

    def get_positions(self) -> List[Position]:
        """
        获取持仓信息

        Returns:
            Position列表
        """
        endpoint = "/account"
        data = {"method": "getPositions"}

        response = self._request("POST", endpoint, data, public=False)

        positions = []
        try:
            for pos_data in response:
                position = Position(
                    symbol=pos_data.get("coin", ""),
                    side=pos_data.get("side", "BOTH"),
                    size=Decimal(pos_data.get("szi", 0)),
                    entry_price=Decimal(pos_data.get("entry_price", 0)),
                    mark_price=Decimal(pos_data.get("markPx", 0)),
                    liquidation_price=Decimal(
                        pos_data.get("liquidation_price", 0)
                    ),
                    leverage=Decimal(pos_data.get("leverage", 1)),
                    unrealized_pnl=Decimal(pos_data.get("unrealizedPnl", 0)),
                    realized_pnl=Decimal(pos_data.get("realizedPnl", 0)),
                )
                positions.append(position)
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"解析持仓信息失败: {str(e)}")

        return positions

    def create_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        reduce_only: bool = False,
        post_only: bool = False,
        client_order_id: Optional[str] = None,
    ) -> Order:
        """
        创建订单

        Args:
            symbol: 交易对
            side: 买卖方向
            order_type: 订单类型
            quantity: 数量
            price: 价格 (市价单不需要)
            reduce_only: 仅平仓
            post_only: 仅作为maker
            client_order_id: 客户端订单ID

        Returns:
            Order对象
        """
        endpoint = "/orders"
        data = {
            "method": "createOrder",
            "coin": symbol,
            "side": side.value,
            "type": order_type.value,
            "sz": str(quantity),
            "reduceOnly": reduce_only,
            "postOnly": post_only,
        }

        if price:
            data["px"] = str(price)

        if client_order_id:
            data["clOrdId"] = client_order_id

        response = self._request("POST", endpoint, data, public=False)

        try:
            order_data = response.get("response", {}).get("order", {})
            return Order(
                order_id=order_data.get("oid", ""),
                symbol=symbol,
                side=side,
                order_type=order_type,
                price=Decimal(order_data.get("px", 0)),
                quantity=Decimal(order_data.get("sz", 0)),
                filled=Decimal(order_data.get("filled", 0)),
                status=OrderStatus.OPEN,
                timestamp=datetime.utcnow(),
                client_order_id=client_order_id,
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"创建订单失败: {str(e)}")

    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """
        取消订单

        Args:
            symbol: 交易对
            order_id: 订单ID

        Returns:
            是否取消成功
        """
        endpoint = "/orders"
        data = {
            "method": "cancelOrder",
            "coin": symbol,
            "oid": order_id,
        }

        response = self._request("POST", endpoint, data, public=False)

        try:
            return response.get("status") == "ok"
        except Exception as e:
            raise HyperliquidAPIError(f"取消订单失败: {str(e)}")

    def modify_order(
        self,
        symbol: str,
        order_id: str,
        new_price: Optional[Decimal] = None,
        new_quantity: Optional[Decimal] = None,
    ) -> Order:
        """
        修改订单

        Args:
            symbol: 交易对
            order_id: 订单ID
            new_price: 新价格
            new_quantity: 新数量

        Returns:
            修改后的Order对象
        """
        endpoint = "/orders"
        data = {
            "method": "modifyOrder",
            "coin": symbol,
            "oid": order_id,
        }

        if new_price:
            data["px"] = str(new_price)
        if new_quantity:
            data["sz"] = str(new_quantity)

        response = self._request("POST", endpoint, data, public=False)

        try:
            order_data = response.get("response", {}).get("order", {})
            return Order(
                order_id=order_data.get("oid", ""),
                symbol=symbol,
                side=OrderSide.BUY,  # 需要从响应获取
                order_type=OrderType.LIMIT,  # 需要从响应获取
                price=Decimal(order_data.get("px", 0)),
                quantity=Decimal(order_data.get("sz", 0)),
                filled=Decimal(order_data.get("filled", 0)),
                status=OrderStatus.OPEN,
                timestamp=datetime.utcnow(),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"修改订单失败: {str(e)}")

    def get_order_status(self, symbol: str, order_id: str) -> Order:
        """
        查询订单状态

        Args:
            symbol: 交易对
            order_id: 订单ID

        Returns:
            Order对象
        """
        endpoint = "/orders"
        data = {
            "method": "getOrderStatus",
            "coin": symbol,
            "oid": order_id,
        }

        response = self._request("POST", endpoint, data, public=False)

        try:
            order_data = response
            status_str = order_data.get("status", "").lower()
            # 映射状态
            status_map = {
                "open": OrderStatus.OPEN,
                "filled": OrderStatus.FILLED,
                "cancelled": OrderStatus.CANCELLED,
                "partially_filled": OrderStatus.PARTIAL_FILLED,
            }

            return Order(
                order_id=order_id,
                symbol=symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=Decimal(order_data.get("px", 0)),
                quantity=Decimal(order_data.get("sz", 0)),
                filled=Decimal(order_data.get("filled", 0)),
                status=status_map.get(status_str, OrderStatus.OPEN),
                timestamp=datetime.utcnow(),
            )
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"查询订单状态失败: {str(e)}")

    def get_order_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Order]:
        """
        获取订单历史

        Args:
            symbol: 交易对 (可选，不指定则返回所有)
            limit: 返回数量

        Returns:
            Order列表
        """
        endpoint = "/orders"
        data = {
            "method": "orderHistory",
            "limit": limit,
        }

        if symbol:
            data["coin"] = symbol

        response = self._request("POST", endpoint, data, public=False)

        orders = []
        try:
            for order_data in response:
                status_str = order_data.get("status", "").lower()
                status_map = {
                    "open": OrderStatus.OPEN,
                    "filled": OrderStatus.FILLED,
                    "cancelled": OrderStatus.CANCELLED,
                    "partially_filled": OrderStatus.PARTIAL_FILLED,
                }

                order = Order(
                    order_id=order_data.get("oid", ""),
                    symbol=order_data.get("coin", ""),
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    price=Decimal(order_data.get("px", 0)),
                    quantity=Decimal(order_data.get("sz", 0)),
                    filled=Decimal(order_data.get("filled", 0)),
                    status=status_map.get(status_str, OrderStatus.OPEN),
                    timestamp=datetime.utcnow(),
                )
                orders.append(order)
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"获取订单历史失败: {str(e)}")

        return orders

    def get_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Trade]:
        """
        获取成交记录

        Args:
            symbol: 交易对 (可选)
            limit: 返回数量

        Returns:
            Trade列表
        """
        endpoint = "/trades"
        data = {
            "method": "userTrades",
            "limit": limit,
        }

        if symbol:
            data["coin"] = symbol

        response = self._request("POST", endpoint, data, public=False)

        trades = []
        try:
            for trade_data in response:
                trade = Trade(
                    trade_id=trade_data.get("tid", ""),
                    order_id=trade_data.get("oid", ""),
                    symbol=trade_data.get("coin", ""),
                    side=OrderSide.BUY,
                    price=Decimal(trade_data.get("px", 0)),
                    quantity=Decimal(trade_data.get("sz", 0)),
                    fee=Decimal(trade_data.get("fee", 0)),
                    fee_currency="USDC",
                    timestamp=datetime.fromtimestamp(
                        trade_data.get("time", 0) / 1000
                    ),
                )
                trades.append(trade)
        except (KeyError, ValueError, TypeError) as e:
            raise HyperliquidAPIError(f"获取成交记录失败: {str(e)}")

        return trades

    def close(self) -> None:
        """关闭会话"""
        self.session.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.close()
