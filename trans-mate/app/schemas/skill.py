"""技能相关 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class RegistryItem(BaseModel):
    name: str
    description: str
    license: str = ""
    installed: bool = False


class RegistryResponse(BaseModel):
    items: List[RegistryItem]


class InstalledItem(BaseModel):
    name: str
    version: str
    description: str = ""
    source: str = ""
    installed_at: Optional[datetime] = None


class InstalledResponse(BaseModel):
    items: List[InstalledItem]


class InstallRequest(BaseModel):
    user_id: str
    name: str


class InstallResponse(BaseModel):
    name: str
    version: str
