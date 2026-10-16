"""
会话与聊天消息相关数据模型（Pydantic Schemas）
"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ConversationCreate(BaseModel):
    """创建会话请求

    user_id 由登录态推导（Depends(get_current_user)），不接受客户端指定。
    """

    title: str = Field("新会话", description="会话标题")


class ConversationUpdate(BaseModel):
    """更新会话请求"""

    title: str = Field(..., description="会话标题")


class ConversationResponse(BaseModel):
    """会话信息响应"""

    id: int = Field(..., description="会话ID")
    user_id: str = Field(..., description="用户ID")
    title: str = Field(..., description="会话标题")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """聊天消息响应"""

    id: int = Field(..., description="消息ID")
    conversation_id: int = Field(..., description="会话ID")
    role: str = Field(..., description="角色: user, assistant")
    content: str = Field("", description="消息内容")
    tool_events: Optional[str] = Field(None, description="工具调用事件记录（JSON）")
    created_at: Optional[datetime] = Field(None, description="创建时间")

    class Config:
        from_attributes = True
