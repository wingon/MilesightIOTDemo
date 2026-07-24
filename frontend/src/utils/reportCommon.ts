import type { Ug65Row } from '@/api/milesight'
import { brand } from '@/theme/colorConfig'
import type { EChartsCoreOption } from 'echarts/core'

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

export function num(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value)
    return Number.isFinite(n) ? n : null
  }
  return null
}

export function shortTime(value: string) {
  const part = value.includes('T') ? value.split('T')[1] : value.split(' ')[1]
  return (part || value).slice(0, 8)
}

/** Resolve gateway model (ug65 / ug56) from row field or topic path. */
export function resolveGatewayModel(row: Pick<Ug65Row, 'gateway_model' | 'topic'>): string | null {
  const fromField = (row.gateway_model || '').trim().toLowerCase()
  if (fromField === 'ug65' || fromField === 'ug56') return fromField.toUpperCase()
  const match = (row.topic || '').match(/^milesight\/(ug65|ug56)(?:\/|$)/i)
  return match ? match[1].toUpperCase() : null
}

/** Latest uplink's gateway model (API returns newest first). */
export function latestGatewayModel(rows: Array<Pick<Ug65Row, 'gateway_model' | 'topic'>>): string | null {
  for (const row of rows) {
    const model = resolveGatewayModel(row)
    if (model) return model
  }
  return null
}

/** Display datetime as YYYY-MM-DD HH:MM:SS (no milliseconds). */
export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null
  const normalized = value.trim().replace('T', ' ')
  const match = normalized.match(
    /^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})/,
  )
  if (!match) {
    const fallback = normalized.slice(0, 19)
    return fallback || null
  }
  const [, yyyy, mo, dd, hh, mm, ss] = match
  const pad = (n: string) => n.padStart(2, '0')
  return `${yyyy}-${mo}-${dd} ${pad(hh)}:${pad(mm)}:${pad(ss)}`
}

/**
 * Table / UI timestamps in Asia/Hong_Kong (UTC+8), full year:
 * YYYY-MM-DD HH:MM:SS
 *
 * MariaDB CURRENT_TIMESTAMP / naive DATETIME from this project are UTC.
 * Strings with explicit offsets (e.g. gatewayTime ...+08:00) are converted via that offset.
 */
export function formatTableTime(value: string | null | undefined): string {
  return formatTableTimeUtcPlus8(value)
}

/** @deprecated alias — use formatTableTime */
export function formatTableTimeUtcPlus8(value: string | null | undefined): string {
  if (!value) return '—'
  const text = value.trim()

  const offsetMatch = text.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?([+-]\d{2}):?(\d{2})$/,
  )
  if (offsetMatch) {
    const [, y, mo, d, hh, mm, ss, offH, offM] = offsetMatch
    const sign = offH.startsWith('-') ? -1 : 1
    const offsetMin = sign * (Math.abs(Number(offH)) * 60 + Number(offM))
    const utcMs =
      Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(hh), Number(mm), Number(ss)) -
      offsetMin * 60_000
    return formatUtcMsAsHkt(utcMs)
  }

  const zMatch = text.match(
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?Z$/i,
  )
  if (zMatch) {
    const [, y, mo, d, hh, mm, ss] = zMatch
    const utcMs = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(hh), Number(mm), Number(ss))
    return formatUtcMsAsHkt(utcMs)
  }

  // Naive MariaDB DATETIME — treat as UTC (matches docker MariaDB default TZ)
  const naive = text.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{1,2}):(\d{1,2}):(\d{1,2})/)
  if (naive) {
    const [, y, mo, d, hh, mm, ss] = naive
    const utcMs = Date.UTC(Number(y), Number(mo) - 1, Number(d), Number(hh), Number(mm), Number(ss))
    return formatUtcMsAsHkt(utcMs)
  }

  return formatDateTime(text) || '—'
}

function formatUtcMsAsHkt(utcMs: number): string {
  if (!Number.isFinite(utcMs)) return '—'
  const hkt = new Date(utcMs + 8 * 3600_000)
  const y = String(hkt.getUTCFullYear())
  const mo = String(hkt.getUTCMonth() + 1).padStart(2, '0')
  const d = String(hkt.getUTCDate()).padStart(2, '0')
  const hh = String(hkt.getUTCHours()).padStart(2, '0')
  const mm = String(hkt.getUTCMinutes()).padStart(2, '0')
  const ss = String(hkt.getUTCSeconds()).padStart(2, '0')
  return `${y}-${mo}-${d} ${hh}:${mm}:${ss}`
}

/** Prefer gatewayTime from payload, then uplink_time column. */
export function rowUplinkTime(row: Pick<Ug65Row, 'uplink_time' | 'payload_json'>): string | null {
  const payload = asRecord(row.payload_json)
  const gatewayTime = payload?.gatewayTime
  if (typeof gatewayTime === 'string' && gatewayTime.trim()) return gatewayTime.trim()
  return row.uplink_time || null
}

export function filterByEui(rows: Ug65Row[], eui: string) {
  const target = eui.toUpperCase()
  return rows.filter((r) => (r.dev_eui || '').toUpperCase() === target)
}

/** Chronological ascending for charts (API returns newest-first) */
export function chronological<T>(rows: T[]): T[] {
  return [...rows].reverse()
}

export function payloadList(rows: Ug65Row[]) {
  return rows.map((r) => asRecord(r.payload_json) || {})
}

export interface MetricStats {
  latest: number | null
  min: number | null
  max: number | null
  avg: number | null
  count: number
}

export function metricStats(values: Array<number | null | undefined>): MetricStats {
  const nums = values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
  if (!nums.length) {
    return { latest: null, min: null, max: null, avg: null, count: 0 }
  }
  const sum = nums.reduce((a, b) => a + b, 0)
  return {
    latest: nums[nums.length - 1] ?? null,
    min: Math.min(...nums),
    max: Math.max(...nums),
    avg: sum / nums.length,
    count: nums.length,
  }
}

export function formatNum(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) return '—'
  return Number(value.toFixed(digits)).toString()
}

export function timeOverview(rows: Array<{ received_at: string }>) {
  if (!rows.length) {
    return { from: null as string | null, to: null as string | null, hours: null as number | null, intervalSec: null as number | null }
  }
  const chrono = chronological(rows)
  const fromRaw = chrono[0]?.received_at || null
  const toRaw = chrono[chrono.length - 1]?.received_at || null
  const from = formatDateTime(fromRaw)
  const to = formatDateTime(toRaw)
  let hours: number | null = null
  let intervalSec: number | null = null
  if (fromRaw && toRaw) {
    const a = Date.parse(fromRaw.replace(' ', 'T'))
    const b = Date.parse(toRaw.replace(' ', 'T'))
    if (Number.isFinite(a) && Number.isFinite(b) && b >= a) {
      hours = (b - a) / 3600000
      if (chrono.length >= 2) {
        const gaps: number[] = []
        for (let i = 1; i < chrono.length; i++) {
          const t0 = Date.parse((chrono[i - 1].received_at || '').replace(' ', 'T'))
          const t1 = Date.parse((chrono[i].received_at || '').replace(' ', 'T'))
          if (Number.isFinite(t0) && Number.isFinite(t1) && t1 > t0) gaps.push((t1 - t0) / 1000)
        }
        if (gaps.length) {
          gaps.sort((x, y) => x - y)
          intervalSec = gaps[Math.floor(gaps.length / 2)]
        }
      }
    }
  }
  return { from, to, hours, intervalSec }
}

export function rangeText(stats: MetricStats, digits = 1) {
  if (!stats.count) return '—'
  return `Range ${formatNum(stats.min, digits)} – ${formatNum(stats.max, digits)} · avg ${formatNum(stats.avg, digits)}`
}

export const chartColors = {
  gold: brand.primary,
  ink: brand.ink,
  charcoal: brand.charcoal,
  muted: brand.muted,
  line: brand.line,
  current: '#C4A574',
  total: '#8B7355',
  temp: '#5B7C99',
  status: '#A88955',
  signal: '#6B6B6B',
  snr: '#8B5A2B',
  load: '#3D7A5A',
  co2: '#8B7355',
  humidity: '#5B7C99',
  pm25: '#A88955',
  pm10: '#6B6B6B',
  tvoc: '#3D7A5A',
  hcho: '#B42318',
  pressure: '#4A5568',
  light: '#C4A574',
  pir: '#8B5A2B',
} as const

export function baseLineOption(
  times: string[],
  series: EChartsCoreOption['series'],
  extra?: Partial<EChartsCoreOption>,
): EChartsCoreOption {
  return {
    color: [chartColors.gold, chartColors.total, chartColors.temp, chartColors.signal],
    tooltip: { trigger: 'axis' },
    grid: { top: 36, right: 48, bottom: 36, left: 52 },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { color: brand.muted, fontSize: 10 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: brand.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: brand.line } },
    },
    series,
    ...extra,
  }
}

export function singleMetricOption(
  times: string[],
  data: Array<number | null>,
  label: string,
  color: string,
  unit = '',
): EChartsCoreOption {
  return baseLineOption(times, [
    {
      name: unit ? `${label} (${unit})` : label,
      type: 'line',
      smooth: true,
      showSymbol: false,
      areaStyle: { color: `${color}28` },
      lineStyle: { width: 2, color },
      itemStyle: { color },
      data,
    },
  ])
}
