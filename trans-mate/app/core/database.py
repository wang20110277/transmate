"""
模型基类和数据库连接
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，创建所有表"""
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401
    from app.models.skill import UserSkill, Artifact  # noqa: F401

    Base.metadata.create_all(bind=engine)
