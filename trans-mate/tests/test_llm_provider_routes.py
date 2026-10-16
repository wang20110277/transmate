"""模型供应商（BYOK）API：全离线，模型调用以替身拦截

铁律：身份只取自 Authorization 头；API Key 只进不出（读取只回掩码）。
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy.orm import sessionmaker

import app.services.llm_provider_service as svc
import main as main_module
from app.core import config, crypto
from app.core.database import get_db
from conftest import create_user


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    """加解密用固定密钥，测试不依赖 .env 里的 SECRET_KEY"""
    monkeypatch.setattr(crypto, "SECRET_KEY", "unit-test-secret")


@pytest.fixture
def client(monkeypatch, db, allow_any_token):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(config, "RATE_LIMIT_ENABLED", False)
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


@pytest.fixture
def user(db):
    return create_user(db, "u1")


def _payload(**over):
    data = {
        "name": "智谱GLM",
        "api_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "sk-secret-key-1234567890",
        "models": ["glm-4-flash", "glm-4-plus"],
        "active_model": "glm-4-flash",
    }
    data.update(over)
    return data


@pytest.mark.unit
def test_requires_auth(client):
    assert client.get("/api/settings/llm/providers").status_code == 401
    assert client.post("/api/settings/llm/providers", json=_payload()).status_code == 401


@pytest.mark.unit
def test_create_masks_key_and_first_becomes_default(client, user, allow_any_token):
    headers = allow_any_token(user)
    resp = client.post("/api/settings/llm/providers", json=_payload(), headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "智谱GLM"
    assert body["is_default"] is True
    assert body["active_model"] == "glm-4-flash"
    assert body["api_key_masked"] == "sk-s******7890"
    # 明文 Key 绝不出现在响应里
    assert "sk-secret-key-1234567890" not in resp.text

    listed = client.get("/api/settings/llm/providers", headers=headers).json()
    assert listed["source"] == "user"
    assert listed["active_model"] == "glm-4-flash"
    assert listed["active_provider_name"] == "智谱GLM"
    assert len(listed["items"]) == 1


@pytest.mark.unit
def test_key_is_encrypted_at_rest(client, db, user, allow_any_token):
    from app.models.llm_provider import UserLLMProvider

    client.post("/api/settings/llm/providers", json=_payload(), headers=allow_any_token(user))
    row = db.query(UserLLMProvider).one()
    assert row.api_key_cipher != "sk-secret-key-1234567890"
    assert "sk-secret-key-1234567890" not in row.api_key_cipher


@pytest.mark.unit
def test_plaintext_key_never_returned_on_update(client, user, allow_any_token):
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    resp = client.put(
        f"/api/settings/llm/providers/{pid}",
        json={"models": ["glm-4-plus"]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["models"] == ["glm-4-plus"]
    assert body["active_model"] == "glm-4-plus"  # 原当前模型已不在列表 → 回落首个
    assert body["api_key_masked"] == "sk-s******7890"  # Key 未被清空


@pytest.mark.unit
def test_update_rejects_model_outside_list(client, user, allow_any_token):
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    resp = client.put(
        f"/api/settings/llm/providers/{pid}",
        json={"active_model": "gpt-4o"},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "不在模型列表中" in resp.json()["detail"]


@pytest.mark.unit
def test_create_requires_at_least_one_model(client, user, allow_any_token):
    resp = client.post(
        "/api/settings/llm/providers",
        json=_payload(models=[], active_model=None),
        headers=allow_any_token(user),
    )
    assert resp.status_code == 400


@pytest.mark.unit
def test_duplicate_name_rejected(client, user, allow_any_token):
    headers = allow_any_token(user)
    client.post("/api/settings/llm/providers", json=_payload(), headers=headers)
    resp = client.post("/api/settings/llm/providers", json=_payload(), headers=headers)
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


@pytest.mark.unit
def test_cannot_touch_other_users_provider(client, db, allow_any_token):
    u1 = create_user(db, "u1")
    u2 = create_user(db, "u2")
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=allow_any_token(u1)
    ).json()["id"]

    h2 = allow_any_token(u2)
    assert client.put(
        f"/api/settings/llm/providers/{pid}", json={"name": "x"}, headers=h2
    ).status_code == 404
    assert client.delete(f"/api/settings/llm/providers/{pid}", headers=h2).status_code == 404
    assert client.post(
        f"/api/settings/llm/providers/{pid}/default", headers=h2
    ).status_code == 404
    assert client.post(f"/api/settings/llm/providers/{pid}/test", headers=h2).status_code == 404
    # 别人的列表里看不到，也改不动
    assert client.get("/api/settings/llm/providers", headers=h2).json()["items"] == []


@pytest.mark.unit
def test_set_default_switches_active_model(client, user, allow_any_token):
    headers = allow_any_token(user)
    a = client.post(
        "/api/settings/llm/providers", json=_payload(name="A"), headers=headers
    ).json()
    b = client.post(
        "/api/settings/llm/providers",
        json=_payload(name="B", active_model="glm-4-plus"),
        headers=headers,
    ).json()
    assert a["is_default"] is True and b["is_default"] is False

    resp = client.post(f"/api/settings/llm/providers/{b['id']}/default", headers=headers)
    assert resp.status_code == 200

    listed = client.get("/api/settings/llm/providers", headers=headers).json()
    assert listed["active_provider_name"] == "B"
    assert listed["active_model"] == "glm-4-plus"
    defaults = [i["id"] for i in listed["items"] if i["is_default"]]
    assert defaults == [b["id"]]


@pytest.mark.unit
def test_delete_default_promotes_remaining(client, user, allow_any_token):
    headers = allow_any_token(user)
    a = client.post(
        "/api/settings/llm/providers", json=_payload(name="A"), headers=headers
    ).json()
    b = client.post(
        "/api/settings/llm/providers", json=_payload(name="B"), headers=headers
    ).json()
    client.post(f"/api/settings/llm/providers/{b['id']}/default", headers=headers)

    assert client.delete(
        f"/api/settings/llm/providers/{b['id']}", headers=headers
    ).status_code == 200
    listed = client.get("/api/settings/llm/providers", headers=headers).json()
    assert [i["id"] for i in listed["items"]] == [a["id"]]
    assert listed["items"][0]["is_default"] is True
    assert listed["source"] == "user"


@pytest.mark.unit
def test_disabling_default_falls_back_to_platform(client, user, allow_any_token):
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    resp = client.put(
        f"/api/settings/llm/providers/{pid}", json={"enabled": False}, headers=headers
    )
    assert resp.status_code == 200

    listed = client.get("/api/settings/llm/providers", headers=headers).json()
    assert listed["source"] == "env"
    assert listed["active_provider_name"] == "平台默认"


@pytest.mark.unit
def test_test_connection_success(client, user, allow_any_token, monkeypatch):
    seen = []

    class _Model:
        async def ainvoke(self, prompt, **kwargs):
            seen.append(prompt)
            return AIMessage(content="pong")

    monkeypatch.setattr(svc, "build_chat_model", lambda cfg: _Model())
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    body = client.post(f"/api/settings/llm/providers/{pid}/test", headers=headers).json()
    assert body["success"] is True
    assert "glm-4-flash" in body["message"]
    assert body["latency_ms"] is not None
    assert seen == ["ping"]


@pytest.mark.unit
def test_test_connection_failure_is_readable(client, user, allow_any_token, monkeypatch):
    class _Model:
        async def ainvoke(self, prompt, **kwargs):
            raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(svc, "build_chat_model", lambda cfg: _Model())
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    body = client.post(f"/api/settings/llm/providers/{pid}/test", headers=headers).json()
    assert body["success"] is False
    assert "401" in body["message"]


@pytest.mark.unit
def test_test_connection_timeout(client, user, allow_any_token, monkeypatch):
    class _Model:
        async def ainvoke(self, prompt, **kwargs):
            await asyncio.sleep(5)
            return AIMessage(content="too late")

    monkeypatch.setattr(svc, "build_chat_model", lambda cfg: _Model())
    monkeypatch.setattr(svc, "TEST_TIMEOUT_SECONDS", 0.01)
    headers = allow_any_token(user)
    pid = client.post(
        "/api/settings/llm/providers", json=_payload(), headers=headers
    ).json()["id"]

    body = client.post(f"/api/settings/llm/providers/{pid}/test", headers=headers).json()
    assert body["success"] is False
    assert "超时" in body["message"]
