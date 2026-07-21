import type { TofRow } from '@/api/milesight'
import type { EChartsCoreOption } from 'echarts/core'
import {
  asRecord,
  baseLineOption,
  chartColors,
  chronological,
  formatNum,
  metricStats,
  num,
  rangeText,
  shortTime,
  singleMetricOption,
  timeOverview,
} from './reportCommon'

function periodicOf(row: TofRow) {
  return Array.isArray(row.line_periodic_data) ? asRecord(row.line_periodic_data[0]) : null
}

function totalOf(row: TofRow) {
  return Array.isArray(row.line_total_data) ? asRecord(row.line_total_data[0]) : null
}

export function buildVs135Overview(rows: TofRow[]) {
  const chrono = chronological(rows)
  const times = chrono.map((r) => shortTime(r.received_at))
  const periodIn = chrono.map((r) => num(periodicOf(r)?.in) ?? 0)
  const periodOut = chrono.map((r) => num(periodicOf(r)?.out) ?? 0)
  const inCounted = chrono.map((r) => num(totalOf(r)?.in_counted) ?? 0)
  const outCounted = chrono.map((r) => num(totalOf(r)?.out_counted) ?? 0)
  const netFlow = periodIn.map((v, i) => v - (periodOut[i] ?? 0))

  const periodInStats = metricStats(periodIn)
  const periodOutStats = metricStats(periodOut)
  const inCountedStats = metricStats(inCounted)
  const outCountedStats = metricStats(outCounted)
  const time = timeOverview(rows)

  const devices = new Set(rows.map((r) => r.device_sn).filter(Boolean))
  const latest = rows[0]
  const latestPeriodic = latest ? periodicOf(latest) : null
  const latestTotal = latest ? totalOf(latest) : null

  const sumIn = periodIn.reduce((a, b) => a + b, 0)
  const sumOut = periodOut.reduce((a, b) => a + b, 0)
  const activeRatio =
    periodIn.length > 0
      ? (periodIn.filter((v, i) => v > 0 || (periodOut[i] ?? 0) > 0).length / periodIn.length) * 100
      : 0

  return {
    packetCount: rows.length,
    deviceCount: devices.size,
    deviceSn: latest?.device_sn || null,
    deviceName: latest?.device_name || null,
    time,
    periodInStats,
    periodOutStats,
    inCountedStats,
    outCountedStats,
    latestPeriodIn: num(latestPeriodic?.in),
    latestPeriodOut: num(latestPeriodic?.out),
    latestInCounted: num(latestTotal?.in_counted),
    latestOutCounted: num(latestTotal?.out_counted),
    sumIn,
    sumOut,
    activeRatio,
    times,
    chrono,
    periodIn,
    periodOut,
    inCounted,
    outCounted,
    netFlow,
  }
}

export function buildVs135Insights(
  ov: ReturnType<typeof buildVs135Overview>,
  labels: {
    traffic: string
    peakIn: string
    peakOut: string
    cumulative: string
    activity: string
    interval: string
  },
) {
  const items = [
    labels.traffic.replace('{in}', String(ov.sumIn)).replace('{out}', String(ov.sumOut)),
    labels.peakIn
      .replace('{max}', formatNum(ov.periodInStats.max, 0))
      .replace('{avg}', formatNum(ov.periodInStats.avg, 1)),
    labels.peakOut
      .replace('{max}', formatNum(ov.periodOutStats.max, 0))
      .replace('{avg}', formatNum(ov.periodOutStats.avg, 1)),
    labels.cumulative
      .replace('{in}', formatNum(ov.latestInCounted, 0))
      .replace('{out}', formatNum(ov.latestOutCounted, 0)),
    labels.activity.replace('{ratio}', formatNum(ov.activeRatio, 1)),
  ]
  if (ov.time.intervalSec != null) {
    items.push(labels.interval.replace('{sec}', formatNum(ov.time.intervalSec, 0)))
  }
  return items
}

export type Vs135MainMetric = 'periodIn' | 'periodOut' | 'inCounted' | 'outCounted' | 'netFlow'

export function buildVs135MainOption(
  ov: ReturnType<typeof buildVs135Overview>,
  metric: Vs135MainMetric,
  label: string,
): EChartsCoreOption {
  const map: Record<Vs135MainMetric, Array<number | null>> = {
    periodIn: ov.periodIn,
    periodOut: ov.periodOut,
    inCounted: ov.inCounted,
    outCounted: ov.outCounted,
    netFlow: ov.netFlow,
  }
  const colorMap: Record<Vs135MainMetric, string> = {
    periodIn: chartColors.gold,
    periodOut: chartColors.charcoal,
    inCounted: chartColors.total,
    outCounted: chartColors.temp,
    netFlow: chartColors.load,
  }
  const data = map[metric]
  const color = colorMap[metric]
  if (metric === 'periodIn' || metric === 'periodOut' || metric === 'netFlow') {
    return {
      color: [color],
      tooltip: { trigger: 'axis' },
      grid: { top: 28, right: 18, bottom: 36, left: 48 },
      xAxis: {
        type: 'category',
        data: ov.times,
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
          barMaxWidth: 18,
          itemStyle: { color },
          data,
        },
      ],
    }
  }
  return singleMetricOption(ov.times, data, label, color)
}

export function buildVs135PeriodOption(
  ov: ReturnType<typeof buildVs135Overview>,
  labels: { periodIn: string; periodOut: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.periodIn,
        type: 'bar',
        barMaxWidth: 14,
        itemStyle: { color: chartColors.gold },
        data: ov.periodIn,
      },
      {
        name: labels.periodOut,
        type: 'bar',
        barMaxWidth: 14,
        itemStyle: { color: chartColors.charcoal },
        data: ov.periodOut,
      },
    ],
    {
      legend: {
        data: [labels.periodIn, labels.periodOut],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 18, bottom: 48, left: 48 },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: chartColors.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: chartColors.line } },
      },
    },
  )
}

export function buildVs135CumulativeOption(
  ov: ReturnType<typeof buildVs135Overview>,
  labels: { inCounted: string; outCounted: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.inCounted,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: chartColors.gold },
        itemStyle: { color: chartColors.gold },
        data: ov.inCounted,
      },
      {
        name: labels.outCounted,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: chartColors.charcoal },
        itemStyle: { color: chartColors.charcoal },
        data: ov.outCounted,
      },
    ],
    {
      legend: {
        data: [labels.inCounted, labels.outCounted],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 18, bottom: 48, left: 48 },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: chartColors.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: chartColors.line } },
      },
    },
  )
}

export function buildVs135CombinedOption(
  ov: ReturnType<typeof buildVs135Overview>,
  labels: {
    periodIn: string
    periodOut: string
    inCounted: string
    outCounted: string
    cumulative: string
  },
): EChartsCoreOption {
  return {
    color: [chartColors.gold, chartColors.charcoal, chartColors.total, chartColors.temp],
    tooltip: { trigger: 'axis' },
    legend: {
      data: [labels.periodIn, labels.periodOut, labels.inCounted, labels.outCounted],
      bottom: 0,
      textStyle: { color: chartColors.muted, fontSize: 11 },
    },
    grid: { top: 28, right: 48, bottom: 48, left: 48 },
    xAxis: {
      type: 'category',
      data: ov.times,
      axisLabel: { color: chartColors.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: chartColors.line } },
    },
    yAxis: [
      {
        type: 'value',
        name: labels.periodIn,
        minInterval: 1,
        axisLabel: { color: chartColors.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: chartColors.line } },
      },
      {
        type: 'value',
        name: labels.cumulative,
        minInterval: 1,
        axisLabel: { color: chartColors.muted, fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      { name: labels.periodIn, type: 'bar', barMaxWidth: 12, data: ov.periodIn },
      { name: labels.periodOut, type: 'bar', barMaxWidth: 12, data: ov.periodOut },
      {
        name: labels.inCounted,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: ov.inCounted,
      },
      {
        name: labels.outCounted,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: ov.outCounted,
      },
    ],
  }
}

export function buildVs135NetOption(ov: ReturnType<typeof buildVs135Overview>, label: string) {
  return {
    color: [chartColors.load],
    tooltip: { trigger: 'axis' },
    grid: { top: 28, right: 18, bottom: 36, left: 48 },
    xAxis: {
      type: 'category',
      data: ov.times,
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
        barMaxWidth: 16,
        data: ov.netFlow.map((v) => ({
          value: v,
          itemStyle: { color: v >= 0 ? chartColors.gold : chartColors.charcoal },
        })),
      },
    ],
  } as EChartsCoreOption
}

export function vs135RangeLine(stats: ReturnType<typeof metricStats>, digits = 0) {
  return rangeText(stats, digits)
}
