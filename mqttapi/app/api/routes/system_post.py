"""岗位管理：分页查询 / 新增 / 修改 / 删除。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/post", tags=["system-post"])


class PostBody(BaseModel):
    post_code: str = Field(..., min_length=1, max_length=64, description="岗位编码")
    post_name: str = Field(..., min_length=1, max_length=50, description="岗位名称")
    post_sort: int = Field(0, ge=0, description="显示顺序")
    status: str = Field("0", description="状态（0正常 1停用）")
    remark: str | None = Field(None, max_length=500)


@router.get("/list")
def list_posts(
    post_code: str | None = Query(None, max_length=64),
    post_name: str | None = Query(None, max_length=50),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:post:list")),
) -> dict[str, Any]:
    rows, total = db.list_posts(
        keyword=(post_code or post_name),
        status=status,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/options")
def post_options(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:post:list")),
) -> list[dict[str, Any]]:
    """全部启用岗位（下拉/分配用）。"""
    rows, _ = db.list_posts(status="0", limit=1000)
    return rows


@router.post("")
def create_post(
    body: PostBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:post:add")),
) -> dict[str, Any]:
    if db.get_post_by_code(body.post_code) is not None:
        raise AuthError("岗位编码已存在", code=400)
    post_id = db.create_post({
        **body.model_dump(),
        "create_by": user["username"],
    })
    record_operlog(
        db, request, user, title="岗位管理", business_type=BT_INSERT,
        param=body.model_dump(), result={"post_id": post_id},
    )
    return {"post_id": post_id}


@router.put("/{post_id}")
def update_post(
    post_id: int,
    body: PostBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:post:edit")),
) -> dict[str, Any]:
    if db.get_post_by_id(post_id) is None:
        raise AuthError("岗位不存在", code=404)
    db.update_post(post_id, {
        **body.model_dump(),
        "update_by": user["username"],
    })
    record_operlog(
        db, request, user, title="岗位管理", business_type=BT_UPDATE,
        param={"post_id": post_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/{post_id}")
def delete_post(
    post_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:post:remove")),
) -> dict[str, Any]:
    if db.get_post_by_id(post_id) is None:
        raise AuthError("岗位不存在", code=404)
    db.delete_post(post_id)
    record_operlog(
        db, request, user, title="岗位管理", business_type=BT_DELETE,
        param={"post_id": post_id},
    )
    return {"ok": True}
