"""
鉴权依赖与限流模块测试

覆盖 P0 安全修复的三个回归点：
1. 业务路由未带/带无效 token 一律 401
2. 禁用账号即使 token 有效也不得入境
3. 限流超阈值返回 429，且 Redis 故障时不阻断业务
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
import main as main_module
from conftest import create_user


class FakeRedis:
    """极简内存 Redis 替身：仅 incr + expire + 计数器"""

    def __init__(self):
        self.counters = {}

    def incr(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, key, ttl):
        return True


class BrokenRedis:
    def incr(self, key):
        raise ConnectionError("redis down")

    def expire(self, key, ttl):
        return True


@pytest.fixture
def client(monkeypatch, db, allow_any_token):
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    def override_get_db():
        session = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.fixture
def user(db):
    return create_user(db, "u1")


def _headers(user_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {user_id}:test-device:test-token"}


# ==================== 配置解析 ====================


def test_env_bool_parses_false_strings():
    """'false'/'0'/'no' 必须是假值：此前直接 os.getenv 导致恒为真"""
    from app.core.config import _env_bool

    for raw in ("false", "FALSE", "0", "no", "off", "", "   "):
        assert _env_bool("__NOPE__") is False
    assert _env_bool("__NOPE__", default=True) is True
    for raw in ("1", "true", "TRUE", "yes", "on"):
        import os
        os.environ["_TEST_BOOL"] = raw
        assert _env_bool("_TEST_BOOL") is True
    os.environ.pop("_TEST_BOOL", None)


def test_env_int_rejects_garbage():
    from app.core.config import _env_int

    import os
    os.environ["_TEST_INT"] = "abc"
    assert _env_int("_TEST_INT", default=7) == 7
    os.environ["_TEST_INT"] = "42"
    assert _env_int("_TEST_INT") == 42
    os.environ.pop("_TEST_INT", None)


# ==================== 路由鉴权 ====================


def test_conversations_require_token(client):
    """未带 token 一律 401（不让 FastAPI 用 422 抢答）"""
    assert client.get("/api/conversations").status_code == 401
    assert client.post("/api/conversations", json={"title": "x"}).status_code == 401


def test_conversations_reject_garbage_token(client):
    assert client.get("/api/conversations", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/conversations", headers={"Authorization": "Basic zzz"}).status_code == 401


def test_disabled_user_cannot_use_token(client, db, monkeypatch):
    """账号被禁用后，即便 Redis 里 token 仍有效也不得入境"""
    monkeypatch.setattr(
        "app.services.auth_service.verify_access_token",
        lambda user_id, device_id, token: True,
    )
    disabled = create_user(db, "u2", status=0)
    assert client.get("/api/conversations", headers=_headers(disabled.id)).status_code == 401


def test_me_still_works_for_valid_user(client, user, allow_any_token):
    resp = client.get("/api/auth/me", headers=allow_any_token(user))
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "u1"


# ==================== 限流 ====================


def test_rate_limit_blocks_after_threshold(monkeypatch):
    from app.core import ratelimit

    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "redis_client", fake)
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_REQUESTS_PER_MINUTE", 3)

    for _ in range(3):
        ratelimit.enforce_rate_limit("u1", "probe")
    with pytest.raises(Exception) as exc:
        ratelimit.enforce_rate_limit("u1", "probe")
    assert getattr(exc.value, "status_code", None) == 429
    # 其他 action 有独立窗口
    ratelimit.enforce_rate_limit("u1", "other")


def test_rate_limit_noop_when_disabled(monkeypatch):
    from app.core import ratelimit

    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "redis_client", fake)
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_ENABLED", False)

    for _ in range(100):
        ratelimit.enforce_rate_limit("u1", "probe")


def test_rate_limit_degrades_when_redis_down(monkeypatch):
    """Redis 故障必须放行：限流不能成为业务单点"""
    from app.core import ratelimit

    monkeypatch.setattr(ratelimit, "redis_client", BrokenRedis())
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_ENABLED", True)

    for _ in range(50):
        ratelimit.enforce_rate_limit("u1", "probe")


def test_ws_turn_limit_uses_its_own_threshold(monkeypatch):
    from app.core import ratelimit

    fake = FakeRedis()
    monkeypatch.setattr(ratelimit, "redis_client", fake)
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(ratelimit.config, "WS_RATE_LIMIT_TURNS_PER_MINUTE", 2)
    monkeypatch.setattr(ratelimit.config, "RATE_LIMIT_REQUESTS_PER_MINUTE", 99)

    ratelimit.enforce_ws_turn_limit("u1")
    ratelimit.enforce_ws_turn_limit("u1")
    with pytest.raises(Exception) as exc:
        ratelimit.enforce_ws_turn_limit("u1")
    assert exc.value.status_code == 429
