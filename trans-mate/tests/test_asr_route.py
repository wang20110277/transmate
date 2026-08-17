"""
语音转写代理路由测试（mock ASR 服务，不依赖外部服务）
"""
import httpx
import pytest
from fastapi.testclient import TestClient

import app.base.asr_routes as asr_routes


@pytest.fixture
def client(monkeypatch):
    import main as main_module
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    with TestClient(main_module.app) as test_client:
        yield test_client


@pytest.mark.unit
def test_transcribe_success(client, monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"success": True, "text": "你好世界"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post("/api/asr/transcribe", content=b"fake-audio", headers={"Content-Type": "audio/webm"})
    assert response.status_code == 200
    assert response.json() == {"success": True, "text": "你好世界"}


@pytest.mark.unit
def test_transcribe_empty_body(client):
    response = client.post("/api/asr/transcribe", content=b"")
    assert response.status_code == 400


@pytest.mark.unit
def test_transcribe_asr_unavailable(client, monkeypatch):
    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post("/api/asr/transcribe", content=b"fake-audio")
    assert response.status_code == 502
    assert "不可用" in response.json()["detail"]


@pytest.mark.unit
def test_transcribe_asr_failure(client, monkeypatch):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"success": False, "error": "decode failed"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post("/api/asr/transcribe", content=b"fake-audio")
    assert response.status_code == 502
    assert "decode failed" in response.json()["detail"]
