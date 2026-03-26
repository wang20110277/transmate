"""
用户信息相关数据模型（Pydantic Schemas）
"""

from pydantic import BaseModel, Field
from typing import Optional


class UserInfoResponse(BaseModel):
    """用户信息响应"""

    id: int = Field(..., description="用户ID")
    user_id: str = Field(..., description="用户ID标识")
    nickname: Optional[str] = Field(None, description="昵称")
    avatar_url: Optional[str] = Field(None, description="头像URL")
    phone: Optional[str] = Field(None, description="手机号")
    role: str = Field(..., description="角色")
    is_password_set: bool = Field(..., description="是否已设置密码")

    class Config:
        from_attributes = True
