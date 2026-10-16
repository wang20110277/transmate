"""
用户自带模型供应商（BYOK）

每个用户可配置多条供应商记录，各自持有 Base URL / API Key / 模型列表；
api_key_cipher 存 Fernet 密文，任何接口只回传掩码，不落明文、不回明文。
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base


class UserLLMProvider(Base):
    """用户的模型供应商配置（OpenAI 兼容端点）"""

    __tablename__ = "trans_user_llm_provider"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_llm_provider_name"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="自增ID，主键")
    user_id = Column(String(50), nullable=False, index=True, comment="所属用户ID")
    name = Column(String(50), nullable=False, comment="显示名，如 智谱GLM")
    provider = Column(
        String(50), nullable=False, default="openai", comment="langchain model_provider"
    )
    api_url = Column(String(500), nullable=False, comment="OpenAI 兼容 base_url")
    api_key_cipher = Column(Text, nullable=False, comment="API Key 密文(Fernet)")
    models = Column(Text, nullable=False, default="[]", comment="可用模型名 JSON 数组")
    active_model = Column(String(100), nullable=False, default="", comment="当前选用的模型")
    temperature = Column(Float, nullable=False, default=0.1, comment="采样温度")
    enabled = Column(Boolean, nullable=False, default=True, comment="是否启用")
    is_default = Column(
        Boolean, nullable=False, default=False, comment="是否为该用户当前使用的配置"
    )
    created_at = Column(DateTime, nullable=False, default=datetime.now, comment="创建时间")
    updated_at = Column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now, comment="更新时间"
    )
