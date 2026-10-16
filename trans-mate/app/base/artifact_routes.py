"""制品路由:列表/下载(预签名 URL)/回收站(归档/恢复/彻底删除)

鉴权约定：身份来自 Authorization header，user_id 一律取当前登录用户，
禁止客户端传 user_id（此前任何人均可列出/删除他人制品）。
"""
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.skill import Artifact
from app.models.user import User
from app.schemas.artifact import (
    ArtifactDownloadResponse,
    ArtifactItem,
    ArtifactListResponse,
    MessageResponse,
)
from app.services.skill_service import _get_storage

logger = logging.getLogger(__name__)

PRESIGN_EXPIRES_SECONDS = 3600

router = APIRouter(prefix="/api/artifacts", tags=["制品"])


def _get_storage_service():
    """模块级注入点:测试 monkeypatch 本函数替身存储"""
    return _get_storage()


def _get_owned(db: Session, artifact_id: int, user: User) -> Artifact:
    row = db.query(Artifact).filter_by(id=artifact_id, user_id=user.user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="制品不存在")
    return row


@router.get("", response_model=ArtifactListResponse)
async def list_artifacts(
    conversation_id: int | None = None,
    archived: bool = Query(False, description="true=回收站列表"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Artifact).filter_by(user_id=user.user_id, archived=archived)
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
            archived=r.archived, archived_at=r.archived_at,
        ) for r in rows],
        total=total,
    )


@router.post("/{artifact_id}/archive", response_model=MessageResponse)
async def archive_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """归档进回收站(对象本体保留,可恢复)"""
    row = _get_owned(db, artifact_id, user)
    row.archived = True
    row.archived_at = datetime.now()
    db.commit()
    return MessageResponse(message="已移入回收站")


@router.post("/{artifact_id}/restore", response_model=MessageResponse)
async def restore_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """从回收站恢复"""
    row = _get_owned(db, artifact_id, user)
    row.archived = False
    row.archived_at = None
    db.commit()
    return MessageResponse(message="已恢复")


@router.delete("/{artifact_id}", response_model=MessageResponse)
async def purge_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """彻底删除:删 MinIO 对象 + PG 行;对象删除失败不阻塞(孤儿对象仅记日志)"""
    row = _get_owned(db, artifact_id, user)
    try:
        _get_storage_service().delete_key(row.storage_key)
    except Exception as exc:
        logger.warning("制品对象删除失败 key=%s: %s", row.storage_key, exc)
    db.delete(row)
    db.commit()
    return MessageResponse(message="已彻底删除")


@router.get("/{artifact_id}/download", response_model=ArtifactDownloadResponse)
async def download_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _get_owned(db, artifact_id, user)
    try:
        url = _get_storage_service().presigned_get_url(
            row.storage_key, PRESIGN_EXPIRES_SECONDS, filename=row.filename
        )
    except Exception as exc:
        logger.error("生成预签名下载地址失败 id=%s: %s", artifact_id, exc)
        raise HTTPException(status_code=502, detail="下载地址生成失败") from exc
    return ArtifactDownloadResponse(
        id=row.id, filename=row.filename, url=url,
        expires_in=PRESIGN_EXPIRES_SECONDS,
    )
