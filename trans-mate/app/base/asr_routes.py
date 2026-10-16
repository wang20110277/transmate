"""
语音转写路由（OpenAI 兼容形态）

对外暴露 OpenAI 官方接口：
    POST /v1/audio/transcriptions   multipart/form-data: file, model, ...

可用 OpenAI SDK 直接指向本服务：
    OpenAI(base_url="http://<host>:8000/v1", api_key="<本服务 token>")
        .audio.transcriptions.create(...)

上游是本地 freeswitch-asr 服务（固定模型），本路由只做协议转译。
鉴权：必须登录——ASR 是 CPU 推理资源，匿名滥用会打满服务。
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.core.config import ASR_BASE_URL
from app.core.ratelimit import enforce_rate_limit
from app.core.security import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/audio", tags=["语音转写"])

# 转写超时：ASR 首次推理与 ffmpeg 解码可能较慢
ASR_TIMEOUT = 60.0

# 上游不返回时间戳，因此只支持这两种响应格式
SUPPORTED_RESPONSE_FORMATS = ("json", "text")


@router.post("/transcriptions")
async def create_transcription(
    file: UploadFile = File(..., description="音频文件，支持 webm/wav/mp3 等任意格式"),
    model: str = Form("whisper-1", description="兼容字段：上游为固定模型，此值不参与选择"),
    language: Optional[str] = Form(None, description="兼容字段：上游自动识别语种"),
    prompt: Optional[str] = Form(None, description="兼容字段：上游暂不支持"),
    response_format: str = Form("json", description="json(默认) 或 text"),
    temperature: Optional[float] = Form(None, description="兼容字段：上游暂不支持"),
    user: User = Depends(get_current_user),
):
    """
    OpenAI 兼容的语音转写接口。

    - response_format=json（默认）→ {"text": "..."}
    - response_format=text → 纯文本

    其余 OpenAI 响应格式（srt/vtt/verbose_json）依赖上游返回时间戳，暂不支持。
    """
    enforce_rate_limit(user.user_id, "asr_transcribe")

    fmt = (response_format or "json").strip().lower()
    if fmt not in SUPPORTED_RESPONSE_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"response_format={response_format} 暂不支持，仅支持: {list(SUPPORTED_RESPONSE_FORMATS)}",
        )

    audio_bytes = await file.read()
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

    text = result.get("text", "")
    if fmt == "text":
        return PlainTextResponse(text)
    return {"text": text}
