"""制品 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ArtifactItem(BaseModel):
    id: int
    conversation_id: int
    filename: str
    size: int
    description: str = ""
    created_at: Optional[datetime] = None
    archived: bool = False
    archived_at: Optional[datetime] = None


class ArtifactListResponse(BaseModel):
    items: List[ArtifactItem]
    total: int


class ArtifactDownloadResponse(BaseModel):
    url: str


class MessageResponse(BaseModel):
    message: str
