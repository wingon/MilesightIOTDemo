"""部门管理：树形查询 / 新增 / 修改 / 删除。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/dept", tags=["system-dept"])


class DeptBody(BaseModel):
    parent_id: int = Field(0, description="父部门ID")
    dept_name: str = Field(..., min_length=1, max_length=30, description="部门名称")
    order_num: int = Field(0, ge=0, description="显示顺序")
    leader: str | None = Field(None, max_length=20)
    phone: str | None = Field(None, max_length=11)
    email: str | None = Field(None, max_length=50)
    status: str = Field("0", description="状态（0正常 1停用）")


@router.get("/list")
def list_depts(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:dept:list")),
) -> list[dict[str, Any]]:
    """部门全量列表（前端构树）。"""
    return db.list_depts()


@router.post("")
def create_dept(
    body: DeptBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dept:add")),
) -> dict[str, Any]:
    if body.parent_id != 0 and db.get_dept_by_id(body.parent_id) is None:
        raise AuthError("上级部门不存在", code=400)
    dept_id = db.create_dept({
        **body.model_dump(),
        "create_by": user["username"],
    })
    record_operlog(
        db, request, user, title="部门管理", business_type=BT_INSERT,
        param=body.model_dump(), result={"dept_id": dept_id},
    )
    return {"dept_id": dept_id}


@router.put("/{dept_id}")
def update_dept(
    dept_id: int,
    body: DeptBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dept:edit")),
) -> dict[str, Any]:
    if db.get_dept_by_id(dept_id) is None:
        raise AuthError("部门不存在", code=404)
    if body.parent_id == dept_id:
        raise AuthError("上级部门不能是自身", code=400)
    db.update_dept(dept_id, {
        **body.model_dump(),
        "update_by": user["username"],
    })
    record_operlog(
        db, request, user, title="部门管理", business_type=BT_UPDATE,
        param={"dept_id": dept_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/{dept_id}")
def delete_dept(
    dept_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:dept:remove")),
) -> dict[str, Any]:
    if db.get_dept_by_id(dept_id) is None:
        raise AuthError("部门不存在", code=404)
    if db.has_children_dept(dept_id):
        raise AuthError("存在下级部门，不允许删除", code=400)
    if db.dept_has_users(dept_id):
        raise AuthError("部门存在用户，不允许删除", code=400)
    db.delete_dept(dept_id)
    record_operlog(
        db, request, user, title="部门管理", business_type=BT_DELETE,
        param={"dept_id": dept_id},
    )
    return {"ok": True}
