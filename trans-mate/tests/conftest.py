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
def db(monkeypatch):
    """chat_service 单测用的独立内存库会话"""
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401
    from app.models.skill import UserSkill, Artifact  # noqa: F401
    from app.models.llm_provider import UserLLMProvider  # noqa: F401

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    # 运行期懒导入 SessionLocal 的代码(如 save_artifact 工具)也落到同一测试库,
    # 避免误连开发库;import 时已绑定 SessionLocal 的模块(main.py 等)不受影响
    monkeypatch.setattr(
        "app.core.database.SessionLocal",
        sessionmaker(bind=engine, autocommit=False, autoflush=False),
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def allow_any_token(monkeypatch):
    """鉴权替身：任意 wire token 视为有效（测试不依赖 Redis 会话存储）

    生产环境中 token 有效性由 Redis 中的 auth:session 决定。
    返回鉴权头工厂，用法：headers=allow_any_token(user)
    """
    monkeypatch.setattr(
        "app.services.auth_service.verify_access_token",
        lambda user_id, device_id, token: True,
    )

    def _factory(user) -> dict:
        return {"Authorization": f"Bearer {user.id}:test-device:test-token"}

    return _factory


def create_user(db, user_id: str = "u1", **kwargs):
    """在测试库中造一个用户并返回（默认 status=1 正常）"""
    from app.models.user import User

    fields = dict(
        user_id=user_id,
        nickname=f"用户{user_id}",
        register_source="PASSWORD",
        status=1,
        is_password_set=1,
        role="user",
    )
    fields.update(kwargs)
    user = User(**fields)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
