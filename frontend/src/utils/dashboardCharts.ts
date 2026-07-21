import type { TofRow, Ug65Row } from '@/api/milesight'
import { brand } from '@/theme/colorConfig'
import type { EChartsCoreOption } from 'echarts/core'

export const AIR_EUI = '24E124710E317752'
export const CT103_EUI = '24E124746E228250'

function shortTime(value: string) {
  const part = value.includes('T') ? value.split('T')[1] : value.split(' ')[1]
  return (part || value).slice(0, 5)
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function num(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function buildPeopleOption(
  rows: TofRow[],
  labels: { periodIn: string; periodOut: string; cumulative: string; inCounted: string; outCounted: string },
): EChartsCoreOption {
  const chronological = [...rows].reverse()
  const times = chronological.map((r) => shortTime(r.received_at))
  const periodIn = chronological.map((r) => {
    const item = Array.isArray(r.line_periodic_data) ? r.line_periodic_data[0] : null
    return num(asRecord(item)?.in) ?? 0
  })
  const periodOut = chronological.map((r) => {
    const item = Array.isArray(r.line_periodic_data) ? r.line_periodic_data[0] : null
    return num(asRecord(item)?.out) ?? 0
  })
  const inCounted = chronological.map((r) => {
    const item = Array.isArray(r.line_total_data) ? r.line_total_data[0] : null
    return num(asRecord(item)?.in_counted) ?? 0
  })
  const outCounted = chronological.map((r) => {
    const item = Array.isArray(r.line_total_data) ? r.line_total_data[0] : null
    return num(asRecord(item)?.out_counted) ?? 0
  })

  return {
    color: [brand.primary, brand.charcoal, '#8B7355', '#4A5568'],
    tooltip: { trigger: 'axis' },
    legend: {
      data: [labels.periodIn, labels.periodOut, labels.inCounted, labels.outCounted],
      bottom: 0,
      textStyle: { color: brand.muted, fontSize: 11 },
    },
    grid: { top: 28, right: 18, bottom: 48, left: 48 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: brand.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: [
      {
        type: 'value',
        name: labels.periodIn,
        minInterval: 1,
        axisLabel: { color: brand.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: brand.line } },
      },
      {
        type: 'value',
        name: labels.cumulative,
        minInterval: 1,
        axisLabel: { color: brand.muted, fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      { name: labels.periodIn, type: 'bar', data: periodIn, barMaxWidth: 14 },
      { name: labels.periodOut, type: 'bar', data: periodOut, barMaxWidth: 14 },
      {
        name: labels.inCounted,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: inCounted,
      },
      {
        name: labels.outCounted,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: outCounted,
      },
    ],
  }
}

export type AirMetricKey = 'co2' | 'temperature' | 'humidity' | 'pm2_5'

export function buildAirMetricOption(
  rows: Ug65Row[],
  metric: AirMetricKey,
  label: string,
  unit: string,
  color: string = brand.primary,
): EChartsCoreOption {
  const air = [...rows]
    .filter((r) => (r.dev_eui || '').toUpperCase() === AIR_EUI)
    .reverse()
  const times = air.map((r) => shortTime(r.received_at))
  const payload = air.map((r) => asRecord(r.payload_json) || {})

  return {
    color: [color],
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: unknown) =>
        value == null ? '-' : `${value}${unit ? ` ${unit}` : ''}`,
    },
    grid: { top: 28, right: 18, bottom: 28, left: 48 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: brand.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: {
      type: 'value',
      name: unit,
      axisLabel: { color: brand.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        name: label,
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: { color: `${color}2E` },
        data: payload.map((p) => num(p[metric])),
      },
    ],
  }
}

export function buildCurrentOption(
  rows: Ug65Row[],
  labels: { current: string; totalCurrent: string },
): EChartsCoreOption {
  const ct = [...rows]
    .filter((r) => (r.dev_eui || '').toUpperCase() === CT103_EUI)
    .reverse()
  const times = ct.map((r) => shortTime(r.received_at))
  const payload = ct.map((r) => asRecord(r.payload_json) || {})

  return {
    color: [brand.primary, brand.charcoal],
    tooltip: { trigger: 'axis' },
    legend: {
      data: [labels.current, labels.totalCurrent],
      bottom: 0,
      textStyle: { color: brand.muted, fontSize: 11 },
    },
    grid: { top: 28, right: 48, bottom: 48, left: 48 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: brand.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: [
      {
        type: 'value',
        name: 'A',
        axisLabel: { color: brand.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: brand.line } },
      },
      {
        type: 'value',
        name: 'ΣA',
        axisLabel: { color: brand.muted, fontSize: 10 },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: labels.current,
        type: 'line',
        smooth: true,
        showSymbol: false,
        areaStyle: { color: 'rgba(196,165,116,0.18)' },
        data: payload.map((p) => num(p.current)),
      },
      {
        name: labels.totalCurrent,
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: payload.map((p) => num(p.total_current)),
      },
    ],
  }
}

export function latestAirSnapshot(rows: Ug65Row[]) {
  const latest = rows.find((r) => (r.dev_eui || '').toUpperCase() === AIR_EUI)
  return asRecord(latest?.payload_json)
}

export function latestCurrentSnapshot(rows: Ug65Row[]) {
  const latest = rows.find((r) => (r.dev_eui || '').toUpperCase() === CT103_EUI)
  return asRecord(latest?.payload_json)
}

export function latestPeopleSnapshot(rows: TofRow[]) {
  const latest = rows[0]
  if (!latest) return null
  const periodic = Array.isArray(latest.line_periodic_data)
    ? asRecord(latest.line_periodic_data[0])
    : null
  const total = Array.isArray(latest.line_total_data)
    ? asRecord(latest.line_total_data[0])
    : null
  return { periodic, total }
}
