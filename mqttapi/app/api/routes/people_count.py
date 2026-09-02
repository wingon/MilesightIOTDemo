from __future__ import annotations

import threading
import uuid
from datetime import date as DateType, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.cctv_sync import CONFIG_ENABLED, sync_date, sync_date_range
from app.db import Database
from app.security import AuthError

router = APIRouter(prefix="/api/v1", tags=["people-count"])

# 範圍回填任務狀態（記憶體存儲，重啟後丟失；任務可重跑，跳過已有日期）
_SYNC_TASKS: dict[str, dict[str, Any]] = {}
_SYNC_TASKS_LOCK = threading.Lock()

# 允許的最大查詢範圍（6 個月）
MAX_BACKFILL_DAYS = 183


class PeopleCountSyncBody(BaseModel):
    date: DateType | None = Field(default=None, description="要同步的單一日期（與 date_from/date_to 二選一）")
    date_from: DateType | None = Field(default=None, description="範圍回填開始日期（需同時傳 date_to）")
    date_to: DateType | None = Field(default=None, description="範圍回填結束日期（需同時傳 date_from）")


def _sync_enabled(db: Database) -> bool:
    config = db.get_config_by_key(CONFIG_ENABLED)
    return ((config or {}).get("config_value") or "Y").strip().upper() == "Y"


def _run_range_task(
    task_id: str,
    date_from: DateType,
    date_to: DateType,
    settings,
) -> None:
    """後台執行範圍回填，並更新任務狀態與進度。"""
    db = Database(settings)

    def _update_progress(completed: int, total: int, current: DateType) -> None:
        with _SYNC_TASKS_LOCK:
            task = _SYNC_TASKS.get(task_id)
            if task is None:
                return
            task["progress"] = round(completed * 100 / total) if total else 100
            task["done_days"] = completed
            task["total_days"] = total
            task["current_date"] = str(current)

    try:
        result = sync_date_range(
            db, settings, date_from, date_to, on_progress=_update_progress
        )
        with _SYNC_TASKS_LOCK:
            task = _SYNC_TASKS[task_id]
            task["status"] = "done"
            task["progress"] = 100
            task["done_days"] = task.get("total_days", 0)
            task["current_date"] = None
            task["result"] = result
            task["finished_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
    except Exception as exc:
        with _SYNC_TASKS_LOCK:
            task = _SYNC_TASKS[task_id]
            task["status"] = "failed"
            task["error"] = str(exc)
            task["finished_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
        import logging

        logging.getLogger(__name__).exception("範圍回填任務 %s 失敗", task_id)


@router.get("/people-count/hourly")
def list_people_count_hourly(
    date_from: DateType | None = Query(
        default=None, description="Filter: date >= date_from"
    ),
    date_to: DateType | None = Query(
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
    date_from: DateType | None = Query(default=None),
    date_to: DateType | None = Query(default=None),
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
    date_from: DateType | None = Query(default=None),
    date_to: DateType | None = Query(default=None),
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
    date_from: DateType | None = Query(default=None),
    date_to: DateType | None = Query(default=None),
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
    body: PeopleCountSyncBody = Body(default=PeopleCountSyncBody()),
    db: Database = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """手動觸發 CCTV 人流統計同步。

    支援兩種模式：
      - 單天：body.date 指定日期（缺省為今天），同步執行
      - 範圍：body.date_from + body.date_to，檢查範圍內缺失日期並回填（後台執行，回傳 task_id）
    受參數設定 cctv.sync.enabled 控制；為 N 時拒絕執行。
    """
    if not _sync_enabled(db):
        raise AuthError("CCTV 人流同步已停用", code=400)

    # 範圍模式
    if body.date_from is not None or body.date_to is not None:
        if body.date_from is None or body.date_to is None:
            raise AuthError("範圍回填必須同時提供 date_from 與 date_to", code=400)
        if body.date_from > body.date_to:
            raise AuthError("date_from 不能晚於 date_to", code=400)
        span_days = (body.date_to - body.date_from).days + 1
        if span_days > MAX_BACKFILL_DAYS:
            raise AuthError(
                f"查詢範圍超出限制：最多僅能查詢 6 個月（{MAX_BACKFILL_DAYS} 天）內的資料",
                code=400,
            )
        task_id = uuid.uuid4().hex
        # 先計算缺失日期總數，讓 total_days 在任務啟動時即有值（可顯示總進度）
        existing_dates = db.get_existing_people_count_dates_range(
            body.date_from, body.date_to
        )
        missing_days = [
            (body.date_from + timedelta(days=i))
            for i in range((body.date_to - body.date_from).days + 1)
            if (body.date_from + timedelta(days=i)) not in existing_dates
        ]
        total_missing = len(missing_days)
        with _SYNC_TASKS_LOCK:
            _SYNC_TASKS[task_id] = {
                "task_id": task_id,
                "date_from": str(body.date_from),
                "date_to": str(body.date_to),
                "status": "running",
                "progress": 0,
                "done_days": 0,
                "total_days": total_missing,
                "current_date": None,
                "started_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "result": None,
                "error": None,
            }
        thread = threading.Thread(
            target=_run_range_task,
            args=(task_id, body.date_from, body.date_to, db.settings),
            daemon=True,
        )
        thread.start()
        return {
            "task_id": task_id,
            "date_from": str(body.date_from),
            "date_to": str(body.date_to),
            "status": "running",
            "message": "範圍回填已於後台開始執行，可查詢 /api/v1/people-count/sync/status/{task_id}",
        }

    # 單天模式（同步執行）
    target_date = body.date or DateType.today()
    return sync_date(db, db.settings, target_date)


@router.get("/people-count/sync/status/{task_id}")
def get_sync_status(
    task_id: str,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """查詢範圍回填任務的執行狀態。"""
    with _SYNC_TASKS_LOCK:
        task = _SYNC_TASKS.get(task_id)
    if task is None:
        raise AuthError("任務不存在或已過期（記憶體任務在服務重啟後丟失）", code=404)
    return dict(task)