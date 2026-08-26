"""
Skill 服务:GitHub 注册表浏览 + 安装/卸载
"""
import logging
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, TypedDict

import httpx
import yaml
from sqlalchemy.orm import Session

from app.core.config import (
    SKILL_MAX_FILES,
    SKILL_MAX_FILE_BYTES,
    SKILL_REGISTRY_CACHE_TTL,
    SKILL_REGISTRY_OWNER,
    SKILL_REGISTRY_PROXY,
    SKILL_REGISTRY_REF,
    SKILL_REGISTRY_REPO,
    SKILL_REGISTRY_SUBDIR,
    SKILL_REGISTRY_TOKEN,
)
from app.models.skill import UserSkill
from app.services.storage_service import StorageService, get_storage

logger = logging.getLogger(__name__)

SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9-]+$")

# 测试注入口:设为 httpx.MockTransport 即离线
_registry_transport: Optional[httpx.BaseTransport] = None

# TTL 缓存:ts -> (存入时间, 结果)
_registry_cache: dict[str, tuple[float, list]] = {}
_registry_commit_sha: dict[str, str] = {}


class SkillServiceError(Exception):
    """技能服务业务异常(message 面向用户可读)"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class SkillRegistryItem(TypedDict):
    name: str
    description: str
    license: str
    path: str  # 仓库内技能目录路径


def _build_client() -> httpx.Client:
    headers = {"Accept": "application/vnd.github+json"}
    if SKILL_REGISTRY_TOKEN:
        headers["Authorization"] = f"Bearer {SKILL_REGISTRY_TOKEN}"
    return httpx.Client(
        base_url=f"https://api.github.com/repos/{SKILL_REGISTRY_OWNER}/{SKILL_REGISTRY_REPO}",
        headers=headers,
        transport=_registry_transport,
        proxy=SKILL_REGISTRY_PROXY or None,
        timeout=15.0,
        follow_redirects=True,
    )


def parse_skill_md(content: str, dir_name: str) -> Optional[dict]:
    """解析 SKILL.md frontmatter;不合法返回 None"""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or not description or name != dir_name:
        return None
    if not SKILL_NAME_PATTERN.match(name):
        return None
    return {
        "name": name,
        "description": description,
        "license": str(data.get("license", "") or "").strip(),
    }


def _api_root() -> str:
    return f"/contents/{SKILL_REGISTRY_SUBDIR}" if SKILL_REGISTRY_SUBDIR else "/contents/"


def _fetch_json(client: httpx.Client, path: str):
    response = client.get(path)
    if response.status_code != 200:
        raise SkillServiceError(f"GitHub API 请求失败 {path}: HTTP {response.status_code}")
    return response.json()


def _fetch_skill_md(client: httpx.Client, dir_path: str) -> Optional[str]:
    """下载技能目录下 SKILL.md 原文;404 返回 None"""
    listing = _fetch_json(client, f"/contents/{dir_path}/SKILL.md")
    if isinstance(listing, list):
        listing = listing[0]
    download_url = listing.get("download_url")
    if not download_url:
        return None
    raw = client.get(download_url)
    if raw.status_code != 200:
        return None
    return raw.text


def list_registry(force: bool = False) -> list[SkillRegistryItem]:
    """列出仓库技能目录(TTL 缓存降级:失败时若缓存未过期返回旧值)"""
    cached = _registry_cache.get("items")
    if not force and cached and time.time() - cached[0] < SKILL_REGISTRY_CACHE_TTL:
        return cached[1]

    try:
        with _build_client() as client:
            entries = _fetch_json(client, _api_root())
            dirs = [e["path"] for e in entries if e.get("type") == "dir"]
            items: list[SkillRegistryItem] = []
            for dir_path in dirs:
                content = _fetch_skill_md(client, dir_path)
                if content is None:
                    continue
                meta = parse_skill_md(content, dir_path.rsplit("/", 1)[-1])
                if meta is None:
                    logger.warning("跳过不合规技能目录: %s", dir_path)
                    continue
                items.append(
                    SkillRegistryItem(
                        name=meta["name"], description=meta["description"],
                        license=meta["license"], path=dir_path,
                    )
                )
    except SkillServiceError:
        if cached:  # 降级返回旧缓存
            return cached[1]
        raise
    except httpx.HTTPError as exc:
        if cached:
            return cached[1]
        raise SkillServiceError(f"技能仓库不可达: {exc}") from exc

    _registry_cache["items"] = (time.time(), items)
    return items


def clear_registry_cache() -> None:
    _registry_cache.clear()


# 测试可覆盖的单例(不改 get_storage 全局,避免影响其它服务的测试)
_storage_singleton_override: Optional[StorageService] = None


def _get_storage() -> StorageService:
    return _storage_singleton_override or get_storage()


def latest_commit_sha() -> str:
    """仓库 ref 最新 commit sha(安装版本号)"""
    with _build_client() as client:
        response = client.get(f"/commits/{SKILL_REGISTRY_REF}")
        if response.status_code != 200:
            raise SkillServiceError(f"获取仓库版本失败: HTTP {response.status_code}")
        data = response.json()
        return data["sha"] if isinstance(data, dict) else data[0]["sha"]


def _walk_skill_dir(client: httpx.Client, dir_path: str) -> list[dict]:
    """递归列出技能目录全部文件(contents API)"""
    files: list[dict] = []
    entries = _fetch_json(client, f"/contents/{dir_path}")
    for entry in entries:
        if entry.get("type") == "file":
            files.append(entry)
        elif entry.get("type") == "dir":
            files.extend(_walk_skill_dir(client, entry["path"]))
    return files


def install_skill(db: Session, user_id: str, name: str) -> UserSkill:
    """安装:临时目录全量下载校验 → 上传 MinIO → 最后写 PG 清单(失败即清理)"""
    if not SKILL_NAME_PATTERN.match(name):
        raise SkillServiceError(f"技能名称不合法: {name}")

    existing = db.query(UserSkill).filter_by(user_id=user_id, name=name).first()
    if existing is not None:
        raise SkillServiceError(f"技能已安装: {name}")

    storage = _get_storage()
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"skill-{uuid.uuid4().hex[:8]}-"))
    prefix = f"skills/{user_id}/{name}"
    try:
        with _build_client() as client:
            files = _walk_skill_dir(client, name)
            if not files:
                raise SkillServiceError(f"技能目录不存在或为空: {name}")
            if len(files) > SKILL_MAX_FILES:
                raise SkillServiceError(f"技能文件数超限({len(files)} > {SKILL_MAX_FILES})")
            for entry in files:
                if int(entry.get("size", 0)) > SKILL_MAX_FILE_BYTES:
                    raise SkillServiceError(f"文件大小超限: {entry['path']}")
                raw = client.get(entry["download_url"])
                if raw.status_code != 200:
                    raise SkillServiceError(f"下载失败: {entry['path']}")
                rel = entry["path"][len(name):].strip("/")
                target = tmp_dir / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw.content)

        skill_md = (tmp_dir / "SKILL.md").read_text(encoding="utf-8") if (tmp_dir / "SKILL.md").exists() else None
        if skill_md is None:
            raise SkillServiceError(f"技能缺少 SKILL.md: {name}")
        meta = parse_skill_md(skill_md, name)
        if meta is None:
            raise SkillServiceError(f"SKILL.md 不合规(name 必须等于目录名且为小写-数字-连字符)")

        storage.upload_prefix(tmp_dir, prefix)

        row = UserSkill(
            user_id=user_id,
            name=name,
            version=latest_commit_sha(),
            description=meta["description"],
            source=f"{SKILL_REGISTRY_OWNER}/{SKILL_REGISTRY_REPO}@{SKILL_REGISTRY_REF}",
        )
        db.add(row)
        db.commit()
        return row
    except Exception:
        storage.delete_prefix(prefix)  # 不留半成品(spec §5)
        db.rollback()
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def uninstall_skill(db: Session, user_id: str, name: str) -> None:
    if not SKILL_NAME_PATTERN.match(name):
        raise SkillServiceError(f"技能名称不合法: {name}")
    row = db.query(UserSkill).filter_by(user_id=user_id, name=name).first()
    if row is None:
        raise SkillServiceError(f"未安装该技能: {name}")
    _get_storage().delete_prefix(f"skills/{user_id}/{name}")
    db.delete(row)
    db.commit()


def list_installed(db: Session, user_id: str) -> list[UserSkill]:
    return (
        db.query(UserSkill)
        .filter_by(user_id=user_id)
        .order_by(UserSkill.installed_at.desc())
        .all()
    )
