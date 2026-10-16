"""
微信登录服务模块
处理微信扫码登录流程：生成二维码、查询状态、处理回调
"""

import secrets
import string
import json
import base64
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy.orm import Session
from app.core.redis import redis_client
from app.core.config import (
    WECHAT_APPID,
    WECHAT_SECRET,
    WECHAT_REDIRECT_URI,
    WECHAT_QR_CODE_EXPIRE_SECONDS,
    SECRET_KEY,
)
from app.models.user import User
from app.services.user_service import create_user, get_user_by_wechat_openid
import requests


class WeChatLoginStatus:
    """微信登录状态常量"""

    PENDING = "pending"  # 等待扫码
    SCANNED = "scanned"  # 已扫码
    AUTHORIZED = "authorized"  # 已授权
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期


class WeChatService:
    """微信登录服务类"""

    # Redis key 前缀
    QR_CODE_KEY_PREFIX = "wechat:qr:"
    STATE_KEY_PREFIX = "wechat:state:"
    TOKEN_KEY_PREFIX = "wechat:token:"

    def __init__(self):
        self.appid = WECHAT_APPID
        self.secret = WECHAT_SECRET
        self.redirect_uri = WECHAT_REDIRECT_URI
        self.qr_expire_seconds = WECHAT_QR_CODE_EXPIRE_SECONDS
        # 初始化加密密钥
        self._init_encryption_key()

    def _init_encryption_key(self):
        """初始化 Fernet 加密密钥"""
        # 使用 SECRET_KEY 生成加密密钥
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"wechat_login_salt",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(SECRET_KEY.encode()))
        self.cipher = Fernet(key)

    def encrypt_token(self, token: str) -> str:
        """
        加密 access_token

        Args:
            token: 明文 access_token

        Returns:
            加密后的 token (base64 字符串)
        """
        try:
            encrypted = self.cipher.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            print(f"Token 加密失败: {e}")
            return token  # 加密失败返回原文（降级处理）

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        解密 access_token

        Args:
            encrypted_token: 加密的 token

        Returns:
            解密后的明文 token
        """
        try:
            # 先解码 base64
            encrypted = base64.urlsafe_b64decode(encrypted_token.encode())
            decrypted = self.cipher.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            print(f"Token 解密失败: {e}")
            return encrypted_token  # 解密失败返回原文（兼容未加密数据）

    def generate_scene_id(self) -> str:
        """生成唯一的 scene_id"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(32))

    def generate_state(self) -> str:
        """生成用于防止 CSRF 的 state 参数"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(16))

    def _get_qr_code_key(self, scene_id: str) -> str:
        """获取 Redis key"""
        return f"{self.QR_CODE_KEY_PREFIX}{scene_id}"

    def _get_state_key(self, state: str) -> str:
        """获取 state 的 Redis key"""
        return f"{self.STATE_KEY_PREFIX}{state}"

    def create_qr_code(self) -> Dict[str, Any]:
        """
        创建微信登录二维码

        Returns:
            {
                "scene_id": "xxx",
                "qr_code_url": "https://api.qrserver.com/v1/create-qr-code/?data=xxx",
                "expire_seconds": 300
            }
        """
        scene_id = self.generate_scene_id()
        state = self.generate_state()

        # 构建微信授权 URL
        # 使用微信网页授权模式
        wechat_auth_url = (
            f"https://open.weixin.qq.com/connect/qrconnect?"
            f"appid={self.appid}&"
            f"redirect_uri={self.redirect_uri}&"
            f"response_type=code&"
            f"scope=snsapi_login&"
            f"state={state}"
        )

        # 使用二维码生成服务
        qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={wechat_auth_url}"

        # 存储到 Redis
        qr_data = {
            "scene_id": scene_id,
            "state": state,
            "status": WeChatLoginStatus.PENDING,
            "created_at": datetime.now().isoformat(),
            "wechat_auth_url": wechat_auth_url,
        }

        redis_client.setex(
            self._get_qr_code_key(scene_id), self.qr_expire_seconds, json.dumps(qr_data)
        )

        # 存储 state 验证
        redis_client.setex(self._get_state_key(state), self.qr_expire_seconds, scene_id)

        return {
            "scene_id": scene_id,
            "qr_code_url": qr_code_url,
            "expire_seconds": self.qr_expire_seconds,
        }

    def get_login_status(self, scene_id: str) -> Dict[str, Any]:
        """
        查询登录状态

        Returns:
            {
                "status": "pending|scanned|authorized|rejected|expired",
                "user_info": {...},  # 如果已授权
                "message": "..."     # 状态说明
            }
        """
        key = self._get_qr_code_key(scene_id)
        data = redis_client.get(key)

        if not data:
            return {"status": WeChatLoginStatus.EXPIRED, "message": "二维码已过期"}

        qr_data = json.loads(data)
        status = qr_data.get("status", WeChatLoginStatus.PENDING)

        result = {"status": status, "message": self._get_status_message(status)}

        # 如果已授权，返回用户信息
        if status == WeChatLoginStatus.AUTHORIZED:
            user_info = qr_data.get("user_info", {})
            result["user_info"] = user_info
            result["auth_code"] = qr_data.get("auth_code")

        return result

    def _get_status_message(self, status: str) -> str:
        """获取状态说明"""
        messages = {
            WeChatLoginStatus.PENDING: "等待扫码",
            WeChatLoginStatus.SCANNED: "已扫码，等待确认",
            WeChatLoginStatus.AUTHORIZED: "已授权",
            WeChatLoginStatus.REJECTED: "用户拒绝授权",
            WeChatLoginStatus.EXPIRED: "二维码已过期",
        }
        return messages.get(status, "未知状态")

    def update_login_status(
        self,
        scene_id: str,
        status: str,
        user_info: Optional[Dict] = None,
        auth_code: Optional[str] = None,
    ) -> bool:
        """更新登录状态"""
        key = self._get_qr_code_key(scene_id)
        data = redis_client.get(key)

        if not data:
            return False

        qr_data = json.loads(data)
        qr_data["status"] = status

        if user_info:
            qr_data["user_info"] = user_info

        if auth_code:
            qr_data["auth_code"] = auth_code

        # 重新设置过期时间（保留剩余时间）
        ttl = redis_client.ttl(key)
        redis_client.setex(key, max(ttl, 60), json.dumps(qr_data))

        return True

    def validate_state(self, state: str) -> Optional[str]:
        """
        验证 state 参数，防止 CSRF 攻击

        Returns:
            对应的 scene_id，如果无效则返回 None
        """
        key = self._get_state_key(state)
        scene_id = redis_client.get(key)

        if scene_id:
            # 验证成功后删除 state
            redis_client.delete(key)
            return scene_id

        return None

    def exchange_code_for_access_token(self, code: str) -> Optional[Dict[str, Any]]:
        """
        用授权码换取 access_token

        Returns:
            {
                "access_token": "xxx",
                "expires_in": 7200,
                "refresh_token": "xxx",
                "openid": "xxx",
                "unionid": "xxx"
            }
        """
        url = "https://api.weixin.qq.com/sns/oauth2/access_token"
        params = {
            "appid": self.appid,
            "secret": self.secret,
            "code": code,
            "grant_type": "authorization_code",
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "errcode" in data:
                print(f"微信 API 错误: {data}")
                return None

            # 加密 access_token 和 refresh_token
            encrypted_access_token = self.encrypt_token(data.get("access_token"))
            encrypted_refresh_token = (
                self.encrypt_token(data.get("refresh_token"))
                if data.get("refresh_token")
                else None
            )

            return {
                "access_token": encrypted_access_token,
                "access_token_raw": data.get("access_token"),  # 保留原始token供即时使用
                "expires_in": data.get("expires_in"),
                "refresh_token": encrypted_refresh_token,
                "openid": data.get("openid"),
                "unionid": data.get("unionid"),
            }
        except Exception as e:
            print(f"换取 access_token 失败: {e}")
            return None

    def get_user_info(self, access_token: str, openid: str) -> Optional[Dict[str, Any]]:
        """
        获取微信用户信息

        Returns:
            {
                "openid": "xxx",
                "nickname": "xxx",
                "sex": 1,
                "province": "xxx",
                "city": "xxx",
                "country": "xxx",
                "headimgurl": "xxx",
                "unionid": "xxx"
            }
        """
        url = "https://api.weixin.qq.com/sns/userinfo"
        params = {"access_token": access_token, "openid": openid}

        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()

            if "errcode" in data:
                print(f"获取用户信息失败: {data}")
                return None

            return {
                "openid": data.get("openid"),
                "nickname": data.get("nickname"),
                "sex": data.get("sex"),
                "province": data.get("province"),
                "city": data.get("city"),
                "country": data.get("country"),
                "headimgurl": data.get("headimgurl"),
                "unionid": data.get("unionid"),
            }
        except Exception as e:
            print(f"获取用户信息失败: {e}")
            return None

    def find_or_create_user(
        self, db: Session, wechat_info: Dict[str, Any]
    ) -> Tuple[User, bool]:
        """
        根据微信信息查找或创建用户

        Args:
            db: 数据库会话
            wechat_info: 微信用户信息

        Returns:
            (user, is_new) - 用户对象和是否是新用户
        """
        openid = wechat_info.get("openid")
        unionid = wechat_info.get("unionid")

        # 先通过 openid 查找
        user = get_user_by_wechat_openid(db, openid)

        if user:
            # 更新用户信息
            user.wechat_nickname = wechat_info.get("nickname")
            user.wechat_avatar = wechat_info.get("headimgurl")
            user.wechat_unionid = unionid
            user.updated_at = datetime.now()
            db.commit()
            return user, False

        # 创建新用户
        nickname = wechat_info.get("nickname", f"微信用户_{openid[-6:]}")
        avatar_url = wechat_info.get("headimgurl")

        user_data = {
            "user_id": f"wechat_{openid[-10:]}",
            "nickname": nickname,
            "avatar_url": avatar_url,
            "wechat_openid": openid,
            "wechat_unionid": unionid,
            "wechat_nickname": nickname,
            "wechat_avatar": avatar_url,
            "register_source": "WECHAT",
            "status": 1,
            "role": "user",
        }

        user = create_user(db, user_data)
        return user, True

    def store_encrypted_token(
        self, scene_id: str, access_token: str, expire_seconds: int = 7200
    ) -> bool:
        """
        加密并存储 access_token 到 Redis

        Args:
            scene_id: 场景ID
            access_token: 明文 access_token
            expire_seconds: 过期时间（秒）

        Returns:
            是否存储成功
        """
        try:
            encrypted_token = self.encrypt_token(access_token)
            key = f"{self.TOKEN_KEY_PREFIX}{scene_id}"
            redis_client.setex(key, expire_seconds, encrypted_token)
            return True
        except Exception as e:
            print(f"存储加密 token 失败: {e}")
            return False

    def get_decrypted_token(self, scene_id: str) -> Optional[str]:
        """
        从 Redis 获取并解密 access_token

        Args:
            scene_id: 场景ID

        Returns:
            解密后的 access_token，如果不存在则返回 None
        """
        try:
            key = f"{self.TOKEN_KEY_PREFIX}{scene_id}"
            encrypted_token = redis_client.get(key)
            if not encrypted_token:
                return None
            return self.decrypt_token(encrypted_token)
        except Exception as e:
            print(f"获取解密 token 失败: {e}")
            return None

    def delete_stored_token(self, scene_id: str) -> bool:
        """
        删除存储的 access_token

        Args:
            scene_id: 场景ID

        Returns:
            是否删除成功
        """
        try:
            key = f"{self.TOKEN_KEY_PREFIX}{scene_id}"
            redis_client.delete(key)
            return True
        except Exception as e:
            print(f"删除 token 失败: {e}")
            return False


# 创建全局服务实例
wechat_service = WeChatService()
