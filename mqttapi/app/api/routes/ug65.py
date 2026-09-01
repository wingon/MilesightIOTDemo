from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user, get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["ug65"])

DEFAULT_LOOKBACK_HOURS = 48
# Set to False to test the original server-time window behavior.
USE_LATEST_RECORD_WINDOW = True


def _resolve_window(
    since: datetime | None,
    until: datetime | None,
    latest_received_at: datetime | None,
) -> tuple[datetime, datetime | None]:
    """Use the latest matching database row as the end of the default window."""
    # Original implementation (server-time anchor):
    # if since is not None:
    #     return since, until
    # return (
    #     datetime.now().replace(tzinfo=None) - timedelta(hours=DEFAULT_LOOKBACK_HOURS),
    #     until,
    # )
    if since is not None:
        return since, until
    if latest_received_at is None:
        return datetime.now().replace(tzinfo=None) - timedelta(hours=DEFAULT_LOOKBACK_HOURS), until
    return (
        latest_received_at - timedelta(hours=DEFAULT_LOOKBACK_HOURS),
        until or latest_received_at,
    )


@router.get("/ug65/devices")
def list_ug65_devices(
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
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
        description="received_at >= since (default: 48 hours before the latest matching row)",
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
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    latest_received_at = (
        db.latest_ug65_received_at(dev_eui=dev_eui, gateway_model=gateway_model)
        if since is None and USE_LATEST_RECORD_WINDOW
        else None
    )
    effective_since, effective_until = _resolve_window(since, until, latest_received_at)
    items, total = db.list_ug65(
        dev_eui=dev_eui,
        gateway_model=gateway_model,
        since=effective_since,
        until=effective_until,
        limit=limit,
        offset=offset,
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "since": effective_since.isoformat(sep=" "),
        "until": effective_until.isoformat(sep=" ") if effective_until else None,
        "items": items,
    }


@router.get("/ug65/{row_id}")
def get_ug65(
    row_id: int,
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    row = db.get_ug65(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"ug65 id={row_id} not found")
    return row
