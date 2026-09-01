"""参数设置：分页查询 / 新增 / 修改 / 删除。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/config", tags=["system-config"])


class ConfigBody(BaseModel):
    config_name: str = Field(..., min_length=1, max_length=100, description="参数名称")
    config_key: str = Field(..., min_length=1, max_length=100, description="参数键名")
    config_value: str = Field(..., max_length=500, description="参数键值")
    config_type: str = Field("N", description="系统内置（Y是 N否）")
    remark: str | None = Field(None, max_length=500)


@router.get("/list")
def list_configs(
    config_name: str | None = Query(None, max_length=100),
    config_key: str | None = Query(None, max_length=100),
    config_type: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:config:list")),
) -> dict[str, Any]:
    rows, total = db.list_configs(
        keyword=(config_name or config_key),
        config_type=config_type,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.post("")
def create_config(
    body: ConfigBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:config:add")),
) -> dict[str, Any]:
    if db.get_config_by_key(body.config_key) is not None:
        raise AuthError("参数键名已存在", code=400)
    config_id = db.create_config({
        **body.model_dump(),
        "create_by": user["username"],
    })
    record_operlog(
        db, request, user, title="参数设置", business_type=BT_INSERT,
        param=body.model_dump(), result={"config_id": config_id},
    )
    return {"config_id": config_id}


@router.put("/{config_id}")
def update_config(
    config_id: int,
    body: ConfigBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:config:edit")),
) -> dict[str, Any]:
    row = db.get_config_by_id(config_id)
    if row is None:
        raise AuthError("参数不存在", code=404)
    db.update_config(config_id, {
        **body.model_dump(),
        "update_by": user["username"],
    })
    record_operlog(
        db, request, user, title="参数设置", business_type=BT_UPDATE,
        param={"config_id": config_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/{config_id}")
def delete_config(
    config_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:config:remove")),
) -> dict[str, Any]:
    row = db.get_config_by_id(config_id)
    if row is None:
        raise AuthError("参数不存在", code=404)
    if row.get("config_type") == "Y":
        raise AuthError("内置参数不允许删除", code=400)
    db.delete_config(config_id)
    record_operlog(
        db, request, user, title="参数设置", business_type=BT_DELETE,
        param={"config_id": config_id},
    )
    return {"ok": True}
