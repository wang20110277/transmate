"""
OpenAI 兼容语音合成接口测试（mock TTS WebSocket 与 edge-tts，不依赖外部服务）

接口：POST /v1/audio/speech（JSON）
鉴权：需要登录态。
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from conftest import create_user

import app.base.tts_routes as tts_routes

URL = "/v1/audio/speech"


class FakeWebSocket:
    def __init__(self, frames):
        self.frames = list(frames)
        self.sent = None

    async def send(self, data):
        self.sent = json.loads(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.frames:
            return self.frames.pop(0)
        raise StopAsyncIteration


class FakeConnect:
    """模拟 websockets.connect(...) 返回的异步上下文管理器"""

    def __init__(self, fake_ws: FakeWebSocket):
        self.fake_ws = fake_ws

    async def __aenter__(self):
        return self.fake_ws

    async def __aexit__(self, *args):
        return False


class FakeEdgeStream:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.chunks:
            return self.chunks.pop(0)
        raise StopAsyncIteration


class FakeEdgeCommunicate:
    """模拟 edge_tts.Communicate（记录 text/voice/rate）"""
    last_instance = None
    stream_chunks = [{"type": "audio", "data": b"\xff\xfb"}, {"type": "audio", "data": b"\x90\x00"}]
    raise_error = None

    def __init__(self, text, voice, rate=None, **kwargs):
        self.text = text
        self.voice = voice
        self.rate = rate
        FakeEdgeCommunicate.last_instance = self

    def stream(self):
        if FakeEdgeCommunicate.raise_error:
            raise FakeEdgeCommunicate.raise_error
        return FakeEdgeStream(list(FakeEdgeCommunicate.stream_chunks))


@pytest.fixture
def client(monkeypatch, db, allow_any_token):
    import main as main_module
    from app.core.database import get_db

    monkeypatch.setattr(main_module, "init_db", lambda: None)

    def override_get_db():
        session = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    FakeEdgeCommunicate.raise_error = None
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.fixture
def user(db, allow_any_token):
    return create_user(db, "u1")


def _auth(user):
    return {"Authorization": f"Bearer {user.id}:test-device:test-token"}


def parse_wav(wav: bytes):
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    sample_rate = int.from_bytes(wav[24:28], "little")
    return sample_rate


# ==================== Edge TTS（默认引擎，tts-1） ====================

@pytest.mark.unit
def test_speech_edge_default(client, monkeypatch, user):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(URL, json={"input": "你好"}, headers=_auth(user))
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"\xff\xfb\x90\x00"
    # model 省略时默认 tts-1 → edge 引擎，默认中文女声，未指定 speed 不加 rate
    assert FakeEdgeCommunicate.last_instance.voice == tts_routes.EDGE_VOICE
    assert FakeEdgeCommunicate.last_instance.text == "你好"
    assert FakeEdgeCommunicate.last_instance.rate is None


@pytest.mark.unit
def test_speech_edge_accepts_openai_model_name(client, monkeypatch, user):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(
        URL, json={"model": "tts-1-hd", "input": "你好"}, headers=_auth(user)
    )
    assert response.status_code == 200


@pytest.mark.unit
def test_speech_edge_custom_voice_passthrough(client, monkeypatch, user):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(
        URL, json={"input": "你好", "voice": "zh-CN-YunxiNeural"}, headers=_auth(user)
    )
    assert response.status_code == 200
    assert FakeEdgeCommunicate.last_instance.voice == "zh-CN-YunxiNeural"


@pytest.mark.unit
def test_speech_maps_openai_voice_name(client, monkeypatch, user):
    """OpenAI 音色名（Edge 无法合成）应映射到可用中文音色，而不是直接透传导致 502"""
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(URL, json={"input": "你好", "voice": "alloy"}, headers=_auth(user))
    assert response.status_code == 200
    assert FakeEdgeCommunicate.last_instance.voice == "zh-CN-XiaoxiaoNeural"


@pytest.mark.unit
def test_speech_speed_maps_to_edge_rate(client, monkeypatch, user):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(URL, json={"input": "你好", "speed": 1.5}, headers=_auth(user))
    assert response.status_code == 200
    assert FakeEdgeCommunicate.last_instance.rate == "+50%"


@pytest.mark.unit
def test_speech_speed_out_of_range_400(client, user):
    response = client.post(URL, json={"input": "你好", "speed": 5.0}, headers=_auth(user))
    assert response.status_code == 400
    assert "speed" in response.json()["detail"]


@pytest.mark.unit
def test_speech_edge_rejects_non_mp3_format(client, user):
    """edge 只出 MP3，不做转码：请求 wav 明确报错而非返回假格式"""
    response = client.post(
        URL, json={"input": "你好", "response_format": "wav"}, headers=_auth(user)
    )
    assert response.status_code == 400
    assert "response_format" in response.json()["detail"]


@pytest.mark.unit
def test_speech_edge_failure(client, monkeypatch, user):
    FakeEdgeCommunicate.raise_error = RuntimeError("network down")
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(URL, json={"input": "你好"}, headers=_auth(user))
    assert response.status_code == 502
    assert "Edge TTS" in response.json()["detail"]


# ==================== CosyVoice（freeswitch-tts） ====================

def _patch_cosyvoice(monkeypatch, frames):
    fake = FakeWebSocket(frames)
    monkeypatch.setattr(tts_routes.websockets, "connect", lambda *a, **k: FakeConnect(fake))
    return fake


@pytest.mark.unit
def test_speech_cosyvoice_default_wav(client, monkeypatch, user):
    pcm = b"\x00\x01" * 100
    fake = _patch_cosyvoice(
        monkeypatch, [pcm, pcm, json.dumps({"status": "completed", "stats": {}})]
    )

    response = client.post(URL, json={"model": "cosyvoice", "input": "你好"}, headers=_auth(user))
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    body = response.content
    assert parse_wav(body) == tts_routes.TTS_SAMPLE_RATE
    assert len(body) == 44 + len(pcm) * 2
    assert body[44:] == pcm + pcm
    assert fake.sent["text"] == "你好"
    assert fake.sent["mode"] == "cross_lingual"


@pytest.mark.unit
def test_speech_cosyvoice_pcm_raw(client, monkeypatch, user):
    pcm = b"\x02\x03" * 50
    _patch_cosyvoice(monkeypatch, [pcm, json.dumps({"status": "completed"})])

    response = client.post(
        URL,
        json={"model": "cosyvoice", "input": "你好", "response_format": "pcm"},
        headers=_auth(user),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/pcm"
    assert response.content == pcm  # 裸 PCM，无 WAV 头


@pytest.mark.unit
def test_speech_cosyvoice_rejects_mp3(client, user):
    response = client.post(
        URL,
        json={"model": "cosyvoice", "input": "你好", "response_format": "mp3"},
        headers=_auth(user),
    )
    assert response.status_code == 400
    assert "response_format" in response.json()["detail"]


@pytest.mark.unit
def test_speech_cosyvoice_rejects_speed(client, user):
    """cosyvoice 协议无语速参数：显式报错，避免静默忽略"""
    response = client.post(
        URL, json={"model": "cosyvoice", "input": "你好", "speed": 1.5}, headers=_auth(user)
    )
    assert response.status_code == 400
    assert "speed" in response.json()["detail"]


@pytest.mark.unit
def test_speech_cosyvoice_error(client, monkeypatch, user):
    _patch_cosyvoice(monkeypatch, [json.dumps({"error": "invalid text", "code": "INVALID_PARAMS"})])

    response = client.post(URL, json={"model": "cosyvoice", "input": "你好"}, headers=_auth(user))
    assert response.status_code == 502
    assert "invalid text" in response.json()["detail"]


# ==================== 参数校验 ====================

@pytest.mark.unit
def test_speech_empty_input(client, user):
    response = client.post(URL, json={"input": "  "}, headers=_auth(user))
    assert response.status_code == 400


@pytest.mark.unit
def test_speech_unknown_model(client, user):
    response = client.post(URL, json={"model": "xxx", "input": "你好"}, headers=_auth(user))
    assert response.status_code == 400
    assert "未知模型" in response.json()["detail"]


@pytest.mark.unit
def test_speech_requires_auth(client):
    """匿名不得占用 TTS 推理资源"""
    assert client.post(URL, json={"input": "你好"}).status_code == 401
