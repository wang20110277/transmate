"""
用户数据模型
"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, Integer
from app.core.database import Base


class User(Base):
    """用户表模型"""
    __tablename__ = "trans_user"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键")
    username = Column(String(50), nullable=False, unique=True, comment="用户名，唯一")
    email = Column(String(100), nullable=True, unique=True, comment="邮箱，唯一，可空")
    password_hash = Column(String(255), nullable=True, comment="密码哈希，可空")
    is_password_set = Column(Integer, nullable=False, default=0, comment="是否已设置密码: 0-未设置, 1-已设置")
    nickname = Column(String(50), nullable=True, comment="昵称")
    avatar_url = Column(String(500), nullable=True, comment="头像URL")
    phone = Column(String(20), nullable=True, unique=True, comment="手机号，唯一，可空")
    wechat_openid = Column(String(100), nullable=True, unique=True, comment="微信openid，唯一，可空")
    wechat_unionid = Column(String(100), nullable=True, comment="微信unionid，可空")
    register_source = Column(String(20), nullable=False, comment="注册来源：WECHAT, SMS, PASSWORD")
    status = Column(Integer, nullable=False, default=1, comment="状态: 1-正常, 0-禁用")
    role = Column(String(20), nullable=False, default="user", comment="角色: admin, user")
    created_at = Column(DateTime, nullable=True, default=datetime.now, comment="创建时间")
    updated_at = Column(DateTime, nullable=True, default=datetime.now, onupdate=datetime.now, comment="更新时间")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
