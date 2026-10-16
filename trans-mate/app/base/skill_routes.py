"""技能路由:注册表浏览/安装/卸载/已装列表

鉴权约定：身份来自 Authorization header，user_id 取当前登录用户。
registry（仓库目录）可匿名浏览，其余一律需登录且仅能操作自己的安装记录。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ratelimit import enforce_rate_limit
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.skill import (
    InstallRequest,
    InstallResponse,
    InstalledItem,
    InstalledResponse,
    RegistryItem,
    RegistryResponse,
)
from app.services import skill_service
from app.services.skill_service import SkillServiceError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["技能"])


@router.get("/registry", response_model=RegistryResponse)
async def list_registry_route():
    """浏览技能仓库（不标记已装状态）"""
    try:
        items = skill_service.list_registry()
        return RegistryResponse(items=[
            RegistryItem(name=i["name"], description=i["description"], license=i["license"])
            for i in items
        ])
    except SkillServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/registry/me", response_model=RegistryResponse)
async def list_registry_for_me(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """浏览技能仓库并标记当前用户已装项"""
    try:
        items = skill_service.list_registry()
        installed = {r.name for r in skill_service.list_installed(db, user.user_id)}
        return RegistryResponse(
            items=[
                RegistryItem(
                    name=i["name"], description=i["description"],
                    license=i["license"], installed=i["name"] in installed,
                )
                for i in items
            ]
        )
    except SkillServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/installed", response_model=InstalledResponse)
async def list_installed_route(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = skill_service.list_installed(db, user.user_id)
    return InstalledResponse(items=[InstalledItem(
        name=r.name, version=r.version, description=r.description,
        source=r.source, installed_at=r.installed_at,
    ) for r in rows])


@router.post("/install", response_model=InstallResponse)
async def install_route(
    request: InstallRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    enforce_rate_limit(user.user_id, "skill_install")
    try:
        row = skill_service.install_skill(db, user.user_id, request.name)
        return InstallResponse(name=row.name, version=row.version)
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.delete("/{name}")
async def uninstall_route(
    name: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        skill_service.uninstall_skill(db, user.user_id, name)
        return {"success": True}
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/refresh")
async def refresh_route(user: User = Depends(get_current_user)):
    """清除技能仓库注册表缓存（管理员操作）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    skill_service.clear_registry_cache()
    return {"success": True}
