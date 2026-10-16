"""
WebSocket + harness 集成测试：streaming 聚合、thread_id 透传、会话删除清 checkpoint
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from conftest import create_user, make_sqlite_engine


@pytest.fixture
def client(monkeypatch, allow_any_token):
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    import main as main_module
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    # HTTP 路由走 Depends(get_db)，必须覆盖到同一测试库，否则连真实 Postgres
    from app.core.database import get_db

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    main_module.app.dependency_overrides[get_db] = override_get_db

    db = TestSession()
    user = create_user(db, "u1")
    db.close()

    with TestClient(main_module.app) as test_client:
        yield test_client, engine, user
    main_module.app.dependency_overrides.clear()


class StubHarness:
    """记录 thread_id 与 clear_thread 调用的 harness 替身"""

    def __init__(self):
        self.threads = []
        self.cleared = []
        self.seen_user_ids = []

    async def astream(self, history, thread_id, user_id=None):
        self.threads.append(thread_id)
        self.seen_user_ids.append(user_id)
        yield {"type": "agent_start", "agent": "deep_agent"}
        yield {"type": "token", "content": "好的"}
        yield {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}}
        yield {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "晴"}
        yield {"type": "plan_update", "todos": [{"content": "查天气", "status": "completed"}]}
        yield {"type": "subagent_start", "name": "stock_data_expert", "task": "查行情"}
        yield {"type": "subagent_end", "name": "stock_data_expert", "result": "完成"}

    async def clear_thread(self, thread_id):
        self.cleared.append(thread_id)


def _headers(user):
    return {"Authorization": f"Bearer {user.id}:test-device:test-token"}


@pytest.mark.integration
def test_ws_flow_uses_harness_thread(client, monkeypatch):
    test_client, engine, user = client
    stub = StubHarness()
    from app.llm import streaming
    monkeypatch.setattr(streaming, "get_agent_harness", lambda: stub)

    with test_client.websocket_connect(f"/ws?token={user.id}:test-device:test-token") as ws:
        ws.send_text(json.dumps({"type": "chat_message", "message": "北京天气"}))
        events = []
        while True:
            e = json.loads(ws.receive_text())
            events.append(e)
            if e["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert types[0] == "conversation_created"
    for expected in ["agent_start", "token", "tool_call", "tool_result",
                     "plan_update", "subagent_start", "subagent_end", "done"]:
        assert expected in types

    done = events[-1]
    assert done["content"] == "好的"
    assert done["tool_events"][0]["result"] == "晴"
    # thread_id 按会话 id 生成
    assert stub.threads == [f"conv-{events[0]['conversation_id']}"]


@pytest.mark.integration
def test_delete_conversation_clears_checkpoint(client, monkeypatch):
    test_client, engine, user = client
    stub = StubHarness()
    import app.base.chat_routes as chat_routes
    monkeypatch.setattr(chat_routes, "get_agent_harness", lambda: stub)

    conv = test_client.post(
        "/api/conversations", json={"title": "测试"}, headers=_headers(user)
    ).json()
    resp = test_client.delete(f"/api/conversations/{conv['id']}", headers=_headers(user))
    assert resp.status_code == 200
    assert stub.cleared == [f"conv-{conv['id']}"]


@pytest.mark.integration
def test_delete_other_users_conversation_404(client):
    """不得删除他人会话"""
    test_client, engine, user = client
    Session = sessionmaker(bind=engine)
    db = Session()
    other = create_user(db, "u2")
    from app.services import chat_service
    conv = chat_service.create_conversation(db, other.user_id)
    conv_id = conv.id
    db.close()

    resp = test_client.delete(f"/api/conversations/{conv_id}", headers=_headers(user))
    assert resp.status_code == 404

    db = Session()
    from app.models.conversation import Conversation
    assert db.get(Conversation, conv_id) is not None
    db.close()


@pytest.mark.integration
def test_anonymous_message_not_persisted(client, monkeypatch):
    """匿名消息:不建会话、不写消息表、不发 conversation_created,thread 为连接级 anon-*"""
    test_client, engine, user = client
    stub = StubHarness()
    from app.llm import streaming
    monkeypatch.setattr(streaming, "get_agent_harness", lambda: stub)

    with test_client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "chat_message", "message": "随便聊聊"}))
        events = []
        while True:
            e = json.loads(ws.receive_text())
            events.append(e)
            if e["type"] == "done":
                break

    types = [e["type"] for e in events]
    assert "conversation_created" not in types
    assert types[0] == "agent_start"  # 流直接开始,无会话事件
    assert len(stub.threads) == 1 and stub.threads[0].startswith("anon-")

    from app.models.conversation import Conversation, ChatMessage

    Session = sessionmaker(bind=engine)
    db = Session()
    assert db.query(Conversation).count() == 0
    assert db.query(ChatMessage).count() == 0
    db.close()
