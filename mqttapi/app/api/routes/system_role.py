"""角色管理：CRUD + 分配菜单权限 + 数据权限（data_scope）+ 变更状态。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_AUTHORIZE, BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/role", tags=["system-role"])


class RoleBody(BaseModel):
    role_name: str = Field(..., min_length=1, max_length=50)
    role_key: str = Field(..., min_length=1, max_length=50)
    sort: int = Field(0)
    status: int = Field(1, ge=0, le=1)
    data_scope: str = Field("1", description="数据范围(1全部 2自定义 3本部门 4本部门及以下 5仅本人)")
    remark: str | None = Field(None, max_length=200)


class AssignMenusBody(BaseModel):
    menu_ids: list[int] = Field(default_factory=list)


class DataScopeBody(BaseModel):
    data_scope: str = Field("1", description="数据范围")
    dept_ids: list[int] = Field(default_factory=list)


class StatusBody(BaseModel):
    status: int = Field(1, ge=0, le=1)


class DeleteBody(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


@router.get("/list")
def list_roles(
    role_name: str | None = Query(None, max_length=50, description="角色名称"),
    role_key: str | None = Query(None, max_length=50, description="权限字符"),
    status: int | None = Query(None, ge=0, le=1),
    begin: str | None = Query(None, description="创建时间起（YYYY-MM-DD）"),
    end: str | None = Query(None, description="创建时间止（YYYY-MM-DD）"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> dict[str, Any]:
    rows, total = db.list_sys_roles(
        role_name=role_name, role_key=role_key, status=status,
        begin=begin, end=end, offset=offset, limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/options")
def role_options(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> list[dict[str, Any]]:
    """全部启用角色（下拉选项用）。"""
    return db.list_all_roles()


# 注意：/menu-tree、/dept-tree 为静态路径，必须定义在 /{role_id} 之前，否则会被 {role_id} 捕获。
@router.get("/menu-tree")
def menu_tree(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> dict[str, Any]:
    """完整菜单树（若依 menuTreeselect / roleMenuTreeselect）。"""
    return {"menus": db.list_all_menus()}


@router.get("/dept-tree")
def dept_tree(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> dict[str, Any]:
    """部门完整树（若依 deptTreeSelect，用于数据权限自定义部门勾选）。"""
    return {"depts": db.get_dept_tree()}


@router.get("/{role_id}")
def get_role(
    role_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> dict[str, Any]:
    """角色详情（用于编辑回显，含 data_scope）。"""
    role = db.get_sys_role(role_id)
    if role is None:
        raise AuthError("角色不存在", code=404)
    return role


@router.get("/{role_id}/menus")
def get_role_menus(
    role_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> list[int]:
    """角色已授权的菜单 ID 列表（回显勾选用）。"""
    return db.get_role_menu_ids(role_id)


@router.get("/{role_id}/depts")
def get_role_depts(
    role_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:role:list")),
) -> list[int]:
    """角色自定义数据权限选中的部门 ID 列表（回显勾选用）。"""
    return db.get_role_dept_ids(role_id)


@router.post("")
def create_role(
    body: RoleBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:add")),
) -> dict[str, Any]:
    if db.get_sys_role_by_key(body.role_key) is not None:
        raise AuthError("角色标识已存在", code=400)
    role_id = db.create_sys_role(body.model_dump())
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_INSERT,
        param=body.model_dump(), result={"id": role_id},
    )
    return {"id": role_id}


@router.put("/{role_id}")
def update_role(
    role_id: int,
    body: RoleBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:edit")),
) -> dict[str, Any]:
    if db.get_sys_role(role_id) is None:
        raise AuthError("角色不存在", code=404)
    existing = db.get_sys_role_by_key(body.role_key)
    if existing is not None and int(existing["id"]) != role_id:
        raise AuthError("角色标识已存在", code=400)
    db.update_sys_role(role_id, body.model_dump())
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_UPDATE,
        param={"id": role_id, **body.model_dump()},
    )
    return {"ok": True}


@router.put("/{role_id}/menus")
def assign_menus(
    role_id: int,
    body: AssignMenusBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:assignMenu")),
) -> dict[str, Any]:
    if db.get_sys_role(role_id) is None:
        raise AuthError("角色不存在", code=404)
    db.set_role_menus(role_id, body.menu_ids)
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_AUTHORIZE,
        param={"id": role_id, "menu_ids": body.menu_ids},
    )
    return {"ok": True}


@router.put("/{role_id}/data-scope")
def assign_data_scope(
    role_id: int,
    body: DataScopeBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:edit")),
) -> dict[str, Any]:
    if db.get_sys_role(role_id) is None:
        raise AuthError("角色不存在", code=404)
    db.update_sys_role(role_id, {"data_scope": body.data_scope})
    if body.data_scope == "2":
        db.set_role_depts(role_id, body.dept_ids)
    else:
        db.set_role_depts(role_id, [])
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_AUTHORIZE,
        param={"id": role_id, "data_scope": body.data_scope, "dept_ids": body.dept_ids},
    )
    return {"ok": True}


@router.put("/{role_id}/status")
def change_status(
    role_id: int,
    body: StatusBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:edit")),
) -> dict[str, Any]:
    if db.get_sys_role(role_id) is None:
        raise AuthError("角色不存在", code=404)
    db.update_sys_role(role_id, {"status": body.status})
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_UPDATE,
        param={"id": role_id, "status": body.status},
    )
    return {"ok": True}


@router.delete("/{role_id}")
def delete_role(
    role_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:remove")),
) -> dict[str, Any]:
    if db.get_sys_role(role_id) is None:
        raise AuthError("角色不存在", code=404)
    if db.get_sys_role(role_id).get("role_key") == db.SUPER_ADMIN_ROLE_KEY:
        raise AuthError("内置超级管理员角色不允许删除", code=400)
    db.delete_sys_role(role_id)
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_DELETE,
        param={"id": role_id},
    )
    return {"ok": True}


@router.delete("")
def delete_roles_batch(
    body: DeleteBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:role:remove")),
) -> dict[str, Any]:
    """批量删除角色（不含超管）。"""
    if not body.role_ids:
        raise AuthError("请选择要删除的角色", code=400)
    deleted = 0
    for rid in body.role_ids:
        role = db.get_sys_role(rid)
        if role is None:
            continue
        if role.get("role_key") == db.SUPER_ADMIN_ROLE_KEY:
            continue
        db.delete_sys_role(rid)
        deleted += 1
    record_operlog(
        db, request, user, title="角色管理", business_type=BT_DELETE,
        param={"role_ids": body.role_ids}, result={"deleted": deleted},
    )
    return {"ok": True, "deleted": deleted}
