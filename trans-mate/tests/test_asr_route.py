"""
OpenAI 兼容语音转写接口测试（mock 上游 ASR 服务，不依赖外部服务）

接口：POST /v1/audio/transcriptions（multipart/form-data）
鉴权：需要登录态（ASR 是推理资源，匿名滥用会打满服务）。
"""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
import main as main_module
from conftest import create_user

URL = "/v1/audio/transcriptions"


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
    try:
        with TestClient(main_module.app) as test_client:
            yield test_client
    finally:
        main_module.app.dependency_overrides.clear()


@pytest.fixture
def user(db, allow_any_token):
    return create_user(db, "u1")


def _files(content: bytes = b"fake-audio"):
    return {"file": ("recording.webm", content, "audio/webm")}


@pytest.mark.unit
def test_transcribe_success_returns_openai_shape(client, monkeypatch, user, allow_any_token):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"success": True, "text": "你好世界"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post(
        URL, files=_files(), data={"model": "whisper-1"}, headers=allow_any_token(user)
    )
    assert response.status_code == 200
    # OpenAI 形态：{"text": ...}，而非旧的 {"success": ..., "text": ...}
    assert response.json() == {"text": "你好世界"}


@pytest.mark.unit
def test_transcribe_response_format_text(client, monkeypatch, user, allow_any_token):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"success": True, "text": "纯文本"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post(
        URL, files=_files(), data={"response_format": "text"}, headers=allow_any_token(user)
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "纯文本"


@pytest.mark.unit
def test_transcribe_rejects_unsupported_response_format(client, user, allow_any_token):
    """上游不返回时间戳，srt/vtt/verbose_json 明确拒绝而非静默降级"""
    response = client.post(
        URL, files=_files(), data={"response_format": "srt"}, headers=allow_any_token(user)
    )
    assert response.status_code == 400
    assert "response_format" in response.json()["detail"]


@pytest.mark.unit
def test_transcribe_requires_auth(client):
    """匿名不得占用 ASR 推理资源"""
    assert client.post(URL, files=_files(), data={"model": "whisper-1"}).status_code == 401


@pytest.mark.unit
def test_transcribe_empty_file(client, user, allow_any_token):
    response = client.post(
        URL, files=_files(b""), data={"model": "whisper-1"}, headers=allow_any_token(user)
    )
    assert response.status_code == 400
    assert "为空" in response.json()["detail"]


@pytest.mark.unit
def test_transcribe_asr_unavailable(client, monkeypatch, user, allow_any_token):
    async def fake_post(self, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post(URL, files=_files(), headers=allow_any_token(user))
    assert response.status_code == 502
    assert "不可用" in response.json()["detail"]


@pytest.mark.unit
def test_transcribe_asr_failure(client, monkeypatch, user, allow_any_token):
    async def fake_post(self, url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"success": False, "error": "decode failed"}, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    response = client.post(URL, files=_files(), headers=allow_any_token(user))
    assert response.status_code == 502
    assert "decode failed" in response.json()["detail"]
