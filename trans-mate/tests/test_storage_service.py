"""StorageService 内存实现(FakeStorage)契约测试"""
from pathlib import Path

import pytest

from tests.fake_storage import FakeStorage


@pytest.mark.unit
def test_upload_and_download_prefix_roundtrip(tmp_path: Path):
    storage = FakeStorage()
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "SKILL.md").write_text("hello", encoding="utf-8")
    (src / "sub" / "helper.py").write_text("print()", encoding="utf-8")

    count = storage.upload_prefix(src, "skills/u1/demo-skill")
    assert count == 2
    assert sorted(storage.list_keys("skills/u1/demo-skill")) == [
        "skills/u1/demo-skill/SKILL.md",
        "skills/u1/demo-skill/sub/helper.py",
    ]

    dst = tmp_path / "dst"
    storage.download_prefix("skills/u1/demo-skill", dst)
    assert (dst / "SKILL.md").read_text(encoding="utf-8") == "hello"
    assert (dst / "sub" / "helper.py").exists()


@pytest.mark.unit
def test_delete_prefix_and_isolation():
    storage = FakeStorage()
    storage.put_bytes("skills/u1/a/SKILL.md", b"1")
    storage.put_bytes("skills/u2/a/SKILL.md", b"2")
    storage.delete_prefix("skills/u1/")
    assert storage.list_keys("skills/") == ["skills/u2/a/SKILL.md"]


@pytest.mark.unit
def test_put_get_bytes_and_presigned():
    storage = FakeStorage()
    storage.put_bytes("artifacts/u1/x.pptx", b"data")
    assert storage.get_bytes("artifacts/u1/x.pptx") == b"data"
    assert storage.presigned_get_url("artifacts/u1/x.pptx", 3600) == "fake:///artifacts/u1/x.pptx"
