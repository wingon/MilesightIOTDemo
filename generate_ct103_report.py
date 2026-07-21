# -*- coding: utf-8 -*-
"""Parse CT103 UG65 datastream CSV and emit SingleElectric HTML reports (zh-Hant + en)."""
import re
import json
from pathlib import Path
from collections import Counter
from statistics import mean, median, pstdev
from datetime import datetime

CSV_PATH = Path(
    r"c:\RossData\code\woac\MilesightAnalysis\files\UG65_20260715-1555_60.0.0.49_datastream.csv"
)
OUT_ZH = Path(
    r"c:\RossData\code\woac\MilesightAnalysis\SingleElectric_UG65_CT103_470M_report.html"
)
OUT_EN = Path(
    r"c:\RossData\code\woac\MilesightAnalysis\SingleElectric_UG65_CT103_470M_report_en.html"
)

TEMP_STATUS = {
    "zh": {0: "正常", 1: "超出量程", 2: "溫度感測器未安裝"},
    "en": {0: "Normal", 1: "Over range", 2: "Temperature sensor not installed"},
}


def _to_float(s):
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_rssi_snr(field: str, chunk: str, snr_detail, rssi_detail):
    field = field.strip()
    if "/" in field:
        a, b = field.split("/", 1)
        rssi, snr = _to_float(a), _to_float(b)
        if rssi is not None or snr is not None:
            return rssi, snr
    rm = rssi_detail.search(chunk)
    sm = snr_detail.search(chunk)
    return _to_float(rm.group(1) if rm else None), _to_float(sm.group(1) if sm else None)


def fmt_time(iso: str) -> str:
    return iso.replace("T", " ")[:19]


def parse_dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "avg": round(mean(vals), 3),
        "med": round(median(vals), 3),
        "std": round(pstdev(vals), 3) if len(vals) > 1 else 0,
    }


def parse_csv(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    body = "\n".join(text.splitlines()[1:])
    row_pat = re.compile(
        r"^([0-9A-Fa-f]{16}),([0-9A-Fa-f]{16}),(\d+),(SF\d+BW\d+),\s*"
        r"([^,]*),(\d+),(\d+),(\w+),(20\d{2}-\d{2}-\d{2}T[^,]+),",
        re.M,
    )
    json_pat = re.compile(r"JSON:\s*(\{.*?\})", re.DOTALL)
    snr_detail = re.compile(r"^SNR:\s*([-\d.]+)", re.M)
    rssi_detail = re.compile(r"^RSSI:\s*([-\d.]+)", re.M)

    starts = list(row_pat.finditer(body))
    records = []
    for i, m in enumerate(starts):
        start = m.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
        chunk = body[start:end]
        g = m.groups()
        rssi, snr = parse_rssi_snr(g[4], chunk, snr_detail, rssi_detail)
        payload = {}
        jm = json_pat.search(chunk)
        if jm:
            try:
                payload = json.loads(jm.group(1).replace('""', '"'))
            except json.JSONDecodeError:
                payload = {}
        records.append(
            {
                "time": g[8],
                "device": g[0],
                "gateway": g[1],
                "freq_mhz": round(int(g[2]) / 1e6, 1),
                "dr": g[3],
                "rssi": rssi,
                "snr": snr,
                "size": int(g[5]),
                "fcnt": int(g[6]),
                "type": g[7],
                "payload": payload,
            }
        )

    ct103_devices = {r["device"] for r in records if "current" in r["payload"]}
    if not ct103_devices:
        raise SystemExit("No CT103 current sensor packets found in CSV")
    target_device = max(
        ct103_devices,
        key=lambda d: sum(1 for r in records if r["device"] == d and "current" in r["payload"]),
    )
    records = [r for r in records if r["device"] == target_device]
    records.sort(key=lambda r: r["time"])
    sensors = [r for r in records if "current" in r["payload"]]
    info_pkts = [r for r in records if "firmware_version" in r["payload"] or "sn" in r["payload"]]

    has_temp = [r for r in sensors if "temperature" in r["payload"]]
    status_2 = [r for r in sensors if r["payload"].get("temperature_sensor_status") == 2]

    duration_h = 0
    interval_med = 0
    if len(sensors) >= 2:
        dts = [parse_dt(r["time"]) for r in sensors]
        duration_h = round((dts[-1] - dts[0]).total_seconds() / 3600, 2)
        diffs = [(dts[i] - dts[i - 1]).total_seconds() for i in range(1, len(dts))]
        interval_med = int(median(diffs))

    zero_current = sum(1 for r in sensors if r["payload"].get("current", 0) == 0)
    below_6a = sum(1 for r in sensors if r["payload"].get("current", 0) < 6)
    load_ratio = round((len(sensors) - zero_current) / len(sensors) * 100, 1) if sensors else 0

    temp_status_timeline = []
    for r in sensors:
        p = r["payload"]
        if "temperature" in p:
            temp_status_timeline.append(1)
        elif p.get("temperature_sensor_status") == 2:
            temp_status_timeline.append(2)
        elif "temperature_sensor_status" in p:
            temp_status_timeline.append(p["temperature_sensor_status"])
        else:
            temp_status_timeline.append(None)

    info = info_pkts[0]["payload"] if info_pkts else {}
    return {
        "csv_name": path.name,
        "device": target_device,
        "gateway": records[0]["gateway"] if records else "-",
        "t0": records[0]["time"] if records else "-",
        "t1": records[-1]["time"] if records else "-",
        "records": records,
        "sensors": sensors,
        "device_packet_total": len(records),
        "has_temp": has_temp,
        "status_2": status_2,
        "current_stats": stats([r["payload"]["current"] for r in sensors]),
        "total_stats": stats([r["payload"]["total_current"] for r in sensors]),
        "temp_stats": stats([r["payload"]["temperature"] for r in sensors if "temperature" in r["payload"]]),
        "rssi_stats": stats([r["rssi"] for r in sensors if r["rssi"] is not None]),
        "snr_stats": stats([r["snr"] for r in sensors if r["snr"] is not None]),
        "type_counts": Counter(r["type"] for r in records),
        "dr_counts": Counter(r["dr"] for r in records),
        "freq_counts": Counter(r["freq_mhz"] for r in records),
        "duration_h": duration_h,
        "interval_med": interval_med,
        "zero_current": zero_current,
        "below_6a": below_6a,
        "load_ratio": load_ratio,
        "info": info,
        "lorawan_class": {0: "Class A", 1: "Class B", 2: "Class C"}.get(
            info.get("lorawan_class"), info.get("lorawan_class", "—")
        ),
        "latest": sensors[-1]["payload"] if sensors else {},
        "labels": [fmt_time(r["time"]) for r in sensors],
        "full_times": [r["time"] for r in sensors],
        "current_data": [r["payload"]["current"] for r in sensors],
        "total_data": [r["payload"]["total_current"] for r in sensors],
        "temperature_data": [r["payload"].get("temperature") for r in sensors],
        "temp_status_timeline": temp_status_timeline,
        "rssi_data": [r["rssi"] for r in sensors],
        "snr_data": [r["snr"] for r in sensors],
        "freq_list": ", ".join(f"{k} MHz" for k in sorted(Counter(r["freq_mhz"] for r in records).keys())),
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def temp_cell(payload: dict, lang: str) -> str:
    st_map = TEMP_STATUS[lang]
    if "temperature" in payload:
        return f"{payload['temperature']} °C"
    st = payload.get("temperature_sensor_status")
    if st is not None:
        code = f"Code {st}" if lang == "en" else f"代碼 {st}"
        return st_map.get(st, code)
    return "—"


def temp_status_label(payload: dict, lang: str) -> str:
    if "temperature" in payload:
        return "Installed (reading available)" if lang == "en" else "已安裝（有讀數）"
    st = payload.get("temperature_sensor_status")
    if st is not None:
        code = f"Code {st}" if lang == "en" else f"代碼 {st}"
        return TEMP_STATUS[lang].get(st, code)
    return "—"


def load_level(a, lang: str):
    if lang == "en":
        if a <= 0:
            return "Idle", "good"
        if a < 0.5:
            return "Low load", "good"
        if a < 1.0:
            return "Medium load", "caution"
        return "High load", "warn"
    if a <= 0:
        return "待機", "good"
    if a < 0.5:
        return "低負載", "good"
    if a < 1.0:
        return "中負載", "caution"
    return "高負載", "warn"


def build_insights(ctx: dict, lang: str) -> list[str]:
    sensors = ctx["sensors"]
    if not sensors:
        return []
    ins = []
    c0 = sensors[0]["payload"]["current"]
    c1 = sensors[-1]["payload"]["current"]
    delta = round(c1 - c0, 2)
    zero_pct = round(ctx["zero_current"] / len(sensors) * 100, 1)
    cs = ctx["current_stats"]
    lr = ctx["load_ratio"]

    if lang == "en":
        if ctx["zero_current"] > 0:
            ins.append(
                f"{ctx['zero_current']}/{len(sensors)} packets ({zero_pct}%) reported 0 A instantaneous current; "
                f"load detected {lr}% of the time."
            )
        else:
            ins.append(
                f"Instantaneous current changed from {c0} A to {c1} A (Δ {delta:+.2f} A); load activity {lr}%."
            )
        if cs:
            ins.append(f"Instantaneous current range {cs['min']}–{cs['max']} A, average {cs['avg']} A.")
        if ctx["total_stats"] and ctx["total_stats"]["max"] > 0:
            ins.append(
                f"Cumulative current (total_current) increased from {sensors[0]['payload']['total_current']} A·h "
                f"to {sensors[-1]['payload']['total_current']} A·h."
            )
        ins.append(
            f"Temperature: {len(ctx['has_temp'])}/{len(sensors)} packets include cable temperature readings; "
            f"{len(ctx['status_2'])}/{len(sensors)} report temperature_sensor_status=2 (sensor not installed)."
        )
        if ctx["below_6a"] == len(sensors):
            ins.append(
                "All instantaneous current readings were below 6 A. Per CT103 specs, induced power may be insufficient "
                "for periodic uplinks; continued reporting may indicate Type-C external power or supercap residual charge."
            )
        elif ctx["below_6a"] > 0:
            ins.append(
                f"{ctx['below_6a']}/{len(sensors)} packets had current below 6 A; device may stop reporting when "
                "induced current is insufficient."
            )
        if ctx["rssi_stats"] and ctx["snr_stats"]:
            q = "good" if ctx["rssi_stats"]["avg"] > -90 and ctx["snr_stats"]["avg"] > 5 else "fair"
            ins.append(
                f"LoRaWAN signal quality is {q}: avg RSSI {ctx['rssi_stats']['avg']} dBm, avg SNR {ctx['snr_stats']['avg']} dB."
            )
        if ctx["interval_med"]:
            ins.append(f"Median uplink interval ~{ctx['interval_med']} s.")
        return ins

    if ctx["zero_current"] > 0:
        ins.append(
            f"監測期間有 {ctx['zero_current']}/{len(sensors)} 筆（{zero_pct}%）即時電流為 0 A；"
            f"其餘 {lr}% 時間偵測到負載電流。"
        )
    else:
        ins.append(f"即時電流由 {c0} A 變化至 {c1} A（Δ {delta:+.2f} A），負載活動比例 {lr}%。")
    if cs:
        ins.append(f"即時電流範圍 {cs['min']}–{cs['max']} A，平均 {cs['avg']} A。")
    if ctx["total_stats"] and ctx["total_stats"]["max"] > 0:
        ins.append(
            f"累計電流（total_current）由 {sensors[0]['payload']['total_current']} A·h "
            f"增至 {sensors[-1]['payload']['total_current']} A·h。"
        )
    ins.append(
        f"溫度資料：{len(ctx['has_temp'])}/{len(sensors)} 筆含導線溫度讀數；"
        f"{len(ctx['status_2'])}/{len(sensors)} 筆回報 temperature_sensor_status=2（溫度感測器未安裝）。"
    )
    if ctx["below_6a"] == len(sensors):
        ins.append(
            "本段監測期間所有即時電流均低於 6 A；依 CT103 規格，感應供電可能不足以維持週期上報，"
            "若仍能收到資料，可能與 Type-C 外接供電或超級電容殘餘電量有關。"
        )
    elif ctx["below_6a"] > 0:
        ins.append(
            f"有 {ctx['below_6a']}/{len(sensors)} 筆即時電流低於 6 A，低電流時裝置可能因感應電流不足而停止上報。"
        )
    if ctx["rssi_stats"] and ctx["snr_stats"]:
        q = "良好" if ctx["rssi_stats"]["avg"] > -90 and ctx["snr_stats"]["avg"] > 5 else "一般"
        ins.append(f"LoRaWAN 訊號品質{q}：平均 RSSI {ctx['rssi_stats']['avg']} dBm、平均 SNR {ctx['snr_stats']['avg']} dB。")
    if ctx["interval_med"]:
        ins.append(f"上行回報間隔中位數約 {ctx['interval_med']} 秒。")
    return ins


def notes_html(ctx: dict, lang: str) -> str:
    n, s2, t = len(ctx["has_temp"]), len(ctx["status_2"]), len(ctx["sensors"])
    if lang == "en":
        title = "Temperature Sensing & Power Notes"
        return f"""
  <h2 class="section-title" style="margin-top:2.5rem">{title}</h2>
  <div class="card notes">
    <ul class="insights">
      <li><strong>temperature_sensor_status = 2</strong>: In this report, interpreted as <strong>temperature sensor not installed</strong>.
        At the protocol layer this maps to raw value <code>0xFFFF</code> (official manual: "collection failed").
        When the optional NTC cable temperature sensor is not connected, the device continuously reports this status.</li>
      <li><strong>Shared Type-C port</strong>: CT103 USB Type-C is used for ToolBox configuration/debugging and the
        <strong>optional cable temperature sensor</strong> — not simultaneously. Without the probe, periodic packets
        typically include <code>temperature_sensor_status</code> but not <code>temperature</code>.</li>
      <li><strong>Induced-current startup threshold</strong>: Per CT103 specs, minimum measured current is about
        <strong>12 A</strong> at 1-minute reporting (about <strong>6 A</strong> at 10-minute reporting).
        Below the induced-power threshold, the device may <strong>stop periodic uplinks</strong> or enter low-power/low-voltage mode.</li>
      <li><strong>Type-C external power</strong>: Supplying 5 V via Type-C allows continued reporting even when measured
        current is below threshold; however <strong>this is not Milesight's recommended approach</strong>
        (designed for induced self-power; Type-C is primarily for configuration and optional temperature sensing).</li>
      <li><strong>This dataset</strong>: {n}/{t} packets include cable temperature readings; {s2}/{t} show status=2 (not installed),
        indicating the temperature sensor was connected only during a short test window.</li>
    </ul>
  </div>"""
    return f"""
  <h2 class="section-title" style="margin-top:2.5rem">溫度感測與供電說明</h2>
  <div class="card notes">
    <ul class="insights">
      <li><strong>temperature_sensor_status = 2</strong>：本報告解讀為<strong>溫度感測器未安裝</strong>。
        通訊協議層對應原始值 <code>0xFFFF</code>，官方手冊稱「採集失敗」；在未接選配 NTC 導線溫度感測器時，裝置會持續回報此狀態。</li>
      <li><strong>共用 Type-C 接口</strong>：CT103 的 USB Type-C 同時用於 ToolBox 調試/配置與<strong>選配導線溫度感測器</strong>連接，
        兩者不能同時使用。未接溫度探頭時，週期包中通常只出現 <code>temperature_sensor_status</code> 而無 <code>temperature</code> 欄位。</li>
      <li><strong>感應電流啟動門檻</strong>：依 CT103 規格，1 分鐘上報週期下所需最小被測電流約 <strong>12 A</strong>（10 分鐘週期約 6 A）。
        當被測電流<strong>低於感應供電門檻</strong>時，裝置可能<strong>無法持續上報</strong>或進入低功耗/低電壓模式。</li>
      <li><strong>Type-C 外接供電</strong>：若透過 Type-C 提供 5 V 供電，即使被測電流未達門檻，裝置仍可持續上報；
        但<strong>這並非 Milesight 的推薦做法</strong>（官方設計為感應電流自供電，Type-C 主要用於配置與選配溫度感測器）。</li>
      <li><strong>本批資料觀察</strong>：{n}/{t} 筆含導線溫度讀數，{s2}/{t} 筆為 status=2（未安裝）；
        說明測試過程中僅少數時段接入了溫度感測器。</li>
    </ul>
  </div>"""


def build_html(ctx: dict, lang: str) -> str:
    L = _labels(lang)
    sensors = ctx["sensors"]
    latest = ctx["latest"]
    cs, ts, rssi_s, snr_s = ctx["current_stats"], ctx["total_stats"], ctx["rssi_stats"], ctx["snr_stats"]
    temp_s = ctx["temp_stats"]
    load_label, load_cls = load_level(latest.get("current", 0), lang)
    insights = build_insights(ctx, lang)
    latest_temp = temp_status_label(latest, lang)
    installed = "Installed" if lang == "en" else "已安裝"
    to_word = "to" if lang == "en" else "至"
    avg_word = "avg" if lang == "en" else "平均"
    range_word = "Range" if lang == "en" else "範圍"

    table_rows = "".join(
        f"<tr><td>{fmt_time(r['time'])}</td>"
        f"<td>{r['payload']['current']}</td>"
        f"<td>{r['payload']['total_current']}</td>"
        f"<td>{r['payload'].get('temperature', '—')}</td>"
        f"<td>{temp_cell(r['payload'], lang) if 'temperature' not in r['payload'] else installed}</td>"
        f"<td>{r['rssi'] if r['rssi'] is not None else '—'}</td>"
        f"<td>{r['snr'] if r['snr'] is not None else '—'}</td>"
        f"<td>{r['fcnt']}</td></tr>"
        for r in reversed(sensors)
    )

    temp_range = (
        f"{range_word} {temp_s['min']}–{temp_s['max']} °C"
        if temp_s
        else (L["no_temp_most"] if lang == "en" else "本段多數封包無溫度讀數")
    )

    notes = notes_html(ctx, lang)
    font = "'Segoe UI', system-ui, sans-serif" if lang == "en" else "'Segoe UI', 'PingFang TC', 'Microsoft JhengHei', system-ui, sans-serif"

    js = _chart_js(ctx, lang)

    return f"""<!DOCTYPE html>
<html lang="{'en' if lang == 'en' else 'zh-Hant'}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{L['title']}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --surface: #1e293b; --surface2: #334155; --text: #f1f5f9;
    --muted: #94a3b8; --accent: #38bdf8; --good: #10b981; --warn: #fbbf24;
    --bad: #ef4444; --border: #475569; --current: #f59e0b; --total: #8b5cf6; --temp: #6366f1;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: {font}; background: var(--bg); color: var(--text); line-height: 1.6; min-height: 100vh; }}
  .header {{ background: linear-gradient(135deg, #78350f 0%, #1e3a5f 50%, #0f172a 100%); padding: 2.5rem 2rem; border-bottom: 1px solid var(--border); }}
  .header h1 {{ font-size: 1.75rem; font-weight: 700; }}
  .header .subtitle {{ color: var(--muted); margin-top: 0.5rem; font-size: 0.95rem; }}
  .badge {{ display: inline-block; background: rgba(56,189,248,0.15); color: var(--accent); padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; margin-right: 0.5rem; margin-top: 0.75rem; }}
  .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
  .section-title {{ font-size: 1.1rem; font-weight: 600; margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 2px solid var(--accent); display: inline-block; }}
  .overview-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
  .overview-card .ov-label {{ color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
  .overview-card .ov-value {{ font-size: 1.5rem; font-weight: 700; margin-top: 0.25rem; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; }}
  .stat-card .stat-label {{ color: var(--muted); font-size: 0.8rem; }}
  .stat-card .stat-value {{ font-size: 1.6rem; font-weight: 700; margin: 0.25rem 0; }}
  .stat-card .unit {{ font-size: 0.75rem; color: var(--muted); margin-left: 2px; }}
  .stat-card .stat-range {{ font-size: 0.72rem; color: var(--muted); }}
  .stat-card.warn {{ border-color: var(--warn); background: rgba(251,191,36,0.08); }}
  .stat-card.good {{ border-color: var(--good); background: rgba(16,185,129,0.08); }}
  .load-badge {{ display: inline-flex; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; font-size: 1.1rem; margin-bottom: 1rem; }}
  .load-badge.good {{ background: rgba(16,185,129,0.15); color: #34d399; }}
  .load-badge.caution {{ background: rgba(245,158,11,0.15); color: #fbbf24; }}
  .load-badge.warn {{ background: rgba(239,68,68,0.15); color: #f87171; }}
  .insights {{ list-style: none; display: flex; flex-direction: column; gap: 0.75rem; }}
  .insights li {{ padding: 0.85rem 1rem; border-radius: 8px; background: var(--surface2); border-left: 3px solid var(--accent); font-size: 0.9rem; }}
  .notes code {{ background: rgba(0,0,0,0.25); padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.85em; }}
  .chart-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(480px, 1fr)); gap: 1.25rem; }}
  .chart-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.25rem; }}
  .chart-card h3 {{ font-size: 0.95rem; margin-bottom: 0.5rem; color: var(--muted); }}
  .chart-note {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 0.75rem; }}
  .chart-wrap {{ position: relative; height: 260px; }}
  .chart-wrap.tall {{ height: 320px; }}
  .tabs {{ display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem; }}
  .tab {{ background: var(--surface2); border: 1px solid var(--border); color: var(--text); padding: 0.4rem 1rem; border-radius: 8px; cursor: pointer; font-size: 0.85rem; }}
  .tab:hover, .tab.active {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}
  .lorawan-table, .data-table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  .lorawan-table th, .lorawan-table td, .data-table th, .data-table td {{ padding: 0.5rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
  .lorawan-table th, .data-table th {{ color: var(--muted); font-size: 0.75rem; }}
  .data-table td {{ white-space: nowrap; }}
  .scroll {{ overflow: auto; max-height: 400px; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; padding: 2rem; border-top: 1px solid var(--border); margin-top: 2rem; }}
  @media (max-width: 600px) {{ .chart-grid {{ grid-template-columns: 1fr; }} .header {{ padding: 1.5rem 1rem; }} }}
</style>
</head>
<body>

<header class="header">
  <h1>{L['h1']}</h1>
  <p class="subtitle">{L['subtitle']}</p>
  <span class="badge">{L['badge_device']}{ctx['device']}</span>
  <span class="badge">{L['badge_gw']}{ctx['gateway']}</span>
  <span class="badge">IP: 60.0.0.49</span>
  <span class="badge">{L['badge_band']}</span>
  <span class="badge">{L['badge_data']}{ctx['csv_name']}</span>
</header>

<div class="container">

  <h2 class="section-title">{L['sec_overview']}</h2>
  <div class="overview-grid">
    <div class="card overview-card">
      <div class="ov-label">{L['ov_packets']}</div>
      <div class="ov-value">{len(sensors)} / {ctx['device_packet_total']}</div>
    </div>
    <div class="card overview-card">
      <div class="ov-label">{L['ov_time']}</div>
      <div class="ov-value" style="font-size:1rem">{fmt_time(ctx['t0'])}</div>
      <div style="color:var(--muted);font-size:0.85rem">{to_word} {fmt_time(ctx['t1'])}</div>
    </div>
    <div class="card overview-card">
      <div class="ov-label">{L['ov_duration']}</div>
      <div class="ov-value">{ctx['duration_h']} h</div>
    </div>
    <div class="card overview-card">
      <div class="ov-label">{L['ov_interval']}</div>
      <div class="ov-value">~{ctx['interval_med']} s</div>
    </div>
    <div class="card overview-card">
      <div class="ov-label">{L['ov_load']}</div>
      <div class="ov-value">{ctx['load_ratio']}%</div>
    </div>
    <div class="card overview-card">
      <div class="ov-label">{L['ov_temp2']}</div>
      <div class="ov-value">{len(ctx['status_2'])}/{len(sensors)}</div>
      <div style="color:var(--muted);font-size:0.85rem">{L['ov_temp2_sub'].format(n=len(ctx['has_temp']))}</div>
    </div>
  </div>

  <h2 class="section-title">{L['sec_latest']}</h2>
  <div class="stat-grid">
    <div class="card stat-card {'warn' if load_cls=='warn' else 'good' if load_cls=='good' else ''}">
      <div class="stat-label">{L['lbl_current']}</div>
      <div class="stat-value" style="color:var(--current)">{latest.get('current', '—')}<span class="unit">A</span></div>
      <div class="stat-range">{range_word} {cs['min'] if cs else '—'} – {cs['max'] if cs else '—'} · {avg_word} {cs['avg'] if cs else '—'}</div>
    </div>
    <div class="card stat-card">
      <div class="stat-label">{L['lbl_total']}</div>
      <div class="stat-value" style="color:var(--total)">{latest.get('total_current', '—')}<span class="unit">A·h</span></div>
      <div class="stat-range">{range_word} {ts['min'] if ts else '—'} – {ts['max'] if ts else '—'}</div>
    </div>
    <div class="card stat-card">
      <div class="stat-label">{L['lbl_cable_temp']}</div>
      <div class="stat-value" style="color:var(--temp);font-size:1.3rem">{latest.get('temperature', '—')}<span class="unit">{'' if 'temperature' not in latest else '°C'}</span></div>
      <div class="stat-range">{temp_range}</div>
    </div>
    <div class="card stat-card">
      <div class="stat-label">{L['lbl_temp_status']}</div>
      <div class="stat-value" style="color:var(--temp);font-size:1.05rem">{latest_temp}</div>
      <div class="stat-range">{L['lbl_temp_status_hint']}</div>
    </div>
    <div class="card stat-card">
      <div class="stat-label">RSSI / SNR</div>
      <div class="stat-value" style="color:#38bdf8;font-size:1.2rem">{sensors[-1]['rssi'] if sensors and sensors[-1]['rssi'] is not None else '—'} dBm</div>
      <div class="stat-range">SNR {sensors[-1]['snr'] if sensors and sensors[-1]['snr'] is not None else '—'} dB</div>
    </div>
  </div>

  <h2 class="section-title">{L['sec_insights']}</h2>
  <div class="card">
    <div class="load-badge {load_cls}">{L['load_prefix']}{load_label} ({latest.get('current', 0)} A)</div>
    <ul class="insights">{''.join(f'<li>{i}</li>' for i in insights)}</ul>
  </div>

  <h2 class="section-title">{L['sec_charts']}</h2>
  <div class="tabs" id="chartTabs"></div>
  <div class="chart-card">
    <h3 id="mainChartTitle">{L['chart_main']}</h3>
    <div class="chart-wrap tall"><canvas id="mainChart"></canvas></div>
  </div>

  <h2 class="section-title" style="margin-top:2.5rem">{L['sec_multi']}</h2>
  <div class="chart-grid">
    <div class="chart-card"><h3>{L['chart_ct']}</h3><div class="chart-wrap"><canvas id="currentTotalChart"></canvas></div></div>
    <div class="chart-card">
      <h3>{L['chart_temp']}</h3>
      <p class="chart-note">{L['chart_temp_note'].format(n=len(ctx['has_temp']), s2=len(ctx['status_2']))}</p>
      <div class="chart-wrap"><canvas id="tempChart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>{L['chart_temp_status']}</h3>
      <p class="chart-note">{L['chart_temp_status_note']}</p>
      <div class="chart-wrap"><canvas id="tempStatusChart"></canvas></div>
    </div>
    <div class="chart-card"><h3>{L['chart_hist']}</h3><div class="chart-wrap"><canvas id="histChart"></canvas></div></div>
    <div class="chart-card"><h3>{L['chart_load']}</h3><div class="chart-wrap"><canvas id="loadChart"></canvas></div></div>
    <div class="chart-card"><h3>{L['chart_signal']}</h3><div class="chart-wrap"><canvas id="signalChart"></canvas></div></div>
  </div>

  <h2 class="section-title" style="margin-top:2.5rem">{L['sec_lora']}</h2>
  <div class="card">
    <table class="lorawan-table">
      <tr><th>{L['th_param']}</th><th>{L['th_value']}</th></tr>
      <tr><td>{L['lr_mod']}</td><td>LoRa · {', '.join(f'{k}×{v}' for k,v in ctx['dr_counts'].items())} · CR 4/5</td></tr>
      <tr><td>{L['lr_freq']}</td><td>{ctx['freq_list'] or '—'}</td></tr>
      <tr><td>{L['lr_rssi']}</td><td>{rssi_s['min'] if rssi_s else '—'} ~ {rssi_s['max'] if rssi_s else '—'} dBm ({avg_word} {rssi_s['avg'] if rssi_s else '—'})</td></tr>
      <tr><td>{L['lr_snr']}</td><td>{snr_s['min'] if snr_s else '—'} ~ {snr_s['max'] if snr_s else '—'} dB ({avg_word} {snr_s['avg'] if snr_s else '—'})</td></tr>
      <tr><td>{L['lr_size']}</td><td>{Counter(r['size'] for r in sensors).most_common(1)[0][0] if sensors else '—'} bytes</td></tr>
      <tr><td>{L['lr_port']}</td><td>85</td></tr>
      <tr><td>{L['lr_class']}</td><td>{ctx['lorawan_class']}</td></tr>
      <tr><td>{L['lr_fw']}</td><td>{ctx['info'].get('firmware_version', '—')} / {ctx['info'].get('hardware_version', '—')}</td></tr>
      <tr><td>{L['lr_sn']}</td><td>{ctx['info'].get('sn', '—')}</td></tr>
      <tr><td>{L['lr_types']}</td><td>{', '.join(f'{k}:{v}' for k,v in sorted(ctx['type_counts'].items()))}</td></tr>
    </table>
  </div>

  <h2 class="section-title" style="margin-top:2.5rem">{L['sec_detail']}</h2>
  <div class="card scroll">
    <table class="data-table">
      <thead><tr>
        <th>{L['col_time']}</th><th>{L['col_current']}</th><th>{L['col_total']}</th>
        <th>{L['col_temp']}</th><th>{L['col_temp_st']}</th><th>RSSI</th><th>SNR</th><th>Fcnt</th>
      </tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </div>

  {notes}

</div>

<footer class="footer">{L['footer'].format(src=ctx['csv_name'], gen=ctx['generated'])}</footer>

{js}
</body>
</html>"""


def _labels(lang: str) -> dict:
    if lang == "en":
        return {
            "title": "CT103_470M Single-Phase Current Sensor Analysis Report",
            "h1": "CT103_470M Single-Phase Current Sensor Analysis Report",
            "subtitle": "Milesight CT103 current monitoring · UG65 LoRaWAN gateway data stream analysis",
            "badge_device": "Device EUI: ",
            "badge_gw": "Gateway: ",
            "badge_band": "Band: 470 MHz",
            "badge_data": "Data: ",
            "sec_overview": "Data Overview",
            "ov_packets": "Valid Sensor Packets",
            "ov_time": "Time Range",
            "ov_duration": "Monitoring Duration",
            "ov_interval": "Reporting Interval",
            "ov_load": "Load Activity Ratio",
            "ov_temp2": "Temperature status=2",
            "ov_temp2_sub": "Not installed · {n} with readings",
            "sec_latest": "Latest Sensor Readings",
            "lbl_current": "Instantaneous Current (current)",
            "lbl_total": "Cumulative Current (total_current)",
            "lbl_cable_temp": "Cable Temperature",
            "lbl_temp_status": "Temperature Sensor Status",
            "lbl_temp_status_hint": "status=2 = optional NTC probe not installed",
            "no_temp_most": "Most packets in this period have no temperature reading",
            "sec_insights": "Analysis Insights",
            "load_prefix": "Current load state: ",
            "sec_charts": "Current Trend Charts",
            "chart_main": "Instantaneous Current Trend",
            "sec_multi": "Multi-Parameter Comparison",
            "chart_ct": "Instantaneous & Cumulative Current",
            "chart_temp": "Cable Temperature (packets with readings only)",
            "chart_temp_note": "{n} packets with temperature field; {s2} with status=2 (not installed)",
            "chart_temp_status": "Temperature Sensor Status Timeline",
            "chart_temp_status_note": "2 = not installed · 1 = installed with reading · stepped line",
            "chart_hist": "Instantaneous Current Distribution",
            "chart_load": "Load State (0=idle / 1=load present)",
            "chart_signal": "LoRaWAN Signal Quality (RSSI / SNR)",
            "sec_lora": "LoRaWAN Link Information",
            "th_param": "Parameter",
            "th_value": "Value",
            "lr_mod": "Modulation",
            "lr_freq": "Uplink Frequencies",
            "lr_rssi": "RSSI Range",
            "lr_snr": "SNR Range",
            "lr_size": "Payload Size",
            "lr_port": "Application Port",
            "lr_class": "Device Class",
            "lr_fw": "Firmware / Hardware",
            "lr_sn": "Serial Number",
            "lr_types": "Packet Types",
            "sec_detail": "Sensor Reading Details",
            "col_time": "Time",
            "col_current": "Current A",
            "col_total": "Total A·h",
            "col_temp": "Cable Temp",
            "col_temp_st": "Temp Sensor Status",
            "footer": "Auto-generated report · Source: {src} · Generated: {gen}",
        }
    return {
        "title": "CT103_470M 單相電流感測器分析報告",
        "h1": "CT103_470M 單相電流感測器分析報告",
        "subtitle": "Milesight CT103 單相電流監測 · UG65 LoRaWAN 閘道器資料流分析",
        "badge_device": "裝置 EUI：",
        "badge_gw": "閘道器：",
        "badge_band": "頻段：470 MHz",
        "badge_data": "資料：",
        "sec_overview": "資料概覽",
        "ov_packets": "有效感測封包",
        "ov_time": "時間範圍",
        "ov_duration": "監測時長",
        "ov_interval": "回報間隔",
        "ov_load": "負載活動比例",
        "ov_temp2": "溫度 status=2",
        "ov_temp2_sub": "未安裝 · 有讀數 {n} 筆",
        "sec_latest": "最新感測讀數",
        "lbl_current": "即時電流 (current)",
        "lbl_total": "累計電流 (total_current)",
        "lbl_cable_temp": "導線溫度",
        "lbl_temp_status": "溫度感測器狀態",
        "lbl_temp_status_hint": "status=2 表示未安裝選配 NTC 探頭",
        "no_temp_most": "本段多數封包無溫度讀數",
        "sec_insights": "分析洞察",
        "load_prefix": "目前負載狀態：",
        "sec_charts": "電流趨勢圖表",
        "chart_main": "即時電流趨勢",
        "sec_multi": "多參數對比",
        "chart_ct": "即時電流 & 累計電流",
        "chart_temp": "導線溫度（僅有讀數的封包）",
        "chart_temp_note": "共 {n} 筆含 temperature 欄位；其餘 {s2} 筆為 status=2（未安裝）",
        "chart_temp_status": "溫度感測器狀態時序",
        "chart_temp_status_note": "2 = 未安裝（status=2）· 1 = 已安裝且有讀數 · 階梯線",
        "chart_hist": "即時電流分佈（直方圖）",
        "chart_load": "負載狀態（0=待機 / 1=有電流）",
        "chart_signal": "LoRaWAN 訊號品質 (RSSI / SNR)",
        "sec_lora": "LoRaWAN 鏈路資訊",
        "th_param": "參數",
        "th_value": "數值",
        "lr_mod": "調變方式",
        "lr_freq": "上行頻率",
        "lr_rssi": "RSSI 範圍",
        "lr_snr": "SNR 範圍",
        "lr_size": "封包大小",
        "lr_port": "應用埠",
        "lr_class": "裝置類別",
        "lr_fw": "韌體 / 硬體",
        "lr_sn": "序號 SN",
        "lr_types": "封包類型",
        "sec_detail": "感測讀數明細",
        "col_time": "時間",
        "col_current": "電流 A",
        "col_total": "累計 A·h",
        "col_temp": "導線溫度",
        "col_temp_st": "溫度感測狀態",
        "footer": "報告自動產生 · 資料來源：{src} · 產生時間：{gen}",
    }


def _chart_js(ctx: dict, lang: str) -> str:
    trend_suffix = " Trend" if lang == "en" else " 趨勢"
    if lang == "en":
        ds = [
            {"key": "current", "label": "Instantaneous Current", "unit": "A", "color": "#f59e0b"},
            {"key": "total_current", "label": "Cumulative Current", "unit": "A·h", "color": "#8b5cf6"},
        ]
        lbl_cur, lbl_tot = "Instantaneous Current (A)", "Cumulative Current (A·h)"
        lbl_temp = "Cable Temperature (°C)"
        lbl_tst = "Status (2=not installed, 1=reading)"
        tst_cb = "{0:'—',1:'Installed',2:'Not installed'}"
        lbl_load = "Load present"
    else:
        ds = [
            {"key": "current", "label": "即時電流", "unit": "A", "color": "#f59e0b"},
            {"key": "total_current", "label": "累計電流", "unit": "A·h", "color": "#8b5cf6"},
        ]
        lbl_cur, lbl_tot = "即時電流 (A)", "累計電流 (A·h)"
        lbl_temp = "導線溫度 (°C)"
        lbl_tst = "狀態 (2=未安裝, 1=有讀數)"
        tst_cb = "{0:'—',1:'已安裝',2:'未安裝'}"
        lbl_load = "有負載"

    return f"""<script>
const labels = {json.dumps(ctx['labels'], ensure_ascii=False)};
const fullTimes = {json.dumps(ctx['full_times'], ensure_ascii=False)};
const currentData = {json.dumps(ctx['current_data'])};
const totalData = {json.dumps(ctx['total_data'])};
const temperatureData = {json.dumps(ctx['temperature_data'])};
const tempStatusData = {json.dumps(ctx['temp_status_timeline'])};
const rssiData = {json.dumps(ctx['rssi_data'])};
const snrData = {json.dumps(ctx['snr_data'])};
const trendSuffix = {json.dumps(trend_suffix)};
const datasets = {json.dumps(ds, ensure_ascii=False)};
const dataByKey = {{ current: currentData, total_current: totalData }};

const chartDefaults = {{
  responsive: true, maintainAspectRatio: false,
  plugins: {{
    legend: {{ labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }},
    tooltip: {{ mode: 'index', intersect: false, callbacks: {{ title: (items) => fullTimes[items[0].dataIndex] || items[0].label }} }}
  }},
  scales: {{
    x: {{ ticks: {{ color: '#64748b', maxTicksLimit: 10, maxRotation: 45 }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }},
    y: {{ ticks: {{ color: '#64748b' }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }}
  }},
  interaction: {{ mode: 'nearest', axis: 'x', intersect: false }}
}};

function makeLineChart(canvasId, ds, extraOpts) {{
  return new Chart(document.getElementById(canvasId), {{ type: 'line', data: {{ labels, datasets: ds }}, options: {{ ...chartDefaults, ...extraOpts }} }});
}}

let mainChart;
const tabsEl = document.getElementById('chartTabs');
datasets.forEach((ds, i) => {{
  const btn = document.createElement('button');
  btn.className = 'tab' + (i === 0 ? ' active' : '');
  btn.textContent = ds.label;
  btn.onclick = () => {{
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('mainChartTitle').textContent = ds.label + trendSuffix;
    mainChart.data.datasets[0].data = dataByKey[ds.key];
    mainChart.data.datasets[0].label = ds.label + (ds.unit ? ' (' + ds.unit + ')' : '');
    mainChart.data.datasets[0].borderColor = ds.color;
    mainChart.data.datasets[0].backgroundColor = ds.color + '22';
    mainChart.update();
  }};
  tabsEl.appendChild(btn);
}});

mainChart = makeLineChart('mainChart', [{{
  label: datasets[0].label + ' (' + datasets[0].unit + ')', data: currentData,
  borderColor: '#f59e0b', backgroundColor: '#f59e0b22', fill: true, tension: 0.3, pointRadius: 2, borderWidth: 2
}}]);

makeLineChart('currentTotalChart', [
  {{ label: {json.dumps(lbl_cur)}, data: currentData, borderColor: '#f59e0b', tension: 0.3, pointRadius: 0, borderWidth: 2, yAxisID: 'y' }},
  {{ label: {json.dumps(lbl_tot)}, data: totalData, borderColor: '#8b5cf6', tension: 0.3, pointRadius: 0, borderWidth: 2, yAxisID: 'y1' }}
], {{ scales: {{ x: chartDefaults.scales.x,
  y: {{ position: 'left', title: {{ display: true, text: 'A', color: '#f59e0b' }}, ticks: {{ color: '#f59e0b' }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }},
  y1: {{ position: 'right', title: {{ display: true, text: 'A·h', color: '#8b5cf6' }}, ticks: {{ color: '#8b5cf6' }}, grid: {{ drawOnChartArea: false }} }}
}}}});

makeLineChart('tempChart', [{{
  label: {json.dumps(lbl_temp)}, data: temperatureData, borderColor: '#6366f1', backgroundColor: '#6366f133',
  spanGaps: false, tension: 0.3, pointRadius: 5, pointHoverRadius: 7, borderWidth: 2
}}]);

makeLineChart('tempStatusChart', [{{
  label: {json.dumps(lbl_tst)}, data: tempStatusData, borderColor: '#ec4899', backgroundColor: '#ec489933',
  stepped: true, spanGaps: false, pointRadius: 0, borderWidth: 2
}}], {{ scales: {{ x: chartDefaults.scales.x,
  y: {{ min: 0, max: 2.5, ticks: {{ stepSize: 1, color: '#ec4899', callback: (v) => ({tst_cb}[v] ?? v) }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }}
}}}});

(function() {{
  const vals = currentData.filter(v => v > 0);
  const bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2];
  const counts = bins.slice(0, -1).map((b, i) => vals.filter(v => v >= b && v < bins[i+1]).length);
  new Chart(document.getElementById('histChart'), {{
    type: 'bar',
    data: {{ labels: bins.slice(0,-1).map((b,i)=>b+'-'+bins[i+1]), datasets: [{{ data: counts, backgroundColor: '#f59e0b99', borderColor: '#f59e0b', borderRadius: 4 }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }},
      scales: {{ x: {{ ticks: {{ color: '#64748b' }}, grid: {{ display: false }} }}, y: {{ beginAtZero: true, ticks: {{ color: '#64748b', stepSize: 1 }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }} }}
    }}
  }});
}})();

makeLineChart('loadChart', [{{
  label: {json.dumps(lbl_load)}, data: currentData.map(v => v > 0 ? 1 : 0),
  borderColor: '#10b981', backgroundColor: '#10b98133', fill: true, stepped: true, pointRadius: 0, borderWidth: 2
}}], {{ scales: {{ x: chartDefaults.scales.x, y: {{ min: 0, max: 1, ticks: {{ stepSize: 1, color: '#10b981' }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }} }} }});

makeLineChart('signalChart', [
  {{ label: 'RSSI (dBm)', data: rssiData, borderColor: '#38bdf8', tension: 0.3, pointRadius: 0, borderWidth: 2, yAxisID: 'y' }},
  {{ label: 'SNR (dB)', data: snrData, borderColor: '#a78bfa', tension: 0.3, pointRadius: 0, borderWidth: 2, yAxisID: 'y1' }}
], {{ scales: {{ x: chartDefaults.scales.x,
  y: {{ position: 'left', title: {{ display: true, text: 'dBm', color: '#38bdf8' }}, ticks: {{ color: '#38bdf8' }}, grid: {{ color: 'rgba(71,85,105,0.3)' }} }},
  y1: {{ position: 'right', title: {{ display: true, text: 'dB', color: '#a78bfa' }}, ticks: {{ color: '#a78bfa' }}, grid: {{ drawOnChartArea: false }} }}
}}}});
</script>"""


if __name__ == "__main__":
    ctx = parse_csv(CSV_PATH)
    OUT_ZH.write_text(build_html(ctx, "zh"), encoding="utf-8")
    OUT_EN.write_text(build_html(ctx, "en"), encoding="utf-8")
    print(f"Wrote {OUT_ZH}")
    print(f"Wrote {OUT_EN}")
    print(f"ct103_records={ctx['device_packet_total']} sensors={len(ctx['sensors'])}")
