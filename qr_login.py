"""
扫码登录模块 - 支持Hyperliquid OAuth扫码认证
QR Code Login Module - Hyperliquid OAuth Support
"""

import qrcode
import json
import asyncio
import aiohttp
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
import hashlib
import secrets
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuthSession:
    """认证会话"""
    session_id: str
    state: str
    qr_code_data: str
    created_at: datetime
    expires_at: datetime
    is_authenticated: bool = False
    user_id: Optional[str] = None
    access_token: Optional[str] = None


class QRCodeLoginManager:
    """
    Hyperliquid 扫码登录管理器
    
    流程:
    1. 用户启动应用
    2. 显示二维码
    3. 用户用Hyperliquid app扫码
    4. 用户在Hyperliquid app中授权
    5. 应用自动获得认证
    6. 应用自动创建交易连接
    """
    
    def __init__(
        self,
        client_id: str = "crypto-ai-trader",
        callback_url: str = "http://localhost:3000/auth/callback",
        sandbox_mode: bool = False
    ):
        self.client_id = client_id
        self.callback_url = callback_url
        self.sandbox_mode = sandbox_mode
        
        # 会话管理
        self.sessions: Dict[str, AuthSession] = {}
        self.current_session: Optional[AuthSession] = None
        
        # 回调函数
        self.on_authenticated: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        logger.info(f"🔐 QR登录管理器初始化 | 沙箱: {sandbox_mode}")
    
    def generate_auth_url(self) -> tuple[str, str]:
        """
        生成Hyperliquid认证URL和QR码
        
        返回:
            (qr_code_image_base64, auth_url)
        """
        # 生成唯一的state和session_id
        state = secrets.token_urlsafe(32)
        session_id = secrets.token_urlsafe(16)
        
        # Hyperliquid OAuth 端点
        oauth_endpoint = "https://app.hyperliquid.xyz/auth/authorize"
        if self.sandbox_mode:
            oauth_endpoint = "https://testnet.hyperliquid.com/auth/authorize"
        
        # 构建授权URL
        auth_url = f"{oauth_endpoint}?client_id={self.client_id}&redirect_uri={self.callback_url}&state={state}&response_type=code"
        
        # 创建会话
        session = AuthSession(
            session_id=session_id,
            state=state,
            qr_code_data=auth_url,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=10)
        )
        
        self.sessions[session_id] = session
        self.current_session = session
        
        # 生成QR码
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(auth_url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # 转换为base64
        import io
        import base64
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        logger.info(f"✅ 已生成QR码 | Session: {session_id}")
        
        return qr_base64, auth_url
    
    async def handle_callback(self, code: str, state: str) -> bool:
        """
        处理Hyperliquid回调
        
        参数:
            code: 授权码
            state: 状态token
            
        返回:
            是否认证成功
        """
        # 验证state
        session = self.current_session
        if not session or session.state != state:
            logger.error("❌ State不匹配，可能是CSRF攻击")
            if self.on_error:
                await self.on_error("State mismatch")
            return False
        
        # 检查过期
        if datetime.now() > session.expires_at:
            logger.error("❌ 认证已过期")
            if self.on_error:
                await self.on_error("Session expired")
            return False
        
        try:
            # 交换授权码获取访问令牌
            access_token = await self._exchange_code_for_token(code)
            
            if not access_token:
                logger.error("❌ 获取访问令牌失败")
                return False
            
            # 获取用户信息
            user_info = await self._get_user_info(access_token)
            
            if not user_info:
                logger.error("❌ 获取用户信息失败")
                return False
            
            # 更新会话
            session.is_authenticated = True
            session.user_id = user_info.get("user_id")
            session.access_token = access_token
            
            logger.info(f"✅ 认证成功 | 用户: {session.user_id}")
            
            # 触发回调
            if self.on_authenticated:
                await self.on_authenticated({
                    "user_id": session.user_id,
                    "access_token": access_token,
                    "user_info": user_info
                })
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 认证过程出错: {e}")
            if self.on_error:
                await self.on_error(str(e))
            return False
    
    async def _exchange_code_for_token(self, code: str) -> Optional[str]:
        """交换授权码获取访问令牌"""
        token_endpoint = "https://api.hyperliquid.com/auth/token"
        if self.sandbox_mode:
            token_endpoint = "https://testnet.hyperliquid.com/api/auth/token"
        
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "redirect_uri": self.callback_url
                }
                
                async with session.post(token_endpoint, json=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("access_token")
                    else:
                        logger.error(f"Token交换失败: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"Token交换异常: {e}")
            return None
    
    async def _get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """获取用户信息"""
        user_info_endpoint = "https://api.hyperliquid.com/auth/user"
        if self.sandbox_mode:
            user_info_endpoint = "https://testnet.hyperliquid.com/api/auth/user"
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {access_token}"}
                async with session.get(user_info_endpoint, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        logger.error(f"获取用户信息失败: {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        if not self.current_session:
            return False
        return self.current_session.is_authenticated
    
    def get_access_token(self) -> Optional[str]:
        """获取访问令牌"""
        if not self.current_session:
            return None
        return self.current_session.access_token
    
    def get_user_id(self) -> Optional[str]:
        """获取用户ID"""
        if not self.current_session:
            return None
        return self.current_session.user_id
    
    async def logout(self) -> None:
        """登出"""
        if self.current_session:
            self.current_session.is_authenticated = False
            self.current_session = None
        
        logger.info("✅ 已登出")


# 使用示例
if __name__ == "__main__":
    import asyncio
    
    async def main():
        # 初始化登录管理器
        login_manager = QRCodeLoginManager(sandbox_mode=False)
        
        # 定义回调
        async def on_auth(auth_info):
            print(f"\n✅ 认证成功!")
            print(f"   用户ID: {auth_info['user_id']}")
            print(f"   访问令牌: {auth_info['access_token'][:20]}...")
        
        async def on_error(error):
            print(f"\n❌ 认证错误: {error}")
        
        login_manager.on_authenticated = on_auth
        login_manager.on_error = on_error
        
        # 生成QR码
        qr_base64, auth_url = login_manager.generate_auth_url()
        
        print("\n" + "="*60)
        print("🔐 Hyperliquid 扫码登录")
        print("="*60)
        print("\n📱 请用Hyperliquid App扫描下方二维码:")
        print(f"\n[QR Code would display here - Base64: {qr_base64[:50]}...]")
        print(f"\n或点击链接: {auth_url}")
        print("\n等待授权中...\n")
        
        # 模拟收到回调
        # 实际应用中，这会来自Hyperliquid服务器
        await asyncio.sleep(3)
        print("💡 提示: 在Hyperliquid App中点击'授权'")
        
        # 模拟授权成功
        await asyncio.sleep(5)
        success = await login_manager.handle_callback(
            code="test_auth_code_123",
            state=login_manager.current_session.state
        )
        
        if success:
            print(f"\n✅ 登录成功！")
            print(f"   用户ID: {login_manager.get_user_id()}")
            print(f"   已认证: {login_manager.is_authenticated()}")
