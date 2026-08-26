"""SkillService 安装/卸载/已装列表(FakeStorage + MockTransport + 内存库)"""
import httpx
import pytest

import app.services.skill_service as skill_service
from app.services.skill_service import (
    SkillServiceError,
    install_skill,
    list_installed,
    uninstall_skill,
)
from tests.fake_storage import FakeStorage

RAW_SKILL_MD = "---\nname: demo-skill\ndescription: 演示技能\n---\n# Demo\n"
HELPER = "print('hi')"


def _install_transport(*, big_file: bool = False, fail_raw: bool = False):
    def _handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "sha-latest"}, request=request)
        if path.endswith("/contents/demo-skill"):
            files = [
                {"name": "SKILL.md", "path": "demo-skill/SKILL.md", "type": "file",
                 "size": 10 * 1024 * 1024 + 1 if big_file else 30,
                 "download_url": "https://raw.test/demo-skill/SKILL.md"},
                {"name": "helper.py", "path": "demo-skill/helper.py", "type": "file",
                 "size": 20, "download_url": "https://raw.test/demo-skill/helper.py"},
            ]
            return httpx.Response(200, json=files, request=request)
        if "raw.test" in str(request.url) and path.endswith("SKILL.md"):
            if fail_raw:
                return httpx.Response(500, request=request)
            return httpx.Response(200, text=RAW_SKILL_MD, request=request)
        if "raw.test" in str(request.url) and path.endswith("helper.py"):
            return httpx.Response(200, text=HELPER, request=request)
        return httpx.Response(404, request=request)

    return httpx.MockTransport(_handler)


@pytest.fixture
def storage():
    fake = FakeStorage()
    skill_service._storage_singleton_override = fake
    yield fake
    skill_service._storage_singleton_override = None


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    skill_service.clear_registry_cache()
    monkeypatch.setattr(skill_service, "_registry_transport", None)


@pytest.mark.unit
def test_install_downloads_and_records(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    row = install_skill(db, "u1", "demo-skill")
    assert row.version == "sha-latest"
    assert row.name == "demo-skill"
    keys = storage.list_keys("skills/u1/demo-skill")
    assert any(k.endswith("SKILL.md") for k in keys)
    assert any(k.endswith("helper.py") for k in keys)
    assert [r.name for r in list_installed(db, "u1")] == ["demo-skill"]


@pytest.mark.unit
def test_install_rejects_oversize_file(db, storage, monkeypatch):
    monkeypatch.setattr(
        skill_service, "_registry_transport", _install_transport(big_file=True)
    )
    with pytest.raises(SkillServiceError, match="大小超限"):
        install_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []  # 无残留
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_install_midway_failure_cleans_up(db, storage, monkeypatch):
    monkeypatch.setattr(
        skill_service, "_registry_transport", _install_transport(fail_raw=True)
    )
    with pytest.raises(SkillServiceError):
        install_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_install_bad_name_rejected(db, storage):
    with pytest.raises(SkillServiceError, match="名称不合法"):
        install_skill(db, "u1", "../escape")


@pytest.mark.unit
def test_uninstall_removes_storage_and_row(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    install_skill(db, "u1", "demo-skill")
    uninstall_skill(db, "u1", "demo-skill")
    assert storage.list_keys("skills/u1/") == []
    assert list_installed(db, "u1") == []


@pytest.mark.unit
def test_users_isolated(db, storage, monkeypatch):
    monkeypatch.setattr(skill_service, "_registry_transport", _install_transport())
    install_skill(db, "u1", "demo-skill")
    assert list_installed(db, "u2") == []
    with pytest.raises(KeyError):
        storage.get_bytes("skills/u2/demo-skill/SKILL.md")
