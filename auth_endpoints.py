"""
FastAPI 认证端点 - 扫码登录
Auth Endpoints - QR Code Login
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import logging
from typing import Optional, Dict, Any
from qr_login import QRCodeLoginManager

logger = logging.getLogger(__name__)

# 初始化QR登录管理器
qr_login_manager = QRCodeLoginManager(
    client_id="crypto-ai-trader",
    callback_url="http://localhost:3000/auth/callback",
    sandbox_mode=False  # 生产环境改为False
)

# 创建路由
router = APIRouter(prefix="/api/auth", tags=["authentication"])

# 全局变量存储认证状态
auth_sessions: Dict[str, Dict[str, Any]] = {}


@router.post("/generate-qr")
async def generate_qr():
    """
    生成QR码用于登录
    
    返回:
    {
        "qr_code_base64": "base64编码的QR码图片",
        "session_id": "会话ID",
        "expires_in": 600,  # 10分钟后过期
        "message": "请在Hyperliquid App中扫描二维码"
    }
    """
    try:
        qr_base64, auth_url = qr_login_manager.generate_auth_url()
        
        session_id = qr_login_manager.current_session.session_id
        
        logger.info(f"✅ 生成QR码 | Session: {session_id}")
        
        return {
            "qr_code_base64": qr_base64,
            "session_id": session_id,
            "expires_in": 600,
            "auth_url": auth_url,
            "message": "请在Hyperliquid App中扫描二维码"
        }
    except Exception as e:
        logger.error(f"❌ 生成QR码失败: {e}")
        raise HTTPException(status_code=500, detail="生成QR码失败")


@router.get("/status/{session_id}")
async def check_auth_status(session_id: str):
    """
    检查认证状态
    
    返回:
    {
        "authenticated": true/false,
        "user_id": "用户ID",
        "user_info": { ... },
        "access_token": "访问令牌",
        "message": "认证状态"
    }
    """
    try:
        session = qr_login_manager.sessions.get(session_id)
        
        if not session:
            return {
                "authenticated": False,
                "message": "会话不存在"
            }
        
        # 检查过期
        from datetime import datetime
        if datetime.now() > session.expires_at:
            return {
                "authenticated": False,
                "message": "会话已过期"
            }
        
        return {
            "authenticated": session.is_authenticated,
            "user_id": session.user_id,
            "user_info": {
                "user_id": session.user_id,
            } if session.user_id else None,
            "access_token": session.access_token,
            "message": "已认证" if session.is_authenticated else "等待认证中..."
        }
    except Exception as e:
        logger.error(f"❌ 检查认证状态失败: {e}")
        raise HTTPException(status_code=500, detail="检查认证状态失败")


@router.post("/callback")
async def auth_callback(request: Request):
    """
    Hyperliquid OAuth 回调端点
    
    参数:
    - code: 授权码
    - state: 状态token
    
    返回:
    {
        "success": true/false,
        "message": "成功/失败信息"
    }
    """
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="缺少必要参数")
        
        # 处理回调
        success = await qr_login_manager.handle_callback(code, state)
        
        if success:
            logger.info(f"✅ 认证成功 | 用户: {qr_login_manager.get_user_id()}")
            return {
                "success": True,
                "message": "认证成功",
                "user_id": qr_login_manager.get_user_id(),
                "redirect": "/dashboard"
            }
        else:
            logger.error("❌ 认证失败")
            return {
                "success": False,
                "message": "认证失败"
            }
    except Exception as e:
        logger.error(f"❌ 回调处理失败: {e}")
        raise HTTPException(status_code=500, detail="回调处理失败")


@router.get("/verify")
async def verify_auth(request: Request):
    """
    验证当前是否已认证
    
    返回:
    {
        "authenticated": true/false,
        "user_id": "用户ID"
    }
    """
    return {
        "authenticated": qr_login_manager.is_authenticated(),
        "user_id": qr_login_manager.get_user_id()
    }


@router.post("/logout")
async def logout():
    """
    登出
    
    返回:
    {
        "success": true,
        "message": "已登出"
    }
    """
    try:
        await qr_login_manager.logout()
        logger.info("✅ 用户已登出")
        return {
            "success": True,
            "message": "已登出"
        }
    except Exception as e:
        logger.error(f"❌ 登出失败: {e}")
        raise HTTPException(status_code=500, detail="登出失败")


@router.get("/refresh-qr")
async def refresh_qr():
    """
    刷新QR码 (如果当前QR码过期)
    
    返回:
    {
        "qr_code_base64": "新的QR码",
        "session_id": "新的会话ID",
        "expires_in": 600
    }
    """
    try:
        qr_base64, auth_url = qr_login_manager.generate_auth_url()
        
        session_id = qr_login_manager.current_session.session_id
        
        logger.info(f"✅ 刷新QR码 | Session: {session_id}")
        
        return {
            "qr_code_base64": qr_base64,
            "session_id": session_id,
            "expires_in": 600,
            "message": "QR码已刷新"
        }
    except Exception as e:
        logger.error(f"❌ 刷新QR码失败: {e}")
        raise HTTPException(status_code=500, detail="刷新QR码失败")


@router.get("/session-info")
async def get_session_info():
    """
    获取当前会话信息
    
    返回:
    {
        "session_id": "会话ID",
        "authenticated": true/false,
        "user_id": "用户ID",
        "created_at": "创建时间",
        "expires_at": "过期时间"
    }
    """
    if not qr_login_manager.current_session:
        raise HTTPException(status_code=404, detail="没有活跃的会话")
    
    session = qr_login_manager.current_session
    
    return {
        "session_id": session.session_id,
        "authenticated": session.is_authenticated,
        "user_id": session.user_id,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at.isoformat()
    }


# 在主 FastAPI app 中注册这些路由:
# 
# from fastapi import FastAPI
# from auth_endpoints import router as auth_router
# 
# app = FastAPI()
# app.include_router(auth_router)


if __name__ == "__main__":
    # 测试示例
    print("✅ 认证端点已准备")
    print("\n可用的API端点:")
    print("  POST /api/auth/generate-qr        - 生成QR码")
    print("  GET  /api/auth/status/{session_id} - 检查认证状态")
    print("  POST /api/auth/callback            - OAuth回调")
    print("  GET  /api/auth/verify              - 验证认证")
    print("  POST /api/auth/logout              - 登出")
    print("  GET  /api/auth/refresh-qr          - 刷新QR码")
    print("  GET  /api/auth/session-info        - 获取会话信息")
