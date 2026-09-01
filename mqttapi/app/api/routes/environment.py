from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["environment"])


@router.get("/environment/devices")
def list_environment_devices(
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """WingOnIOT environment device list (Environment_Device) with bound cell and room."""
    return db.list_environment_devices()


class BindDeviceCellRequest(BaseModel):
    floor_id: int
    row_no: int
    col_no: int


@router.post("/environment/devices/{sn}/cell")
def bind_device_cell(
    sn: str,
    body: BindDeviceCellRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Bind the device to a specific cell (device → cell; replaces the previous binding)."""
    result = db.bind_device_cell(sn, body.floor_id, body.row_no, body.col_no)
    if result != "ok":
        if result == "floor_mismatch":
            raise HTTPException(status_code=409, detail="Floor mismatch: device floor differs from cell floor")
        raise HTTPException(status_code=404, detail="Device or cell not found")
    return {"ok": True}


@router.delete("/environment/devices/{sn}/cell")
def unbind_device_cell(
    sn: str,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Unbind all cell bindings of the device."""
    ok = db.unbind_device_cell(sn)
    if not ok:
        raise HTTPException(status_code=404, detail="No binding to remove")
    return {"ok": True}


@router.get("/environment/monitoring")
def list_environment_monitoring(
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows"),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Paginated Environmental_Monitoring list (newest writes first)."""
    items, total = db.list_environment_monitoring(limit=limit, offset=offset)
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/environment/floor-summary")
def floor_environment_summary(
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Latest temperature/humidity aggregated per floor (median of each device's latest record)."""
    return db.floor_environment_summary()
