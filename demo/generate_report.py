# -*- coding: utf-8 -*-
"""人流統計 DEMO 數據產生器

讀取 WingOnIOT.people_count_hourly 全部原始資料，於本機聚合出 demo/index.html
所需的 22 張圖表資料，寫入 demo/data.json。

執行方式（在工作目錄 demo/ 下）：
    ../.venv/Scripts/python.exe generate_report.py

連線設定優先讀取 ../mqttapi/.env 的 WINGON_DB_*，缺省 root/root@127.0.0.1:3306/WingOnIOT。

排除規則：若最新一天的 17 時及以後沒有任何人次，判定該天尚未完整，自動排除
（並在 meta 標註統計區間）。
"""

import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
import pymysql

HERE = Path(__file__).resolve().parent
load_dotenv(HERE.parent / "mqttapi" / ".env")

DB = {
    "host": os.getenv("WINGON_DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("WINGON_DB_PORT", "3306")),
    "user": os.getenv("WINGON_DB_USER", "root"),
    "password": os.getenv("WINGON_DB_PASSWORD", "root"),
    "database": os.getenv("WINGON_DB_NAME", "WingOnIOT"),
    "charset": "utf8mb4",
}

FLOORS = ["B1/F", "G/F", "1/F", "2/F", "3/F", "4/F", "5/F", "6/F"]
WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]  # 0=週一


def fetch_rows():
    conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **DB)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT date, hour, channel_name, enter_count, exit_count "
                "FROM people_count_hourly ORDER BY date, hour, channel_name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [
        {
            "date": r["date"],
            "hour": r["hour"],
            "channel_name": r["channel_name"],
            "enter": int(r["enter_count"] or 0),
            "exit": int(r["exit_count"] or 0),
        }
        for r in rows
    ]


def effective_range(rows):
    """取最後一個「17 時後仍有非零人次」的日期為截止日（排除未完整/異常日）。"""
    late_by_date = defaultdict(int)
    for r in rows:
        if r["hour"] >= 17:
            late_by_date[r["date"]] += r["enter"] + r["exit"]
    complete = [d for d, v in late_by_date.items() if v > 0]
    if not complete:
        return None, None
    date_to = max(complete)
    date_from = min(r["date"] for r in rows)
    return date_from, date_to


def channel_type(name):
    n = name.lower()
    if "lift" in n:
        return "lift"
    if "<" in name or ">" in name or "(up" in name.lower() or "(dw" in name.lower():
        return "stairs"
    return "entrance"


def floor_of(name):
    m = re.match(r"^(B1/F|G/F|[0-6]/F)", name)
    return m.group(1) if m else None


def floors_of(name):
    """通道關聯的所有樓層（電梯/出入口 = 1 層；樓梯 = 2 層）。"""
    if channel_type(name) == "stairs":
        fs = set()
        for frm, to in sankey_edges(name):
            fs.add(frm)
            fs.add(to)
        return fs
    f = floor_of(name)
    return {f} if f else set()


def sankey_edges(name):
    """由通道名稱解析樓層流向；僅樓梯類有方向。回傳 [(from, to)]。"""
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


def build_report(rows):
    d0, d1 = effective_range(rows)
    if d0 is None or d1 is None:
        raise RuntimeError("沒有可用的完整資料日")
    rows = [r for r in rows if d0 <= r["date"] <= d1]
    days = sorted({r["date"] for r in rows})
    n_days = len(days)
    is_weekend = lambda d: d.weekday() >= 5  # 5=六, 6=日

    # --- 基本總量 ---
    total_enter = sum(r["enter"] for r in rows)
    total_exit = sum(r["exit"] for r in rows)
    total_people = total_enter + total_exit

    # --- daily ---
    daily = []
    daily_by_date = {}
    for d in days:
        er = sum(r["enter"] for r in rows if r["date"] == d)
        xr = sum(r["exit"] for r in rows if r["date"] == d)
        daily_by_date[d] = {"enter": er, "exit": xr, "total": er + xr}
        daily.append(
            {
                "date": d.isoformat(),
                "weekday": d.weekday(),
                "enter": er,
                "exit": xr,
                "total": er + xr,
            }
        )

    # --- hour（每日平均） ---
    hour_by_day = defaultdict(lambda: {"enter": 0, "exit": 0})
    for r in rows:
        hour_by_day[(r["date"], r["hour"])]["enter"] += r["enter"]
        hour_by_day[(r["date"], r["hour"])]["exit"] += r["exit"]
    daily_hour = [
        {
            "date": d.isoformat(),
            "hour": h,
            "total": v["enter"] + v["exit"],
        }
        for (d, h), v in sorted(hour_by_day.items())
    ]
    hour = []
    for h in range(24):
        enter = sum(v["enter"] for (d, hh), v in hour_by_day.items() if hh == h)
        exit_ = sum(v["exit"] for (d, hh), v in hour_by_day.items() if hh == h)
        hour.append(
            {
                "hour": h,
                "enter": round(enter / n_days, 1),
                "exit": round(exit_ / n_days, 1),
                "total": round((enter + exit_) / n_days, 1),
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
    ]

    # --- weekday × hour（每日平均總人次） ---
    wh_accum = defaultdict(lambda: defaultdict(float))
    for r in rows:
        wh_accum[r["date"].weekday()][r["hour"]] += r["enter"] + r["exit"]
    weekday_hour = []
    for w in range(7):
        for h in range(24):
            weekday_hour.append(
                {
                    "weekday": w,
                    "hour": h,
                    "total": round(wh_accum[w][h] / weekday_accum[w]["days"], 1),
                }
            )

    # --- channel ---
    ch_accum = defaultdict(lambda: {"enter": 0, "exit": 0})
    for r in rows:
        ch_accum[r["channel_name"]]["enter"] += r["enter"]
        ch_accum[r["channel_name"]]["exit"] += r["exit"]
    type_labels = {"lift": "電梯", "stairs": "樓梯", "entrance": "出入口/大堂"}
    channel = [
        {
            "channel_name": name,
            "enter": v["enter"],
            "exit": v["exit"],
            "total": v["enter"] + v["exit"],
            "type": channel_type(name),
            "type_label": type_labels.get(channel_type(name), channel_type(name)),
            "floors": sorted(floors_of(name)),
        }
        for name, v in sorted(
            ch_accum.items(), key=lambda kv: -(kv[1]["enter"] + kv[1]["exit"])
        )
    ]

    # --- channel × hour（總人次） ---
    ch_h_accum = defaultdict(lambda: defaultdict(int))
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
    floor = [
        {
            "floor": f,
            "enter": floor_accum[f]["enter"],
            "exit": floor_accum[f]["exit"],
            "total": floor_accum[f]["enter"] + floor_accum[f]["exit"],
        }
        for f in FLOORS
    ]

    # --- byFloor（每層完整視角：含樓梯/電梯/出入口全部通道） ---
    floors = []
    for f in FLOORS:
        chans = [name for name in ch_accum if f in floors_of(name)]
        chans_sorted = sorted(chans, key=lambda n: -(ch_accum[n]["enter"] + ch_accum[n]["exit"]))
        f_enter = sum(ch_accum[n]["enter"] for n in chans)
        f_exit = sum(ch_accum[n]["exit"] for n in chans)
        hour24 = [0] * 24
        daily_by_floor = {d: 0 for d in days}
        for r in rows:
            if f in floors_of(r["channel_name"]):
                hour24[r["hour"]] += r["enter"] + r["exit"]
                daily_by_floor[r["date"]] += r["enter"] + r["exit"]
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
                        "type_label": type_labels.get(channel_type(n), channel_type(n)),
                    }
                    for n in chans_sorted
                ],
                "hour": hour24,
                "daily": [
                    {"date": d.isoformat(), "total": daily_by_floor[d]} for d in days
                ],
            }
        )

    # --- channel type ---
    ct_accum = defaultdict(lambda: {"enter": 0, "exit": 0, "count": 0})
    for name, v in ch_accum.items():
        t = channel_type(name)
        ct_accum[t]["enter"] += v["enter"]
        ct_accum[t]["exit"] += v["exit"]
        ct_accum[t]["count"] += 1
    channel_type_summary = [
        {
            "type": t,
            "label": type_labels.get(t, t),
            "enter": v["enter"],
            "exit": v["exit"],
            "total": v["enter"] + v["exit"],
            "count": v["count"],
        }
        for t, v in sorted(ct_accum.items(), key=lambda kv: -(kv[1]["enter"] + kv[1]["exit"]))
    ]

    # --- sankey（樓梯流向） ---
    floor_order = {f: i for i, f in enumerate(FLOORS)}
    sk_accum = defaultdict(int)
    for name, v in ch_accum.items():
        if channel_type(name) != "stairs":
            continue
        edges = sankey_edges(name)
        total = v["enter"] + v["exit"]
        share = total / len(edges) if edges else 0
        for (frm, to) in edges:
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

    # --- 異常日（與同星期平均偏差%） ---
    wd_avg = {a["weekday"]: a["total"] for a in weekday}
    anomalies = []
    for d in days:
        w = d.weekday()
        avg = wd_avg[w]
        dev = (daily_by_date[d]["total"] - avg) / avg * 100 if avg else 0
        anomalies.append(
            {
                "date": d.isoformat(),
                "weekday": w,
                "total": daily_by_date[d]["total"],
                "avg": round(avg, 1),
                "dev_pct": round(dev, 1),
                "flag": abs(dev) >= 25,
            }
        )

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
    busiest_channel = channel[0]
    busiest_floor = max(floor, key=lambda x: x["total"])

    meta = {
        "date_from": d0.isoformat(),
        "date_to": d1.isoformat(),
        "days": n_days,
        "total_people": total_people,
        "total_enter": total_enter,
        "total_exit": total_exit,
        "daily_avg": round(total_people / n_days, 1),
        "max_day": {"date": max_day["date"], "total": max_day["total"]},
        "peak_hour": {"hour": peak_hour["hour"], "avg": peak_hour["total"]},
        "weekend_ratio": weekend_ratio,
        "busiest_channel": {
            "name": busiest_channel["channel_name"],
            "total": busiest_channel["total"],
        },
        "busiest_floor": {"floor": busiest_floor["floor"], "total": busiest_floor["total"]},
        "generated_at": datetime.now().isoformat(sep=" ", timespec="seconds"),
    }

    return {
        "meta": meta,
        "daily": daily,
        "dailyHour": daily_hour,
        "hour": hour,
        "weekday": weekday,
        "weekdayHour": weekday_hour,
        "channel": channel,
        "channelHour": channel_hour,
        "floor": floor,
        "floors": floors,
        "channelType": channel_type_summary,
        "sankey": sankey,
        "anomalies": anomalies,
    }


def main():
    rows = fetch_rows()
    if not rows:
        print("ERROR: people_count_hourly 無資料")
        return 1
    report = build_report(rows)
    out = HERE / "data.json"
    out.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = report["meta"]
    print(f"OK: 統計區間 {meta['date_from']} ~ {meta['date_to']}（{meta['days']} 天）")
    print(f"    總人次 {meta['total_people']:,}，已寫入 {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())