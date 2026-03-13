"""
核心配置模块
统一管理所有配置，所有配置从 .env 加载
"""

import os
from dotenv import load_dotenv

load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT")
DEBUG = os.getenv("DEBUG")
LOG_LEVEL = os.getenv("LOG_LEVEL")

SECRET_KEY = os.getenv("SECRET_KEY")

ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_DAYS = os.getenv("REFRESH_TOKEN_EXPIRE_DAYS")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_DB = os.getenv("REDIS_DB")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

DEFAULT_API_URL = os.getenv("DEFAULT_API_URL")
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL")

KIMI_MODEL = os.getenv("KIMI_MODEL")
KIMI_PROVIDER = os.getenv("KIMI_PROVIDER")
KIMI_API_URL = os.getenv("KIMI_API_URL")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
KIMI_TIMEOUT = os.getenv("KIMI_TIMEOUT")

WECHAT_APPID = os.getenv("WECHAT_APPID")
WECHAT_SECRET = os.getenv("WECHAT_SECRET")
WECHAT_REDIRECT_URI = os.getenv("WECHAT_REDIRECT_URI")
WECHAT_LOGIN_ENABLED = os.getenv("WECHAT_LOGIN_ENABLED")
WECHAT_QR_CODE_EXPIRE_SECONDS = 300

SMS_ACCESS_KEY = os.getenv("SMS_ACCESS_KEY")
SMS_SECRET_KEY = os.getenv("SMS_SECRET_KEY")
SMS_SIGN_NAME = os.getenv("SMS_SIGN_NAME")
SMS_TEMPLATE_CODE = os.getenv("SMS_TEMPLATE_CODE")

TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS")

RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED")
RATE_LIMIT_REQUESTS_PER_MINUTE = os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE")

SESSION_TIMEOUT = os.getenv("SESSION_TIMEOUT")

MAX_UPLOAD_SIZE = os.getenv("MAX_UPLOAD_SIZE")
UPLOAD_DIR = os.getenv("UPLOAD_DIR")

# RAG Configuration
KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "app",
    "llm",
    "knowledge",
)
CHROMA_STORE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "app",
    "llm", 
    "store",
)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.5"))

# RAGAS Evaluation Configuration
RAGAS_API_KEY = os.getenv("RAGAS_API_KEY", os.getenv("OPENAI_API_KEY", ""))
