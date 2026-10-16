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
# 注意：app.schemas.chat 里也有一个同名的 MessageResponse（会话消息，字段为
# id/conversation_id/role/content）。此前这里把它一并 re-export，会覆盖掉上面
# auth 的通用消息体，导致 auth 路由构造 MessageResponse(message=...) 时校验失败，
# 登出 / 改密码 / 改昵称三个接口全部 500。聊天消息模型请直接从 app.schemas.chat 导入。
from app.schemas.chat import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
)

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
    # Chat schemas
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
]
