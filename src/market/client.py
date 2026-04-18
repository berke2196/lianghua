"""
AsterDex API client - Handles all API communication with exchange
"""

import urllib.parse
import aiohttp
from typing import Optional, Dict, Any
import logging

from config import Config
from security import get_global_key

logger = logging.getLogger(__name__)

# Global session for connection pooling
_http_session: Optional[aiohttp.ClientSession] = None


def get_session() -> aiohttp.ClientSession:
    """Get or create global HTTP session"""
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession()
    return _http_session


class AsterDexClient:
    """AsterDex API client"""

    def __init__(self, user: str, signer: str):
        self.user = user
        self.signer = signer
        self.base_url = Config.ASTER_BASE
        self.headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AsterDex-Trader/1.0"
        }

    async def get_balance(self) -> Optional[Dict]:
        """Get account balance"""
        return await self._authenticated_get("/fapi/v3/balance")

    async def get_positions(self) -> Optional[Dict]:
        """Get account positions"""
        return await self._authenticated_get("/fapi/v3/positionRisk")

    async def get_open_orders(self, symbol: str = None) -> Optional[Dict]:
        """Get open orders"""
        params = {"symbol": symbol} if symbol else {}
        return await self._authenticated_get("/fapi/v3/openOrders", params)

    async def place_order(self, symbol: str, side: str, quantity: float, price: float) -> Optional[Dict]:
        """Place a new order"""
        params = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "type": "LIMIT",
            "timeInForce": "GTC",
        }
        return await self._authenticated_post("/fapi/v3/order", params)

    async def cancel_order(self, symbol: str, order_id: str) -> Optional[Dict]:
        """Cancel an order"""
        params = {"symbol": symbol, "orderId": order_id}
        return await self._authenticated_delete("/fapi/v3/order", params)

    async def cancel_all_orders(self, symbol: str) -> Optional[Dict]:
        """Cancel all orders for a symbol"""
        params = {"symbol": symbol}
        return await self._authenticated_delete("/fapi/v3/allOpenOrders", params)

    async def _authenticated_get(self, path: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated GET request"""
        private_key = get_global_key()
        if not private_key:
            logger.warning("❌ GET request requires authentication")
            return None

        try:
            session = get_session()
            url = self._build_signed_url(path, params or {})
            async with session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                if r.status == 200:
                    return await r.json()
                text = await r.text()
                logger.error(f"GET {path} -> {r.status}: {text[:400]}")
                return None
        except Exception as e:
            logger.error(f"GET {path} error: {e}")
            return None

    async def _authenticated_post(self, path: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated POST request"""
        private_key = get_global_key()
        if not private_key:
            logger.warning("❌ POST request requires authentication")
            return None

        try:
            session = get_session()
            body = self._build_signed_body(params or {})
            url = self.base_url + path

            async with session.post(url, data=body, headers=self.headers, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                result = await r.json()
                if r.status not in (200, 201):
                    logger.error(f"POST {path} -> {r.status}: {result}")
                return result
        except Exception as e:
            logger.error(f"POST {path} error: {e}")
            return None

    async def _authenticated_delete(self, path: str, params: Dict = None) -> Optional[Dict]:
        """Make authenticated DELETE request"""
        private_key = get_global_key()
        if not private_key:
            logger.warning("❌ DELETE request requires authentication")
            return None

        try:
            session = get_session()
            url = self._build_signed_url(path, params or {})

            async with session.delete(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=Config.API_TIMEOUT)) as r:
                return await r.json()
        except Exception as e:
            logger.error(f"DELETE {path} error: {e}")
            return None

    def _build_signed_url(self, path: str, params: Dict) -> str:
        """Build signed URL for API request"""
        # TODO: Implement signing logic (EIP-712)
        p = dict(params)
        p["user"] = self.user
        p["signer"] = self.signer
        qs = urllib.parse.urlencode(p)
        return self.base_url + path + "?" + qs

    def _build_signed_body(self, params: Dict) -> Dict:
        """Build signed body for POST request"""
        p = dict(params)
        p["user"] = self.user
        p["signer"] = self.signer
        # TODO: Add signature
        return p
