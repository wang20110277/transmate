"""技能物化器:按 PG 清单从存储物化到本地缓存目录"""
from pathlib import Path

import pytest

from app.llm.harness.skill_materializer import sync_user_skills
from app.models.skill import UserSkill
from tests.fake_storage import FakeStorage


def _seed(db, user_id, skills):
    for name, version in skills:
        db.add(UserSkill(user_id=user_id, name=name, version=version, description="",
                         source="test"))
    db.commit()


@pytest.mark.unit
def test_sync_downloads_all_skills(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"---\nname: demo-a\n---\nA")
    storage.put_bytes("skills/u1/demo-b/SKILL.md", b"---\nname: demo-b\n---\nB")
    _seed(db, "u1", [("demo-a", "v1"), ("demo-b", "v1")])

    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").read_bytes().startswith(b"---")
    assert (Path(cache_dir) / "demo-b" / "SKILL.md").exists()
    assert (Path(cache_dir) / ".manifest").exists()


@pytest.mark.unit
def test_sync_skips_when_fingerprint_unchanged(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"A")
    _seed(db, "u1", [("demo-a", "v1")])
    sync_user_skills(db, "u1", storage=storage)
    # 删掉对象模拟"不应再下载"
    storage.delete_prefix("skills/")
    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").exists()  # 复用本地缓存


@pytest.mark.unit
def test_sync_refreshes_when_version_changes(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))
    storage = FakeStorage()
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"old")
    _seed(db, "u1", [("demo-a", "v1")])
    sync_user_skills(db, "u1", storage=storage)
    storage.put_bytes("skills/u1/demo-a/SKILL.md", b"new")
    row = db.query(UserSkill).filter_by(user_id="u1", name="demo-a").first()
    row.version = "v2"
    db.commit()
    cache_dir = sync_user_skills(db, "u1", storage=storage)
    assert (Path(cache_dir) / "demo-a" / "SKILL.md").read_bytes() == b"new"


@pytest.mark.unit
def test_sync_failure_degrades_to_empty(db, tmp_path, monkeypatch):
    monkeypatch.setattr("app.core.config.SKILL_CACHE_ROOT", str(tmp_path))

    class BrokenStorage(FakeStorage):
        def list_keys(self, prefix):
            raise RuntimeError("minio down")

    _seed(db, "u1", [("demo-a", "v1")])
    cache_dir = sync_user_skills(db, "u1", storage=BrokenStorage())
    assert Path(cache_dir).exists()  # 返回空目录,不抛异常(降级运行)
