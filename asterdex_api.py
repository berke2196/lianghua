"""
AsterDex 交易所 API 集成模块
支持期货交易、实时行情、账户管理
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import aiohttp
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AsterDexAPI:
    """AsterDex 交易所 API 封装"""

    # API 端点
    BASE_URL = "https://api.asterdex.com"
    WS_URL = "wss://stream.asterdex.com"

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        """
        初始化 AsterDex API 客户端

        Args:
            api_key: API 密钥
            api_secret: API 密钥
            testnet: 是否使用测试网
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.session = None
        self.base_url = self.BASE_URL
        self.ws_url = self.WS_URL

    async def _request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """发送 API 请求"""
        try:
            url = f"{self.base_url}{endpoint}"
            headers = self._get_headers()

            if not self.session:
                self.session = aiohttp.ClientSession()

            async with self.session.request(method, url, headers=headers, params=params, json=data, timeout=30) as resp:
                result = await resp.json()

                if resp.status == 200:
                    return result.get('data', result)
                else:
                    logger.error(f"API Error: {result}")
                    raise Exception(f"API Error: {result.get('message', 'Unknown error')}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise

    def _get_headers(self) -> Dict:
        """生成请求头"""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp)

        return {
            "X-API-KEY": self.api_key,
            "X-API-SIGNATURE": signature,
            "X-API-TIMESTAMP": timestamp,
            "Content-Type": "application/json"
        }

    def _generate_signature(self, timestamp: str) -> str:
        """生成签名"""
        message = f"{self.api_key}{timestamp}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def get_account_info(self) -> Dict:
        """获取账户信息"""
        try:
            return await self._request("GET", "/v1/account")
        except Exception as e:
            logger.error(f"获取账户信息失败: {e}")
            return None

    async def get_balance(self) -> Dict:
        """获取账户余额"""
        try:
            account = await self.get_account_info()
            if account:
                return {
                    "total_balance": account.get("totalBalance", 0),
                    "available_balance": account.get("availableBalance", 0),
                    "usdt_balance": account.get("usdtBalance", 0),
                    "equity": account.get("equity", 0),
                    "margin_used": account.get("marginUsed", 0),
                    "margin_ratio": account.get("marginRatio", 0)
                }
            return None
        except Exception as e:
            logger.error(f"获取余额失败: {e}")
            return None

    async def get_ticker(self, symbol: str) -> Dict:
        """获取行情数据"""
        try:
            data = await self._request("GET", f"/v1/ticker/24hr", params={"symbol": symbol})
            if data:
                return {
                    "symbol": symbol,
                    "price": float(data.get("lastPrice", 0)),
                    "change_24h": float(data.get("priceChangePercent", 0)),
                    "high_24h": float(data.get("highPrice", 0)),
                    "low_24h": float(data.get("lowPrice", 0)),
                    "volume_24h": float(data.get("volume", 0)),
                    "bid": float(data.get("bid", 0)),
                    "ask": float(data.get("ask", 0))
                }
            return None
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            return None

    async def get_candlesticks(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[float]:
        """获取K线数据"""
        try:
            # 转换时间间隔格式
            interval_map = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1h": "1h",
                "4h": "4h",
                "1d": "1d"
            }

            data = await self._request(
                "GET",
                f"/v1/klines",
                params={
                    "symbol": symbol,
                    "interval": interval_map.get(interval, "1m"),
                    "limit": limit
                }
            )

            if data:
                # AsterDex 返回的是 [timestamp, open, high, low, close, volume] 格式
                prices = [float(candle[4]) for candle in data]  # 取收盘价
                return prices
            return []
        except Exception as e:
            logger.error(f"获取K线失败: {e}")
            return []

    async def get_current_price(self, symbol: str) -> Optional[float]:
        """获取当前价格"""
        try:
            ticker = await self.get_ticker(symbol)
            return ticker.get("price") if ticker else None
        except Exception as e:
            logger.error(f"获取价格失败: {e}")
            return None

    async def place_order(
        self,
        symbol: str,
        side: str,  # BUY or SELL
        size: float,
        price: Optional[float] = None,
        leverage: int = 1,
        order_type: str = "LIMIT"
    ) -> Dict:
        """下单"""
        try:
            order_data = {
                "symbol": symbol,
                "side": side.upper(),
                "quantity": size,
                "leverage": leverage,
                "type": "MARKET" if price is None else "LIMIT"
            }

            if price is not None:
                order_data["price"] = price

            response = await self._request("POST", "/v1/orders", data=order_data)

            if response:
                return {
                    "order_id": response.get("orderId"),
                    "symbol": symbol,
                    "side": side,
                    "size": size,
                    "price": price,
                    "leverage": leverage,
                    "status": response.get("status"),
                    "timestamp": datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"下单失败: {e}")
            raise

    async def get_positions(self) -> List[Dict]:
        """获取持仓"""
        try:
            data = await self._request("GET", "/v1/positions")

            positions = []
            if data:
                for pos in data:
                    positions.append({
                        "symbol": pos.get("symbol"),
                        "side": pos.get("positionSide"),  # LONG or SHORT
                        "size": float(pos.get("positionAmount", 0)),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "current_price": float(pos.get("markPrice", 0)),
                        "unrealized_pnl": float(pos.get("unrealizedProfit", 0)),
                        "pnl_percent": float(pos.get("profitPercent", 0)),
                        "leverage": int(pos.get("leverage", 1)),
                        "margin_type": pos.get("marginType")
                    })

            return positions
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return []

    async def get_trades(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取交易历史"""
        try:
            params = {"limit": limit}
            if symbol:
                params["symbol"] = symbol

            data = await self._request("GET", "/v1/trades", params=params)

            trades = []
            if data:
                for trade in data:
                    trades.append({
                        "trade_id": trade.get("id"),
                        "symbol": trade.get("symbol"),
                        "side": trade.get("side"),
                        "size": float(trade.get("qty", 0)),
                        "price": float(trade.get("price", 0)),
                        "timestamp": trade.get("time"),
                        "status": "FILLED",
                        "pnl": float(trade.get("realizedPnl", 0))
                    })

            return trades
        except Exception as e:
            logger.error(f"获取交易历史失败: {e}")
            return []

    async def close_position(self, symbol: str) -> Dict:
        """平仓"""
        try:
            # 获取当前持仓
            positions = await self.get_positions()
            position = next((p for p in positions if p["symbol"] == symbol), None)

            if not position:
                raise Exception(f"找不到 {symbol} 的持仓")

            # 平仓需要下反向单
            close_side = "SELL" if position["side"] == "LONG" else "BUY"

            order = await self.place_order(
                symbol=symbol,
                side=close_side,
                size=position["size"],
                price=None,
                leverage=position["leverage"]
            )

            return order
        except Exception as e:
            logger.error(f"平仓失败: {e}")
            raise

    async def get_supported_symbols(self) -> List[str]:
        """获取支持的交易对"""
        try:
            data = await self._request("GET", "/v1/exchangeInfo")

            symbols = []
            if data and "symbols" in data:
                for symbol_info in data["symbols"]:
                    if symbol_info.get("status") == "TRADING":
                        symbols.append(symbol_info.get("symbol"))

            return symbols
        except Exception as e:
            logger.error(f"获取交易对失败: {e}")
            return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # 默认列表

    async def set_leverage(self, symbol: str, leverage: int) -> Dict:
        """设置杠杆"""
        try:
            data = await self._request(
                "POST",
                "/v1/leverage",
                data={
                    "symbol": symbol,
                    "leverage": leverage
                }
            )
            return data
        except Exception as e:
            logger.error(f"设置杠杆失败: {e}")
            raise

    async def set_stop_loss(self, symbol: str, trigger_price: float, price: float = None) -> Dict:
        """设置止损"""
        try:
            data = await self._request(
                "POST",
                "/v1/orders/stop-loss",
                data={
                    "symbol": symbol,
                    "triggerPrice": trigger_price,
                    "price": price or trigger_price
                }
            )
            return data
        except Exception as e:
            logger.error(f"设置止损失败: {e}")
            raise

    async def set_take_profit(self, symbol: str, trigger_price: float, price: float = None) -> Dict:
        """设置止盈"""
        try:
            data = await self._request(
                "POST",
                "/v1/orders/take-profit",
                data={
                    "symbol": symbol,
                    "triggerPrice": trigger_price,
                    "price": price or trigger_price
                }
            )
            return data
        except Exception as e:
            logger.error(f"设置止盈失败: {e}")
            raise

    async def get_order_book(self, symbol: str, limit: int = 20) -> Dict:
        """获取订单簿"""
        try:
            data = await self._request(
                "GET",
                f"/v1/depth",
                params={"symbol": symbol, "limit": limit}
            )

            if data:
                return {
                    "bids": data.get("bids", []),
                    "asks": data.get("asks", []),
                    "timestamp": datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"获取订单簿失败: {e}")
            return None

    async def close(self):
        """关闭连接"""
        if self.session:
            await self.session.close()


class AsterDexWebSocketClient:
    """AsterDex WebSocket 客户端"""

    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.ws = None
        self.is_connected = False

    async def connect(self):
        """连接到 WebSocket"""
        try:
            session = aiohttp.ClientSession()
            self.ws = await session.ws_connect(f"{AsterDexAPI.WS_URL}/stream")
            self.is_connected = True
            logger.info("✅ WebSocket 已连接")
        except Exception as e:
            logger.error(f"❌ WebSocket 连接失败: {e}")

    async def subscribe(self, symbol: str, event_type: str = "trade"):
        """订阅流数据"""
        if not self.is_connected:
            await self.connect()

        try:
            message = {
                "method": "SUBSCRIBE",
                "params": [f"{symbol.lower()}@{event_type}"],
                "id": 1
            }
            await self.ws.send_json(message)
            logger.info(f"✅ 已订阅 {symbol} {event_type}")
        except Exception as e:
            logger.error(f"❌ 订阅失败: {e}")

    async def listen(self):
        """监听消息"""
        try:
            async for msg in self.ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    yield data
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    logger.error("WebSocket 错误")
                    break
        except Exception as e:
            logger.error(f"监听失败: {e}")

    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            self.is_connected = False
            logger.info("WebSocket 已关闭")
