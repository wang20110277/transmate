"""UserSkill / Artifact 模型与表结构测试"""
import pytest

from app.models.skill import Artifact, UserSkill


@pytest.mark.unit
def test_user_skill_table_columns(db):
    table = UserSkill.__table__
    assert table.name == "trans_user_skill"
    cols = {c.name for c in table.columns}
    assert {"id", "user_id", "name", "version", "description", "source", "installed_at"} <= cols
    uniques = [str(u) for u in table.constraints if "UniqueConstraint" in str(u)]
    assert any("user_id" in u and "name" in u for u in uniques)


@pytest.mark.unit
def test_artifact_table_columns(db):
    table = Artifact.__table__
    assert table.name == "trans_artifact"
    cols = {c.name for c in table.columns}
    assert {
        "id", "user_id", "conversation_id", "filename", "size", "storage_key",
        "description", "created_at",
    } <= cols


@pytest.mark.unit
def test_models_create_and_query(db):
    skill = UserSkill(
        user_id="u1", name="demo-skill", version="abc123",
        description="演示", source="anthropics/skills@main",
    )
    db.add(skill)
    db.commit()
    rows = db.query(UserSkill).filter_by(user_id="u1").all()
    assert [r.name for r in rows] == ["demo-skill"]
