"""
Redis 连接管理
"""

import redis

from app.core.config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)

redis_client = redis.Redis(connection_pool=redis_pool)


class RedisKeys:
    @staticmethod
    def sms_code(phone: str) -> str:
        return f"sms:code:{phone}"

    @staticmethod
    def auth_session(user_id: str, device_id: str) -> str:
        return f"auth:session:{user_id}:{device_id}"

    @staticmethod
    def auth_refresh(user_id: str, device_id: str) -> str:
        return f"auth:refresh:{user_id}:{device_id}"


class RedisTTL:
    SMS_CODE = 60
    AUTH_SESSION = 2 * 60 * 60
    AUTH_REFRESH = 7 * 24 * 60 * 60


def get_redis():
    return redis_client
