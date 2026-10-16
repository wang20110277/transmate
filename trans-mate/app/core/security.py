"""
安全依赖：从请求中解析当前登录用户

【铁律】所有业务路由必须通过 Depends(get_current_user) 取身份，
禁止从 query/body 读取客户端自称的 user_id —— 否则任何人都能
通过改一个参数访问/删除他人的会话、制品与技能。
"""
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import get_current_user_from_token


def authenticate_token(db: Session, authorization: str) -> Optional[User]:
    """解析 Bearer token 返回正常状态用户；无效/已禁用返回 None

    HTTP 路由与 WebSocket 握手共用此函数，保证两侧鉴权口径一致。
    """
    user = get_current_user_from_token(db, authorization)
    if user is None or user.status != 1:
        return None
    return user


async def get_current_user(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> User:
    """HTTP 路由鉴权依赖：缺失或无效 token 一律 401

    header 用 Optional 默认 None：缺 header 时由本函数返回 401，
    而不是让 FastAPI 的参数校验先返回 422（对前端不友好且泄漏参数结构）。
    """
    user = authenticate_token(db, authorization or "")
    if user is None:
        raise HTTPException(status_code=401, detail="未登录或token已过期")
    return user
