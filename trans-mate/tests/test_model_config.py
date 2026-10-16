"""BYOK 模型解析与 harness 缓存失效

覆盖：
- 敏感字段加解密 / 掩码 / 密文损坏降级
- resolve_config 的「用户配置 → 平台兜底」优先级
- 换模型后 harness 必须重建 agent（否则一直用旧模型）
"""
import pytest

import app.llm.harness.deep_agent_harness as dah
from app.core import crypto
from app.llm.harness.deep_agent_harness import DeepAgentHarness
from app.llm.model_config import (
    SOURCE_ENV,
    SOURCE_USER,
    config_fingerprint,
    resolve_config,
)
from app.models.llm_provider import UserLLMProvider
from app.services import llm_provider_service as svc


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    """加解密用固定密钥，测试不依赖 .env 里的 SECRET_KEY"""
    monkeypatch.setattr(crypto, "SECRET_KEY", "unit-test-secret")


def _provider(**over):
    data = {
        "name": "智谱GLM",
        "api_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key": "sk-test-key-abcdefgh",
        "models": ["glm-4-flash", "glm-4-plus"],
        "active_model": "glm-4-flash",
    }
    data.update(over)
    return data


# ---------------------------------------------------------------- 加密

@pytest.mark.unit
def test_encrypt_roundtrip_and_mask():
    cipher = crypto.encrypt_secret("sk-test-key-abcdefgh")
    assert cipher != "sk-test-key-abcdefgh"
    assert crypto.decrypt_secret(cipher) == "sk-test-key-abcdefgh"
    assert crypto.mask_secret("sk-test-key-abcdefgh") == "sk-t******efgh"
    assert crypto.mask_secret("short") == "*****"
    assert crypto.mask_secret("") == ""


@pytest.mark.unit
def test_decrypt_garbage_returns_empty():
    """密文损坏/密钥轮换时不抛异常，返回空串交给上层降级"""
    assert crypto.decrypt_secret("not-a-valid-token") == ""
    assert crypto.decrypt_secret("") == ""


@pytest.mark.unit
def test_decrypt_fails_after_secret_rotation(monkeypatch):
    cipher = crypto.encrypt_secret("sk-test-key-abcdefgh")
    monkeypatch.setattr(crypto, "SECRET_KEY", "rotated-secret")
    assert crypto.decrypt_secret(cipher) == ""


# ---------------------------------------------------------------- 解析

@pytest.mark.unit
def test_no_config_falls_back_to_env(db):
    cfg = resolve_config(db, "u1")
    assert cfg.source == SOURCE_ENV
    assert config_fingerprint(db, "u1") == SOURCE_ENV


@pytest.mark.unit
def test_user_config_takes_precedence(db):
    svc.create_provider(db, "u1", _provider())
    cfg = resolve_config(db, "u1")
    assert cfg.source == SOURCE_USER
    assert cfg.model == "glm-4-flash"
    assert cfg.api_key == "sk-test-key-abcdefgh"
    assert cfg.api_url == "https://open.bigmodel.cn/api/paas/v4"
    assert cfg.provider_name == "智谱GLM"


@pytest.mark.unit
def test_config_is_per_user(db):
    svc.create_provider(db, "u1", _provider())
    assert resolve_config(db, "u2").source == SOURCE_ENV


@pytest.mark.unit
def test_disabled_or_undecryptable_falls_back_to_env(db, monkeypatch):
    row = svc.create_provider(db, "u1", _provider())
    svc.update_provider(db, "u1", row.id, {"enabled": False})
    assert resolve_config(db, "u1").source == SOURCE_ENV

    # 重新启用，但密钥已轮换 → 解不开 → 仍回退平台默认
    svc.update_provider(db, "u1", row.id, {"enabled": True})
    monkeypatch.setattr(crypto, "SECRET_KEY", "rotated-secret")
    cfg = resolve_config(db, "u1")
    assert cfg.source == SOURCE_ENV


@pytest.mark.unit
def test_fingerprint_changes_when_model_switches(db):
    row = svc.create_provider(db, "u1", _provider())
    before = config_fingerprint(db, "u1")
    svc.update_provider(db, "u1", row.id, {"active_model": "glm-4-plus"})
    after = config_fingerprint(db, "u1")
    assert before != after
    assert resolve_config(db, "u1").model == "glm-4-plus"


# ---------------------------------------------------------------- harness 接线

@pytest.fixture
def captured(monkeypatch, tmp_path, db):
    """捕获 create_deep_agent 调用；物化器直写空缓存目录"""
    calls = []
    import deepagents

    monkeypatch.setattr(
        deepagents, "create_deep_agent",
        lambda **kwargs: calls.append(kwargs) or object(),
    )
    monkeypatch.setattr(dah, "AGENT_CACHE_SIZE", 2)
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "cache"))

    from pathlib import Path

    from app.core import config as app_config

    monkeypatch.setattr(
        "app.llm.harness.skill_materializer.sync_user_skills",
        lambda db_, uid, **kw: Path(app_config.SKILL_CACHE_ROOT, uid),
    )
    return calls


@pytest.mark.unit
def test_harness_rebuilds_agent_when_model_changes(captured, db, monkeypatch):
    built = []
    monkeypatch.setattr(
        dah, "build_chat_model", lambda cfg: built.append(cfg.model) or f"model:{cfg.model}"
    )

    harness = DeepAgentHarness()
    harness._model = object()  # 平台默认模型（不应被用到）

    row = svc.create_provider(db, "u1", _provider())
    first = harness._get_agent_for_user("u1", db)
    assert harness._get_agent_for_user("u1", db) is first  # 配置未变 → 命中缓存
    assert built == ["glm-4-flash"]

    svc.update_provider(db, "u1", row.id, {"active_model": "glm-4-plus"})
    second = harness._get_agent_for_user("u1", db)
    assert second is not first  # 换模型 → 必须重建
    assert built == ["glm-4-flash", "glm-4-plus"]
    assert captured[-1]["model"] == "model:glm-4-plus"


@pytest.mark.unit
def test_harness_uses_platform_default_without_user_config(captured, db, monkeypatch):
    harness = DeepAgentHarness()
    platform = object()
    harness._model = platform
    harness._get_agent_for_user("u1", db)
    assert captured[-1]["model"] is platform
