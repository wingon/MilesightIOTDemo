from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user, get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["facade"])


class FacadeConfigRequest(BaseModel):
    orientation: str = "vertical"
    widthRatio: float = 0.4
    heightRatio: float = 0.7
    cellWindows: dict[str, bool] = {}


@router.get("/building/facade-config")
def get_facade_config(db: Database = Depends(get_db)) -> dict[str, Any]:
    """Get the facade window configuration."""
    row = db.get_facade_config()
    if row is None:
        return {
            "orientation": "vertical",
            "widthRatio": 0.4,
            "heightRatio": 0.7,
            "cellWindows": {},
        }
    return row.get("config_json", row)


@router.post("/building/facade-config")
def save_facade_config(
    body: FacadeConfigRequest,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Save the facade window configuration."""
    config = body.model_dump()
    row_id = db.save_facade_config(config)
    return {"ok": True, "id": row_id}
