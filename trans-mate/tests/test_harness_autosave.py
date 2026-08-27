"""harness 轮末自动补录:write_file 过但未 save_artifact 的文件自动上云盘

小模型(glm-4-flash)常只 write_file 就宣称"已保存",用户云盘看不到。
harness 在每轮 astream 结束后对差集文件自动调用 save_artifact 兜底,
conversation_id 沿用本轮 thread_id。
"""
import pytest

from app.llm.harness.deep_agent_harness import DeepAgentHarness
from app.models.skill import Artifact
from tests.fake_storage import FakeStorage


class _FakeAgent:
    """吐出 write_file 工具事件的假 agent(无 save_artifact)"""

    def __init__(self, events):
        self._events = events

    async def astream_events(self, inp, config, version="v2"):
        for ev in self._events:
            yield ev


def _tool_events(tool_name: str, tool_input: dict) -> list[dict]:
    return [
        {"event": "on_tool_start", "name": tool_name, "data": {"input": tool_input}},
        {"event": "on_tool_end", "name": tool_name, "data": {"output": "ok"}},
    ]


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path))
    # 物化器在每轮 astream 前跑,隔离其缓存目录避免污染真实 store/skill_cache
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "skill_cache"))
    return tmp_path


def _make_harness(events) -> DeepAgentHarness:
    """注入假 agent 到用户缓存:user_id 路径走 _user_agents,不走 agent 参数"""
    harness = DeepAgentHarness()
    harness._initialized = True
    harness._user_agents["u9"] = _FakeAgent(events)
    return harness


@pytest.mark.asyncio
@pytest.mark.unit
async def test_unsaved_write_file_autosaved_as_artifact(db, sandbox, monkeypatch):
    """轮内 write_file 且无 save_artifact → 轮末自动补录,制品带会话 id"""
    import app.services.skill_service as skill_service

    storage = FakeStorage()
    monkeypatch.setattr(skill_service, "_storage_singleton_override", storage)

    from pathlib import Path

    path = Path(sandbox) / "u9" / "sessions" / "conv-5" / "note.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# hi")

    events = _tool_events("write_file", {"file_path": "/sessions/conv-5/note.md"})
    harness = _make_harness(events)

    got = [ev async for ev in harness.astream([], "conv-5", user_id="u9")]

    row = db.query(Artifact).filter_by(user_id="u9").one()
    assert row.conversation_id == 5  # thread_id conv-5 正确关联
    assert storage.list_keys("u9/artifacts/")  # 已上传 MinIO 键前缀
    # 补录以 status 事件告知前端
    assert any("自动保存" in str(ev.get("message", "")) for ev in got)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_already_saved_file_not_duplicated(db, sandbox, monkeypatch):
    """轮内已 save_artifact 的文件不重复补录"""
    import app.services.skill_service as skill_service

    storage = FakeStorage()
    monkeypatch.setattr(skill_service, "_storage_singleton_override", storage)

    from pathlib import Path

    path = Path(sandbox) / "u9" / "sessions" / "conv-6" / "a.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x")

    events = _tool_events("write_file", {"file_path": "/sessions/conv-6/a.md"})
    events += _tool_events("save_artifact", {"source_path": "/sessions/conv-6/a.md"})
    harness = _make_harness(events)

    _ = [ev async for ev in harness.astream([], "conv-6", user_id="u9")]

    assert db.query(Artifact).filter_by(user_id="u9").count() == 0  # 模型自己没存成,也没有重复


@pytest.mark.asyncio
@pytest.mark.unit
async def test_traversal_path_not_autosaved(db, sandbox, monkeypatch):
    """越界路径不补录(save_artifact 自身校验兜底)"""
    import app.services.skill_service as skill_service

    storage = FakeStorage()
    monkeypatch.setattr(skill_service, "_storage_singleton_override", storage)

    events = _tool_events("write_file", {"file_path": "/../../etc/passwd"})
    harness = _make_harness(events)

    got = [ev async for ev in harness.astream([], "conv-7", user_id="u9")]

    assert db.query(Artifact).filter_by(user_id="u9").count() == 0
    assert not any("自动保存" in str(ev.get("message", "")) for ev in got)
