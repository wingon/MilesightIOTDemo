from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Body, Depends, Query

from app.api.deps import get_current_user, get_db
from app.cctv_sync import CONFIG_ENABLED, sync_date
from app.db import Database
from app.security import AuthError

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
    _user: dict = Depends(get_current_user),
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
def list_people_count_channels(
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[str]:
    """Distinct channel_name values used to build the filter dropdown."""
    return db.list_people_count_channels()


@router.get("/people-count/stats/hourly")
def people_count_hourly_stats(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
    ip_address: str | None = Query(default=None),
    channel_name: str | None = Query(default=None),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Hourly enter/exit aggregation (for charts)."""
    return db.people_count_hourly_stats(
        date_from=date_from,
        date_to=date_to,
        hour=hour,
        ip_address=ip_address,
        channel_name=channel_name,
    )


@router.get("/people-count/stats/daily")
def people_count_daily_stats(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
    ip_address: str | None = Query(default=None),
    channel_name: str | None = Query(default=None),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Daily enter/exit aggregation (for charts)."""
    return db.people_count_daily_stats(
        date_from=date_from,
        date_to=date_to,
        hour=hour,
        ip_address=ip_address,
        channel_name=channel_name,
    )


@router.get("/people-count/stats/channel")
def people_count_channel_stats(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    hour: int | None = Query(default=None, ge=0, le=23),
    ip_address: str | None = Query(default=None),
    channel_name: str | None = Query(default=None),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """Channel enter/exit aggregation (for charts)."""
    return db.people_count_channel_stats(
        date_from=date_from,
        date_to=date_to,
        hour=hour,
        ip_address=ip_address,
        channel_name=channel_name,
    )


@router.post("/people-count/sync")
def sync_people_count(
    request_date: date | None = Body(default=None, description="要同步的日期，缺省為今天"),
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """手動觸發 CCTV 人流統計同步。

    受參數設定 cctv.sync.enabled 控制；為 N 時拒絕執行。
    """
    config = db.get_config_by_key(CONFIG_ENABLED)
    enabled = (config or {}).get("config_value") or "Y"
    if enabled.strip().upper() != "Y":
        raise AuthError("CCTV 人流同步已停用", code=400)

    target_date = request_date or date.today()
    return sync_date(db, db.settings, target_date)