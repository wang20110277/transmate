"""鉴权路由:password/login 的 wire token 协议(登录后 /me 必须可用)

get_current_user_from_token 要求 Authorization Bearer 携带
`user_id:device_id:access_token` 三段格式,登录/刷新端点必须按该协议返回。
"""
import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
import main as main_module

WIRE_TOKEN_RE = re.compile(r"^\d+:[^:]+:[^:]+$")


class FakeRedis:
    """auth_service 用到的最小 Redis 表面(setex/get/delete)"""

    def __init__(self):
        self.data = {}

    def setex(self, key, ttl, value):
        self.data[key] = value

    def get(self, key):
        return self.data.get(key)

    def delete(self, key):
        self.data.pop(key, None)


@pytest.fixture
def client(monkeypatch, db):
    import app.services.auth_service as auth_service

    monkeypatch.setattr(auth_service, "redis_client", FakeRedis())
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    session_factory = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.mark.unit
def test_password_login_returns_wire_token(client):
    """新手机号注册登录:access_token 必须是 user_id:device_id:token 三段"""
    resp = client.post(
        "/api/auth/password/login",
        json={"phone": "13800138000", "password": "test123456",
              "confirm_password": "test123456"},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert WIRE_TOKEN_RE.match(token), f"非三段 wire 格式: {token}"


@pytest.mark.unit
def test_password_login_then_me_roundtrip(client):
    """登录拿到的 token 直接调 /me 必须通过(前后端协议一致)"""
    login = client.post(
        "/api/auth/password/login",
        json={"phone": "13800138001", "password": "test123456",
              "confirm_password": "test123456"},
    )
    token = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["phone"] == "13800138001"


@pytest.mark.unit
def test_refresh_returns_wire_token(client):
    """refresh 端点同样必须返回三段 wire token"""
    login = client.post(
        "/api/auth/password/login",
        json={"phone": "13800138002", "password": "test123456",
              "confirm_password": "test123456"},
    )
    data = login.json()
    uid = data["id"]
    device_id = data["device_id"]

    refreshed = client.post(
        "/api/auth/refresh",
        json={"user_id": uid, "device_id": device_id,
              "refresh_token": data["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert WIRE_TOKEN_RE.match(refreshed.json()["access_token"])
