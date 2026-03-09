"""
核心配置模块
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Token配置
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # 2小时
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7天

# 安全配置
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")

# 微信配置
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")
WECHAT_REDIRECT_URI = os.getenv("WECHAT_REDIRECT_URI", "http://localhost:8000/api/auth/wechat/callback")
WECHAT_LOGIN_ENABLED = os.getenv("WECHAT_LOGIN_ENABLED", "true").lower() == "true"
WECHAT_QR_CODE_EXPIRE_SECONDS = 300  # 二维码有效期5分钟
WECHAT_APPID = os.getenv("WECHAT_APPID", "")
WECHAT_SECRET = os.getenv("WECHAT_SECRET", "")

# 短信配置
SMS_ACCESS_KEY = os.getenv("SMS_ACCESS_KEY", "")
SMS_SECRET_KEY = os.getenv("SMS_SECRET_KEY", "")
SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME", "")
SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE", "")
