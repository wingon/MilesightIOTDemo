import type { PeopleCountStatsRow } from '@/api/peopleCount'
import { brand } from '@/theme/colorConfig'
import type { EChartsCoreOption } from 'echarts/core'

/**
 * 按小时统计的进出人数柱状图
 * X轴: 0-23 小时
 */
export function buildHourlyBarOption(
  rows: PeopleCountStatsRow[],
  labels: { enter: string; exit: string },
): EChartsCoreOption {
  const hourlyMap = new Map<number, { enter: number; exit: number }>()

  for (let h = 0; h < 24; h++) {
    hourlyMap.set(h, { enter: 0, exit: 0 })
  }

  for (const row of rows) {
    if (row.hour != null) {
      hourlyMap.set(row.hour, {
        enter: Number(row.enter_count),
        exit: Number(row.exit_count),
      })
    }
  }

  const hours = Array.from({ length: 24 }, (_, i) => `${i}:00`)
  const enterData = Array.from({ length: 24 }, (_, i) => hourlyMap.get(i)?.enter ?? 0)
  const exitData = Array.from({ length: 24 }, (_, i) => hourlyMap.get(i)?.exit ?? 0)

  return {
    color: [brand.primary, brand.charcoal],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [labels.enter, labels.exit],
      bottom: 0,
      textStyle: { color: brand.muted, fontSize: 11 },
    },
    grid: { top: 20, right: 16, bottom: 44, left: 48 },
    xAxis: {
      type: 'category',
      data: hours,
      axisLabel: { color: brand.muted, fontSize: 10, interval: 2 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: brand.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        name: labels.enter,
        type: 'bar',
        data: enterData,
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
      },
      {
        name: labels.exit,
        type: 'bar',
        data: exitData,
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
      },
    ],
  }
}

/**
 * 按日期统计的进出人数折线图
 * 以数据范围为中心，前后各扩展1天
 */
export function buildDailyTrendOption(
  rows: PeopleCountStatsRow[],
  labels: { enter: string; exit: string },
): EChartsCoreOption {
  const dailyMap = new Map<string, { enter: number; exit: number }>()

  for (const row of rows) {
    if (row.date) {
      dailyMap.set(row.date, {
        enter: Number(row.enter_count),
        exit: Number(row.exit_count),
      })
    }
  }

  const sortedDates = Array.from(dailyMap.keys()).sort()

  if (sortedDates.length === 0) {
    const today = new Date()
    const emptyDates: string[] = []
    const emptyLabels: string[] = []
    for (let i = -3; i <= 3; i++) {
      const d = new Date(today)
      d.setDate(d.getDate() + i)
      const dateStr = d.toISOString().split('T')[0]
      emptyDates.push(dateStr)
      emptyLabels.push(dateStr.slice(5))
    }
    return {
      color: [brand.primary, brand.charcoal],
      tooltip: { trigger: 'axis' },
      legend: {
        data: [labels.enter, labels.exit],
        bottom: 0,
        textStyle: { color: brand.muted, fontSize: 11 },
      },
      grid: { top: 20, right: 16, bottom: 44, left: 48 },
      xAxis: {
        type: 'category',
        data: emptyLabels,
        axisLabel: { color: brand.muted, fontSize: 10 },
        axisLine: { lineStyle: { color: brand.line } },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLabel: { color: brand.muted, fontSize: 10 },
        splitLine: { lineStyle: { color: brand.line } },
      },
      series: [
        { name: labels.enter, type: 'line', smooth: true, showSymbol: true, symbolSize: 8, areaStyle: { color: `${brand.primary}2E` }, data: Array(7).fill(0) },
        { name: labels.exit, type: 'line', smooth: true, showSymbol: true, symbolSize: 8, areaStyle: { color: `${brand.charcoal}2E` }, data: Array(7).fill(0) },
      ],
    }
  }

  const firstDate = new Date(sortedDates[0])
  const lastDate = new Date(sortedDates[sortedDates.length - 1])
  firstDate.setDate(firstDate.getDate() - 1)
  lastDate.setDate(lastDate.getDate() + 1)

  const dates: string[] = []
  const dateLabels: string[] = []
  const cursor = new Date(firstDate)
  while (cursor <= lastDate) {
    const dateStr = cursor.toISOString().split('T')[0]
    dates.push(dateStr)
    dateLabels.push(dateStr.slice(5))
    cursor.setDate(cursor.getDate() + 1)
  }

  const enterData = dates.map((d) => dailyMap.get(d)?.enter ?? 0)
  const exitData = dates.map((d) => dailyMap.get(d)?.exit ?? 0)

  return {
    color: [brand.primary, brand.charcoal],
    tooltip: { trigger: 'axis' },
    legend: {
      data: [labels.enter, labels.exit],
      bottom: 0,
      textStyle: { color: brand.muted, fontSize: 11 },
    },
    grid: { top: 20, right: 16, bottom: 44, left: 48 },
    xAxis: {
      type: 'category',
      data: dateLabels,
      axisLabel: { color: brand.muted, fontSize: 10, rotate: dates.length > 10 ? 45 : 0 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: brand.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        name: labels.enter,
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 8,
        areaStyle: { color: `${brand.primary}2E` },
        data: enterData,
      },
      {
        name: labels.exit,
        type: 'line',
        smooth: true,
        showSymbol: true,
        symbolSize: 8,
        areaStyle: { color: `${brand.charcoal}2E` },
        data: exitData,
      },
    ],
  }
}

/**
 * 按通道统计的进出人数 - 水平柱状图
 * 只显示 Top 10，其余合并为"其他"
 */
export function buildChannelBarOption(
  rows: PeopleCountStatsRow[],
  labels: { enter: string; exit: string; unknownChannel?: string },
): EChartsCoreOption {
  const sorted = rows
    .map((row) => ({
      name: row.channel_name || labels.unknownChannel || 'Unknown',
      enter: Number(row.enter_count),
      exit: Number(row.exit_count),
    }))
    .sort((a, b) => (b.enter + b.exit) - (a.enter + a.exit))

  const topN = 10
  const displayRows = sorted.slice(0, topN)

  const channelNames = displayRows.map((r) => r.name)
  const enterData = displayRows.map((r) => r.enter)
  const exitData = displayRows.map((r) => r.exit)

  return {
    color: [brand.primary, brand.charcoal],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      data: [labels.enter, labels.exit],
      bottom: 0,
      textStyle: { color: brand.muted, fontSize: 11 },
    },
    grid: { top: 12, right: 16, bottom: 36, left: 8, containLabel: true },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: brand.muted, fontSize: 10 },
      splitLine: { lineStyle: { color: brand.line } },
    },
    yAxis: {
      type: 'category',
      data: channelNames.slice().reverse(),
      axisLabel: {
        color: brand.muted,
        fontSize: 10,
        width: 100,
        overflow: 'truncate',
      },
      axisLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        name: labels.enter,
        type: 'bar',
        stack: 'total',
        data: enterData.slice().reverse(),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [0, 0, 0, 0] },
      },
      {
        name: labels.exit,
        type: 'bar',
        stack: 'total',
        data: exitData.slice().reverse(),
        barMaxWidth: 18,
        itemStyle: { borderRadius: [0, 2, 2, 0] },
      },
    ],
  }
}
