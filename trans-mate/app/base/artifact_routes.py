"""制品路由:列表/下载(预签名 URL)"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.skill import Artifact
from app.schemas.artifact import ArtifactDownloadResponse, ArtifactItem, ArtifactListResponse
from app.services.skill_service import _get_storage

PRESIGN_EXPIRES_SECONDS = 3600

router = APIRouter(prefix="/api/artifacts", tags=["制品"])


def _get_storage_service():
    """模块级注入点:测试 monkeypatch 本函数替身存储"""
    return _get_storage()


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    user_id: str,
    conversation_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Artifact).filter_by(user_id=user_id)
    if conversation_id is not None:
        query = query.filter_by(conversation_id=conversation_id)
    total = query.count()
    rows = (
        query.order_by(Artifact.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return ArtifactListResponse(
        items=[ArtifactItem(
            id=r.id, conversation_id=r.conversation_id, filename=r.filename,
            size=r.size, description=r.description, created_at=r.created_at,
        ) for r in rows],
        total=total,
    )


@router.get("/{artifact_id}/download", response_model=ArtifactDownloadResponse)
async def download_artifact(artifact_id: int, user_id: str, db: Session = Depends(get_db)):
    row = db.query(Artifact).filter_by(id=artifact_id, user_id=user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="制品不存在")
    try:
        url = _get_storage_service().presigned_get_url(row.storage_key, PRESIGN_EXPIRES_SECONDS)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"对象存储不可用: {exc}") from exc
    return ArtifactDownloadResponse(url=url)
