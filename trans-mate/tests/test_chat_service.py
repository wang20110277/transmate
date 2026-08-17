"""
会话服务单元测试（sqlite 内存库）
"""
import pytest

from app.models.conversation import ChatMessage  # noqa: F401
from app.services import chat_service


@pytest.mark.unit
def test_create_and_list_conversations(db):
    chat_service.create_conversation(db, "u1")
    chat_service.create_conversation(db, "u1", "自定义标题")
    chat_service.create_conversation(db, "u2")

    result = chat_service.list_conversations(db, "u1")
    assert len(result) == 2
    assert all(c.user_id == "u1" for c in result)
    assert result[0].title in ("新会话", "自定义标题")


@pytest.mark.unit
def test_rename_and_delete_conversation(db):
    conversation = chat_service.create_conversation(db, "u1")
    cid = conversation.id

    renamed = chat_service.update_conversation_title(db, cid, "新名字")
    assert renamed.title == "新名字"

    assert chat_service.delete_conversation(db, cid) is True
    assert chat_service.get_conversation(db, cid) is None
    assert chat_service.delete_conversation(db, cid) is False


@pytest.mark.unit
def test_add_message_and_auto_title(db):
    conversation = chat_service.create_conversation(db, "u1")
    cid = conversation.id

    chat_service.add_message(db, cid, "user", "帮我查一下北京天气")
    chat_service.add_message(db, cid, "assistant", "北京今天晴", tool_events=[{"id": "t1", "name": "get_weather"}])

    # 首条用户消息自动生成标题
    refreshed = chat_service.get_conversation(db, cid)
    assert refreshed.title == "帮我查一下北京天气"

    messages = chat_service.list_messages(db, cid)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
    assert "get_weather" in messages[1].tool_events


@pytest.mark.unit
def test_list_messages_returns_recent_ascending(db):
    conversation = chat_service.create_conversation(db, "u1")
    cid = conversation.id

    for i in range(10):
        chat_service.add_message(db, cid, "user", f"消息{i}")

    messages = chat_service.list_messages(db, cid, limit=3)
    assert len(messages) == 3
    assert messages[0].content == "消息7"
    assert messages[-1].content == "消息9"


@pytest.mark.unit
def test_delete_conversation_cascades_messages(db):
    conversation = chat_service.create_conversation(db, "u1")
    cid = conversation.id
    chat_service.add_message(db, cid, "user", "hello")

    chat_service.delete_conversation(db, cid)
    assert db.query(ChatMessage).filter(ChatMessage.conversation_id == cid).count() == 0
