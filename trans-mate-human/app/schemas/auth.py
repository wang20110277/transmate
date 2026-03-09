"""
认证相关数据模型（Pydantic Schemas）
"""
from pydantic import BaseModel, Field
from typing import Optional


class WechatLoginRequest(BaseModel):
    """微信登录请求"""
    code: str = Field(..., description="微信授权code")
    phone: Optional[str] = Field(None, description="手机号（可选）")


class SMSCodeRequest(BaseModel):
    """发送短信验证码请求"""
    phone: str = Field(..., description="手机号", pattern=r"^1\d{10}$")


class SMSCodeResponse(BaseModel):
    """发送短信验证码响应"""
    message: str = Field(..., description="提示信息")
    expires_in: int = Field(..., description="过期时间（秒）")


class SMSLoginRequest(BaseModel):
    """短信验证码登录请求"""
    phone: str = Field(..., description="手机号", pattern=r"^1\d{10}$")
    code: str = Field(..., description="验证码", min_length=4, max_length=6)


class PasswordLoginRequest(BaseModel):
    """密码登录请求"""
    phone: str = Field(..., description="手机号", pattern=r"^1\d{10}$")
    password: str = Field(..., description="密码", min_length=6)
    confirm_password: Optional[str] = Field(None, description="确认密码（首次注册时需要）")


class TokenResponse(BaseModel):
    """Token响应"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    access_token: str = Field(..., description="访问token")
    refresh_token: str = Field(..., description="刷新token")
    device_id: str = Field(..., description="设备ID")
    is_first_login: bool = Field(..., description="是否首次登录")


class RefreshTokenRequest(BaseModel):
    """刷新token请求"""
    user_id: int = Field(..., description="用户ID")
    device_id: str = Field(..., description="设备ID")
    refresh_token: str = Field(..., description="刷新token")


class RefreshTokenResponse(BaseModel):
    """刷新token响应"""
    access_token: str = Field(..., description="新的访问token")
    refresh_token: str = Field(..., description="新的刷新token")


class LogoutRequest(BaseModel):
    """登出请求"""
    device_id: str = Field(..., description="设备ID")


class MessageResponse(BaseModel):
    """通用消息响应"""
    message: str = Field(..., description="消息内容")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: Optional[str] = Field(None, description="旧密码（未设置密码时可为空）")
    new_password: str = Field(..., description="新密码", min_length=6)
    confirm_password: str = Field(..., description="确认密码", min_length=6)
