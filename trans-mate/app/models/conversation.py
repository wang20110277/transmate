"""
会话与消息数据模型
"""

from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, Text, ForeignKey

from app.core.database import Base


class Conversation(Base):
    """会话表模型"""

    __tablename__ = "trans_conversation"

    id = Column(
        BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键"
    )
    user_id = Column(String(50), nullable=False, index=True, comment="用户ID")
    title = Column(String(100), nullable=False, default="新会话", comment="会话标题")
    created_at = Column(
        DateTime, nullable=True, default=datetime.now, comment="创建时间"
    )
    updated_at = Column(
        DateTime,
        nullable=True,
        default=datetime.now,
        onupdate=datetime.now,
        comment="更新时间",
    )


class ChatMessage(Base):
    """聊天消息表模型"""

    __tablename__ = "trans_chat_message"

    id = Column(
        BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键"
    )
    conversation_id = Column(
        BigInteger,
        ForeignKey("trans_conversation.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="会话ID",
    )
    role = Column(String(20), nullable=False, comment="角色: user, assistant")
    content = Column(Text, nullable=False, default="", comment="消息内容")
    tool_events = Column(
        Text,
        nullable=True,
        comment="工具调用事件记录（JSON 序列化）",
    )
    created_at = Column(
        DateTime, nullable=True, default=datetime.now, comment="创建时间"
    )
