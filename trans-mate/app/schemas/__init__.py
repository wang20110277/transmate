"""
Schemas包初始化
导出所有数据模型供外部使用
"""
from app.schemas.auth import (
    WechatLoginRequest,
    SMSCodeRequest,
    SMSCodeResponse,
    SMSLoginRequest,
    PasswordLoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    MessageResponse,
    ChangePasswordRequest,
)
from app.schemas.user import UserInfoResponse

__all__ = [
    # Auth schemas
    "WechatLoginRequest",
    "SMSCodeRequest",
    "SMSCodeResponse",
    "SMSLoginRequest",
    "PasswordLoginRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "RefreshTokenResponse",
    "LogoutRequest",
    "MessageResponse",
    "ChangePasswordRequest",
    # User schemas
    "UserInfoResponse",
]
