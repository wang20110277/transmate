"""Harness 用户工作区接线:工厂缓存/后端路由/user_id=None 回归"""
import pytest

import app.llm.harness.deep_agent_harness as dah
from app.llm.harness.deep_agent_harness import DeepAgentHarness


class _RecordingHarness(DeepAgentHarness):
    """不触发重量级初始化,只测工厂路径"""
    pass


@pytest.fixture
def captured(monkeypatch, tmp_path, db):
    """捕获 create_deep_agent 调用参数;物化器直写空缓存目录"""
    captured_calls = []
    import deepagents

    def fake_create_deep_agent(**kwargs):
        captured_calls.append(kwargs)
        return object()

    monkeypatch.setattr(deepagents, "create_deep_agent", fake_create_deep_agent)
    monkeypatch.setattr(dah, "AGENT_CACHE_SIZE", 2)
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "cache"))
    # patch 源模块(_get_agent_for_user 内部从 skill_materializer 导入,patch dah 属性无效)
    from pathlib import Path

    from app.core import config as app_config

    monkeypatch.setattr(
        "app.llm.harness.skill_materializer.sync_user_skills",
        lambda db_, uid, **kw: Path(app_config.SKILL_CACHE_ROOT, uid),
    )
    return captured_calls


@pytest.mark.unit
def test_build_agent_with_user_uses_skills_and_composite(captured, db):
    dah._build_agent(model=object(), checkpointer=None, user_id="u1")
    kwargs = captured[-1]
    assert kwargs["skills"] == ["/skills/"]
    from deepagents.backends.composite import CompositeBackend

    assert isinstance(kwargs["backend"], CompositeBackend)


@pytest.mark.unit
def test_build_agent_without_user_keeps_legacy(captured, db):
    dah._build_agent(model=object(), checkpointer=None, user_id=None)
    kwargs = captured[-1]
    assert "skills" not in kwargs and "backend" not in kwargs


@pytest.mark.unit
def test_agent_cache_keyed_by_user_and_lru(captured, db):
    harness = DeepAgentHarness()
    harness._model = object()  # 跳过真实模型构造
    a1 = harness._get_agent_for_user("u1", db)
    a1_again = harness._get_agent_for_user("u1", db)
    assert a1 is a1_again
    harness._get_agent_for_user("u2", db)
    harness._get_agent_for_user("u3", db)  # AGENT_CACHE_SIZE=2 → u1 被逐出
    assert "u1" not in harness._user_agents
    assert len(harness._user_agents) == 2


@pytest.mark.unit
def test_resolve_agent_none_user_returns_legacy(captured, db, monkeypatch):
    async def _noop():  # initialize 为 async,monkeypatch 需返回协程
        pass

    harness = DeepAgentHarness()
    legacy = object()
    monkeypatch.setattr(harness, "initialize", _noop)
    harness._agent = legacy
    harness._initialized = True
    harness._model = object()  # 跳过真实模型构造(工厂路径需要)
    # user_id=None → 传统单例;非 None → 工厂缓存
    assert harness._resolve_agent(None, db) is legacy
    assert harness._resolve_agent("u1", db) is not legacy
