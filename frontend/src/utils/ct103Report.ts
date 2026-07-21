import type { Ug65Row } from '@/api/milesight'
import type { EChartsCoreOption } from 'echarts/core'
import {
  baseLineOption,
  chartColors,
  chronological,
  filterByEui,
  formatNum,
  metricStats,
  num,
  payloadList,
  rangeText,
  shortTime,
  singleMetricOption,
  timeOverview,
} from './reportCommon'
export const CT103_EUI = '24E124746E228250'

export const TEMP_STATUS_LABEL: Record<number, string> = {
  0: 'Normal',
  1: 'Installed',
  2: 'Temperature sensor not installed',
}

export function ct103Rows(rows: Ug65Row[]) {
  return filterByEui(rows, CT103_EUI)
}

export function buildCt103Overview(rows: Ug65Row[]) {
  const sensor = ct103Rows(rows)
  const chrono = chronological(sensor)
  const payloads = payloadList(chrono)
  const currents = payloads.map((p) => num(p.current))
  const totals = payloads.map((p) => num(p.total_current))
  const temps = payloads.map((p) => num(p.temperature))
  const statuses = payloads.map((p) => num(p.temperature_sensor_status))
  const currentStats = metricStats(currents)
  const totalStats = metricStats(totals)
  const tempStats = metricStats(temps)
  const time = timeOverview(sensor)
  const activeCount = currents.filter((v) => (v ?? 0) > 0).length
  const loadRatio = currents.length ? (activeCount / currents.length) * 100 : 0
  const status2 = statuses.filter((v) => v === 2).length
  const withTemp = temps.filter((v) => v != null).length
  const latest = payloads[payloads.length - 1] || {}
  const latestCurrent = num(latest.current)
  const latestRssi = chrono[chrono.length - 1]?.rssi ?? null
  const latestSnr = chrono[chrono.length - 1]?.lora_snr ?? null
  const rssiStats = metricStats(chrono.map((r) => num(r.rssi)))
  const snrStats = metricStats(chrono.map((r) => num(r.lora_snr)))

  let loadLevel: 'idle' | 'medium' | 'high' = 'idle'
  if ((latestCurrent ?? 0) >= 1) loadLevel = 'high'
  else if ((latestCurrent ?? 0) > 0) loadLevel = 'medium'

  return {
    packetCount: sensor.length,
    time,
    currentStats,
    totalStats,
    tempStats,
    loadRatio,
    status2,
    withTemp,
    latestCurrent,
    latestTotal: num(latest.total_current),
    latestTemp: num(latest.temperature),
    latestTempStatus: num(latest.temperature_sensor_status),
    latestRssi,
    latestSnr,
    rssiStats,
    snrStats,
    loadLevel,
    currents,
    totals,
    temps,
    statuses,
    times: chrono.map((r) => shortTime(r.received_at)),
    chrono,
    payloads,
  }
}

export function buildCt103Insights(ov: ReturnType<typeof buildCt103Overview>, labels: {
  idlePackets: string
  currentRange: string
  totalRise: string
  tempNote: string
  under6a: string
  signal: string
  interval: string
}) {
  const idle = ov.currents.filter((v) => (v ?? 0) === 0).length
  const items = [
    labels.idlePackets
      .replace('{idle}', String(idle))
      .replace('{total}', String(ov.packetCount))
      .replace('{ratio}', formatNum(100 - ov.loadRatio, 1)),
    labels.currentRange
      .replace('{min}', formatNum(ov.currentStats.min, 2))
      .replace('{max}', formatNum(ov.currentStats.max, 2))
      .replace('{avg}', formatNum(ov.currentStats.avg, 2)),
    labels.totalRise
      .replace('{from}', formatNum(ov.totalStats.min, 2))
      .replace('{to}', formatNum(ov.totalStats.max, 2)),
    labels.tempNote
      .replace('{with}', String(ov.withTemp))
      .replace('{total}', String(ov.packetCount))
      .replace('{status2}', String(ov.status2)),
    labels.under6a,
    labels.signal
      .replace('{rssi}', formatNum(ov.rssiStats.avg, 1))
      .replace('{snr}', formatNum(ov.snrStats.avg, 1)),
  ]
  if (ov.time.intervalSec != null) {
    items.push(labels.interval.replace('{sec}', formatNum(ov.time.intervalSec, 0)))
  }
  return items
}

export function buildCt103MainOption(
  ov: ReturnType<typeof buildCt103Overview>,
  metric: 'current' | 'total_current',
  label: string,
): EChartsCoreOption {
  const data = metric === 'current' ? ov.currents : ov.totals
  const unit = metric === 'current' ? 'A' : 'A·h'
  const color = metric === 'current' ? chartColors.current : chartColors.total
  return singleMetricOption(ov.times, data, label, color, unit)
}

export function buildCt103CompareOption(
  ov: ReturnType<typeof buildCt103Overview>,
  labels: { current: string; total: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.current,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: chartColors.current },
        itemStyle: { color: chartColors.current },
        data: ov.currents,
      },
      {
        name: labels.total,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.total },
        itemStyle: { color: chartColors.total },
        data: ov.totals,
      },
    ],
    {
      legend: {
        data: [labels.current, labels.total],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 52, bottom: 48, left: 52 },
      yAxis: [
        {
          type: 'value',
          name: 'A',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: chartColors.line } },
        },
        {
          type: 'value',
          name: 'A·h',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
    },
  )
}

export function buildCt103TempOption(ov: ReturnType<typeof buildCt103Overview>, label: string): EChartsCoreOption {
  return singleMetricOption(ov.times, ov.temps, label, chartColors.temp, '°C')
}

export function buildCt103TempStatusOption(
  ov: ReturnType<typeof buildCt103Overview>,
  label: string,
): EChartsCoreOption {
  return baseLineOption(ov.times, [
    {
      name: label,
      type: 'line',
      step: 'middle',
      showSymbol: false,
      lineStyle: { width: 2, color: chartColors.status },
      itemStyle: { color: chartColors.status },
      areaStyle: { color: `${chartColors.status}22` },
      data: ov.statuses,
    },
  ], {
    yAxis: {
      type: 'value',
      min: 0,
      max: 2.5,
      interval: 1,
      axisLabel: {
        color: chartColors.muted,
        fontSize: 10,
        formatter: (v: number) =>
          ({ 0: '—', 1: 'Installed', 2: 'N/A' } as Record<number, string>)[v] || String(v),
      },
      splitLine: { lineStyle: { color: chartColors.line } },
    },
  })
}

export function buildCt103HistOption(ov: ReturnType<typeof buildCt103Overview>, label: string): EChartsCoreOption {
  const vals = ov.currents.filter((v): v is number => v != null && v > 0)
  const bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
  const counts = bins.slice(0, -1).map((b, i) => vals.filter((v) => v >= b && v < bins[i + 1]).length)
  const labels = bins.slice(0, -1).map((b, i) => `${b}-${bins[i + 1]}`)
  return {
    color: [chartColors.current],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 18, bottom: 36, left: 48 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: chartColors.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: chartColors.line } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: chartColors.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: chartColors.line } },
    },
    series: [
      {
        name: label,
        type: 'bar',
        barMaxWidth: 28,
        data: counts,
        itemStyle: { color: chartColors.current },
      },
    ],
  }
}

export function buildCt103LoadOption(ov: ReturnType<typeof buildCt103Overview>, label: string): EChartsCoreOption {
  return baseLineOption(ov.times, [
    {
      name: label,
      type: 'line',
      step: 'middle',
      showSymbol: false,
      areaStyle: { color: `${chartColors.load}33` },
      lineStyle: { width: 2, color: chartColors.load },
      itemStyle: { color: chartColors.load },
      data: ov.currents.map((v) => ((v ?? 0) > 0 ? 1 : 0)),
    },
  ], {
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      interval: 1,
      axisLabel: { color: chartColors.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: chartColors.line } },
    },
  })
}

export function buildCt103SignalOption(
  ov: ReturnType<typeof buildCt103Overview>,
  labels: { rssi: string; snr: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.rssi,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: chartColors.signal },
        itemStyle: { color: chartColors.signal },
        data: ov.chrono.map((r) => num(r.rssi)),
      },
      {
        name: labels.snr,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.snr },
        itemStyle: { color: chartColors.snr },
        data: ov.chrono.map((r) => num(r.lora_snr)),
      },
    ],
    {
      legend: {
        data: [labels.rssi, labels.snr],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 52, bottom: 48, left: 52 },
      yAxis: [
        {
          type: 'value',
          name: 'dBm',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: chartColors.line } },
        },
        {
          type: 'value',
          name: 'dB',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
    },
  )
}

export function ct103RangeLine(stats: ReturnType<typeof metricStats>, digits = 2) {
  return rangeText(stats, digits)
}
