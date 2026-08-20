from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.db import Database

router = APIRouter(prefix="/api/v1", tags=["people-count"])


@router.get("/people-count/hourly")
def list_people_count_hourly(
    date_from: date | None = Query(
        default=None, description="Filter: date >= date_from"
    ),
    date_to: date | None = Query(
        default=None, description="Filter: date <= date_to"
    ),
    hour: int | None = Query(
        default=None, ge=0, le=23, description="Filter: exact hour (0-23)"
    ),
    ip_address: str | None = Query(
        default=None, description="Filter: exact ip_address"
    ),
    channel_name: str | None = Query(
        default=None, description="Filter: exact channel_name"
    ),
    limit: int = Query(default=20, ge=1, le=500, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Row offset"),
    db: Database = Depends(get_db),
) -> dict[str, Any]:
    """Paginated people_count_hourly rows with index-backed filters.

    Filters are pushed into the WHERE clause; the query is served by the
    idx_date_channel_hour / uk_date_hour_ip indexes.
    """
    items, total = db.list_people_count_hourly(
        date_from=date_from,
        date_to=date_to,
        hour=hour,
        ip_address=ip_address,
        channel_name=channel_name,
        limit=limit,
        offset=offset,
    )
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/people-count/channels")
def list_people_count_channels(db: Database = Depends(get_db)) -> list[str]:
    """Distinct channel_name values used to build the filter dropdown."""
    return db.list_people_count_channels()