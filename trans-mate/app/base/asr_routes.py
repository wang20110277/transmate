"""
语音转写路由模块
代理转发音频到 freeswitch-asr 服务，实现语音转文字
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.core.config import ASR_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asr", tags=["语音转写"])

# 转写超时：ASR 首次推理与 ffmpeg 解码可能较慢
ASR_TIMEOUT = 60.0


@router.post("/transcribe")
async def transcribe_audio(request: Request):
    """
    接收原始音频字节（webm/wav/mp3 等任意格式），转发给 ASR 服务转写。

    响应: {"success": true, "text": "识别文字"}
    """
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="音频内容为空")

    try:
        async with httpx.AsyncClient(timeout=ASR_TIMEOUT) as client:
            response = await client.post(
                f"{ASR_BASE_URL}/asr/file",
                content=audio_bytes,
                headers={"Content-Type": "application/octet-stream"},
            )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"ASR 服务返回错误: {e.response.status_code} {e.response.text[:200]}")
        raise HTTPException(status_code=502, detail=f"ASR服务错误: {e.response.status_code}")
    except httpx.HTTPError as e:
        logger.error(f"ASR 服务连接失败: {e}")
        raise HTTPException(status_code=502, detail="ASR服务不可用")

    if not result.get("success"):
        raise HTTPException(status_code=502, detail=result.get("error", "ASR转写失败"))

    return {"success": True, "text": result.get("text", "")}
