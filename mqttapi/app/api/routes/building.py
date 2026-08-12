from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["building"])


@router.get("/building/cell-shapes")
def list_cell_shapes(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    """3D 樓棟格子形狀設定（Building_Cell_Shape，啟用中）。"""
    return db.list_cell_shapes()
