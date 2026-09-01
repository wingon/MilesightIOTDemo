"""菜单管理：树形菜单 CRUD + 权限标识维护。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, BT_INSERT, BT_UPDATE, record_operlog
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1/system/menu", tags=["system-menu"])

ALLOWED_TYPES = ("M", "C", "F")


class MenuBody(BaseModel):
    parent_id: int = Field(0, ge=0, description="父菜单 ID，0 为根")
    menu_name: str = Field(..., min_length=1, max_length=50)
    i18n_key: str | None = Field(None, max_length=100)
    path: str | None = Field(None, max_length=200)
    component: str | None = Field(None, max_length=200)
    menu_type: str = Field("C", pattern="^[MCF]$")
    permission: str | None = Field(None, max_length=100)
    icon: str | None = Field(None, max_length=100)
    sort: int = Field(0)
    visible: int = Field(1, ge=0, le=1)
    status: int = Field(1, ge=0, le=1)
    remark: str | None = Field(None, max_length=200)


def _validate_parent(db: Database, parent_id: int) -> None:
    """校验父菜单存在；按钮（F）不能作为父级。"""
    if parent_id == 0:
        return
    parent = db.get_sys_menu(parent_id)
    if parent is None:
        raise AuthError("父菜单不存在", code=400)
    if parent.get("menu_type") == "F":
        raise AuthError("按钮不能作为父级菜单", code=400)


@router.get("/list")
def list_menus(
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:menu:list")),
) -> list[dict[str, Any]]:
    """完整菜单树（含按钮），用于菜单管理页。"""
    return db.list_all_menus()


@router.get("/{menu_id}")
def get_menu(
    menu_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:menu:list")),
) -> dict[str, Any]:
    menu = db.get_sys_menu(menu_id)
    if menu is None:
        raise AuthError("菜单不存在", code=404)
    return menu


@router.post("")
def create_menu(
    body: MenuBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:menu:add")),
) -> dict[str, Any]:
    _validate_parent(db, body.parent_id)
    menu_id = db.create_sys_menu(body.model_dump())
    record_operlog(
        db, request, user, title="菜单管理", business_type=BT_INSERT,
        param=body.model_dump(), result={"id": menu_id},
    )
    return {"id": menu_id}


@router.put("/{menu_id}")
def update_menu(
    menu_id: int,
    body: MenuBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:menu:edit")),
) -> dict[str, Any]:
    if db.get_sys_menu(menu_id) is None:
        raise AuthError("菜单不存在", code=404)
    if body.parent_id == menu_id:
        raise AuthError("不能将菜单自身设为父级", code=400)
    _validate_parent(db, body.parent_id)
    db.update_sys_menu(menu_id, body.model_dump())
    record_operlog(
        db, request, user, title="菜单管理", business_type=BT_UPDATE,
        param={"id": menu_id, **body.model_dump()},
    )
    return {"ok": True}


@router.delete("/{menu_id}")
def delete_menu(
    menu_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:menu:remove")),
) -> dict[str, Any]:
    if db.get_sys_menu(menu_id) is None:
        raise AuthError("菜单不存在", code=404)
    if db.count_sys_menu_children(menu_id) > 0:
        raise AuthError("存在子菜单，请先删除子菜单", code=400)
    db.delete_sys_menu(menu_id)
    record_operlog(
        db, request, user, title="菜单管理", business_type=BT_DELETE,
        param={"id": menu_id},
    )
    return {"ok": True}
