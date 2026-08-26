"""
会话路由模块
处理会话与聊天消息相关API
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import logging

from app.core.database import get_db
from app.llm.harness import get_agent_harness
from app.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.services import chat_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.post("", response_model=ConversationResponse)
async def create_conversation(
    request: ConversationCreate, db: Session = Depends(get_db)
):
    """创建新会话"""
    return chat_service.create_conversation(db, request.user_id, request.title)


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(user_id: str, db: Session = Depends(get_db)):
    """获取用户会话列表"""
    return chat_service.list_conversations(db, user_id)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """获取会话详情"""
    conversation = chat_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int, request: ConversationUpdate, db: Session = Depends(get_db)
):
    """重命名会话"""
    conversation = chat_service.update_conversation_title(
        db, conversation_id, request.title
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conversation


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """删除会话及其全部消息，并清理 agent checkpoint"""
    if not chat_service.delete_conversation(db, conversation_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    try:
        await get_agent_harness().clear_thread(f"conv-{conversation_id}")
    except Exception as e:
        logger.warning(f"清除会话 checkpoint 失败 conversation_id={conversation_id}: {e}")
    return {"message": "会话已删除"}


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def list_messages(conversation_id: int, db: Session = Depends(get_db)):
    """获取会话全部消息（历史记录）"""
    conversation = chat_service.get_conversation(db, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")
    return chat_service.list_messages(db, conversation_id, limit=200)
