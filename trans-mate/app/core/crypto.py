"""
敏感字段（API Key）的对称加密

用 Fernet（AES-128-CBC + HMAC）加密后入库，密钥由 SECRET_KEY 派生：
同一部署下稳定；轮换 SECRET_KEY 会导致历史密文无法解密，
届时由调用方按「无 key」处理并回退平台默认，不会中断对话。
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import SECRET_KEY

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY 未配置，无法加密存储 API Key")
    key = base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    """加密为可入库的字符串"""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    """解密；失败（密钥轮换/数据损坏）返回空串，由调用方降级处理"""
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except (InvalidToken, RuntimeError, ValueError) as exc:
        logger.error("敏感字段解密失败: %s", exc)
        return ""


def mask_secret(plain: str) -> str:
    """给前端展示的掩码：仅露首4末4，中间固定 6 个星号"""
    if not plain:
        return ""
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:4]}{'*' * 6}{plain[-4:]}"
