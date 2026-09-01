"""User management: CRUD + role assignment + password reset."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError, hash_password

router = APIRouter(prefix="/api/v1/system/user", tags=["system-user"])


class UserBody(BaseModel):
    username: str | None = Field(None, min_length=1, max_length=50, description="登录账号（新增必填）")
    password: str | None = Field(None, min_length=6, max_length=72, description="密码（新增必填）")
    dept_id: int | None = Field(None, description="部门ID")
    nickname: str | None = Field(None, max_length=50)
    email: str | None = Field(None, max_length=100)
    phone: str | None = Field(None, max_length=20)
    status: int = Field(1, ge=0, le=1)
    remark: str | None = Field(None, max_length=200)


class PasswordBody(BaseModel):
    password: str = Field(..., min_length=6, max_length=72)


class AssignRolesBody(BaseModel):
    role_ids: list[int] = Field(default_factory=list)


class AssignPostsBody(BaseModel):
    post_ids: list[int] = Field(default_factory=list)


@router.get("/list")
def list_users(
    keyword: str | None = Query(None, max_length=50),
    status: int | None = Query(None, ge=0, le=1),
    dept_id: int | None = Query(None, description="部门ID（含子部门）"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    user: dict = Depends(require_permission("system:user:list")),
) -> dict[str, Any]:
    rows, total = db.list_sys_users(
        keyword=keyword, status=status, dept_id=dept_id,
        scope_user_id=user["id"], offset=offset, limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.get("/{user_id}/roles")
def get_user_roles(
    user_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:user:list")),
) -> list[int]:
    """User's current role ID list (for selection echo)."""
    return db.get_user_role_ids(user_id)


@router.post("")
def create_user(
    body: UserBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:add")),
) -> dict[str, Any]:
    if not body.username or not body.password:
        raise AuthError("登录账号与密码必填", code=400)
    if db.get_sys_user_by_username(body.username) is not None:
        raise AuthError("登录账号已存在", code=400)
    user_id = db.create_sys_user({
        **body.model_dump(exclude_none=True),
        "password": hash_password(body.password),
    })
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_INSERT,
        param=body.model_dump(exclude={"password"}), result={"id": user_id},
    )
    return {"id": user_id}


@router.put("/{user_id}")
def update_user(
    user_id: int,
    body: UserBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:edit")),
) -> dict[str, Any]:
    if db.get_sys_user_by_id(user_id) is None:
        raise AuthError("用户不存在", code=404)
    data = body.model_dump(exclude_none=True, exclude={"username", "password"})
    db.update_sys_user(user_id, data)
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_UPDATE,
        param={"id": user_id, **data},
    )
    return {"ok": True}


@router.put("/{user_id}/password")
def reset_password(
    user_id: int,
    body: PasswordBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:resetPwd")),
) -> dict[str, Any]:
    if db.get_sys_user_by_id(user_id) is None:
        raise AuthError("用户不存在", code=404)
    db.reset_sys_user_password(user_id, hash_password(body.password))
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_UPDATE,
        param={"id": user_id, "operation": "重置密码"},
    )
    return {"ok": True}


@router.put("/{user_id}/roles")
def assign_roles(
    user_id: int,
    body: AssignRolesBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:assignRole")),
) -> dict[str, Any]:
    if db.get_sys_user_by_id(user_id) is None:
        raise AuthError("用户不存在", code=404)
    db.set_user_roles(user_id, body.role_ids)
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_UPDATE,
        param={"id": user_id, "role_ids": body.role_ids},
    )
    return {"ok": True}


@router.get("/{user_id}/posts")
def get_user_posts(
    user_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:user:list")),
) -> list[int]:
    """User's current post ID list (for selection echo)."""
    return db.get_user_post_ids(user_id)


@router.put("/{user_id}/posts")
def assign_posts(
    user_id: int,
    body: AssignPostsBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:edit")),
) -> dict[str, Any]:
    if db.get_sys_user_by_id(user_id) is None:
        raise AuthError("用户不存在", code=404)
    db.set_user_posts(user_id, body.post_ids)
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_UPDATE,
        param={"id": user_id, "post_ids": body.post_ids},
    )
    return {"ok": True}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:user:remove")),
) -> dict[str, Any]:
    if db.get_sys_user_by_id(user_id) is None:
        raise AuthError("用户不存在", code=404)
    if int(user_id) == int(user["id"]):
        raise AuthError("不能删除当前登录账号", code=400)
    db.delete_sys_user(user_id)
    record_operlog(
        db, request, user, title="用户管理", business_type=BT_UPDATE,
        param={"id": user_id}, result={"deleted": True},
    )
    return {"ok": True}
