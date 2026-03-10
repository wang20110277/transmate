import redis
import os
from dotenv import load_dotenv

load_dotenv()

# Redis配置
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# 创建Redis连接池
redis_pool = redis.ConnectionPool(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True
)

redis_client = redis.Redis(connection_pool=redis_pool)


class RedisKeys:
    """Redis键名常量"""
    
    @staticmethod
    def sms_code(phone: str) -> str:
        """短信验证码键"""
        return f"sms:code:{phone}"
    
    @staticmethod
    def auth_session(user_id: str, device_id: str) -> str:
        """登录token键"""
        return f"auth:session:{user_id}:{device_id}"
    
    @staticmethod
    def auth_refresh(user_id: str, device_id: str) -> str:
        """刷新token键"""
        return f"auth:refresh:{user_id}:{device_id}"


class RedisTTL:
    """Redis过期时间（秒）"""
    SMS_CODE = 60  # 验证码60秒
    AUTH_SESSION = 2 * 60 * 60  # 登录token 2小时
    AUTH_REFRESH = 7 * 24 * 60 * 60  # 刷新token 7天


def get_redis():
    """获取Redis客户端"""
    return redis_client
