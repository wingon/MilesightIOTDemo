"""登录日志：查询 / 删除 / 清空。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db, require_permission
from app.api.operlog import BT_DELETE, record_operlog
from app.db import Database

router = APIRouter(prefix="/api/v1/system/loginlog", tags=["system-loginlog"])


class IdsBody(BaseModel):
    ids: list[int] = Field(default_factory=list, description="日志 ID 列表")


@router.get("/list")
def list_login_logs(
    user_name: str | None = Query(None, max_length=50),
    status: str | None = Query(None),
    begin: str | None = Query(None, description="开始时间 yyyy-MM-dd HH:mm:ss"),
    end: str | None = Query(None, description="结束时间 yyyy-MM-dd HH:mm:ss"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Database = Depends(get_db),
    _user: dict = Depends(require_permission("system:loginlog:list")),
) -> dict[str, Any]:
    rows, total = db.list_login_logs(
        user_name=user_name,
        status=status,
        begin=begin,
        end=end,
        offset=offset,
        limit=limit,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@router.delete("")
def delete_logs(
    body: IdsBody,
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:loginlog:remove")),
) -> dict[str, Any]:
    if not body.ids:
        return {"ok": True, "deleted": 0}
    deleted = db.delete_login_logs(body.ids)
    record_operlog(
        db, request, user, title="登录日志", business_type=BT_DELETE,
        param={"ids": body.ids}, result={"deleted": deleted},
    )
    return {"ok": True, "deleted": deleted}


@router.delete("/clean")
def clean_logs(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
    _p: dict = Depends(require_permission("system:loginlog:clean")),
) -> dict[str, Any]:
    cleaned = db.clean_login_logs()
    record_operlog(
        db, request, user, title="登录日志", business_type=BT_DELETE,
        param={"operation": "清空登录日志"}, result={"cleaned": cleaned},
    )
    return {"ok": True, "cleaned": cleaned}
