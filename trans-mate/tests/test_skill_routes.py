"""技能路由:全离线(MockTransport+FakeStorage+内存库)

鉴权约定：registry 可匿名浏览；安装/卸载/已装列表需登录态，
user_id 由 token 推导，不接受客户端指定。
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.services.skill_service as skill_service
from app.core.database import get_db
from conftest import create_user
import main as main_module


@pytest.fixture
def client(monkeypatch, db, allow_any_token):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    session_factory = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    # 注入离线 GitHub 与存储
    monkeypatch.setattr(skill_service, "_registry_transport", _registry_transport())
    monkeypatch.setattr(skill_service, "_storage_singleton_override",
                        __import__("tests.fake_storage", fromlist=["FakeStorage"]).FakeStorage())
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


def _registry_transport():
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "sha1"}, request=request)
        if path.endswith("/contents/"):
            return httpx.Response(200, json=[
                {"name": "demo-skill", "path": "demo-skill", "type": "dir"},
            ], request=request)
        if path.endswith("/contents/demo-skill/SKILL.md"):
            return httpx.Response(200, json=[{
                "name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                "size": 10, "download_url": "https://raw.test/demo-skill/SKILL.md",
            }], request=request)
        if path.endswith("/contents/demo-skill"):
            return httpx.Response(200, json=[{
                "name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                 "size": 10, "download_url": "https://raw.test/demo-skill/SKILL.md"},
            ], request=request)
        if "raw.test" in str(request.url):
            return httpx.Response(
                200, text="---\nname: demo-skill\ndescription: 演示\n---\n# D\n",
                request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler)


@pytest.fixture
def user(db):
    return create_user(db, "u1")


@pytest.mark.unit
def test_registry_lists_with_installed_flag(client, db, user, allow_any_token):
    resp = client.get("/api/skills/registry")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["name"] == "demo-skill"
    assert item["installed"] is False

    resp = client.get("/api/skills/registry/me", headers=allow_any_token(user))
    assert resp.json()["items"][0]["installed"] is False


@pytest.mark.unit
def test_install_and_uninstall_roundtrip(client, db, user, allow_any_token):
    headers = allow_any_token(user)
    resp = client.post("/api/skills/install", json={"name": "demo-skill"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo-skill"

    listed = client.get("/api/skills/installed", headers=headers).json()["items"]
    assert [i["name"] for i in listed] == ["demo-skill"]

    reg = client.get("/api/skills/registry/me", headers=headers).json()["items"][0]
    assert reg["installed"] is True

    del_resp = client.delete("/api/skills/demo-skill", headers=headers)
    assert del_resp.status_code == 200
    assert client.get("/api/skills/installed", headers=headers).json()["items"] == []


@pytest.mark.unit
def test_install_requires_auth(client):
    """未登录不能安装技能，也不能冒用他人 user_id 安装"""
    assert client.post("/api/skills/install", json={"name": "demo-skill"}).status_code == 401
    assert client.get("/api/skills/installed").status_code == 401


@pytest.mark.unit
def test_install_duplicate_returns_400(client, db, user, allow_any_token):
    headers = allow_any_token(user)
    client.post("/api/skills/install", json={"name": "demo-skill"}, headers=headers)
    resp = client.post("/api/skills/install", json={"name": "demo-skill"}, headers=headers)
    assert resp.status_code == 400


@pytest.mark.unit
def test_refresh_requires_admin(client, db, allow_any_token):
    user = create_user(db, "u1")
    resp = client.post("/api/skills/refresh", headers=allow_any_token(user))
    assert resp.status_code == 403

    admin = create_user(db, "admin1", role="admin")
    resp = client.post("/api/skills/refresh", headers=allow_any_token(admin))
    assert resp.status_code == 200
