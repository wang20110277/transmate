"""
Skill 服务:GitHub 注册表浏览 + 安装/卸载(安装/卸载在 Task 5 补齐)
"""
import logging
import re
import time
from typing import Optional, TypedDict

import httpx
import yaml
from sqlalchemy.orm import Session

from app.core.config import (
    SKILL_REGISTRY_CACHE_TTL,
    SKILL_REGISTRY_OWNER,
    SKILL_REGISTRY_PROXY,
    SKILL_REGISTRY_REF,
    SKILL_REGISTRY_REPO,
    SKILL_REGISTRY_SUBDIR,
    SKILL_REGISTRY_TOKEN,
)

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
