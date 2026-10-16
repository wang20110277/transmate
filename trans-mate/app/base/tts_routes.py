"""
语音合成路由（OpenAI 兼容形态）

对外暴露 OpenAI 官方接口：
    POST /v1/audio/speech   JSON: model, input, voice, response_format, speed

    from openai import OpenAI
    client = OpenAI(base_url="http://<host>:8000/v1", api_key="<本服务 token>")
    client.audio.speech.create(model="tts-1", voice="alloy", input="你好")

上游引擎（由 model 选择）：
- edge（默认，tts-1 / tts-1-hd / gpt-4o-mini-tts）: 微软 Edge TTS 在线合成，输出 MP3
- cosyvoice（cosyvoice / cosyvoice3）: freeswitch-tts 本地 CosyVoice3 推理，输出 WAV/PCM

鉴权：必须登录——合成是外部/本地推理资源，匿名滥用会打满服务。
"""

import json
import logging
import os
import struct
from typing import Optional

import websockets
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.config import TTS_WS_URL, TTS_PROMPT_WAV
from app.core.ratelimit import enforce_rate_limit
from app.core.security import get_current_user
from app.models.user import User

try:
    import edge_tts
except ImportError:  # 未安装 edge-tts 时仅该引擎不可用
    edge_tts = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["语音合成"])

# CosyVoice3 输出格式：裸 PCM 16bit 小端 单声道 24kHz
TTS_SAMPLE_RATE = 24000
# 合成文本上限，避免推理耗时过长（OpenAI 上限 4096，此处按本服务能力收紧）
TTS_MAX_TEXT_LENGTH = 500
# Edge TTS 默认音色（中文女声）
EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "zh-CN-XiaoxiaoNeural")

# 模型名 → 引擎：兼容 OpenAI 官方模型名，也接受本项目引擎名
MODEL_TO_ENGINE = {
    "tts-1": "edge",
    "tts-1-hd": "edge",
    "gpt-4o-mini-tts": "edge",
    "edge": "edge",
    "cosyvoice": "cosyvoice",
    "cosyvoice3": "cosyvoice",
}
# 各引擎省略 response_format 时的原生输出格式
ENGINE_DEFAULT_FORMAT = {"edge": "mp3", "cosyvoice": "wav"}
# 各引擎支持的输出格式（不做转码，只暴露引擎原生能力）
ENGINE_FORMATS = {"edge": {"mp3"}, "cosyvoice": {"wav", "pcm"}}
FORMAT_MEDIA_TYPE = {"mp3": "audio/mpeg", "wav": "audio/wav", "pcm": "audio/pcm"}

# OpenAI 标准音色名 → Edge 音色：Edge 无法合成这些名字，映射到中文音色
OPENAI_VOICE_TO_EDGE = {
    "alloy": "zh-CN-XiaoxiaoNeural",
    "echo": "zh-CN-YunxiNeural",
    "fable": "zh-CN-XiaoyiNeural",
    "onyx": "zh-CN-YunjianNeural",
    "nova": "zh-CN-XiaoxiaoNeural",
    "shimmer": "zh-CN-XiaoyiNeural",
    "coral": "zh-CN-XiaoxiaoNeural",
    "sage": "zh-CN-YunxiNeural",
    "ash": "zh-CN-YunjianNeural",
    "ballad": "zh-CN-YunxiNeural",
    "verse": "zh-CN-YunxiNeural",
}

# OpenAI speed 允许范围
SPEED_MIN, SPEED_MAX = 0.25, 4.0
# Edge TTS rate 可接受的百分比上限，超出会被上游拒绝
EDGE_RATE_LIMIT_PCT = 100


class SpeechRequest(BaseModel):
    """OpenAI /v1/audio/speech 请求体"""

    model: str = Field("tts-1", description="模型名：tts-1 / tts-1-hd / gpt-4o-mini-tts / cosyvoice")
    input: str = Field(..., description="待合成文本")
    voice: Optional[str] = Field(
        None, description="音色：OpenAI 名（alloy 等）或 Edge 音色名（zh-CN-XiaoxiaoNeural）"
    )
    response_format: Optional[str] = Field(
        None, description="mp3/wav/pcm；省略时取引擎原生格式（edge→mp3, cosyvoice→wav）"
    )
    speed: Optional[float] = Field(None, description="语速 0.25~4.0，仅 edge 引擎支持")


def resolve_voice(voice: Optional[str]) -> str:
    """OpenAI 音色名映射到 Edge 音色；其余原样透传（可能是合法 Edge 音色名）"""
    name = (voice or "").strip()
    if not name:
        return EDGE_VOICE
    return OPENAI_VOICE_TO_EDGE.get(name.lower(), name)


def speed_to_edge_rate(speed: float) -> str:
    """OpenAI speed（1.0 为常速）换算为 Edge rate 百分比字符串，并按 Edge 能力截断"""
    pct = int(round((speed - 1) * 100))
    pct = max(-EDGE_RATE_LIMIT_PCT, min(EDGE_RATE_LIMIT_PCT, pct))
    return f"{pct:+d}%"


def pcm_to_wav(pcm: bytes, sample_rate: int = TTS_SAMPLE_RATE) -> bytes:
    """给裸 PCM 封装 WAV 头（16bit 单声道）"""
    channels, sample_width = 1, 2
    data_size = len(pcm)
    header = b"RIFF" + struct.pack("<I", 36 + data_size) + b"WAVE"
    header += b"fmt " + struct.pack(
        "<IHHIIHH",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * channels * sample_width,
        channels * sample_width,
        sample_width * 8,
    )
    header += b"data" + struct.pack("<I", data_size)
    return header + pcm


async def synthesize_with_edge(text: str, voice: str, rate: Optional[str] = None) -> bytes:
    """Edge TTS 在线合成，返回 MP3 字节"""
    if edge_tts is None:
        raise HTTPException(status_code=503, detail="edge-tts 未安装")

    mp3 = bytearray()
    kwargs = {"rate": rate} if rate else {}
    communicate = edge_tts.Communicate(text, voice, **kwargs)
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3.extend(chunk["data"])
    except Exception as e:
        logger.error(f"Edge TTS 合成失败: {e}")
        raise HTTPException(status_code=502, detail=f"Edge TTS合成失败: {e}")

    if not mp3:
        raise HTTPException(status_code=502, detail="Edge TTS未返回音频")

    return bytes(mp3)


async def synthesize_with_cosyvoice(text: str) -> bytes:
    """freeswitch-tts（CosyVoice3）本地合成，返回裸 PCM（24kHz）"""
    pcm = bytearray()
    error: Optional[dict] = None
    try:
        async with websockets.connect(TTS_WS_URL, open_timeout=10) as ws:
            await ws.send(
                json.dumps(
                    {
                        "text": text,
                        "mode": "cross_lingual",
                        "prompt_wav": TTS_PROMPT_WAV,
                        "stream": True,
                    }
                )
            )
            async for message in ws:
                if isinstance(message, (bytes, bytearray)):
                    pcm.extend(message)
                    continue
                data = json.loads(message)
                if data.get("error"):
                    error = data
                    break
                if data.get("status") == "completed":
                    break
    except TimeoutError:
        logger.error("TTS 合成超时")
        raise HTTPException(status_code=504, detail="TTS合成超时")
    except websockets.WebSocketException as e:
        logger.error(f"TTS 服务连接失败: {e}")
        raise HTTPException(status_code=502, detail="TTS服务不可用")

    if error:
        logger.error(f"TTS 服务返回错误: {error}")
        raise HTTPException(status_code=502, detail=error.get("error", "TTS合成失败"))
    if not pcm:
        raise HTTPException(status_code=502, detail="TTS未返回音频")

    return bytes(pcm)


@router.post("/speech")
async def create_speech(
    request: SpeechRequest,
    user: User = Depends(get_current_user),
):
    """OpenAI 兼容的语音合成接口：返回音频字节流（非 JSON）"""
    enforce_rate_limit(user.user_id, "tts_synthesize")

    text = request.input.strip()
    if not text:
        raise HTTPException(status_code=400, detail="合成文本为空")
    text = text[:TTS_MAX_TEXT_LENGTH]

    model = (request.model or "tts-1").strip().lower()
    engine = MODEL_TO_ENGINE.get(model)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"未知模型: {request.model}；支持: {sorted(MODEL_TO_ENGINE)}",
        )

    fmt = (request.response_format or ENGINE_DEFAULT_FORMAT[engine]).strip().lower()
    if fmt not in ENGINE_FORMATS[engine]:
        raise HTTPException(
            status_code=400,
            detail=(
                f"模型 {model} 不支持 response_format={request.response_format}；"
                f"支持: {sorted(ENGINE_FORMATS[engine])}"
            ),
        )

    speed = request.speed
    if speed is not None and not (SPEED_MIN <= speed <= SPEED_MAX):
        raise HTTPException(
            status_code=400, detail=f"speed 需在 {SPEED_MIN}~{SPEED_MAX} 之间"
        )

    media_type = FORMAT_MEDIA_TYPE[fmt]

    if engine == "edge":
        rate = None
        if speed is not None and speed != 1.0:
            rate = speed_to_edge_rate(speed)
        audio = await synthesize_with_edge(text, resolve_voice(request.voice), rate)
        return Response(content=audio, media_type=media_type)

    # cosyvoice
    if speed is not None and speed != 1.0:
        raise HTTPException(status_code=400, detail="cosyvoice 引擎暂不支持 speed")

    pcm = await synthesize_with_cosyvoice(text)
    if fmt == "pcm":
        return Response(content=pcm, media_type=media_type)
    return Response(content=pcm_to_wav(pcm), media_type=media_type)
