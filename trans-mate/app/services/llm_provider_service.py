"""
用户自带模型供应商（BYOK）的增删改查与连通性测试

约定：
- 每个用户至多一条 is_default=True（由本服务维护，删除/停用后自动补位）
- API Key 只以密文入库，对外一律掩码；更新时省略 api_key 表示沿用原值
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.llm.model_config import (
    SOURCE_USER,
    EffectiveModelConfig,
    build_chat_model,
    resolve_config,
)
from app.models.llm_provider import UserLLMProvider

logger = logging.getLogger(__name__)

TEST_TIMEOUT_SECONDS = 20
TEST_PROMPT = "ping"


class ProviderError(Exception):
    """业务校验失败（映射为对用户可见的 4xx）"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------- 序列化辅助

def _load_models(raw: str) -> List[str]:
    try:
        data = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(m) for m in data] if isinstance(data, list) else []


def _dump_models(models: List[str]) -> str:
    return json.dumps(models, ensure_ascii=False)


def _normalize_models(models: Optional[List[str]]) -> List[str]:
    """去空白、去重、保持顺序"""
    out: List[str] = []
    for item in models or []:
        name = str(item).strip()
        if name and name not in out:
            out.append(name)
    return out


def _pick_active(models: List[str], preferred: Optional[str], explicit: bool) -> str:
    """确定当前模型

    explicit=True 表示调用方明确指定了模型名，必须属于列表，否则报错；
    explicit=False 表示沿用旧值，已失效时静默回落到列表首个。
    """
    if not models:
        raise ProviderError("至少需要填写一个模型名")
    name = (preferred or "").strip()
    if name and name in models:
        return name
    if explicit and name:
        raise ProviderError(f"当前模型「{name}」不在模型列表中")
    return models[0]


def to_item(row: UserLLMProvider) -> Dict[str, Any]:
    """数据库行 → 对外视图（API Key 仅掩码）"""
    return {
        "id": row.id,
        "name": row.name,
        "provider": row.provider,
        "api_url": row.api_url,
        "api_key_masked": mask_secret(decrypt_secret(row.api_key_cipher)),
        "models": _load_models(row.models),
        "active_model": row.active_model,
        "temperature": row.temperature,
        "enabled": row.enabled,
        "is_default": row.is_default,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


# ---------------------------------------------------------------- 查询

def list_providers(db: Session, user_id: str) -> List[UserLLMProvider]:
    return (
        db.query(UserLLMProvider)
        .filter(UserLLMProvider.user_id == user_id)
        .order_by(UserLLMProvider.id.asc())
        .all()
    )


def get_provider(db: Session, user_id: str, provider_id: int) -> UserLLMProvider:
    row = (
        db.query(UserLLMProvider)
        .filter(
            UserLLMProvider.id == provider_id,
            UserLLMProvider.user_id == user_id,
        )
        .first()
    )
    if row is None:
        raise ProviderError("配置不存在", status_code=404)
    return row


def current_status(db: Session, user_id: str) -> Dict[str, str]:
    """当前实际生效的来源（用户配置 or 平台兜底）"""
    cfg = resolve_config(db, user_id)
    return {
        "source": cfg.source,
        "active_model": cfg.model,
        "active_provider_name": cfg.provider_name,
    }


# ---------------------------------------------------------------- 写入

def _clear_other_defaults(db: Session, user_id: str, keep_id: int) -> None:
    """保证同一用户只有一条 is_default（批量更新会绕过 onupdate，正合需要）"""
    (
        db.query(UserLLMProvider)
        .filter(
            UserLLMProvider.user_id == user_id,
            UserLLMProvider.id != keep_id,
            UserLLMProvider.is_default.is_(True),
        )
        .update({"is_default": False}, synchronize_session=False)
    )


def _promote_default(db: Session, user_id: str) -> None:
    """默认项被删/被停用后，把最早的启用项顶上"""
    candidate = (
        db.query(UserLLMProvider)
        .filter(
            UserLLMProvider.user_id == user_id,
            UserLLMProvider.enabled.is_(True),
        )
        .order_by(UserLLMProvider.id.asc())
        .first()
    )
    if candidate is None:
        return
    _clear_other_defaults(db, user_id, candidate.id)
    candidate.is_default = True
    db.commit()


def create_provider(db: Session, user_id: str, data: Dict[str, Any]) -> UserLLMProvider:
    models = _normalize_models(data.get("models"))
    requested = (data.get("active_model") or "").strip()
    active = _pick_active(models, requested, explicit=bool(requested))

    row = UserLLMProvider(
        user_id=user_id,
        name=(data["name"] or "").strip(),
        provider=(data.get("provider") or "openai").strip() or "openai",
        api_url=(data["api_url"] or "").strip(),
        api_key_cipher=encrypt_secret((data["api_key"] or "").strip()),
        models=_dump_models(models),
        active_model=active,
        temperature=data.get("temperature", 0.1),
        enabled=bool(data.get("enabled", True)),
    )
    # 第一条自动成为当前使用
    row.is_default = not list_providers(db, user_id)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProviderError(f"名称「{row.name}」已存在")
    db.refresh(row)
    if row.is_default:
        _clear_other_defaults(db, user_id, row.id)
        db.commit()
        db.refresh(row)
    return row


def update_provider(
    db: Session, user_id: str, provider_id: int, data: Dict[str, Any]
) -> UserLLMProvider:
    row = get_provider(db, user_id, provider_id)

    if data.get("name") is not None:
        row.name = (data["name"] or "").strip() or row.name
    if data.get("provider") is not None:
        row.provider = (data["provider"] or "").strip() or row.provider
    if data.get("api_url") is not None:
        row.api_url = (data["api_url"] or "").strip() or row.api_url
    if data.get("api_key"):
        # 前端回显的是掩码；空值/缺省 = 沿用原 Key
        row.api_key_cipher = encrypt_secret(data["api_key"].strip())
    if data.get("temperature") is not None:
        row.temperature = data["temperature"]
    if data.get("enabled") is not None:
        row.enabled = bool(data["enabled"])

    models = (
        _normalize_models(data["models"])
        if data.get("models") is not None
        else _load_models(row.models)
    )
    requested = (data.get("active_model") or "").strip()
    row.models = _dump_models(models)
    row.active_model = _pick_active(
        models, requested or row.active_model, explicit=bool(requested)
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ProviderError(f"名称「{row.name}」已存在")
    db.refresh(row)

    # 停用当前默认项时，另选一条顶上，避免"有配置却回退平台默认"
    if not row.enabled and row.is_default:
        _promote_default(db, user_id)
        db.refresh(row)
    return row


def delete_provider(db: Session, user_id: str, provider_id: int) -> None:
    row = get_provider(db, user_id, provider_id)
    was_default = row.is_default
    db.delete(row)
    db.commit()
    if was_default:
        _promote_default(db, user_id)


def set_default(db: Session, user_id: str, provider_id: int) -> UserLLMProvider:
    row = get_provider(db, user_id, provider_id)
    if not row.enabled:
        raise ProviderError("已停用的配置不能设为当前使用")
    _clear_other_defaults(db, user_id, row.id)
    row.is_default = True
    db.commit()
    db.refresh(row)
    return row


# ---------------------------------------------------------------- 连通性测试

def _stringify(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        parts = []
        for chunk in content:
            if isinstance(chunk, dict):
                parts.append(str(chunk.get("text", "")))
            else:
                parts.append(str(chunk))
        content = "".join(parts)
    return str(content or "").strip()


async def test_connection(db: Session, user_id: str, provider_id: int) -> Dict[str, Any]:
    """用该配置实际发一次极短请求，验证 URL / Key / 模型名三者都对得上"""
    row = get_provider(db, user_id, provider_id)
    api_key = decrypt_secret(row.api_key_cipher)
    if not api_key:
        return {
            "success": False,
            "message": "API Key 无法解密（SECRET_KEY 可能已轮换），请重新填写",
        }

    cfg = EffectiveModelConfig(
        model=row.active_model,
        provider=row.provider or "openai",
        api_url=row.api_url,
        api_key=api_key,
        temperature=row.temperature,
        source=SOURCE_USER,
        provider_name=row.name,
        provider_id=row.id,
    )

    started = time.monotonic()
    try:
        model = build_chat_model(cfg)
        result = await asyncio.wait_for(
            model.ainvoke(TEST_PROMPT), timeout=TEST_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return {"success": False, "message": f"连接超时（{TEST_TIMEOUT_SECONDS}s）"}
    except Exception as exc:  # noqa: BLE001 - 任何上游异常都要变成可读提示
        logger.warning("模型连通性测试失败 provider_id=%s: %s", provider_id, exc)
        return {"success": False, "message": f"连接失败：{exc}"}

    latency = int((time.monotonic() - started) * 1000)
    return {
        "success": True,
        "message": f"连接成功（{cfg.model}）",
        "latency_ms": latency,
        "sample": _stringify(result)[:100],
    }
