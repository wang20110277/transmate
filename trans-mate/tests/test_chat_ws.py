"""
WebSocket + harness 集成测试：streaming 聚合、thread_id 透传、会话删除清 checkpoint
"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from conftest import make_sqlite_engine


@pytest.fixture
def client(monkeypatch):
    from app.models.user import User  # noqa: F401
    from app.models.conversation import Conversation, ChatMessage  # noqa: F401

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    import main as main_module
    monkeypatch.setattr(main_module, "SessionLocal", TestSession)
    monkeypatch.setattr(main_module, "init_db", lambda: None)

    with TestClient(main_module.app) as test_client:
        yield test_client, engine


class StubHarness:
    """记录 thread_id 与 clear_thread 调用的 harness 替身"""

    def __init__(self):
        self.threads = []
        self.cleared = []

    async def astream(self, history, thread_id):
        self.threads.append(thread_id)
        yield {"type": "agent_start", "agent": "deep_agent"}
        yield {"type": "token", "content": "好的"}
        yield {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}}
        yield {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "晴"}
        yield {"type": "plan_update", "todos": [{"content": "查天气", "status": "completed"}]}
        yield {"type": "subagent_start", "name": "stock_data_expert", "task": "查行情"}
        yield {"type": "subagent_end", "name": "stock_data_expert", "result": "完成"}

    async def clear_thread(self, thread_id):
        self.cleared.append(thread_id)


@pytest.mark.integration
def test_ws_flow_uses_harness_thread(client, monkeypatch):
    test_client, engine = client
    stub = StubHarness()
    from app.llm import streaming
    monkeypatch.setattr(streaming, "get_agent_harness", lambda: stub)

    with test_client.websocket_connect("/ws?user_id=u1") as ws:
        ws.send_text(json.dumps({"type": "chat_message", "message": "北京天气", "user_id": "u1"}))
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
    test_client, engine = client
    stub = StubHarness()
    import app.base.chat_routes as chat_routes
    monkeypatch.setattr(chat_routes, "get_agent_harness", lambda: stub)

    conv = test_client.post(
        "/api/conversations", json={"user_id": "u1", "title": "测试"}
    ).json()
    resp = test_client.delete(f"/api/conversations/{conv['id']}")
    assert resp.status_code == 200
    assert stub.cleared == [f"conv-{conv['id']}"]
