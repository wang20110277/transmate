"""
WebSocket 智能体协议集成测试（内存 sqlite + 伪造流式生成器，不依赖 LLM/外部网络）
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


def collect_until_done(ws, expected_type="done"):
    """接收事件直到出现目标类型"""
    events = []
    while True:
        event = json.loads(ws.receive_text())
        events.append(event)
        if event["type"] in (expected_type, "error"):
            return events


@pytest.mark.integration
def test_ws_full_flow_with_auto_conversation(client):
    test_client, engine = client

    async def fake_stream(history):
        yield {"type": "status", "message": "正在分析意图..."}
        yield {"type": "agent_start", "agent": "base_agent"}
        yield {"type": "token", "content": f"收到{len(history)}条历史。"}
        yield {"type": "tool_call", "id": "t1", "name": "get_weather", "args": {"city": "北京"}}
        yield {"type": "tool_result", "id": "t1", "name": "get_weather", "result": "北京晴"}
        yield {
            "type": "done",
            "content": "收到1条历史。",
            "tool_events": [{"id": "t1", "name": "get_weather", "args": {"city": "北京"}, "result": "北京晴"}],
        }

    import main as main_module
    original = main_module.stream_agent_events
    main_module.stream_agent_events = fake_stream
    try:
        with test_client.websocket_connect("/ws?user_id=u1") as ws:
            # 第一条消息：不带 conversation_id，应自动建会话
            ws.send_text(json.dumps({"type": "chat_message", "message": "你好", "user_id": "u1"}))
            events = collect_until_done(ws)

            types = [e["type"] for e in events]
            assert types[0] == "conversation_created"
            conversation_id = events[0]["conversation_id"]
            assert types[1:] == ["status", "agent_start", "token", "tool_call", "tool_result", "done"]
            assert events[3]["content"] == "收到1条历史。"

            # 第二条消息：带 conversation_id，应有 3 条历史（user+assistant+user）
            ws.send_text(
                json.dumps({"type": "chat_message", "message": "再问一句", "conversation_id": conversation_id})
            )
            events2 = collect_until_done(ws)
            token_event = next(e for e in events2 if e["type"] == "token")
            assert token_event["content"] == "收到3条历史。"

        # 校验落库：4 条消息 + 标题自动生成
        Session = sessionmaker(bind=engine)
        db = Session()
        from app.models.conversation import Conversation
        from app.services import chat_service

        messages = chat_service.list_messages(db, conversation_id)
        assert len(messages) == 4
        assert [m.role for m in messages] == ["user", "assistant", "user", "assistant"]
        assert db.get(Conversation, conversation_id).title == "你好"
        db.close()
    finally:
        main_module.stream_agent_events = original


@pytest.mark.integration
def test_ws_stop_generation(client):
    test_client, engine = client
    import asyncio

    async def slow_stream(history):
        yield {"type": "token", "content": "开始回答"}
        await asyncio.sleep(60)
        yield {"type": "done", "content": "不该到达"}

    import main as main_module
    original = main_module.stream_agent_events
    main_module.stream_agent_events = slow_stream
    try:
        with test_client.websocket_connect("/ws?user_id=u1") as ws:
            ws.send_text(json.dumps({"type": "chat_message", "message": "慢问题", "user_id": "u1"}))
            # 收到 conversation_created 与首个 token
            first = json.loads(ws.receive_text())
            assert first["type"] == "conversation_created"
            token = json.loads(ws.receive_text())
            assert token["type"] == "token"

            # 发送停止指令，应收到 stopped 事件
            ws.send_text(json.dumps({"type": "stop"}))
            stopped = json.loads(ws.receive_text())
            assert stopped["type"] == "stopped"
    finally:
        main_module.stream_agent_events = original


@pytest.mark.integration
def test_ws_plain_text_compat(client):
    """纯文本消息应被兼容解析为 chat_message"""
    test_client, engine = client

    async def fake_stream(history):
        yield {"type": "token", "content": "ok"}
        yield {"type": "done", "content": "ok"}

    import main as main_module
    original = main_module.stream_agent_events
    main_module.stream_agent_events = fake_stream
    try:
        with test_client.websocket_connect("/ws?user_id=u1") as ws:
            ws.send_text("纯文本消息")
            events = collect_until_done(ws)
            assert events[-1]["type"] == "done"
    finally:
        main_module.stream_agent_events = original
