"""技能路由:全离线(MockTransport+FakeStorage+内存库)"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import app.services.skill_service as skill_service
from app.core.database import get_db
import main as main_module


@pytest.fixture
def client(monkeypatch, db):
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
            return httpx.Response(200, json=[
                {"name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                 "size": 10, "download_url": "https://raw.test/demo-skill/SKILL.md"},
            ], request=request)
        if "raw.test" in str(request.url):
            return httpx.Response(
                200, text="---\nname: demo-skill\ndescription: 演示\n---\n# D\n",
                request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler)


@pytest.mark.unit
def test_registry_lists_with_installed_flag(client):
    resp = client.get("/api/skills/registry")
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["name"] == "demo-skill"
    assert item["installed"] is False


@pytest.mark.unit
def test_install_and_uninstall_roundtrip(client):
    resp = client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "demo-skill"

    listed = client.get("/api/skills/installed", params={"user_id": "u1"}).json()["items"]
    assert [i["name"] for i in listed] == ["demo-skill"]

    reg = client.get("/api/skills/registry/u1").json()["items"][0]
    assert reg["installed"] is True

    del_resp = client.delete("/api/skills/demo-skill", params={"user_id": "u1"})
    assert del_resp.status_code == 200
    assert client.get("/api/skills/installed", params={"user_id": "u1"}).json()["items"] == []


@pytest.mark.unit
def test_install_duplicate_returns_400(client):
    client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    resp = client.post("/api/skills/install", json={"user_id": "u1", "name": "demo-skill"})
    assert resp.status_code == 400


@pytest.mark.unit
def test_refresh_clears_cache(client):
    assert client.post("/api/skills/refresh").status_code == 200
