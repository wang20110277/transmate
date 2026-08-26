"""
测试公共夹具
"""
import pytest
from sqlalchemy import create_engine, BigInteger, Integer
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base


def make_sqlite_engine(memory_shared: bool = True):
    """
    创建用于测试的 sqlite 引擎。
    sqlite 不支持 BIGINT 主键自增，创建表前将其映射为 INTEGER。
    """
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, BigInteger) and column.primary_key:
                column.type = Integer()

    if memory_shared:
        return create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine("sqlite://", connect_args={"check_same_thread": False})


@pytest.fixture
def db():
    """chat_service 单测用的独立内存库会话"""
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401
    from app.models.skill import UserSkill, Artifact  # noqa: F401

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
