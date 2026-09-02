"""CCTV 人流統計資料採集服務。

從 Milesight 攝影機 ISAPI 拉取逐小時進出人數，UPSERT 到 people_count_hourly 表。

- 攝影機列表：硬編碼於 CCTV_CAMERAS（不改動）
- 帳號密碼：來自 settings.cctv_username / settings.cctv_password（.env 的 CCTV_USERNAME/CCTV_PASSWORD）
- 主鍵：雪花 ID（app.snowflake.next_id）
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any, Callable

import requests
import xmltodict
from requests.auth import HTTPDigestAuth

from app.config import Settings
from app.db import Database
from app.snowflake import next_id

logger = logging.getLogger(__name__)

# 攝影機列表：(ip_address, channel_name)
CCTV_CAMERAS: list[dict[str, str]] = [
    {"ip_address": "10.98.127.50", "channel_name": "1/F Lift"},
    {"ip_address": "10.98.127.51", "channel_name": "1/F <- G/F (up)"},
    {"ip_address": "10.98.127.52", "channel_name": "1/F -> G/F (dw)"},
    {"ip_address": "10.98.127.29", "channel_name": "2/F <- 1/F (up)"},
    {"ip_address": "10.98.127.38", "channel_name": "2/F 大廈大堂"},
    {"ip_address": "10.98.127.39", "channel_name": "2/F Lift"},
    {"ip_address": "10.98.127.40", "channel_name": "2/F <-> 1/F (up/dw)"},
    {"ip_address": "10.98.127.41", "channel_name": "2/F -> 1/F (dw)"},
    {"ip_address": "10.98.127.37", "channel_name": "3/F Lift"},
    {"ip_address": "10.98.127.35", "channel_name": "3/F -> 2/F (dw)"},
    {"ip_address": "10.98.127.36", "channel_name": "3/F <- 2/F (up)"},
    {"ip_address": "10.98.127.53", "channel_name": "4/F Lift"},
    {"ip_address": "10.98.127.54", "channel_name": "4/F → 5/F (up)"},
    {"ip_address": "10.98.127.60", "channel_name": "4/F → 3/F (dw)"},
    {"ip_address": "10.98.127.32", "channel_name": "5/F Lift"},
    {"ip_address": "10.98.127.33", "channel_name": "5/F <- 4/F (up)"},
    {"ip_address": "10.98.127.34", "channel_name": "5/F -> 4/F (dw)"},
    {"ip_address": "10.98.127.26", "channel_name": "6/F <- 5/F (up)"},
    {"ip_address": "10.98.127.28", "channel_name": "6/F Lift"},
    {"ip_address": "10.98.127.27", "channel_name": "6/F -> 5/F (dw)"},
    {"ip_address": "10.98.127.30", "channel_name": "B1/F <- G/F (dw)"},
    {"ip_address": "10.98.127.31", "channel_name": "B1/F Lift"},
    {"ip_address": "10.98.127.42", "channel_name": "G/F 吳松街出口 (CS)"},
    {"ip_address": "10.98.127.43", "channel_name": "G/F Lift"},
    {"ip_address": "10.98.127.44", "channel_name": "G/F 正門出口 01"},
    {"ip_address": "10.98.127.45", "channel_name": "G/F 職員出口"},
    {"ip_address": "10.98.127.46", "channel_name": "G/F <- B1/F (up)"},
    {"ip_address": "10.98.127.47", "channel_name": "G/F 輪椅出口"},
    {"ip_address": "10.98.127.48", "channel_name": "G/F 正門出口 02"},
    {"ip_address": "10.98.127.49", "channel_name": "G/F 近隧道出口"},
]

_COUNTING_PATH = "System/Video/inputs/channels/1/counting/search"

# 參數設置 key
CONFIG_ENABLED = "cctv.sync.enabled"


def _build_session(settings: Settings) -> requests.Session:
    session = requests.Session()
    session.auth = HTTPDigestAuth(settings.cctv_username, settings.cctv_password)
    return session


def fetch_camera_day(
    session: requests.Session,
    ip_address: str,
    channel_name: str,
    target_date: date,
) -> dict[str, Any] | None:
    """拉取單台攝影機某天的逐小時進出人數。

    回傳 {"enter_list": [24], "exit_list": [24], "enter_total": int, "exit_total": int}。
    連接失敗或格式異常回傳 None。
    """
    url = f"http://{ip_address}/ISAPI/{_COUNTING_PATH}"
    headers = {"Content-Type": "application/xml"}
    start_time = f"{target_date}T00:00:00"
    end_time = f"{target_date}T23:59:59"
    payload = f"""<?xml version="1.0" encoding="UTF-8"?>
    <CountingStatisticsDescription>
      <statisticType>enternum</statisticType>
      <reportType>daily</reportType>
      <timeSpanList>
        <timeSpan>
          <startTime>{start_time}</startTime>
          <endTime>{end_time}</endTime>
        </timeSpan>
      </timeSpanList>
      <child>false</child>
      <regionID/>
    </CountingStatisticsDescription>"""

    try:
        response = session.post(url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        response_dict = xmltodict.parse(response.text)

        result = response_dict.get("CountingStatisticsResult")
        if not result:
            logger.warning("[%s] CountingStatisticsResult not found", channel_name)
            return None

        match_list = result.get("matchList") or {}
        match_element = match_list.get("matchElement")
        if not match_element:
            logger.warning("[%s] matchElement not found", channel_name)
            return None

        if isinstance(match_element, dict):
            match_element = [match_element]

        enter_list: list[int] = []
        exit_list: list[int] = []
        for el in match_element:
            enter_list.append(int(el.get("enterCount") or 0))
            exit_list.append(int(el.get("exitCount") or 0))

        # 確保 24 小時，不足補 0（按順序對應 0~23 時）
        while len(enter_list) < 24:
            enter_list.append(0)
        while len(exit_list) < 24:
            exit_list.append(0)

        return {
            "enter_list": enter_list[:24],
            "exit_list": exit_list[:24],
            "enter_total": sum(enter_list),
            "exit_total": sum(exit_list),
        }
    except requests.exceptions.RequestException as exc:
        logger.warning("[%s] (%s) request error: %s", channel_name, ip_address, exc)
        return None
    except Exception as exc:  # XML 解析等
        logger.warning("[%s] (%s) parse error: %s", channel_name, ip_address, exc)
        return None


def sync_date(
    db: Database,
    settings: Settings,
    target_date: date,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """同步某天的完整 24 小時資料到 people_count_hourly（UPSERT）。

    回傳統計：{date, cameras, rows, failed}。
    """
    own_session = session is None
    if own_session:
        session = _build_session(settings)

    rows = 0
    failed: list[str] = []
    try:
        for camera in CCTV_CAMERAS:
            ip = camera["ip_address"]
            name = camera["channel_name"]
            data = fetch_camera_day(session, ip, name, target_date)
            if data is None:
                failed.append(name)
                data = {
                    "enter_list": [0] * 24,
                    "exit_list": [0] * 24,
                    "enter_total": 0,
                    "exit_total": 0,
                }
            for hour in range(24):
                db.upsert_people_count_hourly(
                    snowflake_id=next_id(),
                    date=target_date,
                    hour=hour,
                    ip_address=ip,
                    channel_name=name,
                    enter_count=data["enter_list"][hour],
                    exit_count=data["exit_list"][hour],
                )
                rows += 1
        logger.info(
            "CCTV sync %s: %d cameras, %d rows, %d failed",
            target_date, len(CCTV_CAMERAS), rows, len(failed),
        )
        return {
            "date": str(target_date),
            "cameras": len(CCTV_CAMERAS),
            "rows": rows,
            "failed": failed,
        }
    finally:
        if own_session:
            session.close()


def sync_today(db: Database, settings: Settings) -> dict[str, Any]:
    """同步今天的資料（用於啟動立即執行與每小時觸發）。"""
    return sync_date(db, settings, date.today())


def sync_yesterday(db: Database, settings: Settings) -> dict[str, Any]:
    """同步昨天完整 24 小時資料（每天 00:05 觸發）。"""
    return sync_date(db, settings, date.today() - timedelta(days=1))


def backfill_current_month(
    db: Database, settings: Settings
) -> dict[str, Any]:
    """檢查當月是否有日期資料缺失，並回填缺失日期的完整 24 小時資料。

    缺失定義：people_count_hourly 中沒有該日期（date）的任何記錄。
    """
    today = date.today()
    existing = db.get_existing_people_count_dates(today.year, today.month)

    missing: list[date] = []
    day = today.replace(day=1)
    while day <= today:
        if day not in existing:
            missing.append(day)
        day += timedelta(days=1)

    results: list[dict[str, Any]] = []
    for d in missing:
        logger.info("Backfill missing date %s", d)
        results.append(sync_date(db, settings, d))

    return {
        "month": f"{today.year}-{today.month:02d}",
        "missing": [str(d) for d in missing],
        "synced": results,
    }


def sync_date_range(
    db: Database,
    settings: Settings,
    date_from: date,
    date_to: date,
    session: requests.Session | None = None,
    on_progress: Callable[[int, int, date], None] | None = None,
) -> dict[str, Any]:
    """回填 [date_from, date_to] 範圍內所有缺失日期的完整 24 小時資料。

    缺失定義：people_count_hourly 中沒有該日期（date）的任何記錄。
    已有資料的日期會自動跳過（可用於中斷後重跑）。

    on_progress(completed, total, current) 在每個日期完成時回調，
    用於後台任務更新進度（completed=已同步天數, total=待同步天數, current=當前日期）。

    回傳：{date_from, date_to, missing: [...], synced: [...]}
    """
    own_session = session is None
    if own_session:
        session = _build_session(settings)

    existing = db.get_existing_people_count_dates_range(date_from, date_to)

    missing: list[date] = []
    day = date_from
    while day <= date_to:
        if day not in existing:
            missing.append(day)
        day += timedelta(days=1)

    total = len(missing)
    results: list[dict[str, Any]] = []
    try:
        for idx, d in enumerate(missing, start=1):
            logger.info("Range backfill missing date %s", d)
            results.append(sync_date(db, settings, d, session=session))
            if on_progress is not None:
                on_progress(idx, total, d)
    finally:
        if own_session:
            session.close()

    return {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "missing": [str(d) for d in missing],
        "synced": results,
    }
