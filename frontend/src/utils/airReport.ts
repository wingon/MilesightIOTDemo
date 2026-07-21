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

export const AIR_EUI = '24E124710E317752'

export type AirMetric =
  | 'temperature'
  | 'humidity'
  | 'co2'
  | 'pm2_5'
  | 'pm10'
  | 'tvoc'
  | 'hcho'
  | 'pressure'
  | 'light_level'
  | 'pir'

export const AIR_METRIC_META: Record<
  AirMetric,
  { unit: string; color: string }
> = {
  temperature: { unit: '°C', color: chartColors.temp },
  humidity: { unit: '%', color: chartColors.humidity },
  co2: { unit: 'ppm', color: chartColors.co2 },
  pm2_5: { unit: 'µg/m³', color: chartColors.pm25 },
  pm10: { unit: 'µg/m³', color: chartColors.pm10 },
  tvoc: { unit: 'ppb', color: chartColors.tvoc },
  hcho: { unit: 'mg/m³', color: chartColors.hcho },
  pressure: { unit: 'hPa', color: chartColors.pressure },
  light_level: { unit: '', color: chartColors.light },
  pir: { unit: '', color: chartColors.pir },
}

export function airRows(rows: Ug65Row[]) {
  return filterByEui(rows, AIR_EUI)
}

function seriesOf(payloads: Record<string, unknown>[], key: AirMetric) {
  return payloads.map((p) => num(p[key]))
}

export function buildAirOverview(rows: Ug65Row[]) {
  const sensor = airRows(rows)
  const chrono = chronological(sensor)
  const payloads = payloadList(chrono)
  const times = chrono.map((r) => shortTime(r.received_at))
  const time = timeOverview(sensor)

  const metrics = (Object.keys(AIR_METRIC_META) as AirMetric[]).reduce(
    (acc, key) => {
      acc[key] = metricStats(seriesOf(payloads, key))
      return acc
    },
    {} as Record<AirMetric, ReturnType<typeof metricStats>>,
  )

  const pirValues = seriesOf(payloads, 'pir')
  const pirActive = pirValues.filter((v) => (v ?? 0) > 0).length
  const pirRatio = pirValues.length ? (pirActive / pirValues.length) * 100 : 0
  const fcnts = chrono.map((r) => num(r.f_cnt)).filter((v): v is number => v != null)
  const rssiStats = metricStats(chrono.map((r) => num(r.rssi)))
  const snrStats = metricStats(chrono.map((r) => num(r.lora_snr)))

  let aqLevel: 'good' | 'caution' | 'warn' = 'good'
  const co2 = metrics.co2.latest
  if (co2 != null && co2 >= 1200) aqLevel = 'warn'
  else if (co2 != null && co2 >= 1000) aqLevel = 'caution'

  return {
    packetCount: sensor.length,
    time,
    metrics,
    pirRatio,
    fcntMin: fcnts.length ? Math.min(...fcnts) : null,
    fcntMax: fcnts.length ? Math.max(...fcnts) : null,
    rssiStats,
    snrStats,
    aqLevel,
    times,
    chrono,
    payloads,
    series: {
      temperature: seriesOf(payloads, 'temperature'),
      humidity: seriesOf(payloads, 'humidity'),
      co2: seriesOf(payloads, 'co2'),
      pm2_5: seriesOf(payloads, 'pm2_5'),
      pm10: seriesOf(payloads, 'pm10'),
      tvoc: seriesOf(payloads, 'tvoc'),
      hcho: seriesOf(payloads, 'hcho'),
      pressure: seriesOf(payloads, 'pressure'),
      light_level: seriesOf(payloads, 'light_level'),
      pir: seriesOf(payloads, 'pir'),
    },
  }
}

export function buildAirInsights(ov: ReturnType<typeof buildAirOverview>, labels: {
  co2: string
  temperature: string
  pm25: string
  pir: string
  signal: string
}) {
  return [
    labels.co2
      .replace('{from}', formatNum(ov.metrics.co2.max, 0))
      .replace('{to}', formatNum(ov.metrics.co2.latest, 0)),
    labels.temperature
      .replace('{min}', formatNum(ov.metrics.temperature.min, 1))
      .replace('{max}', formatNum(ov.metrics.temperature.max, 1)),
    labels.pm25.replace('{max}', formatNum(ov.metrics.pm2_5.max, 0)),
    labels.pir.replace('{ratio}', formatNum(ov.pirRatio, 1)),
    labels.signal
      .replace('{rssi}', formatNum(ov.rssiStats.avg, 1))
      .replace('{snr}', formatNum(ov.snrStats.avg, 1)),
  ]
}

export function buildAirMainOption(
  ov: ReturnType<typeof buildAirOverview>,
  metric: AirMetric,
  label: string,
): EChartsCoreOption {
  const meta = AIR_METRIC_META[metric]
  return singleMetricOption(ov.times, ov.series[metric], label, meta.color, meta.unit)
}

export function buildAirTempHumOption(
  ov: ReturnType<typeof buildAirOverview>,
  labels: { temperature: string; humidity: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.temperature,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: chartColors.temp },
        itemStyle: { color: chartColors.temp },
        data: ov.series.temperature,
      },
      {
        name: labels.humidity,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.humidity },
        itemStyle: { color: chartColors.humidity },
        data: ov.series.humidity,
      },
    ],
    {
      legend: {
        data: [labels.temperature, labels.humidity],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 52, bottom: 48, left: 52 },
      yAxis: [
        {
          type: 'value',
          name: '°C',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: chartColors.line } },
        },
        {
          type: 'value',
          name: '%',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
    },
  )
}

export function buildAirQualityOption(
  ov: ReturnType<typeof buildAirOverview>,
  labels: { co2: string; pm25: string; pm10: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.co2,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: chartColors.co2 },
        data: ov.series.co2,
      },
      {
        name: labels.pm25,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.pm25 },
        data: ov.series.pm2_5,
      },
      {
        name: labels.pm10,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.pm10 },
        data: ov.series.pm10,
      },
    ],
    {
      legend: {
        data: [labels.co2, labels.pm25, labels.pm10],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 52, bottom: 48, left: 52 },
      yAxis: [
        {
          type: 'value',
          name: 'ppm',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: chartColors.line } },
        },
        {
          type: 'value',
          name: 'µg/m³',
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
    },
  )
}

export function buildAirVocOption(
  ov: ReturnType<typeof buildAirOverview>,
  labels: { tvoc: string; hcho: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.tvoc,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: chartColors.tvoc },
        data: ov.series.tvoc,
      },
      {
        name: labels.hcho,
        type: 'line',
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 2, color: chartColors.hcho },
        data: ov.series.hcho,
      },
    ],
    {
      legend: {
        data: [labels.tvoc, labels.hcho],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 18, bottom: 48, left: 48 },
    },
  )
}

export function buildAirPressureOption(ov: ReturnType<typeof buildAirOverview>, label: string) {
  return singleMetricOption(ov.times, ov.series.pressure, label, chartColors.pressure, 'hPa')
}

export function buildAirLightPirOption(
  ov: ReturnType<typeof buildAirOverview>,
  labels: { light: string; pir: string },
): EChartsCoreOption {
  return baseLineOption(
    ov.times,
    [
      {
        name: labels.light,
        type: 'line',
        step: 'middle',
        showSymbol: false,
        yAxisIndex: 0,
        lineStyle: { width: 2, color: chartColors.light },
        data: ov.series.light_level,
      },
      {
        name: labels.pir,
        type: 'line',
        step: 'middle',
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.pir },
        data: ov.series.pir,
      },
    ],
    {
      legend: {
        data: [labels.light, labels.pir],
        bottom: 0,
        textStyle: { color: chartColors.muted, fontSize: 11 },
      },
      grid: { top: 28, right: 52, bottom: 48, left: 52 },
      yAxis: [
        {
          type: 'value',
          name: labels.light,
          minInterval: 1,
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { lineStyle: { color: chartColors.line } },
        },
        {
          type: 'value',
          name: labels.pir,
          min: 0,
          max: 1,
          interval: 1,
          axisLabel: { color: chartColors.muted, fontSize: 10 },
          splitLine: { show: false },
        },
      ],
    },
  )
}

export function buildAirSignalOption(
  ov: ReturnType<typeof buildAirOverview>,
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
        data: ov.chrono.map((r) => num(r.rssi)),
      },
      {
        name: labels.snr,
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        lineStyle: { width: 2, color: chartColors.snr },
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

export function airRangeLine(stats: ReturnType<typeof metricStats>, digits = 1) {
  return rangeText(stats, digits)
}
