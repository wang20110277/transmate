"""
用户服务模块
处理用户相关的数据库操作
"""

import bcrypt
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User


def hash_password(password: str) -> str:
    """使用bcrypt对密码进行哈希"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def generate_user_id() -> str:
    """生成唯一用户ID，格式: trans_xxxx"""
    return f"trans_{uuid.uuid4().hex[:16]}"


def get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    """通过手机号获取用户"""
    return db.query(User).filter(User.phone == phone).first()


def get_user_by_openid(db: Session, openid: str) -> Optional[User]:
    """通过微信openid获取用户"""
    return db.query(User).filter(User.wechat_openid == openid).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """通过ID获取用户"""
    return db.query(User).filter(User.id == user_id).first()


def create_user_by_phone(
    db: Session,
    phone: str,
    password: Optional[str] = None,
    register_source: str = "SMS",
) -> User:
    """
    通过手机号创建用户

    Args:
        db: 数据库会话
        phone: 手机号
        password: 密码（可选）
        register_source: 注册来源

    Returns:
        创建的用户对象
    """
    user = User(
        user_id=generate_user_id(),
        phone=phone,
        password_hash=hash_password(password) if password else None,
        is_password_set=1 if password else 0,
        register_source=register_source,
        status=1,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_user_by_wechat(
    db: Session, openid: str, unionid: Optional[str] = None, phone: Optional[str] = None
) -> User:
    """
    通过微信信息创建用户

    Args:
        db: 数据库会话
        openid: 微信openid
        unionid: 微信unionid（可选）
        phone: 手机号（可选）

    Returns:
        创建的用户对象
    """
    user = User(
        user_id=generate_user_id(),
        phone=phone,
        wechat_openid=openid,
        wechat_unionid=unionid,
        password_hash=None,
        is_password_set=0,
        register_source="WECHAT",
        status=1,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user_password(db: Session, user: User, password: str) -> User:
    """更新用户密码"""
    user.password_hash = hash_password(password)
    user.is_password_set = 1
    db.commit()
    db.refresh(user)
    return user


def update_user_phone(db: Session, user: User, phone: str) -> User:
    """更新用户手机号"""
    user.phone = phone
    db.commit()
    db.refresh(user)
    return user


def update_last_login(db: Session, user: User) -> User:
    """更新最后登录时间"""
    from datetime import datetime

    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)
    return user


def get_user_by_wechat_openid(db: Session, openid: str) -> Optional[User]:
    """
    通过微信openid获取用户（别名）

    Args:
        db: 数据库会话
        openid: 微信openid

    Returns:
        用户对象，如果不存在则返回None
    """
    return get_user_by_openid(db, openid)


def update_user_nickname(db: Session, user: User, nickname: str) -> User:
    """更新用户昵称"""
    user.nickname = nickname
    db.commit()
    db.refresh(user)
    return user


def create_user(db: Session, user_data: dict) -> User:
    """
    通用创建用户方法

    Args:
        db: 数据库会话
        user_data: 用户数据字典

    Returns:
        创建的用户对象
    """
    user = User(
        user_id=user_data.get("user_id", generate_user_id()),
        phone=user_data.get("phone"),
        email=user_data.get("email"),
        password_hash=user_data.get("password_hash"),
        is_password_set=user_data.get("is_password_set", 0),
        nickname=user_data.get("nickname"),
        avatar_url=user_data.get("avatar_url"),
        wechat_openid=user_data.get("wechat_openid"),
        wechat_unionid=user_data.get("wechat_unionid"),
        wechat_nickname=user_data.get("wechat_nickname"),
        wechat_avatar=user_data.get("wechat_avatar"),
        register_source=user_data.get("register_source", "WECHAT"),
        status=user_data.get("status", 1),
        role=user_data.get("role", "user"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
