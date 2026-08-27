"""制品列表/下载路由"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.models.skill import Artifact
import main as main_module


@pytest.fixture
def client(monkeypatch, db):
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    session_factory = sessionmaker(bind=db.bind, autoflush=False, autocommit=False)

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.clear()


@pytest.mark.unit
def test_list_artifacts_filters_by_user(client, db):
    db.add(Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                    storage_key="u1/artifacts/1/a.pptx"))
    db.add(Artifact(user_id="u2", conversation_id=1, filename="b.pptx", size=4,
                    storage_key="u2/artifacts/2/b.pptx"))
    db.commit()
    resp = client.get("/api/artifacts", params={"user_id": "u1"})
    items = resp.json()["items"]
    assert [i["filename"] for i in items] == ["a.pptx"]
    assert resp.json()["total"] == 1


@pytest.mark.unit
def test_list_artifacts_filters_by_conversation(client, db):
    db.add(Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                    storage_key="u1/artifacts/1/a.pptx"))
    db.add(Artifact(user_id="u1", conversation_id=8, filename="c.pptx", size=3,
                    storage_key="u1/artifacts/3/c.pptx"))
    db.commit()
    resp = client.get("/api/artifacts", params={"user_id": "u1", "conversation_id": 9})
    assert [i["filename"] for i in resp.json()["items"]] == ["a.pptx"]


@pytest.mark.unit
def test_download_returns_presigned_url(client, db, monkeypatch):
    row = Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                   storage_key="u1/artifacts/1/a.pptx")
    db.add(row)
    db.commit()
    from app.base import artifact_routes

    monkeypatch.setattr(
        artifact_routes, "_get_storage_service",
        lambda: type("S", (), {"presigned_get_url": lambda self, k, e, filename=None: f"fake:///{k}"})(),
    )
    resp = client.get(f"/api/artifacts/{row.id}/download", params={"user_id": "u1"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("fake:///")


@pytest.mark.unit
def test_download_other_users_artifact_404(client, db):
    row = Artifact(user_id="u1", conversation_id=9, filename="a.pptx", size=3,
                   storage_key="u1/artifacts/1/a.pptx")
    db.add(row)
    db.commit()
    resp = client.get(f"/api/artifacts/{row.id}/download", params={"user_id": "u2"})
    assert resp.status_code == 404


# ===== 回收站:归档/恢复/彻底删除 =====


def _add_artifact(db, **kw):
    row = Artifact(user_id="u1", conversation_id=9, filename="a.md", size=3,
                   storage_key="u1/artifacts/9/a.md")
    for k, v in kw.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()
    return row


@pytest.mark.unit
def test_archive_hides_from_default_list(client, db):
    row = _add_artifact(db)
    resp = client.post(f"/api/artifacts/{row.id}/archive", params={"user_id": "u1"})
    assert resp.status_code == 200
    assert client.get("/api/artifacts", params={"user_id": "u1"}).json()["total"] == 0
    recycled = client.get("/api/artifacts", params={"user_id": "u1", "archived": "true"}).json()
    assert recycled["total"] == 1
    assert recycled["items"][0]["archived"] is True


@pytest.mark.unit
def test_restore_returns_to_default_list(client, db):
    row = _add_artifact(db)
    client.post(f"/api/artifacts/{row.id}/archive", params={"user_id": "u1"})
    resp = client.post(f"/api/artifacts/{row.id}/restore", params={"user_id": "u1"})
    assert resp.status_code == 200
    assert client.get("/api/artifacts", params={"user_id": "u1"}).json()["total"] == 1


@pytest.mark.unit
def test_purge_deletes_storage_and_row(client, db, monkeypatch):
    from tests.fake_storage import FakeStorage

    storage = FakeStorage()
    storage.put_bytes("u1/artifacts/9/a.md", b"x")
    monkeypatch.setattr(
        "app.base.artifact_routes._get_storage_service", lambda: storage
    )
    row = _add_artifact(db)
    resp = client.delete(f"/api/artifacts/{row.id}", params={"user_id": "u1"})
    assert resp.status_code == 200
    assert storage.list_keys("u1/artifacts/9/") == []  # MinIO 对象已删
    assert client.get("/api/artifacts", params={"user_id": "u1"}).json()["total"] == 0


@pytest.mark.unit
def test_recycle_actions_on_other_users_artifact_404(client, db):
    row = _add_artifact(db)
    assert client.post(f"/api/artifacts/{row.id}/archive", params={"user_id": "u2"}).status_code == 404
    assert client.post(f"/api/artifacts/{row.id}/restore", params={"user_id": "u2"}).status_code == 404
    assert client.delete(f"/api/artifacts/{row.id}", params={"user_id": "u2"}).status_code == 404
