from __future__ import annotations

import os
import threading
import uuid
from datetime import date as DateType, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.cctv_sync import CONFIG_ENABLED, sync_date, sync_date_range
from app.db import Database
from app.people_count_export import (
    MAX_EXPORT_DAYS,
    create_export_task,
    get_task,
    normalize_lang,
    text as export_text,
)
from app.security import AuthError

router = APIRouter(prefix="/api/v1", tags=["people-count"])

# 範圍回填任務狀態（記憶體存儲，重啟後丟失；任務可重跑，跳過已有日期）
_SYNC_TASKS: dict[str, dict[str, Any]] = {}
_SYNC_TASKS_LOCK = threading.Lock()

# 允許的最大查詢範圍（6 個月）
MAX_BACKFILL_DAYS = 183
# 一般查詢（統計聚合）允許的最大跨度（3 個月，含兩端的天數）
MAX_QUERY_DAYS = 92


def _normalize_query_range(
    date_from: DateType | None,
    date_to: DateType | None,
) -> tuple[DateType | None, DateType | None]:
    """查詢範圍的預設與限制。

    - 前後端都未提供日期 → 預設最近 7 天（含今天），避免全表掃描
    - 兩端都有值 → 校驗跨度不得超過 3 個月（MAX_QUERY_DAYS 天）
    - 僅提供一端 → 維持原語義
    """
    if date_from is None and date_to is None:
        date_to = DateType.today()
        date_from = date_to - timedelta(days=6)
        return date_from, date_to
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            raise AuthError("date_from 不能晚於 date_to", code=400)
        span_days = (date_to - date_from).days + 1
        if span_days > MAX_QUERY_DAYS:
            raise AuthError(
                f"查詢範圍超出限制：最多僅能查詢 3 個月（{MAX_QUERY_DAYS} 天）內的資料",
                code=400,
            )
    return date_from, date_to


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
    date_from, date_to = _normalize_query_range(date_from, date_to)
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
    date_from, date_to = _normalize_query_range(date_from, date_to)
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
    date_from, date_to = _normalize_query_range(date_from, date_to)
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
    date_from, date_to = _normalize_query_range(date_from, date_to)
    return db.people_count_channel_stats(
        date_from=date_from,
        date_to=date_to,
        hour=hour,
        ip_address=ip_address,
        channel_name=channel_name,
    )


@router.get("/people-count/stats/overview")
def people_count_overview(
    date_from: DateType | None = Query(default=None),
    date_to: DateType | None = Query(default=None),
    hour_from: int | None = Query(default=None, ge=0, le=23),
    hour_to: int | None = Query(default=None, ge=0, le=23),
    ip_address: str | None = Query(default=None),
    channel_name: str | None = Query(default=None),
    exclude_zero: bool = Query(default=False, description="過濾進入和離開皆為 0 的記錄"),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """綜合聚合：KPI 匯總 / 每日 / 時段 / 通道 / 樓層 / 通道類型 / 樓梯流向。

    供「視圖 / 樓層 / 資料」三個頁面使用，回傳結構與 demo/data.json 同構。
    """
    date_from, date_to = _normalize_query_range(date_from, date_to)
    return db.people_count_overview(
        date_from=date_from,
        date_to=date_to,
        hour_from=hour_from,
        hour_to=hour_to,
        ip_address=ip_address,
        channel_name=channel_name,
        exclude_zero=exclude_zero,
    )


@router.post("/people-count/export")
def export_people_count(
    date_from: DateType | None = Query(
        default=None, description="Export: date >= date_from"
    ),
    date_to: DateType | None = Query(
        default=None, description="Export: date <= date_to"
    ),
    hour_from: int | None = Query(default=None, ge=0, le=23),
    hour_to: int | None = Query(default=None, ge=0, le=23),
    channel_name: str | None = Query(default=None),
    exclude_zero: bool = Query(default=False, description="過濾進入和離開皆為 0 的記錄"),
    lang: str = Query(default="zh-TW", description="導出語言：en / zh-TW"),
    db: Database = Depends(get_db),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """建立人流統計 Excel 導出任務（後台執行）。

    產生「每日統計 + 通道統計」兩個工作表的 xlsx；時間範圍上限半年
    （MAX_EXPORT_DAYS=183 天），超限回傳本地化提示。
    建立後請輪詢 GET /people-count/export/status/{task_id} 取得進度。
    """
    lang = normalize_lang(lang)
    if date_from is not None and date_to is not None:
        if date_from > date_to:
            raise AuthError("date_from 不能晚於 date_to", code=400)
        span_days = (date_to - date_from).days + 1
        if span_days > MAX_EXPORT_DAYS:
            raise AuthError(
                export_text(lang, "errTooLong", days=MAX_EXPORT_DAYS),
                code=400,
            )
    task = create_export_task(
        settings=db.settings,
        date_from=date_from,
        date_to=date_to,
        hour_from=hour_from,
        hour_to=hour_to,
        channel_name=channel_name,
        exclude_zero=exclude_zero,
        lang=lang,
    )
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "lang": lang,
        "message": export_text(lang, "msgCreated", task_id=task["task_id"]),
    }


@router.get("/people-count/export/status/{task_id}")
def get_export_status(
    task_id: str,
    lang: str = Query(default="zh-TW"),
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """查詢匯出任務的執行狀態與進度（0 ~ 100）。"""
    lang = normalize_lang(lang)
    task = get_task(task_id)
    if task is None:
        raise AuthError(export_text(lang, "errNotFound"), code=404)
    # 不下發內部 file_path，避免洩漏伺服器路徑
    task = dict(task)
    task.pop("file_path", None)
    return task


@router.get("/people-count/export/download/{task_id}")
def download_export(
    task_id: str,
    lang: str = Query(default="zh-TW"),
    _user: dict = Depends(get_current_user),
) -> FileResponse:
    """下載已完成的匯出檔（僅限 status=done）。"""
    lang = normalize_lang(lang)
    task = get_task(task_id)
    if task is None:
        raise AuthError(export_text(lang, "errNotFound"), code=404)
    if task.get("status") != "done" or not task.get("file_path"):
        raise AuthError(export_text(lang, "errNotReady"), code=400)
    if not os.path.exists(task["file_path"]):
        raise AuthError(export_text(lang, "errNotFound"), code=404)
    return FileResponse(
        task["file_path"],
        media_type="application/zip",
        filename=task.get("filename") or "people_count.zip",
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