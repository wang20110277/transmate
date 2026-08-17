"""
语音合成代理路由测试（mock TTS WebSocket 与 edge-tts，不依赖外部服务）
"""
import json

import pytest
from fastapi.testclient import TestClient

import app.base.tts_routes as tts_routes


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
    """模拟 edge_tts.Communicate"""
    last_instance = None
    stream_chunks = [{"type": "audio", "data": b"\xff\xfb"}, {"type": "audio", "data": b"\x90\x00"}]
    raise_error = None

    def __init__(self, text, voice):
        self.text = text
        self.voice = voice
        FakeEdgeCommunicate.last_instance = self

    def stream(self):
        if FakeEdgeCommunicate.raise_error:
            raise FakeEdgeCommunicate.raise_error
        return FakeEdgeStream(list(FakeEdgeCommunicate.stream_chunks))


@pytest.fixture
def client(monkeypatch):
    import main as main_module
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    FakeEdgeCommunicate.raise_error = None
    with TestClient(main_module.app) as test_client:
        yield test_client


def parse_wav(wav: bytes):
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    sample_rate = int.from_bytes(wav[24:28], "little")
    return sample_rate


# ==================== Edge TTS（默认引擎） ====================

@pytest.mark.unit
def test_synthesize_edge_default(client, monkeypatch):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post("/api/tts/synthesize", json={"text": "你好"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"\xff\xfb\x90\x00"
    # 默认使用中文女声音色
    assert FakeEdgeCommunicate.last_instance.voice == tts_routes.EDGE_VOICE
    assert FakeEdgeCommunicate.last_instance.text == "你好"


@pytest.mark.unit
def test_synthesize_edge_custom_voice(client, monkeypatch):
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post(
        "/api/tts/synthesize",
        json={"text": "你好", "provider": "edge", "voice": "zh-CN-YunxiNeural"},
    )
    assert response.status_code == 200
    assert FakeEdgeCommunicate.last_instance.voice == "zh-CN-YunxiNeural"


@pytest.mark.unit
def test_synthesize_edge_failure(client, monkeypatch):
    FakeEdgeCommunicate.raise_error = RuntimeError("network down")
    monkeypatch.setattr(tts_routes.edge_tts, "Communicate", FakeEdgeCommunicate)

    response = client.post("/api/tts/synthesize", json={"text": "你好"})
    assert response.status_code == 502
    assert "Edge TTS" in response.json()["detail"]


# ==================== CosyVoice（freeswitch-tts） ====================

@pytest.mark.unit
def test_synthesize_cosyvoice_success(client, monkeypatch):
    pcm = b"\x00\x01" * 100
    fake = FakeWebSocket([pcm, pcm, json.dumps({"status": "completed", "stats": {}})])

    def fake_connect(*args, **kwargs):
        return FakeConnect(fake)

    monkeypatch.setattr(tts_routes.websockets, "connect", fake_connect)

    response = client.post("/api/tts/synthesize", json={"text": "你好", "provider": "cosyvoice"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    body = response.content
    assert parse_wav(body) == tts_routes.TTS_SAMPLE_RATE
    # WAV 头 44 字节 + 400 字节 PCM
    assert len(body) == 44 + len(pcm) * 2
    assert body[44:] == pcm + pcm
    # 请求帧带 cross_lingual 模式与参考音频
    assert fake.sent["text"] == "你好"
    assert fake.sent["mode"] == "cross_lingual"


@pytest.mark.unit
def test_synthesize_cosyvoice_error(client, monkeypatch):
    fake = FakeWebSocket([json.dumps({"error": "invalid text", "code": "INVALID_PARAMS"})])

    def fake_connect(*args, **kwargs):
        return FakeConnect(fake)

    monkeypatch.setattr(tts_routes.websockets, "connect", fake_connect)

    response = client.post("/api/tts/synthesize", json={"text": "你好", "provider": "cosyvoice"})
    assert response.status_code == 502
    assert "invalid text" in response.json()["detail"]


# ==================== 参数校验 ====================

@pytest.mark.unit
def test_synthesize_empty_text(client):
    response = client.post("/api/tts/synthesize", json={"text": "  "})
    assert response.status_code == 400


@pytest.mark.unit
def test_synthesize_unknown_provider(client):
    response = client.post("/api/tts/synthesize", json={"text": "你好", "provider": "xxx"})
    assert response.status_code == 400
    assert "未知引擎" in response.json()["detail"]
