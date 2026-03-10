"""
短信验证码服务模块
"""
import random
from typing import Optional, Tuple
from app.core.redis import redis_client, RedisKeys, RedisTTL


def generate_sms_code(length: int = 6) -> str:
    """生成6位数字验证码"""
    return ''.join(random.choices('0123456789', k=length))


def send_sms_code(phone: str) -> Tuple[str, int]:
    """
    发送短信验证码
    
    Args:
        phone: 手机号
    
    Returns:
        (验证码, 过期时间秒数)
    
    Note:
        生产环境需要接入实际短信服务商（如阿里云、腾讯云等）
        当前为演示版本，仅将验证码存储到Redis并返回
    """
    code = generate_sms_code()
    key = RedisKeys.sms_code(phone)
    
    # 存储到Redis，60秒过期
    redis_client.setex(key, RedisTTL.SMS_CODE, code)
    
    # TODO: 生产环境调用短信服务发送
    # 示例：阿里云短信服务
    # send_sms_via_aliyun(phone, code)
    
    return code, RedisTTL.SMS_CODE


def verify_sms_code(phone: str, code: str) -> bool:
    """
    验证短信验证码
    
    Args:
        phone: 手机号
        code: 用户输入的验证码
    
    Returns:
        验证是否成功
    """
    key = RedisKeys.sms_code(phone)
    stored_code = redis_client.get(key)
    
    if stored_code is None:
        return False
    
    if stored_code != code:
        return False
    
    # 验证成功后删除（防止重用）
    redis_client.delete(key)
    return True


def check_sms_code_exists(phone: str) -> bool:
    """检查手机号是否已有未过期的验证码"""
    key = RedisKeys.sms_code(phone)
    return redis_client.exists(key) > 0
