"""
设置路由：用户自带模型供应商（BYOK）的 API 管理

- 全部接口需登录，身份一律取自 Authorization 头
- API Key 只进不出：写入即加密，读取只回掩码
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ratelimit import enforce_rate_limit
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.llm_provider import (
    ProviderCreate,
    ProviderItem,
    ProviderListResponse,
    ProviderUpdate,
    TestResult,
)
from app.services import llm_provider_service as svc
from app.services.llm_provider_service import ProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/settings", tags=["设置"])


def _translate(err: ProviderError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.message)


@router.get("/llm/providers", response_model=ProviderListResponse)
async def list_llm_providers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出我的模型供应商配置 + 当前实际生效的来源"""
    rows = svc.list_providers(db, user.user_id)
    return ProviderListResponse(
        items=[svc.to_item(row) for row in rows],
        **svc.current_status(db, user.user_id),
    )


@router.post("/llm/providers", response_model=ProviderItem)
async def create_llm_provider(
    payload: ProviderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """新增一条供应商配置；用户的第一条自动设为当前使用"""
    try:
        row = svc.create_provider(db, user.user_id, payload.model_dump())
    except ProviderError as err:
        raise _translate(err) from err
    return svc.to_item(row)


@router.put("/llm/providers/{provider_id}", response_model=ProviderItem)
async def update_llm_provider(
    provider_id: int,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新配置；api_key 传空表示沿用原 Key"""
    try:
        row = svc.update_provider(
            db, user.user_id, provider_id, payload.model_dump(exclude_unset=True)
        )
    except ProviderError as err:
        raise _translate(err) from err
    return svc.to_item(row)


@router.delete("/llm/providers/{provider_id}", response_model=dict)
async def delete_llm_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除配置；若删的是当前使用，自动补位下一条"""
    try:
        svc.delete_provider(db, user.user_id, provider_id)
    except ProviderError as err:
        raise _translate(err) from err
    return {"success": True}


@router.post("/llm/providers/{provider_id}/default", response_model=ProviderItem)
async def set_default_llm_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """把该配置设为当前使用（换模型走这里）"""
    try:
        row = svc.set_default(db, user.user_id, provider_id)
    except ProviderError as err:
        raise _translate(err) from err
    return svc.to_item(row)


@router.post("/llm/providers/{provider_id}/test", response_model=TestResult)
async def test_llm_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """真实发一次极短请求，验证 Base URL / API Key / 模型名"""
    enforce_rate_limit(user.user_id, "llm_test")
    try:
        return await svc.test_connection(db, user.user_id, provider_id)
    except ProviderError as err:
        raise _translate(err) from err
