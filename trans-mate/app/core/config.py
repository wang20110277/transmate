"""
核心配置模块
统一管理所有配置，所有配置从 .env 加载
"""

import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """解析布尔型环境变量：'1/true/yes/on'（忽略大小写）为真。

    直接 os.getenv 拿到的字符串 'false' 在 Python 里是真值，
    会导致 allow_credentials / 限流开关等配置永远为开。
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int | None = None) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


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

DB_DRIVER = os.getenv("DB_DRIVER", "postgresql+psycopg2")
DATABASE_URL = (
    f"{DB_DRIVER}://{DB_USER}:{quote_plus(DB_PASSWORD or '')}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

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

# 和风天气：API Host 是账号唯一的请求地址（控制台-设置），且它本身也属于认证要素，
# 光有 KEY 没有 Host 一样请求不到，所以两者都必须从 .env 读。
# 凭据ID 只用于在控制台标识凭据，请求时不需要传。
QWEATHER_API_HOST = os.getenv("QWEATHER_API_HOST")
QWEATHER_API_KEY = os.getenv("QWEATHER_API_KEY")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = _env_bool("CORS_ALLOW_CREDENTIALS", default=False)

# 限流：RATE_LIMIT_ENABLED 开启时，按 RATE_LIMIT_REQUESTS_PER_MINUTE/分钟 限制每用户
RATE_LIMIT_ENABLED = _env_bool("RATE_LIMIT_ENABLED", default=False)
RATE_LIMIT_REQUESTS_PER_MINUTE = _env_int("RATE_LIMIT_REQUESTS_PER_MINUTE", default=60)
# WebSocket 每连接每分钟可发起的生成轮数（LLM 成本主入口）
WS_RATE_LIMIT_TURNS_PER_MINUTE = _env_int("WS_RATE_LIMIT_TURNS_PER_MINUTE", default=10)

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
    "store",
)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.5"))

# RAGAS Evaluation Configuration
RAGAS_API_KEY = os.getenv("RAGAS_API_KEY", os.getenv("OPENAI_API_KEY", ""))

# ASR 语音转写服务（freeswitch-asr）
ASR_BASE_URL = os.getenv("ASR_BASE_URL", "http://127.0.0.1:8002")

# TTS 语音合成服务（freeswitch-tts，CosyVoice3 24kHz）
TTS_WS_URL = os.getenv("TTS_WS_URL", "ws://127.0.0.1:8003/ws/tts")
TTS_PROMPT_WAV = os.getenv("TTS_PROMPT_WAV", "./asset/zero_shot_prompt.wav")

# Deep Agent Harness（langgraph checkpoint 持久化）
CHECKPOINT_DB_PATH = os.getenv(
    "CHECKPOINT_DB_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "store",
        "agent_checkpoints.sqlite",
    ),
)

# Skill 注册表(GitHub 仓库,默认 anthropics/skills)
SKILL_REGISTRY_OWNER = os.getenv("SKILL_REGISTRY_OWNER", "anthropics")
SKILL_REGISTRY_REPO = os.getenv("SKILL_REGISTRY_REPO", "skills")
SKILL_REGISTRY_REF = os.getenv("SKILL_REGISTRY_REF", "main")
SKILL_REGISTRY_SUBDIR = os.getenv("SKILL_REGISTRY_SUBDIR", "")
SKILL_REGISTRY_TOKEN = os.getenv("SKILL_REGISTRY_TOKEN", "")
SKILL_REGISTRY_PROXY = os.getenv("SKILL_REGISTRY_PROXY", "")
SKILL_REGISTRY_CACHE_TTL = float(os.getenv("SKILL_REGISTRY_CACHE_TTL", "300"))

# MinIO 对象存储
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "transmate")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

# 用户云工作区
SANDBOX_ROOT = os.getenv(
    "SANDBOX_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "store", "sandbox"),
)
SKILL_CACHE_ROOT = os.getenv(
    "SKILL_CACHE_ROOT",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "store", "skill_cache"),
)

# 防护上限(spec §6)
SKILL_MAX_FILE_BYTES = int(os.getenv("SKILL_MAX_FILE_BYTES", str(10 * 1024 * 1024)))
SKILL_MAX_FILES = int(os.getenv("SKILL_MAX_FILES", "200"))
ARTIFACT_MAX_BYTES = int(os.getenv("ARTIFACT_MAX_BYTES", str(200 * 1024 * 1024)))
ARTIFACT_MAX_COUNT = int(os.getenv("ARTIFACT_MAX_COUNT", "500"))
