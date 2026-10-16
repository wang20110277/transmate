"""
会话路由模块
处理会话与聊天消息相关API

鉴权约定：
- 身份一律来自 Authorization header（Depends(get_current_user），不再信任请求体里的 user_id
- 所有按 conversation_id 访问的端点都校验归属，防止遍历 ID 看到他人会话
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_user
from app.llm.harness import get_agent_harness
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["会话"])


def _get_owned(db: Session, conversation_id: int, user: User) -> Conversation:
    """取会话并校验归属；不存在或不属于当前用户统一 404（不暴露资源是否存在）"""
    conversation = chat_service.get_conversation(db, conversation_id)
    if not conversation or conversation.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """创建新会话（归属当前登录用户）"""
    return chat_service.create_conversation(db, user.user_id, request.title)


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取当前用户的会话列表"""
    return chat_service.list_conversations(db, user.user_id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取会话详情"""
    return _get_owned(db, conversation_id, user)


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    request: ConversationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """重命名会话"""
    _get_owned(db, conversation_id, user)
    conversation = chat_service.update_conversation_title(
        db, conversation_id, request.title
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除会话及其全部消息，并清理 agent checkpoint"""
    _get_owned(db, conversation_id, user)
    if not chat_service.delete_conversation(db, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        await get_agent_harness().clear_thread(f"conv-{conversation_id}")
    except Exception as e:
        logger.warning(f"清除会话 checkpoint 失败 conversation_id={conversation_id}: {e}")
    return {"message": "会话已删除"}


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """获取会话历史消息"""
    _get_owned(db, conversation_id, user)
    return chat_service.list_messages(db, conversation_id, limit=200)
