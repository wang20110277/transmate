"""
技能路由:注册表浏览/安装/卸载/已装列表
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
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
    """浏览技能仓库(installed 标记需 user_id)"""
    try:
        items = skill_service.list_registry()
        return RegistryResponse(items=[
            RegistryItem(name=i["name"], description=i["description"], license=i["license"])
            for i in items
        ])
    except SkillServiceError as exc:
        raise HTTPException(status_code=502, detail=exc.message) from exc


@router.get("/registry/{user_id}", response_model=RegistryResponse)
async def list_registry_for_user(user_id: str, db: Session = Depends(get_db)):
    """浏览技能仓库并标记该用户已装项"""
    try:
        items = skill_service.list_registry()
        installed = {r.name for r in skill_service.list_installed(db, user_id)}
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
async def list_installed_route(user_id: str, db: Session = Depends(get_db)):
    rows = skill_service.list_installed(db, user_id)
    return InstalledResponse(items=[InstalledItem(
        name=r.name, version=r.version, description=r.description,
        source=r.source, installed_at=r.installed_at,
    ) for r in rows])


@router.post("/install", response_model=InstallResponse)
async def install_route(request: InstallRequest, db: Session = Depends(get_db)):
    try:
        row = skill_service.install_skill(db, request.user_id, request.name)
        return InstallResponse(name=row.name, version=row.version)
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.delete("/{name}")
async def uninstall_route(name: str, user_id: str, db: Session = Depends(get_db)):
    try:
        skill_service.uninstall_skill(db, user_id, name)
        return {"success": True}
    except SkillServiceError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/refresh")
async def refresh_route():
    skill_service.clear_registry_cache()
    return {"success": True}
