"""人流統計 CSV 匯出：後台任務 + 輪詢狀態 + 檔案下載。

- 匯出內容為「每日統計」與「通道統計」兩個 CSV，打包為單一 ZIP（與 /people-count/data 頁一致）
- 時間範圍上限半年（MAX_EXPORT_DAYS=183），超限由路由層在建立任務前攔截
- 任務狀態存記憶體（重啟後丟失），進度以階段百分比回報
- 表頭 / 檔名 / 星期 / 通道類型與錯誤提示詞皆依語言（en / zh-TW）輸出
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import uuid
from datetime import date as DateType, datetime
from typing import Any

from app.db import Database

logger = logging.getLogger(__name__)

# 匯出時間範圍上限：6 個月（與範圍回填上限 MAX_BACKFILL_DAYS 一致）
MAX_EXPORT_DAYS = 183

# 支援的語言
SUPPORTED_LANGS = ("en", "zh-TW")

_EXPORT_DIR = os.path.join(tempfile.gettempdir(), "people_count_export")

_TASKS: dict[str, dict[str, Any]] = {}
_TASKS_LOCK = threading.Lock()

# ---------------------------------------------------------------------------
# 多語言文案
# ---------------------------------------------------------------------------
_TEXT: dict[str, dict[str, Any]] = {
    "zh-TW": {
        "dailyFile": "每日統計.csv",
        "channelFile": "通道統計.csv",
        "dailyCols": ["日期", "星期", "進入", "離開", "合計"],
        "channelCols": ["通道", "樓層", "類型", "進入", "離開", "合計", "淨流"],
        "weekdays": ["週一", "週二", "週三", "週四", "週五", "週六", "週日"],
        "typeLabels": {"lift": "電梯", "stairs": "樓梯", "entrance": "出入口/大堂"},
        "floorSep": "、",
        "errTooLong": "匯出範圍超出限制：最多僅能匯出 6 個月（{days} 天）內的資料",
        "errNoData": "所選範圍內沒有可匯出的資料",
        "errNotFound": "任務不存在或已過期（記憶體任務在服務重啟後遺失）",
        "errNotReady": "任務尚未完成，無法下載",
        "msgCreated": "匯出任務已於後台開始執行，可查詢 /api/v1/people-count/export/status/{task_id}",
    },
    "en": {
        "dailyFile": "daily_statistics.csv",
        "channelFile": "channel_statistics.csv",
        "dailyCols": ["Date", "Weekday", "Enter", "Exit", "Total"],
        "channelCols": ["Channel", "Floor", "Type", "Enter", "Exit", "Total", "Net"],
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "typeLabels": {"lift": "Lift", "stairs": "Stairs", "entrance": "Entrance / Lobby"},
        "floorSep": ", ",
        "errTooLong": "Export range exceeds the limit: at most 6 months ({days} days) of data can be exported",
        "errNoData": "No data to export in the selected range",
        "errNotFound": "Task not found or expired (in-memory tasks are lost after a service restart)",
        "errNotReady": "Task is not finished yet, cannot download",
        "msgCreated": "Export started in the background, check /api/v1/people-count/export/status/{task_id}",
    },
}

# 任務狀態階段：progress 值對應的處理階段
_STAGE_FETCH = "fetching"   # 查詢 / 聚合（0 ~ 60）
_STAGE_FILE = "writing"     # 寫入 ZIP（60 ~ 99）
_STAGE_DONE = "done"
_STAGE_FAILED = "failed"


def text(lang: str, key: str, **kwargs: Any) -> str:
    """取指定語言的文案；未知語言回退 zh-TW。"""
    table = _TEXT.get(lang) or _TEXT["zh-TW"]
    msg = table.get(key, "")
    return msg.format(**kwargs) if kwargs else msg


def normalize_lang(lang: str | None) -> str:
    """將語言參數正規化：未知或不合法一律回退 zh-TW。"""
    return lang if lang in SUPPORTED_LANGS else "zh-TW"


def get_task(task_id: str) -> dict[str, Any] | None:
    with _TASKS_LOCK:
        return dict(_TASKS[task_id]) if task_id in _TASKS else None


# ---------------------------------------------------------------------------
# CSV 產生（打包為 ZIP）
# ---------------------------------------------------------------------------
def _rows_to_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    """將表頭與資料行轉為 UTF-8 (含 BOM) CSV 位元組，方便 Excel 直接開啟中文。"""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def _daily_csv(daily: list[dict[str, Any]], lang: str) -> bytes:
    table = _TEXT.get(lang) or _TEXT["zh-TW"]
    weekdays: list[str] = table["weekdays"]
    rows = []
    for r in daily:
        rows.append(
            [
                r["date"],
                weekdays[int(r["weekday"])] if 0 <= int(r["weekday"]) < 7 else r["weekday"],
                int(r["enter"]),
                int(r["exit"]),
                int(r["total"]),
            ]
        )
    return _rows_to_csv(table["dailyCols"], rows)


def _channel_csv(channel: list[dict[str, Any]], lang: str) -> bytes:
    table = _TEXT.get(lang) or _TEXT["zh-TW"]
    type_labels: dict[str, str] = table["typeLabels"]
    floor_sep: str = table["floorSep"]
    rows = []
    for r in channel:
        ctype = r.get("type") or ""
        rows.append(
            [
                r["channel_name"],
                floor_sep.join(r.get("floors") or []),
                type_labels.get(ctype, ctype or r.get("type_label") or ""),
                int(r["enter"]),
                int(r["exit"]),
                int(r["total"]),
                int(r["enter"]) - int(r["exit"]),
            ]
        )
    return _rows_to_csv(table["channelCols"], rows)


def build_export_file(
    daily: list[dict[str, Any]],
    channel: list[dict[str, Any]],
    lang: str,
) -> str:
    """產生 ZIP（內含每日統計.csv / 通道統計.csv）並寫入暫存目錄，回傳絕對路徑。"""
    import zipfile

    table = _TEXT.get(lang) or _TEXT["zh-TW"]
    os.makedirs(_EXPORT_DIR, exist_ok=True)
    path = os.path.join(
        _EXPORT_DIR,
        f"people_count_export_{datetime.now().strftime('%Y%m%d%H%M%S%f')}.zip",
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(table["dailyFile"], _daily_csv(daily, lang))
        zf.writestr(table["channelFile"], _channel_csv(channel, lang))
    return path


def default_filename(date_from: DateType | None, date_to: DateType | None) -> str:
    frm = date_from.isoformat() if date_from else "all"
    to = date_to.isoformat() if date_to else "all"
    return f"people_count_{frm}_{to}.zip"


# ---------------------------------------------------------------------------
# 後台任務
# ---------------------------------------------------------------------------
def _update(task_id: str, **kwargs: Any) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        task.update(kwargs)


def create_export_task(
    *,
    settings: Any,
    date_from: DateType | None,
    date_to: DateType | None,
    hour_from: int | None,
    hour_to: int | None,
    channel_name: str | None,
    exclude_zero: bool,
    lang: str,
) -> dict[str, Any]:
    """建立後台匯出任務並立即啟動執行緒，回傳任務資訊。"""
    task_id = uuid.uuid4().hex
    task: dict[str, Any] = {
        "task_id": task_id,
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "lang": normalize_lang(lang),
        "status": _STAGE_FETCH,
        "progress": 0,
        "stage": _STAGE_FETCH,
        "filename": None,
        "error": None,
        "created_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
        "finished_at": None,
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = task

    thread = threading.Thread(
        target=_run_export_task,
        args=(task_id, settings, date_from, date_to, hour_from, hour_to,
              channel_name, exclude_zero, normalize_lang(lang)),
        daemon=True,
        name=f"people-count-export-{task_id}",
    )
    thread.start()
    return dict(task)


def _run_export_task(
    task_id: str,
    settings: Any,
    date_from: DateType | None,
    date_to: DateType | None,
    hour_from: int | None,
    hour_to: int | None,
    channel_name: str | None,
    exclude_zero: bool,
    lang: str,
) -> None:
    db = Database(settings)
    try:
        # 1. 查詢 + 聚合（進度 ~60%）
        _update(task_id, status=_STAGE_FETCH, stage=_STAGE_FETCH, progress=10)
        overview = db.people_count_overview(
            date_from=date_from,
            date_to=date_to,
            hour_from=hour_from,
            hour_to=hour_to,
            ip_address=None,
            channel_name=channel_name,
            exclude_zero=exclude_zero,
        )
        _update(task_id, progress=60)
        daily = overview.get("daily") or []
        channel = overview.get("channel") or []
        if not daily and not channel:
            _fail(task_id, text(lang, "errNoData"))
            return

        # 2. 寫入 Excel（~99%）
        _update(task_id, status=_STAGE_FILE, stage=_STAGE_FILE, progress=80)
        path = build_export_file(daily, channel, lang)
        _update(task_id, progress=99)

        with _TASKS_LOCK:
            task = _TASKS.get(task_id)
            if task is None:
                return
            task["status"] = _STAGE_DONE
            task["stage"] = _STAGE_DONE
            task["progress"] = 100
            task["filename"] = default_filename(date_from, date_to)
            task["file_path"] = path
            task["finished_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
    except Exception as exc:
        logger.exception("人流匯出任務 %s 失敗", task_id)
        _fail(task_id, str(exc))


def _fail(task_id: str, message: str) -> None:
    with _TASKS_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        task["status"] = _STAGE_FAILED
        task["stage"] = _STAGE_FAILED
        task["error"] = message
        task["finished_at"] = datetime.now().isoformat(sep=" ", timespec="seconds")
