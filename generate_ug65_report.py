# -*- coding: utf-8 -*-
"""Parse UG65 datastream CSV and emit a self-contained HTML visualization report."""
import re
import json
from pathlib import Path
from collections import Counter
from statistics import mean, median, pstdev
from datetime import datetime

CSV_PATH = Path(r"c:\RossData\code\woac\MilesightAnalysis\files\UG65_20260710-1648_60.0.0.49_datastream.csv")
OUT_PATH = Path(r"c:\RossData\code\woac\MilesightAnalysis\UG65_V5_cursor_grok.html")

text = CSV_PATH.read_text(encoding="utf-8")
body = "\n".join(text.splitlines()[1:])

row_pat = re.compile(
    r"^([0-9A-Fa-f]{16}),([0-9A-Fa-f]{16}),(\d+),(SF\d+BW\d+),\s*"
    r"([^,]*),(\d+),(\d+),(\w+),(20\d{2}-\d{2}-\d{2}T[^,]+),",
    re.M,
)
json_pat = re.compile(r"JSON:\s*(\{.*?\})", re.DOTALL)
snr_detail = re.compile(r"^SNR:\s*([-\d.]+)", re.M)
rssi_detail = re.compile(r"^RSSI:\s*([-\d.]+)", re.M)


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


def parse_rssi_snr(field: str, chunk: str):
    field = field.strip()
    if "/" in field:
        a, b = field.split("/", 1)
        rssi, snr = _to_float(a), _to_float(b)
        if rssi is not None or snr is not None:
            return rssi, snr
    rm = rssi_detail.search(chunk)
    sm = snr_detail.search(chunk)
    return _to_float(rm.group(1) if rm else None), _to_float(sm.group(1) if sm else None)


starts = list(row_pat.finditer(body))
records = []
for i, m in enumerate(starts):
    start = m.start()
    end = starts[i + 1].start() if i + 1 < len(starts) else len(body)
    chunk = body[start:end]
    g = m.groups()
    rssi, snr = parse_rssi_snr(g[4], chunk)
    payload = None
    jm = json_pat.search(chunk)
    if jm:
        try:
            payload = json.loads(jm.group(1).replace('""', '"'))
        except json.JSONDecodeError:
            payload = None
    rec = {
        "time": g[8],
        "device": g[0],
        "gateway": g[1],
        "freq_hz": int(g[2]),
        "freq_mhz": round(int(g[2]) / 1e6, 1),
        "dr": g[3],
        "rssi": rssi,
        "snr": snr,
        "size": int(g[5]),
        "fcnt": int(g[6]),
        "type": g[7],
        "payload": payload or {},
    }
    records.append(rec)

records.sort(key=lambda r: r["time"])

sensor_keys = [
    "temperature",
    "humidity",
    "co2",
    "tvoc",
    "pm2_5",
    "pm10",
    "pressure",
    "hcho",
    "light_level",
    "pir",
]
sensors = [r for r in records if all(k in r["payload"] for k in ("temperature", "co2", "humidity"))]
info_pkts = [r for r in records if "firmware_version" in r["payload"] or "sn" in r["payload"]]


def series(key):
    return [
        {
            "t": r["time"],
            "v": r["payload"][key],
            "rssi": r["rssi"],
            "snr": r["snr"],
            "fcnt": r["fcnt"],
            "freq": r["freq_mhz"],
            "dr": r["dr"],
        }
        for r in sensors
        if key in r["payload"]
    ]


def stats(vals):
    if not vals:
        return None
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "avg": round(mean(vals), 2),
        "med": median(vals),
        "std": round(pstdev(vals), 2) if len(vals) > 1 else 0,
    }


metric_stats = {k: stats([r["payload"][k] for r in sensors if k in r["payload"]]) for k in sensor_keys}
link_rssi = stats([r["rssi"] for r in records if r["rssi"] is not None])
link_snr = stats([r["snr"] for r in records if r["snr"] is not None])

type_counts = Counter(r["type"] for r in records)
dr_counts = Counter(r["dr"] for r in records)
freq_counts = Counter(str(r["freq_mhz"]) for r in records)

# fcnt continuity on uplink unconfirmed with sensor data
fcnts = [r["fcnt"] for r in sensors]
fcnt_gaps = []
for a, b in zip(fcnts, fcnts[1:]):
    if b > a + 1:
        fcnt_gaps.append({"from": a, "to": b, "missing": list(range(a + 1, b))})

device = records[0]["device"] if records else "-"
gateway = records[0]["gateway"] if records else "-"
t0 = records[0]["time"] if records else "-"
t1 = records[-1]["time"] if records else "-"

info = info_pkts[0]["payload"] if info_pkts else {}

# Air quality thresholds (informational)
def co2_level(v):
    if v < 800:
        return "優良"
    if v < 1000:
        return "良好"
    if v < 1500:
        return "偏高"
    return "較差"


def pm25_level(v):
    if v <= 12:
        return "優良"
    if v <= 35:
        return "良好"
    if v <= 55:
        return "偏高"
    return "較差"


avg_co2 = metric_stats["co2"]["avg"] if metric_stats["co2"] else None
avg_pm25 = metric_stats["pm2_5"]["avg"] if metric_stats["pm2_5"] else None

chart_data = {
    "labels": [r["time"][11:19] for r in sensors],
    "fullTimes": [r["time"] for r in sensors],
    "temperature": [r["payload"]["temperature"] for r in sensors],
    "humidity": [r["payload"]["humidity"] for r in sensors],
    "co2": [r["payload"]["co2"] for r in sensors],
    "tvoc": [r["payload"]["tvoc"] for r in sensors],
    "pm25": [r["payload"]["pm2_5"] for r in sensors],
    "pm10": [r["payload"]["pm10"] for r in sensors],
    "pressure": [r["payload"]["pressure"] for r in sensors],
    "hcho": [r["payload"]["hcho"] for r in sensors],
    "light": [r["payload"]["light_level"] for r in sensors],
    "pir": [r["payload"]["pir"] for r in sensors],
    "rssi": [r["rssi"] for r in sensors],
    "snr": [r["snr"] for r in sensors],
    "fcnt": [r["fcnt"] for r in sensors],
    "freq": [r["freq_mhz"] for r in sensors],
}

timeline = [
    {
        "time": r["time"],
        "type": r["type"],
        "dr": r["dr"],
        "freq": r["freq_mhz"],
        "rssi": r["rssi"],
        "snr": r["snr"],
        "fcnt": r["fcnt"],
        "size": r["size"],
        "has_sensor": "temperature" in r["payload"],
        "is_info": "firmware_version" in r["payload"] or "sn" in r["payload"],
    }
    for r in records
]

meta = {
    "source": CSV_PATH.name,
    "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "device": device,
    "gateway": gateway,
    "time_start": t0,
    "time_end": t1,
    "total_packets": len(records),
    "sensor_packets": len(sensors),
    "type_counts": dict(type_counts),
    "dr_counts": dict(dr_counts),
    "freq_counts": dict(sorted(freq_counts.items(), key=lambda x: float(x[0]))),
    "metric_stats": metric_stats,
    "link_rssi": link_rssi,
    "link_snr": link_snr,
    "fcnt_gaps": fcnt_gaps,
    "device_info": {
        "sn": info.get("sn"),
        "firmware_version": info.get("firmware_version"),
        "hardware_version": info.get("hardware_version"),
        "ipso_version": info.get("ipso_version"),
        "lorawan_class": info.get("lorawan_class"),
        "device_status": info.get("device_status"),
    },
    "aqi_notes": {
        "co2_avg": avg_co2,
        "co2_level": co2_level(avg_co2) if avg_co2 is not None else "-",
        "pm25_avg": avg_pm25,
        "pm25_level": pm25_level(avg_pm25) if avg_pm25 is not None else "-",
    },
}

DATA_JSON = json.dumps(
    {"meta": meta, "chart": chart_data, "timeline": timeline, "sensors": sensors},
    ensure_ascii=False,
)

html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>UG65 感測器資料可視化報告 V5 · Cursor Grok</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #1a2332;
    --panel2: #243044;
    --border: #2d3a4f;
    --text: #e8eef7;
    --muted: #8b9bb4;
    --accent: #3d9cf0;
    --good: #3ecf8e;
    --warn: #f0b429;
    --bad: #f07178;
    --temp: #ff7b72;
    --hum: #58a6ff;
    --co2: #d2a8ff;
    --pm: #ffa657;
    --tvoc: #7ee787;
    --press: #79c0ff;
    --rssi: #ff9bce;
    --snr: #a5d6ff;
    --radius: 14px;
    --shadow: 0 8px 28px rgba(0,0,0,.35);
    --font: "Segoe UI", "PingFang TC", "Microsoft JhengHei", sans-serif;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: var(--font);
    background: radial-gradient(1200px 600px at 10% -10%, #1b3a5f 0%, transparent 55%),
                radial-gradient(900px 500px at 100% 0%, #1a3d36 0%, transparent 45%),
                var(--bg);
    color: var(--text);
    line-height: 1.5;
  }}
  header {{
    padding: 28px 32px 18px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(180deg, rgba(26,35,50,.95), rgba(15,20,25,.6));
    position: sticky; top: 0; z-index: 20;
    backdrop-filter: blur(10px);
  }}
  header h1 {{
    margin: 0 0 6px;
    font-size: 1.55rem;
    font-weight: 700;
    letter-spacing: .02em;
  }}
  header .sub {{
    color: var(--muted);
    font-size: .92rem;
    display: flex; flex-wrap: wrap; gap: 10px 18px;
  }}
  header .badge {{
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 10px;
    font-size: .8rem;
  }}
  main {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 22px 20px 48px;
    display: grid;
    gap: 18px;
  }}
  .kpis {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
  }}
  .kpi {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 14px 16px;
    box-shadow: var(--shadow);
  }}
  .kpi .label {{ color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }}
  .kpi .value {{ font-size: 1.45rem; font-weight: 700; margin-top: 4px; }}
  .kpi .hint {{ color: var(--muted); font-size: .78rem; margin-top: 2px; }}
  .kpi.good .value {{ color: var(--good); }}
  .kpi.warn .value {{ color: var(--warn); }}
  .kpi.bad .value {{ color: var(--bad); }}
  .panel {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 18px 14px;
    box-shadow: var(--shadow);
  }}
  .panel h2 {{
    margin: 0 0 12px;
    font-size: 1.05rem;
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
  }}
  .panel h2 span.meta {{ color: var(--muted); font-size: .8rem; font-weight: 500; }}
  .grid-2 {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }}
  @media (max-width: 900px) {{
    .grid-2 {{ grid-template-columns: 1fr; }}
    header {{ padding: 18px 16px; }}
  }}
  .chart-wrap {{ position: relative; height: 280px; }}
  .chart-wrap.tall {{ height: 320px; }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: .85rem;
  }}
  th, td {{
    padding: 8px 10px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    white-space: nowrap;
  }}
  th {{ color: var(--muted); font-weight: 600; font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; }}
  tr:hover td {{ background: rgba(61,156,240,.06); }}
  .tag {{
    display: inline-block;
    padding: 1px 8px;
    border-radius: 999px;
    font-size: .75rem;
    border: 1px solid var(--border);
    background: var(--panel2);
  }}
  .tag.UpUnc {{ color: var(--good); border-color: #2a6b4f; }}
  .tag.DnUnc {{ color: var(--accent); border-color: #2a5078; }}
  .tag.JnReq {{ color: var(--warn); border-color: #7a5c18; }}
  .tag.JnAcc {{ color: #c9a0ff; border-color: #5a3d7a; }}
  .scroll {{ overflow: auto; max-height: 420px; }}
  .note {{
    color: var(--muted);
    font-size: .85rem;
    margin-top: 8px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 10px;
  }}
  .stat-card {{
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
  }}
  .stat-card h3 {{ margin: 0 0 8px; font-size: .9rem; }}
  .stat-card dl {{
    margin: 0;
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2px 10px;
    font-size: .82rem;
  }}
  .stat-card dt {{ color: var(--muted); }}
  .stat-card dd {{ margin: 0; text-align: right; font-variant-numeric: tabular-nums; }}
  footer {{
    text-align: center;
    color: var(--muted);
    font-size: .78rem;
    padding: 8px 16px 28px;
  }}
  .legend-inline {{ display: flex; flex-wrap: wrap; gap: 8px; }}
</style>
</head>
<body>
<header>
  <h1>UG65 LoRaWAN 感測器資料可視化報告</h1>
  <div class="sub">
    <span class="badge">版本 V5 · Cursor Grok</span>
    <span class="badge">來源：{meta["source"]}</span>
    <span class="badge">裝置：{device}</span>
    <span class="badge">閘道：{gateway}</span>
    <span class="badge">區間：{t0[11:19] if len(t0)>19 else t0} – {t1[11:19] if len(t1)>19 else t1}</span>
    <span class="badge">產生：{meta["generated"]}</span>
  </div>
</header>

<main>
  <section class="kpis" id="kpis"></section>

  <section class="panel">
    <h2>環境指標趨勢 <span class="meta">溫度 / 濕度 / CO₂ / TVOC</span></h2>
    <div class="chart-wrap tall"><canvas id="chartEnv"></canvas></div>
    <p class="note">CO₂ 以右側軸顯示（ppm）。參考：&lt;800 優良、800–1000 良好、1000–1500 偏高。</p>
  </section>

  <div class="grid-2">
    <section class="panel">
      <h2>空氣微粒 <span class="meta">PM2.5 / PM10 / HCHO</span></h2>
      <div class="chart-wrap"><canvas id="chartPM"></canvas></div>
    </section>
    <section class="panel">
      <h2>氣壓與光照 / PIR <span class="meta">hPa · level · presence</span></h2>
      <div class="chart-wrap"><canvas id="chartPress"></canvas></div>
    </section>
  </div>

  <div class="grid-2">
    <section class="panel">
      <h2>LoRa 鏈路品質 <span class="meta">RSSI / SNR（感測上行）</span></h2>
      <div class="chart-wrap"><canvas id="chartLink"></canvas></div>
    </section>
    <section class="panel">
      <h2>封包類型與資料速率 <span class="meta">全量 {meta["total_packets"]} 筆</span></h2>
      <div class="chart-wrap"><canvas id="chartTypes"></canvas></div>
    </section>
  </div>

  <div class="grid-2">
    <section class="panel">
      <h2>頻率分佈 <span class="meta">MHz</span></h2>
      <div class="chart-wrap"><canvas id="chartFreq"></canvas></div>
    </section>
    <section class="panel">
      <h2>統計摘要</h2>
      <div class="stats-grid" id="stats"></div>
    </section>
  </div>

  <section class="panel">
    <h2>裝置與連線資訊</h2>
    <div class="stats-grid" id="deviceInfo"></div>
    <p class="note" id="gapNote"></p>
  </section>

  <section class="panel">
    <h2>封包時序明細 <span class="meta">共 {meta["total_packets"]} 筆</span></h2>
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th>時間</th><th>類型</th><th>Fcnt</th><th>DR</th><th>Freq</th>
            <th>RSSI</th><th>SNR</th><th>Size</th><th>內容</th>
          </tr>
        </thead>
        <tbody id="timelineBody"></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>感測讀數明細 <span class="meta">{meta["sensor_packets"]} 筆環境封包</span></h2>
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th>時間</th><th>Temp</th><th>RH</th><th>CO₂</th><th>TVOC</th>
            <th>PM2.5</th><th>PM10</th><th>Press</th><th>Light</th><th>PIR</th>
            <th>RSSI</th><th>SNR</th><th>Fcnt</th>
          </tr>
        </thead>
        <tbody id="sensorBody"></tbody>
      </table>
    </div>
  </section>
</main>

<footer>
  UG65_V5_cursor_grok.html · 資料來源 {meta["source"]} · 僅供分析檢視，空氣品質分級為一般參考閾值
</footer>

<script>
const DATA = {DATA_JSON};

const COLORS = {{
  temp: '#ff7b72', hum: '#58a6ff', co2: '#d2a8ff', tvoc: '#7ee787',
  pm25: '#ffa657', pm10: '#ffd580', hcho: '#f07178', press: '#79c0ff',
  light: '#e3b341', pir: '#c9a0ff', rssi: '#ff9bce', snr: '#a5d6ff',
  grid: 'rgba(139,155,180,.18)', text: '#8b9bb4'
}};

Chart.defaults.color = COLORS.text;
Chart.defaults.borderColor = COLORS.grid;
Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

function fmt(v, digits=1) {{
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return typeof v === 'number' ? v.toFixed(digits) : v;
}}

function kpiClass(level) {{
  if (level === '優良' || level === '良好') return 'good';
  if (level === '偏高') return 'warn';
  if (level === '較差') return 'bad';
  return '';
}}

function renderKpis() {{
  const m = DATA.meta;
  const ms = m.metric_stats;
  const items = [
    {{ label: '總封包', value: m.total_packets, hint: Object.entries(m.type_counts).map(([k,v])=>k+':'+v).join(' · ') }},
    {{ label: '感測上行', value: m.sensor_packets, hint: '含溫濕度/空氣品質 JSON' }},
    {{ label: '平均溫度', value: fmt(ms.temperature?.avg) + ' °C', hint: `範圍 ${{fmt(ms.temperature?.min)}}–${{fmt(ms.temperature?.max)}}` }},
    {{ label: '平均濕度', value: fmt(ms.humidity?.avg, 1) + ' %', hint: `範圍 ${{fmt(ms.humidity?.min,0)}}–${{fmt(ms.humidity?.max,0)}}` }},
    {{ label: '平均 CO₂', value: fmt(ms.co2?.avg, 0) + ' ppm', hint: m.aqi_notes.co2_level, cls: kpiClass(m.aqi_notes.co2_level) }},
    {{ label: '平均 PM2.5', value: fmt(ms.pm2_5?.avg, 1) + ' µg/m³', hint: m.aqi_notes.pm25_level, cls: kpiClass(m.aqi_notes.pm25_level) }},
    {{ label: '平均 RSSI', value: fmt(m.link_rssi?.avg, 1) + ' dBm', hint: `min ${{fmt(m.link_rssi?.min,0)}}` }},
    {{ label: '平均 SNR', value: fmt(m.link_snr?.avg, 1) + ' dB', hint: `min ${{fmt(m.link_snr?.min,1)}}` }},
  ];
  document.getElementById('kpis').innerHTML = items.map(it => `
    <div class="kpi ${{it.cls||''}}">
      <div class="label">${{it.label}}</div>
      <div class="value">${{it.value}}</div>
      <div class="hint">${{it.hint||''}}</div>
    </div>`).join('');
}}

function lineOpts(yTitle, y2Title) {{
  const scales = {{
    x: {{ ticks: {{ maxRotation: 0, autoSkip: true, maxTicksLimit: 8 }}, grid: {{ color: COLORS.grid }} }},
    y: {{ title: {{ display: !!yTitle, text: yTitle }}, grid: {{ color: COLORS.grid }} }}
  }};
  if (y2Title) {{
    scales.y2 = {{ position: 'right', title: {{ display: true, text: y2Title }}, grid: {{ drawOnChartArea: false }} }};
  }}
  return {{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ position: 'top', labels: {{ boxWidth: 12, usePointStyle: true }} }},
      tooltip: {{ callbacks: {{
        title: (items) => DATA.chart.fullTimes[items[0].dataIndex] || items[0].label
      }} }}
    }},
    scales
  }};
}}

function renderCharts() {{
  const c = DATA.chart;
  const labels = c.labels;

  new Chart(document.getElementById('chartEnv'), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: '溫度 °C', data: c.temperature, borderColor: COLORS.temp, backgroundColor: COLORS.temp+'33', tension: .3, yAxisID: 'y', pointRadius: 3 }},
        {{ label: '濕度 %', data: c.humidity, borderColor: COLORS.hum, backgroundColor: COLORS.hum+'33', tension: .3, yAxisID: 'y', pointRadius: 3 }},
        {{ label: 'TVOC', data: c.tvoc, borderColor: COLORS.tvoc, backgroundColor: COLORS.tvoc+'33', tension: .3, yAxisID: 'y', pointRadius: 3 }},
        {{ label: 'CO₂ ppm', data: c.co2, borderColor: COLORS.co2, backgroundColor: COLORS.co2+'33', tension: .3, yAxisID: 'y2', pointRadius: 3, borderWidth: 2 }},
      ]
    }},
    options: lineOpts('°C / % / TVOC', 'CO₂ ppm')
  }});

  new Chart(document.getElementById('chartPM'), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: 'PM2.5', data: c.pm25, borderColor: COLORS.pm25, tension: .3, pointRadius: 3 }},
        {{ label: 'PM10', data: c.pm10, borderColor: COLORS.pm10, tension: .3, pointRadius: 3 }},
        {{ label: 'HCHO', data: c.hcho, borderColor: COLORS.hcho, tension: .3, pointRadius: 3 }},
      ]
    }},
    options: lineOpts('µg/m³')
  }});

  new Chart(document.getElementById('chartPress'), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: '氣壓 hPa', data: c.pressure, borderColor: COLORS.press, tension: .3, yAxisID: 'y', pointRadius: 3 }},
        {{ label: '光照等級', data: c.light, borderColor: COLORS.light, tension: .3, yAxisID: 'y2', pointRadius: 3, stepped: false }},
        {{ label: 'PIR', data: c.pir, borderColor: COLORS.pir, tension: 0, yAxisID: 'y2', pointRadius: 4, showLine: true }},
      ]
    }},
    options: lineOpts('hPa', 'Light / PIR')
  }});

  new Chart(document.getElementById('chartLink'), {{
    type: 'line',
    data: {{
      labels,
      datasets: [
        {{ label: 'RSSI dBm', data: c.rssi, borderColor: COLORS.rssi, tension: .3, yAxisID: 'y', pointRadius: 3 }},
        {{ label: 'SNR dB', data: c.snr, borderColor: COLORS.snr, tension: .3, yAxisID: 'y2', pointRadius: 3 }},
      ]
    }},
    options: lineOpts('RSSI dBm', 'SNR dB')
  }});

  const typeLabels = Object.keys(DATA.meta.type_counts);
  const typeValues = Object.values(DATA.meta.type_counts);
  const typeColors = {{ UpUnc: '#3ecf8e', DnUnc: '#3d9cf0', JnReq: '#f0b429', JnAcc: '#c9a0ff' }};

  new Chart(document.getElementById('chartTypes'), {{
    type: 'bar',
    data: {{
      labels: typeLabels,
      datasets: [{{
        label: '封包數',
        data: typeValues,
        backgroundColor: typeLabels.map(t => typeColors[t] || '#8b9bb4'),
        borderRadius: 6,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }}, grid: {{ color: COLORS.grid }} }},
        x: {{ grid: {{ display: false }} }}
      }}
    }}
  }});

  const freqLabels = Object.keys(DATA.meta.freq_counts);
  const freqValues = Object.values(DATA.meta.freq_counts);
  new Chart(document.getElementById('chartFreq'), {{
    type: 'bar',
    data: {{
      labels: freqLabels.map(f => f + ' MHz'),
      datasets: [{{
        label: '次數',
        data: freqValues,
        backgroundColor: '#3d9cf0aa',
        borderColor: '#3d9cf0',
        borderWidth: 1,
        borderRadius: 6,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }}, grid: {{ color: COLORS.grid }} }},
        x: {{ ticks: {{ maxRotation: 45, minRotation: 0 }}, grid: {{ display: false }} }}
      }}
    }}
  }});
}}

function renderStats() {{
  const ms = DATA.meta.metric_stats;
  const order = [
    ['temperature','溫度 °C'],['humidity','濕度 %'],['co2','CO₂ ppm'],['tvoc','TVOC'],
    ['pm2_5','PM2.5'],['pm10','PM10'],['pressure','氣壓 hPa'],['hcho','HCHO'],
    ['light_level','光照'],['pir','PIR']
  ];
  document.getElementById('stats').innerHTML = order.map(([k, title]) => {{
    const s = ms[k];
    if (!s) return '';
    return `<div class="stat-card"><h3>${{title}}</h3>
      <dl>
        <dt>樣本</dt><dd>${{s.n}}</dd>
        <dt>最小</dt><dd>${{fmt(s.min, k==='co2'?0:2)}}</dd>
        <dt>最大</dt><dd>${{fmt(s.max, k==='co2'?0:2)}}</dd>
        <dt>平均</dt><dd>${{fmt(s.avg, k==='co2'?0:2)}}</dd>
        <dt>中位</dt><dd>${{fmt(s.med, k==='co2'?0:2)}}</dd>
        <dt>標準差</dt><dd>${{fmt(s.std, 2)}}</dd>
      </dl></div>`;
  }}).join('');

  const di = DATA.meta.device_info;
  const dr = DATA.meta.dr_counts;
  document.getElementById('deviceInfo').innerHTML = `
    <div class="stat-card"><h3>裝置</h3>
      <dl>
        <dt>DevEUI</dt><dd>${{DATA.meta.device}}</dd>
        <dt>Gateway</dt><dd>${{DATA.meta.gateway}}</dd>
        <dt>SN</dt><dd>${{di.sn || '—'}}</dd>
        <dt>FW / HW</dt><dd>${{di.firmware_version || '—'}} / ${{di.hardware_version || '—'}}</dd>
        <dt>IPSO</dt><dd>${{di.ipso_version || '—'}}</dd>
        <dt>Class</dt><dd>${{di.lorawan_class != null ? 'Class ' + ({{0:'A',1:'B',2:'C'}}[di.lorawan_class] || di.lorawan_class) : '—'}}</dd>
      </dl>
    </div>
    <div class="stat-card"><h3>資料速率</h3>
      <dl>${{Object.entries(dr).map(([k,v])=>`<dt>${{k}}</dt><dd>${{v}}</dd>`).join('')}}</dl>
    </div>
    <div class="stat-card"><h3>鏈路（全量有值）</h3>
      <dl>
        <dt>RSSI avg</dt><dd>${{fmt(DATA.meta.link_rssi?.avg,1)}} dBm</dd>
        <dt>RSSI range</dt><dd>${{fmt(DATA.meta.link_rssi?.min,0)}} ~ ${{fmt(DATA.meta.link_rssi?.max,0)}}</dd>
        <dt>SNR avg</dt><dd>${{fmt(DATA.meta.link_snr?.avg,1)}} dB</dd>
        <dt>SNR range</dt><dd>${{fmt(DATA.meta.link_snr?.min,1)}} ~ ${{fmt(DATA.meta.link_snr?.max,1)}}</dd>
      </dl>
    </div>
    <div class="stat-card"><h3>觀測時段</h3>
      <dl>
        <dt>開始</dt><dd>${{DATA.meta.time_start}}</dd>
        <dt>結束</dt><dd>${{DATA.meta.time_end}}</dd>
        <dt>來源檔</dt><dd>${{DATA.meta.source}}</dd>
      </dl>
    </div>`;

  const gaps = DATA.meta.fcnt_gaps || [];
  const gapEl = document.getElementById('gapNote');
  if (!gaps.length) {{
    gapEl.textContent = '感測上行 Fcnt 連續性：未發現缺號（於已解析感測封包序列中）。';
  }} else {{
    gapEl.textContent = '感測上行 Fcnt 缺號：' + gaps.map(g => `${{g.from}}→${{g.to}}（缺 ${{g.missing.join(',')}}）`).join('；');
  }}
}}

function renderTables() {{
  const tb = document.getElementById('timelineBody');
  tb.innerHTML = DATA.timeline.map(r => {{
    let content = '—';
    if (r.has_sensor) content = '環境感測';
    else if (r.is_info) content = '裝置資訊';
    else if (r.type === 'JnReq') content = 'Join Request';
    else if (r.type === 'JnAcc') content = 'Join Accept';
    else if (r.type === 'DnUnc') content = '下行';
    return `<tr>
      <td>${{r.time}}</td>
      <td><span class="tag ${{r.type}}">${{r.type}}</span></td>
      <td>${{r.fcnt}}</td>
      <td>${{r.dr}}</td>
      <td>${{r.freq}}</td>
      <td>${{r.rssi ?? '—'}}</td>
      <td>${{r.snr ?? '—'}}</td>
      <td>${{r.size}}</td>
      <td>${{content}}</td>
    </tr>`;
  }}).join('');

  const sb = document.getElementById('sensorBody');
  sb.innerHTML = DATA.sensors.map(r => {{
    const p = r.payload;
    return `<tr>
      <td>${{r.time}}</td>
      <td>${{p.temperature}}</td>
      <td>${{p.humidity}}</td>
      <td>${{p.co2}}</td>
      <td>${{p.tvoc}}</td>
      <td>${{p.pm2_5}}</td>
      <td>${{p.pm10}}</td>
      <td>${{p.pressure}}</td>
      <td>${{p.light_level}}</td>
      <td>${{p.pir}}</td>
      <td>${{r.rssi ?? '—'}}</td>
      <td>${{r.snr ?? '—'}}</td>
      <td>${{r.fcnt}}</td>
    </tr>`;
  }}).join('');
}}

renderKpis();
renderCharts();
renderStats();
renderTables();
</script>
</body>
</html>
"""

OUT_PATH.write_text(html, encoding="utf-8")
print(f"Wrote {OUT_PATH}")
print(f"packets={len(records)} sensors={len(sensors)} types={dict(type_counts)}")
print(f"fcnt_gaps={fcnt_gaps}")
print(f"time {t0} -> {t1}")
