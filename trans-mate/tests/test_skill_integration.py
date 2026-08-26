"""
端到端集成:用户 agent 组装(技能经路由可扫描)/沙箱文件工具/越界拒绝/旧路径回归
不触网、不连 MinIO(FakeStorage+内存库+真实 deepagents 组装)
"""
import pytest

from langchain_core.language_models import BaseChatModel

from app.llm.harness.deep_agent_harness import DeepAgentHarness
from app.models.skill import UserSkill
from tests.fake_storage import FakeStorage


@pytest.fixture
def workspace(tmp_path, monkeypatch, db):
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path / "sandbox"))
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path / "cache"))
    storage = FakeStorage()
    storage.put_bytes(
        "skills/u1/demo-skill/SKILL.md",
        "---\nname: demo-skill\ndescription: 演示技能端到端\n---\n# Demo\n".encode(
            "utf-8"
        ),
    )
    db.add(UserSkill(user_id="u1", name="demo-skill", version="v1", description="",
                     source="test"))
    db.commit()
    # 关键:物化器默认走 _get_storage(),必须注入 FakeStorage 替身,否则直连 MinIO
    import app.services.skill_service as skill_service

    skill_service._storage_singleton_override = storage
    yield tmp_path, storage
    skill_service._storage_singleton_override = None


class _FakeModel(BaseChatModel):
    """最小模型替身:deepagents 组装期只需 bind_tools 可调用

    继承 BaseChatModel 使 deepagents.resolve_model 原样放行(str 才会走 init_chat_model);
    _generate 仅满足抽象方法,组装期不会被调用。
    """

    def bind_tools(self, tools, **kwargs):
        return self

    @property
    def _llm_type(self):
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessage
        from langchain_core.outputs import ChatGeneration, ChatResult

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="ok"))])


@pytest.mark.integration
def test_user_agent_assembles_with_materialized_skills(workspace, db):
    """真实 deepagents 组装 + 物化目录包含该技能(SkillsMiddleware 由 create_deep_agent 挂载)"""
    tmp_path, storage = workspace
    harness = DeepAgentHarness()
    harness._model = _FakeModel()
    agent = harness._get_agent_for_user("u1", db)
    assert agent is not None  # 真实 create_deep_agent(skills=/skills/, backend=Composite)组装成功

    # 物化目录确实包含该技能,且经 CompositeBackend 路由可扫描到
    import pathlib

    from deepagents.middleware.skills import _list_skills

    import app.llm.harness.deep_agent_harness as dah

    cache = pathlib.Path(str(tmp_path / "cache")) / "u1" / "demo-skill" / "SKILL.md"
    assert cache.exists()
    backend = dah._build_backend("u1")
    skills = _list_skills(backend, "/skills/")
    assert [s["name"] for s in skills] == ["demo-skill"]


@pytest.mark.integration
def test_sandbox_file_tools_read_write_and_traversal_denied(workspace, db):
    tmp_path, storage = workspace
    from deepagents.backends.filesystem import FilesystemBackend

    import app.llm.harness.deep_agent_harness as dah

    backend = dah._build_backend("u1")
    # 写入会话目录
    responses = backend.upload_files([("/sessions/conv-1/a.txt", b"hello")])
    assert responses[0].error is None
    resp = backend.download_files(["/sessions/conv-1/a.txt"])[0]
    assert resp.error is None and resp.content == b"hello"
    # 越界拒绝
    assert backend.download_files(["/../../etc/passwd"])[0].error is not None


@pytest.mark.integration
def test_legacy_path_unchanged(db):
    """user_id=None:仍构建默认(无 skills/backend kwargs)agent"""
    import deepagents
    import app.llm.harness.deep_agent_harness as dah

    captured = {}
    original = deepagents.create_deep_agent
    deepagents.create_deep_agent = lambda **kw: captured.update(kw) or object()
    try:
        dah._build_agent(model=object(), checkpointer=None, user_id=None)
    finally:
        deepagents.create_deep_agent = original
    assert "skills" not in captured and "backend" not in captured


@pytest.mark.integration
def test_cached_agent_sees_newly_installed_skill(workspace, db, monkeypatch):
    """安装新技能后,已缓存的用户 agent 无需重建即可看到该技能(最终审查 Critical#1)"""
    from deepagents.middleware.skills import _list_skills

    import app.llm.harness.deep_agent_harness as dah
    from app.models.skill import UserSkill
    from tests.fake_storage import FakeStorage

    storage = FakeStorage()
    storage.put_bytes(
        "skills/u1/late-skill/SKILL.md",
        "---\nname: late-skill\ndescription: 后装技能\n---\n# Late\n".encode("utf-8"),
    )
    monkeypatch.setattr("app.services.skill_service._storage_singleton_override", storage)

    harness = dah.DeepAgentHarness()
    harness._model = _FakeModel()
    harness._get_agent_for_user("u1", db)  # 首次:缓存 agent,清单只有 demo-skill

    db.add(UserSkill(user_id="u1", name="late-skill", version="v1", description="",
                     source="test"))
    db.commit()

    harness._get_agent_for_user("u1", db)  # 第二次:命中缓存,但物化必须重跑
    backend = dah._build_backend("u1")
    names = [s["name"] for s in _list_skills(backend, "/skills/")]
    assert "late-skill" in names
