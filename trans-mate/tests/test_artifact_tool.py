"""save_artifact 工具:沙箱路径解析/上传/上限/错误文案"""
import pytest
from langchain_core.runnables import RunnableConfig

from app.llm.tools.artifact_tool import make_save_artifact_tool
from app.models.skill import Artifact
from tests.fake_storage import FakeStorage


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SANDBOX_ROOT", str(tmp_path))
    (tmp_path / "u1" / "sessions" / "conv-9").mkdir(parents=True)
    (tmp_path / "u1" / "sessions" / "conv-9" / "report.pptx").write_bytes(b"ppt-bytes")
    return tmp_path


def _invoke(tool, source_path, config=None):
    config = config or {"configurable": {"thread_id": "conv-9"}}
    return tool.invoke({"source_path": source_path, "name": "报告"}, config=config)


@pytest.mark.unit
def test_save_artifact_success(db, sandbox):
    storage = FakeStorage()
    tool = make_save_artifact_tool("u1", storage=storage)
    result = _invoke(tool, "/sessions/conv-9/report.pptx")
    assert "已保存" in result
    row = db.query(Artifact).filter_by(user_id="u1").one()
    assert row.conversation_id == 9
    assert row.filename == "报告.pptx" or row.filename == "report.pptx"
    assert row.size == len(b"ppt-bytes")
    keys = storage.list_keys(f"u1/artifacts/{row.id}/") if row.id else storage.list_keys("u1/artifacts/")
    assert keys  # 已上传


@pytest.mark.unit
def test_save_artifact_missing_file(db, sandbox):
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/sessions/conv-9/nope.pptx")
    assert "不存在" in result
    assert db.query(Artifact).count() == 0


@pytest.mark.unit
def test_save_artifact_blocks_traversal(db, sandbox):
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/../../etc/passwd")
    assert "沙箱" in result or "越界" in result or "无效" in result


@pytest.mark.unit
def test_save_artifact_enforces_count_limit(db, sandbox, monkeypatch):
    from app.core.config import ARTIFACT_MAX_COUNT
    monkeypatch.setattr("app.core.config.ARTIFACT_MAX_COUNT", 1)
    db.add(Artifact(user_id="u1", conversation_id=1, filename="a.bin", size=1,
                    storage_key="u1/artifacts/x/a.bin"))
    db.commit()
    tool = make_save_artifact_tool("u1", storage=FakeStorage())
    result = _invoke(tool, "/sessions/conv-9/report.pptx")
    assert "上限" in result
