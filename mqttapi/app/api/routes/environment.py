from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["environment"])


@router.get("/environment/devices")
def list_environment_devices(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """WingOnIOT 环境设备列表（Environment_Device）。"""
    return db.list_environment_devices()


@router.get("/environment/monitoring")
def list_environment_monitoring(
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows"),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Environmental_Monitoring 分页列表（最新写入在前）。"""
    items, total = db.list_environment_monitoring(limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/environment/floor-summary")
def floor_environment_summary(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """按楼层聚合的最新温度/湿度（每台设备最新一条中位值均值）。"""
    return db.floor_environment_summary()
