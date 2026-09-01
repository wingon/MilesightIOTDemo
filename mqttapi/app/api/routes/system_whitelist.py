"""白名单设置：分页查询 / 新增 / 修改 / 删除。

白名单用于大屏等免登录路径：
  - path_type='F'：前端路由前缀，未登录也可访问（前端路由守卫读取）
  - path_type='A'：后端 API 前缀，认证依赖自动放行（deps.get_current_user）
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/whitelist", tags=["system-whitelist"])


class WhitelistBody(BaseModel):
    path: str = Field(..., min_length=1, max_length=255, description="白名单路径（前缀）")
    path_type: str = Field("F", description="类型（F=前端路由 A=后端API）")
    remark: str | None = Field(None, max_length=200)
    status: str = Field("0", description="状态（0正常 1停用）")


@router.get("/list")
def list_whitelists(
    keyword: str | None = Query(None, max_length=100),
    path_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:whitelist:list")),
) -> dict[str, Any]:
    rows, total = db.list_whitelists(
        keyword=keyword,
        path_type=path_type,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("")
def create_whitelist(
    body: WhitelistBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:whitelist:add")),
) -> dict[str, Any]:
    if body.path_type not in ("F", "A"):
        raise AuthError("类型只能是 F（前端）或 A（后端API）", code=400)
    existing, _ = db.list_whitelists(keyword=body.path, path_type=body.path_type, limit=1000)
    if any(w["path"] == body.path for w in existing):
        raise AuthError("该白名单路径已存在", code=400)
    whitelist_id = db.create_whitelist(body.model_dump())
    record_operlog(
        db, request, user, title="白名单设置", business_type=BT_INSERT,
        param=body.model_dump(), result={"id": whitelist_id},
    )
    return {"id": whitelist_id}


@router.put("/{whitelist_id}")
def update_whitelist(
    whitelist_id: int,
    body: WhitelistBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:whitelist:edit")),
) -> dict[str, Any]:
    if db.get_whitelist_by_id(whitelist_id) is None:
        raise AuthError("白名单不存在", code=404)
    db.update_whitelist(whitelist_id, body.model_dump())
    record_operlog(
        db, request, user, title="白名单设置", business_type=BT_UPDATE,
        param={"id": whitelist_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/{whitelist_id}")
def delete_whitelist(
    whitelist_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:whitelist:remove")),
) -> dict[str, Any]:
    if db.get_whitelist_by_id(whitelist_id) is None:
        raise AuthError("白名单不存在", code=404)
    db.delete_whitelist(whitelist_id)
    record_operlog(
        db, request, user, title="白名单设置", business_type=BT_DELETE,
        param={"id": whitelist_id},
    )
    return {"ok": True}
