"""
认证服务模块
处理Token生成、验证和刷新
"""
import secrets
import string
from typing import Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.core.redis import redis_client, RedisKeys, RedisTTL
from app.models.user import User
from app.services.user_service import get_user_by_id


def generate_token(length: int = 32) -> str:
    """生成随机Token字符串"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_device_id() -> str:
    """生成设备ID"""
    return generate_token(16)


def create_auth_tokens(user_id: int, device_id: Optional[str] = None) -> Tuple[str, str, str]:
    """
    创建认证Token
    
    Args:
        user_id: 用户ID
        device_id: 设备ID（可选，不传则自动生成）
    
    Returns:
        (access_token, refresh_token, device_id)
    """
    if device_id is None:
        device_id = generate_device_id()
    
    access_token = generate_token()
    refresh_token = generate_token()

    # 存储到Redis
    session_key = RedisKeys.auth_session(str(user_id), device_id)
    refresh_key = RedisKeys.auth_refresh(str(user_id), device_id)

    redis_client.setex(session_key, RedisTTL.AUTH_SESSION, access_token)
    redis_client.setex(refresh_key, RedisTTL.AUTH_REFRESH, refresh_token)

    return access_token, refresh_token, device_id


def wire_access_token(user_id: int, device_id: str, access_token: str) -> str:
    """wire 格式:登录/刷新接口返回给前端的 access_token 为
    `user_id:device_id:access_token` 三段(get_current_user_from_token 按此解析)。
    Redis 内部仍存裸 token,仅出口拼接。"""
    return f"{user_id}:{device_id}:{access_token}"


def verify_access_token(user_id: int, device_id: str, token: str) -> bool:
    """验证access_token是否有效"""
    session_key = RedisKeys.auth_session(str(user_id), device_id)
    stored_token = redis_client.get(session_key)
    return stored_token == token


def refresh_auth_tokens(user_id: int, device_id: str, refresh_token: str) -> Optional[Tuple[str, str]]:
    """
    刷新Token
    
    Args:
        user_id: 用户ID
        device_id: 设备ID
        refresh_token: 刷新token
    
    Returns:
        如果刷新成功，返回 (new_access_token, new_refresh_token)
        如果刷新失败，返回 None
    """
    refresh_key = RedisKeys.auth_refresh(str(user_id), device_id)
    stored_refresh_token = redis_client.get(refresh_key)
    
    if stored_refresh_token != refresh_token:
        return None
    
    # 生成新的token
    new_access_token = generate_token()
    new_refresh_token = generate_token()
    
    # 更新Redis
    session_key = RedisKeys.auth_session(str(user_id), device_id)
    redis_client.setex(session_key, RedisTTL.AUTH_SESSION, new_access_token)
    redis_client.setex(refresh_key, RedisTTL.AUTH_REFRESH, new_refresh_token)
    
    return new_access_token, new_refresh_token


def logout_user(user_id: int, device_id: str) -> bool:
    """
    用户登出，删除token
    
    Args:
        user_id: 用户ID
        device_id: 设备ID
    
    Returns:
        是否成功
    """
    try:
        session_key = RedisKeys.auth_session(str(user_id), device_id)
        refresh_key = RedisKeys.auth_refresh(str(user_id), device_id)
        redis_client.delete(session_key, refresh_key)
        return True
    except Exception:
        return False


def get_current_user_from_token(
    db: Session,
    authorization: str
) -> Optional[User]:
    """
    从Authorization header中获取当前用户
    
    Args:
        db: 数据库会话
        authorization: Authorization header值 (Bearer token)
    
    Returns:
        用户对象，如果token无效则返回None
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.replace("Bearer ", "")
    
    # 解析token，格式: user_id:device_id:access_token
    parts = token.split(":")
    if len(parts) != 3:
        return None
    
    try:
        user_id = int(parts[0])
        device_id = parts[1]
        access_token = parts[2]
    except ValueError:
        return None
    
    # 验证token
    if not verify_access_token(user_id, device_id, access_token):
        return None
    
    # 获取用户
    user = get_user_by_id(db, user_id)
    return user
