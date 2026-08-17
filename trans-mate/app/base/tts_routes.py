"""
语音合成路由模块
支持两种引擎：
- edge: 微软 Edge TTS（在线，秒级，默认）
- cosyvoice: freeswitch-tts 服务（CosyVoice3，本地推理，CPU 较慢，接口保留）
"""

import json
import logging
import os
import struct
from typing import Optional

import websockets
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response

from app.core.config import TTS_WS_URL, TTS_PROMPT_WAV

try:
    import edge_tts
except ImportError:  # 未安装 edge-tts 时仅该引擎不可用
    edge_tts = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tts", tags=["语音合成"])

# CosyVoice3 输出格式：裸 PCM 16bit 小端 单声道 24kHz
TTS_SAMPLE_RATE = 24000
# 合成文本上限，避免 CPU 推理耗时过长
TTS_MAX_TEXT_LENGTH = 500
# 单次合成总超时
TTS_TIMEOUT = 180.0
# Edge TTS 默认音色（中文女声）
EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "zh-CN-XiaoxiaoNeural")
# Edge TTS 单次合成超时
EDGE_TIMEOUT = 60.0


class SynthesizeRequest(BaseModel):
    text: str = Field(..., description="待合成文本")
    provider: str = Field("edge", description="引擎: edge(默认) 或 cosyvoice")
    voice: Optional[str] = Field(None, description="Edge TTS 音色，如 zh-CN-XiaoxiaoNeural")


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


async def synthesize_with_edge(text: str, voice: Optional[str]) -> Response:
    """Edge TTS 在线合成，返回 MP3"""
    if edge_tts is None:
        raise HTTPException(status_code=503, detail="edge-tts 未安装")

    mp3 = bytearray()
    communicate = edge_tts.Communicate(text, voice or EDGE_VOICE)
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3.extend(chunk["data"])
    except Exception as e:
        logger.error(f"Edge TTS 合成失败: {e}")
        raise HTTPException(status_code=502, detail=f"Edge TTS合成失败: {e}")

    if not mp3:
        raise HTTPException(status_code=502, detail="Edge TTS未返回音频")

    return Response(content=bytes(mp3), media_type="audio/mpeg")


async def synthesize_with_cosyvoice(text: str) -> Response:
    """freeswitch-tts（CosyVoice3）本地合成，返回 WAV（24kHz）"""
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

    return Response(content=pcm_to_wav(bytes(pcm)), media_type="audio/wav")


@router.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """
    文本转语音。
    - provider=edge（默认）: 返回 audio/mpeg，延迟约 1~3 秒
    - provider=cosyvoice: 返回 audio/wav（24kHz），本地 CPU 推理较慢
    """
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="合成文本为空")
    text = text[:TTS_MAX_TEXT_LENGTH]

    provider = (request.provider or "edge").lower()
    if provider == "edge":
        return await synthesize_with_edge(text, request.voice)
    if provider == "cosyvoice":
        return await synthesize_with_cosyvoice(text)
    raise HTTPException(status_code=400, detail=f"未知引擎: {provider}")
