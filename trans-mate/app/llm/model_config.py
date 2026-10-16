"""
按用户解析实际生效的模型配置（BYOK）

优先级：用户默认供应商 → 平台 .env 兜底。
用户配置不完整（缺 key / 缺模型名 / 密文解不开）时安静回退平台默认，
保证「用户配错了」也不会把对话打断。

本模块是 chat model 的唯一构造入口，harness 与「测试连接」都走这里，
避免两处各写一份 init_chat_model 参数而漂移。
"""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import (
    DEFAULT_API_KEY,
    DEFAULT_API_URL,
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
)
from app.core.crypto import decrypt_secret

logger = logging.getLogger(__name__)

SOURCE_USER = "user"
SOURCE_ENV = "env"

ENV_PROVIDER_NAME = "平台默认"


@dataclass(frozen=True)
class EffectiveModelConfig:
    """一次对话实际使用的模型参数"""

    model: str
    provider: str
    api_url: str
    api_key: str
    temperature: float
    source: str
    provider_name: str = ENV_PROVIDER_NAME
    provider_id: Optional[int] = None


def env_config() -> EffectiveModelConfig:
    """平台兜底配置（.env 的 DEFAULT_*）"""
    return EffectiveModelConfig(
        model=DEFAULT_MODEL or "",
        provider=DEFAULT_PROVIDER or "openai",
        api_url=DEFAULT_API_URL or "",
        api_key=DEFAULT_API_KEY or "",
        temperature=0.1,
        source=SOURCE_ENV,
    )


def select_provider_row(db: Optional[Session], user_id: Optional[str]):
    """取该用户实际生效的供应商行：默认项优先，否则最早创建的启用项

    返回 None 表示该用户没有可用配置，调用方回退平台默认。
    """
    if db is None or not user_id:
        return None
    from app.models.llm_provider import UserLLMProvider

    query = db.query(UserLLMProvider).filter(
        UserLLMProvider.user_id == user_id,
        UserLLMProvider.enabled.is_(True),
    )
    row = query.filter(UserLLMProvider.is_default.is_(True)).first()
    if row is None:
        row = query.order_by(UserLLMProvider.id.asc()).first()
    return row


def resolve_config(db: Optional[Session], user_id: Optional[str]) -> EffectiveModelConfig:
    """解析该用户当前生效的模型配置"""
    row = select_provider_row(db, user_id)
    if row is None:
        return env_config()

    api_key = decrypt_secret(row.api_key_cipher)
    if not api_key or not row.active_model or not row.api_url:
        logger.warning(
            "用户 %s 的模型配置不完整（provider_id=%s），回退平台默认", user_id, row.id
        )
        return env_config()

    return EffectiveModelConfig(
        model=row.active_model,
        provider=row.provider or "openai",
        api_url=row.api_url,
        api_key=api_key,
        temperature=row.temperature,
        source=SOURCE_USER,
        provider_name=row.name,
        provider_id=row.id,
    )


def config_fingerprint(db: Optional[Session], user_id: Optional[str]) -> str:
    """配置指纹：变化即需重建缓存的 agent（换模型 / 换 key / 换默认项）"""
    row = select_provider_row(db, user_id)
    if row is None:
        return SOURCE_ENV
    stamp = row.updated_at.isoformat() if row.updated_at else ""
    return f"{SOURCE_USER}:{row.id}:{stamp}:{row.active_model}"


def build_chat_model(cfg: EffectiveModelConfig):
    """构造 langchain chat model（唯一的模型构造入口）"""
    from langchain.chat_models import init_chat_model

    return init_chat_model(
        model=cfg.model,
        model_provider=cfg.provider,
        base_url=cfg.api_url,
        api_key=cfg.api_key,
        temperature=cfg.temperature,
    )
