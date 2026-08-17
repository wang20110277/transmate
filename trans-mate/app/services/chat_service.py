"""
会话服务模块
处理会话与聊天消息的持久化
"""
import json
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ChatMessage


def create_conversation(db: Session, user_id: str, title: str = "新会话") -> Conversation:
    """创建新会话"""
    conversation = Conversation(user_id=user_id, title=title)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def list_conversations(db: Session, user_id: str) -> List[Conversation]:
    """获取用户会话列表，按更新时间倒序"""
    return (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .all()
    )


def get_conversation(db: Session, conversation_id: int) -> Optional[Conversation]:
    """根据ID获取会话"""
    return db.query(Conversation).filter(Conversation.id == conversation_id).first()


def update_conversation_title(
    db: Session, conversation_id: int, title: str
) -> Optional[Conversation]:
    """更新会话标题"""
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return None
    conversation.title = title
    conversation.updated_at = datetime.now()
    db.commit()
    db.refresh(conversation)
    return conversation


def delete_conversation(db: Session, conversation_id: int) -> bool:
    """删除会话及其全部消息"""
    conversation = get_conversation(db, conversation_id)
    if not conversation:
        return False
    db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation_id
    ).delete(synchronize_session=False)
    db.delete(conversation)
    db.commit()
    return True


def add_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    tool_events: Optional[list] = None,
) -> ChatMessage:
    """保存一条消息；assistant 消息首条时自动以内容截断更新会话标题"""
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_events=json.dumps(tool_events, ensure_ascii=False) if tool_events else None,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()
    if conversation:
        if conversation.title == "新会话" and content.strip():
            conversation.title = content.strip()[:20]
        conversation.updated_at = datetime.now()
        db.commit()

    return message


def list_messages(
    db: Session, conversation_id: int, limit: int = 20
) -> List[ChatMessage]:
    """获取会话最近 limit 条消息（按时间正序返回），作为多轮上下文"""
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(messages))
