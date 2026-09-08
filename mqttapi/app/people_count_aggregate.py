"""人流時數統計：基於 people_count_hourly 的聚合計算。

將 generate_report.py 的核心聚合邏輯搬到後端，供「視圖 / 樓層 / 資料」頁面使用。
聚合在 Python 側完成（資料量小），回傳 demo/data.json 同構的結構化 JSON。
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

FLOORS = ["B1/F", "G/F", "1/F", "2/F", "3/F", "4/F", "5/F", "6/F"]
WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]  # 0=週一

TYPE_LABELS = {"lift": "電梯", "stairs": "樓梯", "entrance": "出入口/大堂"}


def channel_type(name: str) -> str:
    n = name.lower()
    if "lift" in n:
        return "lift"
    if "<" in name or ">" in name or "(up" in n or "(dw" in n or "→" in name or "←" in name:
        return "stairs"
    return "entrance"


def floor_of(name: str) -> str | None:
    m = re.match(r"^(B1/F|G/F|[0-6]/F)", name or "")
    return m.group(1) if m else None


def floors_of(name: str) -> set[str]:
    """通道關聯的所有樓層（電梯/出入口 = 1 層；樓梯 = 2 層）。"""
    if channel_type(name) == "stairs":
        fs: set[str] = set()
        for frm, to in sankey_edges(name):
            fs.add(frm)
            fs.add(to)
        return fs
    f = floor_of(name)
    return {f} if f else set()


def sankey_edges(name: str) -> list[tuple[str, str]]:
    """由通道名稱解析樓層流向；僅樓梯類有方向。回傳 [(from, to)]。"""
    name = name.replace("→", "->").replace("←", "<-")
    m = re.match(r"^([A-Z0-9]+/F)\s*<->\s*([A-Z0-9]+/F)", name)
    if m:
        return [(m.group(2), m.group(1)), (m.group(1), m.group(2))]
    m = re.match(r"^([A-Z0-9]+/F)\s*<-\s*([A-Z0-9]+/F)", name)
    if m:
        return [(m.group(2), m.group(1))]
    m = re.match(r"^([A-Z0-9]+/F)\s*->\s*([A-Z0-9]+/F)", name)
    if m:
        return [(m.group(1), m.group(2))]
    return []


def _within_range(
    row_date: date, row_hour: int,
    date_from: date | None, date_to: date | None,
    hour_from: int | None, hour_to: int | None,
) -> bool:
    """連續日期時間範圍判斷：與 db.py SQL 過濾語義一致。

    - 同日：該日且 hour ∈ [hour_from, hour_to]
    - 跨多日：首日 hour>=hour_from、末日 hour<=hour_to、中間日全天
    """
    if date_from is None and date_to is None:
        return True
    if date_from is not None and date_to is not None and date_from != date_to:
        if row_date > date_from and row_date < date_to:
            return True
        if row_date == date_from:
            if hour_from is not None and row_hour < hour_from:
                return False
            return True
        if row_date == date_to:
            if hour_to is not None and row_hour > hour_to:
                return False
            return True
        return False
    # 同一天或只有一端
    if date_from is not None and row_date < date_from:
        return False
    if date_to is not None and row_date > date_to:
        return False
    if hour_from is not None and row_hour < hour_from:
        return False
    if hour_to is not None and row_hour > hour_to:
        return False
    return True


def filter_rows(
    rows: list[dict[str, Any]],
    *,
    date_from: date | None,
    date_to: date | None,
    hour_from: int | None,
    hour_to: int | None,
    channel_name: str | None,
    ip_address: str | None,
    exclude_zero: bool,
) -> list[dict[str, Any]]:
    """依查詢條件過濾原始明細。"""
    out: list[dict[str, Any]] = []
    for r in rows:
        if not _within_range(r["date"], r["hour"], date_from, date_to, hour_from, hour_to):
            continue
        if channel_name and r["channel_name"] != channel_name:
            continue
        if ip_address and r["ip_address"] != ip_address:
            continue
        if exclude_zero and r["enter"] == 0 and r["exit"] == 0:
            continue
        out.append(r)
    return out


def aggregate(
    rows: list[dict[str, Any]],
    *,
    date_from: date | None,
    date_to: date | None,
    hour_from: int | None,
    hour_to: int | None,
    channel_name: str | None,
    ip_address: str | None,
    exclude_zero: bool,
) -> dict[str, Any]:
    """聚合計算，回傳與 demo/data.json 同構的結構。"""
    rows = filter_rows(
        rows,
        date_from=date_from,
        date_to=date_to,
        hour_from=hour_from,
        hour_to=hour_to,
        channel_name=channel_name,
        ip_address=ip_address,
        exclude_zero=exclude_zero,
    )
    if not rows:
        return empty_report()

    days = sorted({r["date"] for r in rows})
    n_days = len(days)
    is_weekend = lambda d: d.weekday() >= 5  # noqa: E731

    total_enter = sum(r["enter"] for r in rows)
    total_exit = sum(r["exit"] for r in rows)
    total_people = total_enter + total_exit

    # --- daily ---
    daily_by_date: dict[date, dict[str, Any]] = {}
    for d in days:
        er = sum(r["enter"] for r in rows if r["date"] == d)
        xr = sum(r["exit"] for r in rows if r["date"] == d)
        daily_by_date[d] = {"enter": er, "exit": xr, "total": er + xr}
    # 以數據實際覆蓋範圍生成連續日期；缺失日補 0，讓趨勢圖保持連續（避免跳點）
    cal_days: list[date] = []
    if days:
        cursor = days[0]
        while cursor <= days[-1]:
            cal_days.append(cursor)
            cursor += timedelta(days=1)
    daily = []
    for d in cal_days:
        rec = daily_by_date.get(d)
        if rec is None:
            rec = {"enter": 0, "exit": 0, "total": 0}
        # 隱藏零流量記錄：整日無進出的日期不輸出
        if exclude_zero and rec["enter"] == 0 and rec["exit"] == 0:
            continue
        daily.append(
            {
                "date": d.isoformat(),
                "weekday": d.weekday(),
                "enter": rec["enter"],
                "exit": rec["exit"],
                "total": rec["enter"] + rec["exit"],
            }
        )

    # --- hour（各時段合計） ---
    hour_by_day: dict[tuple[date, int], dict[str, int]] = defaultdict(lambda: {"enter": 0, "exit": 0})
    for r in rows:
        hour_by_day[(r["date"], r["hour"])]["enter"] += r["enter"]
        hour_by_day[(r["date"], r["hour"])]["exit"] += r["exit"]
    hour = []
    for h in range(24):
        enter = sum(v["enter"] for (d, hh), v in hour_by_day.items() if hh == h)
        exit_ = sum(v["exit"] for (d, hh), v in hour_by_day.items() if hh == h)
        # 隱藏零流量記錄：進出皆為 0 的時段不輸出（避免全 0 柱子仍顯示）
        if exclude_zero and enter == 0 and exit_ == 0:
            continue
        hour.append(
            {
                "hour": h,
                "enter": enter,
                "exit": exit_,
                "total": enter + exit_,
            }
        )

    # --- weekday（每日平均） ---
    weekday_accum = {w: {"enter": 0.0, "exit": 0.0, "days": 0} for w in range(7)}
    for d in days:
        w = d.weekday()
        weekday_accum[w]["enter"] += daily_by_date[d]["enter"]
        weekday_accum[w]["exit"] += daily_by_date[d]["exit"]
        weekday_accum[w]["days"] += 1
    weekday = [
        {
            "weekday": w,
            "name": WEEKDAY_NAMES[w],
            "enter": round(a["enter"] / a["days"], 1),
            "exit": round(a["exit"] / a["days"], 1),
            "total": round((a["enter"] + a["exit"]) / a["days"], 1),
            "days": a["days"],
        }
        for w, a in sorted(weekday_accum.items())
        if a["days"] > 0
    ]

    # --- weekday × hour（每日平均總人次） ---
    wh_accum: dict[int, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for r in rows:
        wh_accum[r["date"].weekday()][r["hour"]] += r["enter"] + r["exit"]
    weekday_hour = [
        {
            "weekday": w,
            "hour": h,
            "total": round(wh_accum[w][h] / weekday_accum[w]["days"], 1),
        }
        for w in range(7)
        for h in range(24)
        if weekday_accum[w]["days"] > 0
        and not (exclude_zero and wh_accum[w][h] == 0)
    ]

    # --- channel ---
    ch_accum: dict[str, dict[str, int]] = defaultdict(lambda: {"enter": 0, "exit": 0})
    for r in rows:
        ch_accum[r["channel_name"]]["enter"] += r["enter"]
        ch_accum[r["channel_name"]]["exit"] += r["exit"]
    channel = [
        {
            "channel_name": name,
            "enter": v["enter"],
            "exit": v["exit"],
            "total": v["enter"] + v["exit"],
            "type": channel_type(name),
            "type_label": TYPE_LABELS.get(channel_type(name), channel_type(name)),
            "floors": sorted(floors_of(name)),
        }
        for name, v in sorted(ch_accum.items(), key=lambda kv: -(kv[1]["enter"] + kv[1]["exit"]))
    ]

    # --- channel × hour（總人次） ---
    ch_h_accum: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        ch_h_accum[r["channel_name"]][r["hour"]] += r["enter"] + r["exit"]
    channel_hour = [
        {"channel_name": name, "hour": h, "total": v}
        for name, hh in ch_h_accum.items()
        for h, v in sorted(hh.items())
    ]

    # --- floor（僅單樓層通道：Lift / 出入口 / 大堂） ---
    floor_accum = {f: {"enter": 0, "exit": 0} for f in FLOORS}
    for name, v in ch_accum.items():
        f = floor_of(name)
        if f and channel_type(name) != "stairs":
            floor_accum[f]["enter"] += v["enter"]
            floor_accum[f]["exit"] += v["exit"]
    floor = []
    for f in FLOORS:
        er = floor_accum[f]["enter"]
        xr = floor_accum[f]["exit"]
        # 隱藏零流量記錄：整層無進出則不輸出
        if exclude_zero and er == 0 and xr == 0:
            continue
        floor.append(
            {
                "floor": f,
                "enter": er,
                "exit": xr,
                "total": er + xr,
            }
        )

    # --- floors（每層完整視角：含樓梯/電梯/出入口全部通道） ---
    floors = []
    for f in FLOORS:
        chans = [name for name in ch_accum if f in floors_of(name)]
        chans_sorted = sorted(chans, key=lambda n: -(ch_accum[n]["enter"] + ch_accum[n]["exit"]))
        f_enter = sum(ch_accum[n]["enter"] for n in chans)
        f_exit = sum(ch_accum[n]["exit"] for n in chans)
        hour24_enter = [0] * 24
        hour24_exit = [0] * 24
        daily_by_floor = {d: 0 for d in days}
        for r in rows:
            if f in floors_of(r["channel_name"]):
                hour24_enter[r["hour"]] += r["enter"]
                hour24_exit[r["hour"]] += r["exit"]
                daily_by_floor[r["date"]] += r["enter"] + r["exit"]
        # 隱藏零流量記錄：整層無進出則不輸出（該層不會出現在樓層按鈕/詳情）
        if exclude_zero and f_enter == 0 and f_exit == 0:
            continue
        floors.append(
            {
                "floor": f,
                "enter": f_enter,
                "exit": f_exit,
                "total": f_enter + f_exit,
                "channels": [
                    {
                        "channel_name": n,
                        "enter": ch_accum[n]["enter"],
                        "exit": ch_accum[n]["exit"],
                        "total": ch_accum[n]["enter"] + ch_accum[n]["exit"],
                        "type": channel_type(n),
                        "type_label": TYPE_LABELS.get(channel_type(n), channel_type(n)),
                    }
                    for n in chans_sorted
                ],
                "hour_enter": hour24_enter,
                "hour_exit": hour24_exit,
                "daily": [
                    {"date": d.isoformat(), "total": daily_by_floor[d]} for d in days
                ],
            }
        )

    # --- channel type ---
    ct_accum: dict[str, dict[str, int]] = defaultdict(lambda: {"enter": 0, "exit": 0, "count": 0})
    for name, v in ch_accum.items():
        t = channel_type(name)
        ct_accum[t]["enter"] += v["enter"]
        ct_accum[t]["exit"] += v["exit"]
        ct_accum[t]["count"] += 1
    channel_type_summary = [
        {
            "type": t,
            "label": TYPE_LABELS.get(t, t),
            "enter": v["enter"],
            "exit": v["exit"],
            "total": v["enter"] + v["exit"],
            "count": v["count"],
        }
        for t, v in sorted(ct_accum.items(), key=lambda kv: -(kv[1]["enter"] + kv[1]["exit"]))
    ]

    # --- sankey（樓梯流向） ---
    floor_order = {f: i for i, f in enumerate(FLOORS)}
    sk_accum: dict[tuple[str, str], int] = defaultdict(int)
    for name, v in ch_accum.items():
        if channel_type(name) != "stairs":
            continue
        edges = sankey_edges(name)
        total = v["enter"] + v["exit"]
        share = total / len(edges) if edges else 0
        for frm, to in edges:
            sk_accum[(frm, to)] += share
    sankey = [
        {
            "from": frm,
            "to": to,
            "direction": "up" if floor_order[to] > floor_order[frm] else "down",
            "value": round(val, 1),
        }
        for (frm, to), val in sorted(sk_accum.items(), key=lambda kv: -kv[1])
    ]

    # --- KPI ---
    weekend_tot = sum(daily_by_date[d]["total"] for d in days if is_weekend(d))
    weekday_tot = sum(daily_by_date[d]["total"] for d in days if not is_weekend(d))
    weekend_days = sum(1 for d in days if is_weekend(d))
    weekday_days = n_days - weekend_days
    weekend_ratio = (
        round((weekend_tot / weekend_days) / (weekday_tot / weekday_days), 2)
        if weekday_days and weekend_days
        else None
    )
    max_day = max(daily, key=lambda x: x["total"])
    peak_hour = max(hour, key=lambda x: x["total"])
    busiest_channel = channel[0] if channel else None
    busiest_floor = max(floor, key=lambda x: x["total"]) if floor else None

    meta = {
        "date_from": min(r["date"] for r in rows).isoformat(),
        "date_to": max(r["date"] for r in rows).isoformat(),
        "days": n_days,
        "total_people": total_people,
        "total_enter": total_enter,
        "total_exit": total_exit,
        "daily_avg": round(total_people / n_days, 1),
        "max_day": {"date": max_day["date"], "total": max_day["total"]},
        "peak_hour": {"hour": peak_hour["hour"], "total": peak_hour["total"]},
        "weekend_ratio": weekend_ratio,
        "busiest_channel": {
            "name": busiest_channel["channel_name"],
            "total": busiest_channel["total"],
        }
        if busiest_channel
        else None,
        "busiest_floor": {"floor": busiest_floor["floor"], "total": busiest_floor["total"]}
        if busiest_floor
        else None,
    }

    return {
        "meta": meta,
        "daily": daily,
        "hour": hour,
        "weekday": weekday,
        "weekdayHour": weekday_hour,
        "channel": channel,
        "channelHour": channel_hour,
        "floor": floor,
        "floors": floors,
        "channelType": channel_type_summary,
        "sankey": sankey,
    }


def empty_report() -> dict[str, Any]:
    """無資料時的結構化空報告。"""
    return {
        "meta": {
            "date_from": None,
            "date_to": None,
            "days": 0,
            "total_people": 0,
            "total_enter": 0,
            "total_exit": 0,
            "daily_avg": 0,
            "max_day": None,
            "peak_hour": None,
            "weekend_ratio": None,
            "busiest_channel": None,
            "busiest_floor": None,
        },
        "daily": [],
        "hour": [],
        "weekday": [],
        "weekdayHour": [],
        "channel": [],
        "channelHour": [],
        "floor": [],
        "floors": [],
        "channelType": [],
        "sankey": [],
    }