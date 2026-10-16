"""
Redis 固定窗口限流

RATE_LIMIT_* 配置项此前已定义但从未接线，等于无限流：
一个用户就能把 LLM key / 短信额度 / ASR-TTS 服务打满。
"""
import logging

from fastapi import HTTPException

from app.core import config
from app.core.redis import redis_client

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 60


def enforce_rate_limit(identity: str, action: str = "default") -> None:
    """按 action+identity 限流，超限抛 429

    Redis 不可用时放行（限流不应成为业务单点）。
    identity 建议用 user_id / 设备指纹等不可伪造值。
    """
    if not config.RATE_LIMIT_ENABLED:
        return

    limit = config.RATE_LIMIT_REQUESTS_PER_MINUTE
    if not limit or limit <= 0:
        return

    key = f"ratelimit:{action}:{identity}"
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, WINDOW_SECONDS)
        if current > limit:
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    except HTTPException:
        raise
    except Exception as exc:  # Redis 故障不限流，保证可用性
        logger.warning("限流检查失败，本次放行: %s", exc)


def enforce_ws_turn_limit(identity: str) -> None:
    """WebSocket 生成轮次限流（LLM 成本主入口）"""
    if not config.RATE_LIMIT_ENABLED:
        return

    limit = config.WS_RATE_LIMIT_TURNS_PER_MINUTE
    if not limit or limit <= 0:
        return

    key = f"ratelimit:ws_turn:{identity}"
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, WINDOW_SECONDS)
        if current > limit:
            raise HTTPException(status_code=429, detail="提问太频繁，请稍后再试")
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("WS 限流检查失败，本次放行: %s", exc)
