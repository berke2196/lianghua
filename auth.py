"""
auth.py — JWT Token 生成与验证
安全特性：短期 token(8h)、jti 防重放、token 黑名单(登出)
"""
import os, time, secrets
from typing import Dict
import jwt
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
load_dotenv()

SECRET   = os.environ.get("JWT_SECRET", "")
ALG      = "HS256"
EXPIRE_H = int(os.environ.get("JWT_EXPIRE_HOURS", "8"))  # 默认 8 小时

if not SECRET or SECRET == "CHANGE_ME_IN_PRODUCTION_USE_RANDOM_32_CHARS":
    import secrets as _s
    from pathlib import Path as _Path
    SECRET = _s.token_hex(32)
    # 自动写入 .env，重启后不再随机（token 不会失效）
    _env_file = _Path(__file__).parent / ".env"
    try:
        _lines = _env_file.read_text(encoding="utf-8").splitlines() if _env_file.exists() else []
        if not any(l.startswith("JWT_SECRET=") for l in _lines):
            _lines.append(f"JWT_SECRET={SECRET}")
            _env_file.write_text("\n".join(_lines) + "\n", encoding="utf-8")
            print(f"[AUTH] ✅ JWT_SECRET 已自动生成并写入 .env（长期有效）")
        else:
            print("[AUTH] ⚠️  JWT_SECRET 已在 .env 中但未加载，请检查 load_dotenv() 调用顺序")
    except Exception as _e:
        print(f"[AUTH] ⚠️  JWT_SECRET 未设置且无法写入 .env: {_e}，重启后 token 将失效")

# ── Token 黑名单（登出后立即失效）──
# 生产环境应用 Redis；这里用字典存 jti->exp，支持按过期时间精确清理
_revoked_jtis: dict = {}  # jti -> exp(unix timestamp)

# ── 单设备登录：每个用户只保留一个有效 jti ──
_active_jti: dict = {}  # user_id -> jti

bearer = HTTPBearer(auto_error=False)

def create_token(user_id: int, username: str, is_admin: bool = False) -> str:
    # 踢掉旧 token（单设备登录）
    old_jti = _active_jti.get(user_id)
    if old_jti:
        _revoked_jtis[old_jti] = int(time.time()) + EXPIRE_H * 3600  # 保守估计旧token最晚过期时间

    jti = secrets.token_hex(16)
    _active_jti[user_id] = jti
    exp_ts = int(time.time()) + EXPIRE_H * 3600
    payload = {
        "sub":      str(user_id),
        "username": username,
        "admin":    is_admin,
        "jti":      jti,
        "exp":      exp_ts,
        "iat":      int(time.time()),
    }
    return jwt.encode(payload, SECRET, algorithm=ALG)

def revoke_token(token: str):
    """登出时将 jti 加入黑名单，并清除 _active_jti 记录"""
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALG])
        jti = payload.get("jti")
        uid = int(payload.get("sub", 0))
        if jti:
            exp = payload.get("exp", int(time.time()) + EXPIRE_H * 3600)
            _revoked_jtis[jti] = exp
            # 同步清除 active 记录（避免登出后旧jti仍占位）
            if _active_jti.get(uid) == jti:
                _active_jti.pop(uid, None)
            # 防止无限增长：超过 10000 条时只清除已过期的 jti
            if len(_revoked_jtis) > 10000:
                cleanup_revoked_jtis()
    except Exception:
        pass

def clear_active_jti(user_id: int):
    """踢下线 / 登出时主动清除该用户的单设备 jti 记录"""
    _active_jti.pop(user_id, None)

def cleanup_revoked_jtis():
    """清理黑名单中已过期的 jti 条目，防止内存无限增长；由定时任务定期调用"""
    now_ts = int(time.time())
    expired = [j for j, ex in list(_revoked_jtis.items()) if ex < now_ts]
    for j in expired:
        _revoked_jtis.pop(j, None)
    return len(expired)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期，请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token 无效")
    if payload.get("jti") in _revoked_jtis:  # dict membership check, O(1)
        raise HTTPException(status_code=401, detail="Token 已失效，请重新登录")
    return payload

def get_current_user(creds: HTTPAuthorizationCredentials = Security(bearer)) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="未登录，请先认证")
    return decode_token(creds.credentials)

def get_admin_user(creds: HTTPAuthorizationCredentials = Security(bearer)) -> dict:
    payload = get_current_user(creds)
    if not payload.get("admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return payload

def get_client_ip(request: Request) -> str:
    """获取真实客户端 IP（兼容反向代理）"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
