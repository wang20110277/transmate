"""模型供应商（BYOK）相关 Pydantic 模型"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ProviderCreate(BaseModel):
    """新建供应商配置"""

    name: str = Field(..., min_length=1, max_length=50, description="显示名")
    api_url: str = Field(..., min_length=1, max_length=500, description="OpenAI 兼容 base_url")
    api_key: str = Field(..., min_length=1, max_length=500, description="API Key（明文，仅本次传输）")
    provider: str = Field("openai", max_length=50, description="langchain model_provider")
    models: List[str] = Field(default_factory=list, description="可用模型名列表")
    active_model: Optional[str] = Field(None, max_length=100, description="当前模型，默认取列表首个")
    temperature: float = Field(0.1, ge=0, le=2)
    enabled: bool = True


class ProviderUpdate(BaseModel):
    """更新供应商配置（字段均可选）"""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    api_url: Optional[str] = Field(None, min_length=1, max_length=500)
    # 省略或空串表示沿用原 Key：前端回显的是掩码，不能拿掩码覆盖真实 Key
    api_key: Optional[str] = Field(None, max_length=500)
    provider: Optional[str] = Field(None, max_length=50)
    models: Optional[List[str]] = None
    active_model: Optional[str] = Field(None, max_length=100)
    temperature: Optional[float] = Field(None, ge=0, le=2)
    enabled: Optional[bool] = None


class ProviderItem(BaseModel):
    """供应商配置（对外视图，API Key 仅掩码）"""

    id: int
    name: str
    provider: str
    api_url: str
    api_key_masked: str
    models: List[str]
    active_model: str
    temperature: float
    enabled: bool
    is_default: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ProviderListResponse(BaseModel):
    """列表 + 当前实际生效的来源"""

    items: List[ProviderItem]
    source: str = Field(..., description="user=用户配置，env=平台兜底")
    active_model: str
    active_provider_name: str


class TestResult(BaseModel):
    """连通性测试结果"""

    success: bool
    message: str
    latency_ms: Optional[int] = None
    sample: Optional[str] = None
