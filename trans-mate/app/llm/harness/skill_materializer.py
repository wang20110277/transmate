"""
技能物化器:PG 清单 → 本地缓存目录(按清单指纹增量)
"""
import hashlib
import logging
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import config
from app.models.skill import UserSkill
from app.services.skill_service import _get_storage
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

MANIFEST_FILE = ".manifest"


def _fingerprint(rows: list[UserSkill]) -> str:
    parts = sorted(f"{r.name}@{r.version}" for r in rows)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def sync_user_skills(
    db: Session, user_id: str, storage: StorageService | None = None
) -> Path:
    """把用户云端技能物化到 SKILL_CACHE_ROOT/{user_id}/;失败降级为空/现状目录

    配置经 config 模块在调用时读取(便于测试 monkeypatch app.core.config.*)
    """
    storage = storage or _get_storage()
    cache_dir = Path(config.SKILL_CACHE_ROOT) / user_id
    rows = db.query(UserSkill).filter_by(user_id=user_id).all()
    fingerprint = _fingerprint(rows)

    staging: Path | None = None
    try:
        if (
            (cache_dir / MANIFEST_FILE).exists()
            and (cache_dir / MANIFEST_FILE).read_text(encoding="utf-8") == fingerprint
        ):
            return cache_dir  # 清单未变,复用缓存

        staging = cache_dir.parent / f".{user_id}.staging"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True, exist_ok=True)
        for row in rows:
            storage.download_prefix(f"{user_id}/skills/{row.name}", staging / row.name)
        # 原子替换:staging -> cache_dir
        shutil.rmtree(cache_dir, ignore_errors=True)
        staging.rename(cache_dir)
        (cache_dir / MANIFEST_FILE).write_text(fingerprint, encoding="utf-8")
    except Exception as exc:
        logger.warning("用户 %s 技能物化失败,降级现有缓存: %s", user_id, exc)
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        cache_dir.mkdir(parents=True, exist_ok=True)  # 至少保证目录存在(可能为空)
    return cache_dir
