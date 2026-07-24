from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["ug65"])

DEFAULT_LOOKBACK_HOURS = 48


def _resolve_since(since: datetime | None) -> datetime:
    """Default to the last 48 hours (server local time, matches MariaDB CURRENT_TIMESTAMP)."""
    if since is not None:
        return since
    return datetime.now().replace(tzinfo=None) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


@router.get("/ug65/devices")
def list_ug65_devices(db: Database = Depends(get_db)) -> list[dict[str, Any]]:
    return db.list_ug65_devices()


@router.get("/ug65")
def list_ug65(
    dev_eui: str | None = Query(default=None, description="Filter by DevEUI"),
    gateway_model: str | None = Query(
        default=None,
        description="Filter by gateway model from topic (ug65 or ug56)",
    ),
    since: datetime | None = Query(
        default=None,
        description="received_at >= since (default: now - 48 hours)",
    ),
    until: datetime | None = Query(default=None, description="received_at <= until"),
    limit: int | None = Query(
        default=None,
        ge=1,
        le=100000,
        description="Max rows; omit to return all rows in the time window",
    ),
    offset: int = Query(default=0, ge=0),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    effective_since = _resolve_since(since)
    items, total = db.list_ug65(
        dev_eui=dev_eui,
        gateway_model=gateway_model,
        since=effective_since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "since": effective_since.isoformat(sep=" "),
        "until": until.isoformat(sep=" ") if until else None,
        "items": items,
    }


@router.get("/ug65/{row_id}")
def get_ug65(row_id: int, db: Database = Depends(get_db)) -> dict[str, Any]:
    row = db.get_ug65(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"ug65 id={row_id} not found")
    return row
