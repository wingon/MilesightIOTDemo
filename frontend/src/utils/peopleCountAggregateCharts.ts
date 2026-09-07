import type { PeopleCountOverview } from '@/api/peopleCount'
import { brand } from '@/theme/colorConfig'
import type { EChartsCoreOption } from 'echarts/core'

/** 樓層順序（B1/F 最低 → 6/F 最高） */
export const FLOOR_ORDER = ['B1/F', 'G/F', '1/F', '2/F', '3/F', '4/F', '5/F', '6/F']

export const WEEKDAYS_ZH = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']

const fmt = (n: number) => Number(n).toLocaleString('en-US')

/** 大標籤字型：面向保安 / 中老年人群，數字清晰可見 */
const labelStyle = (color: string, fontWeight: number | string = 700, fontSize = 13) => ({
  color,
  fontSize,
  fontWeight,
})

function tooltip(trigger: 'axis' | 'item' = 'axis') {
  return {
    trigger,
    backgroundColor: '#ffffff',
    borderColor: '#d8e0ea',
    textStyle: { color: '#1f2733', fontSize: 13 },
    axisPointer: { type: 'shadow' as const, shadowStyle: { color: 'rgba(47,142,229,0.08)' } },
  }
}

function catAxis(data: (string | number)[], opts: { interval?: number } = {}) {
  return {
    type: 'category' as const,
    data,
    axisLine: { lineStyle: { color: brand.line } },
    axisTick: { show: false },
    axisLabel: { color: brand.muted, fontSize: 12, interval: opts.interval ?? 'auto' as unknown as number },
  }
}

function valAxis() {
  return {
    type: 'value' as const,
    splitLine: { lineStyle: { color: '#edf1f7' } },
    axisLabel: { color: brand.muted, fontSize: 12 },
    minInterval: 1,
  }
}

function gridOpt() {
  return { top: 40, left: 12, right: 16, bottom: 8, containLabel: true }
}

/** 每日進出趨勢（折線，帶數值標籤） */
export function buildDailyTrendOption(ov: PeopleCountOverview, labels: { enter: string; exit: string }): EChartsCoreOption {
  const d = ov.daily
  return {
    color: [brand.primary, brand.charcoal],
    tooltip: tooltip(),
    legend: { data: [labels.enter, labels.exit], textStyle: { color: brand.muted, fontSize: 13 }, top: 4 },
    grid: gridOpt(),
    xAxis: catAxis(d.map((r) => r.date.slice(5))),
    yAxis: valAxis(),
    series: [
      {
        name: labels.enter,
        type: 'line',
        smooth: true,
        data: d.map((r) => r.enter),
        symbolSize: 7,
        lineStyle: { width: 2.5 },
        areaStyle: { color: `${brand.primary}2E` },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 12),
          formatter: (p: { value: number }) => fmt(p.value),
        },
      },
      {
        name: labels.exit,
        type: 'line',
        smooth: true,
        data: d.map((r) => r.exit),
        symbolSize: 7,
        lineStyle: { width: 2.5 },
        areaStyle: { color: `${brand.charcoal}2E` },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.charcoal, 700, 12),
          formatter: (p: { value: number }) => fmt(p.value),
        },
      },
    ],
  }
}

/** 24 時進出（柱狀，帶數值標籤）。默認只渲染最近 6 個時段，避免標籤過於擁擠。 */
export function buildHourDistOption(ov: PeopleCountOverview, labels: { enter: string; exit: string }): EChartsCoreOption {
  // 時段按小時升序排列，超出 6 個時只保留最後 6 個（最近的時段）
  const h = ov.hour.length > 6 ? ov.hour.slice(-6) : ov.hour
  return {
    color: [brand.primary, brand.charcoal],
    tooltip: tooltip(),
    legend: { data: [labels.enter, labels.exit], textStyle: { color: brand.muted, fontSize: 13 }, top: 4 },
    grid: gridOpt(),
    xAxis: catAxis(h.map((r) => `${r.hour}:00`)),
    yAxis: valAxis(),
    series: [
      {
        name: labels.enter,
        type: 'bar',
        data: h.map((r) => r.enter),
        barMaxWidth: 22,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 13),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
      {
        name: labels.exit,
        type: 'bar',
        data: h.map((r) => r.exit),
        barMaxWidth: 22,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.charcoal, 700, 13),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
    ],
  }
}

/** 通道總流量 Top 5（分組橫條，數值標籤在右側，深色高對比） */
export function buildChannelTopOption(ov: PeopleCountOverview, labels: { enter: string; exit: string }): EChartsCoreOption {
  const top = ov.channel.slice(0, 5)
  const names = top.map((r) => r.channel_name).reverse()
  return {
    color: [brand.primary, brand.charcoal],
    tooltip: tooltip(),
    legend: { data: [labels.enter, labels.exit], textStyle: { color: brand.muted, fontSize: 13 }, top: 4 },
    grid: gridOpt(),
    xAxis: valAxis(),
    yAxis: {
      type: 'category' as const,
      data: names,
      axisLabel: { color: brand.muted, fontSize: 12, width: 130, overflow: 'truncate' },
      axisLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        name: labels.enter,
        type: 'bar',
        data: top.map((r) => r.enter).reverse(),
        barMaxWidth: 14,
        itemStyle: { borderRadius: [0, 2, 2, 0] },
        label: {
          show: true,
          position: 'right',
          ...labelStyle(brand.primary, 700, 13),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
      {
        name: labels.exit,
        type: 'bar',
        data: top.map((r) => r.exit).reverse(),
        barMaxWidth: 14,
        itemStyle: { borderRadius: [0, 2, 2, 0] },
        label: {
          show: true,
          position: 'right',
          ...labelStyle(brand.charcoal, 700, 13),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
    ],
  }
}

/** 各樓層人次分布（分組柱狀，數值標籤在柱頂，深色高對比） */
export function buildFloorDistOption(ov: PeopleCountOverview, labels: { enter: string; exit: string }): EChartsCoreOption {
  const floors = [...ov.floor].reverse()
  return {
    color: [brand.primary, brand.charcoal],
    tooltip: tooltip(),
    legend: { data: [labels.enter, labels.exit], textStyle: { color: brand.muted, fontSize: 13 }, top: 4 },
    grid: gridOpt(),
    xAxis: catAxis(floors.map((r) => r.floor)),
    yAxis: valAxis(),
    series: [
      {
        name: labels.enter,
        type: 'bar',
        data: floors.map((r) => r.enter),
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 12),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
      {
        name: labels.exit,
        type: 'bar',
        data: floors.map((r) => r.exit),
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.charcoal, 700, 12),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
    ],
  }
}

/** 通道類型分布（甜甜圈，帶數值與百分比） */
export function buildChannelTypeOption(ov: PeopleCountOverview): EChartsCoreOption {
  const ct = ov.channelType
  return {
    tooltip: tooltip('item'),
    legend: { type: 'scroll', textStyle: { color: brand.muted, fontSize: 13 }, bottom: 0 },
    color: [brand.primary, '#e0782f', '#2f9e6e'],
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '45%'],
        label: {
          color: '#1f2733',
          fontSize: 14,
          fontWeight: 700,
          formatter: '{b}\n{d}%',
        },
        labelLine: { length: 12, length2: 8 },
        data: ct.map((r) => ({ name: r.label, value: r.total })),
      },
    ],
  }
}

/** 每日淨流（進 − 出）視覺化：以分組柱顯示每日進入與離開，淨流為兩者之差 */
export function buildDailyNetOption(
  ov: PeopleCountOverview,
  labels: { net: string; enter: string; exit: string },
): EChartsCoreOption {
  const d = ov.daily
  return {
    color: [brand.primary, brand.charcoal],
    tooltip: {
      ...tooltip('item'),
      formatter: (p: { value: number; dataIndex: number; seriesName: string }) => {
        const row = d[p.dataIndex]
        const net = row.enter - row.exit
        return `<b>${row.date}</b><br/>${labels.enter}: ${fmt(row.enter)}<br/>${labels.exit}: ${fmt(row.exit)}<br/>${labels.net}: ${net >= 0 ? '+' : ''}${fmt(net)}`
      },
    },
    legend: {
      data: [labels.enter, labels.exit],
      textStyle: { color: brand.muted, fontSize: 13 },
      top: 4,
    },
    grid: gridOpt(),
    xAxis: catAxis(d.map((r) => r.date.slice(5))),
    yAxis: valAxis(),
    series: [
      {
        name: labels.enter,
        type: 'bar',
        data: d.map((r) => r.enter),
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 12),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
      {
        name: labels.exit,
        type: 'bar',
        data: d.map((r) => r.exit),
        barMaxWidth: 16,
        itemStyle: { borderRadius: [2, 2, 0, 0] },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.charcoal, 700, 12),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
    ],
  }
}

/** 星期 × 小時熱力（平均總人次，用顏色表達，避免密集數值） */
export function buildWeekdayHourOption(ov: PeopleCountOverview, weekdayNames: string[]): EChartsCoreOption {
  const wh = ov.weekdayHour
  const max = Math.max(...wh.map((r) => r.total), 1)
  return {
    tooltip: tooltip('item'),
    grid: { top: 40, left: 12, right: 16, bottom: 8, containLabel: true },
    xAxis: catAxis(Array.from({ length: 24 }, (_, h) => `${h}:00`), { interval: 2 }),
    yAxis: {
      type: 'category' as const,
      data: weekdayNames,
      axisLabel: { color: brand.muted, fontSize: 12 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    visualMap: {
      min: 0,
      max,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      top: 0,
      itemWidth: 12,
      itemHeight: 90,
      textStyle: { color: brand.muted, fontSize: 12 },
      inRange: { color: ['#eef4fb', '#bcd6f2', '#7fb2e6', '#2f6fd6', '#e0782f'] },
    },
    series: [
      {
        type: 'heatmap',
        data: wh.map((r) => [r.hour, r.weekday, r.total]),
        label: { show: false },
      },
    ],
  }
}

/** 累計人次（面積折線，間隔顯示數值標籤避免密集） */
export function buildCumulativeOption(ov: PeopleCountOverview): EChartsCoreOption {
  let acc = 0
  const cum = ov.daily.map((r) => (acc += r.total))
  const n = cum.length
  // 標籤間隔：點數越多間隔越大，避免文字重疊；至少保留首尾與中部 3~4 個
  const interval = n <= 7 ? 0 : Math.max(1, Math.ceil(n / 6) - 1)
  return {
    tooltip: tooltip(),
    grid: gridOpt(),
    xAxis: catAxis(ov.daily.map((r) => r.date.slice(5))),
    yAxis: valAxis(),
    series: [
      {
        type: 'line',
        smooth: true,
        data: cum,
        areaStyle: { color: brand.primary, opacity: 0.15 },
        lineStyle: { color: brand.primary, width: 2.5 },
        symbol: 'circle',
        symbolSize: 6,
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 13),
          interval,
          formatter: (p: { value: number; dataIndex: number }) =>
            p.dataIndex === cum.length - 1 ? '' : fmt(p.value),
        },
        endLabel: {
          show: true,
          position: 'right',
          ...labelStyle(brand.primary, 700, 14),
          formatter: (p: { value: number }) => fmt(p.value),
        },
      },
    ],
  }
}

/** 樓梯流向桑基圖 */
export function buildSankeyOption(ov: PeopleCountOverview): EChartsCoreOption {
  const nodes = new Set<string>()
  const links = ov.sankey.map((r) => {
    const dir = r.direction === 'up' ? '\u2191' : '\u2193'
    const s = `${r.from}${dir}`
    const t = `${r.to}${dir}`
    nodes.add(s)
    nodes.add(t)
    return { source: s, target: t, value: r.value }
  })
  return {
    tooltip: tooltip('item'),
    series: [
      {
        type: 'sankey',
        data: [...nodes].map((n) => ({ name: n })),
        links,
        layoutIterations: 16,
        nodeWidth: 16,
        nodeGap: 12,
        lineStyle: { color: 'gradient', curveness: 0.5, opacity: 0.4 },
        emphasis: { focus: 'adjacency' },
        label: {
          color: '#1f2733',
          fontSize: 12,
          fontWeight: 600,
          formatter: (p: { name: string }) => p.name.replace(/[↑↓]$/, ''),
        },
        itemStyle: {
          color: (p: { name: string }) =>
            p.name.endsWith('↑') ? 'rgba(47,111,214,0.85)' : 'rgba(224,120,47,0.85)',
          borderColor: 'rgba(255,255,255,0.5)',
        },
      },
    ],
  }
}

/** 單樓層通道佔比（甜甜圈，帶數值與百分比） */
export function buildFloorChannelShareOption(floorChannels: Array<{ channel_name: string; total: number }>): EChartsCoreOption {
  return {
    tooltip: tooltip('item'),
    legend: { type: 'scroll', textStyle: { color: brand.muted, fontSize: 13 }, bottom: 0 },
    color: [brand.primary, '#2f9e6e', '#e0782f', '#c9a227', '#7a5fd0', '#2f9ea6', '#d6454f', '#5a7fae', '#c0a86a'],
    series: [
      {
        type: 'pie',
        radius: ['40%', '66%'],
        center: ['50%', '44%'],
        label: {
          color: '#1f2733',
          fontSize: 13,
          fontWeight: 700,
          formatter: '{b}\n{d}%',
        },
        labelLine: { length: 10, length2: 8 },
        data: floorChannels.map((c) => ({ name: c.channel_name, value: c.total })),
      },
    ],
  }
}

/** 單樓層通道 × 小時熱力 */
export function buildFloorChannelHourOption(
  floor: PeopleCountOverview['floors'][number],
  channelHour: Array<{ channel_name: string; hour: number; total: number }>,
): EChartsCoreOption {
  const names = floor.channels.map((c) => c.channel_name)
  const nameSet = new Set(names)
  const heatRows = channelHour.filter((r) => nameSet.has(r.channel_name))
  const max = Math.max(...heatRows.map((r) => r.total), 1)
  const idx = new Map(names.map((n, i) => [n, i]))
  return {
    tooltip: tooltip('item'),
    grid: { top: 40, left: 12, right: 16, bottom: 8, containLabel: true },
    xAxis: catAxis(Array.from({ length: 24 }, (_, h) => `${h}:00`), { interval: 2 }),
    yAxis: {
      type: 'category' as const,
      data: names,
      axisLabel: { color: brand.muted, fontSize: 11, width: 110, overflow: 'truncate' },
      axisLine: { lineStyle: { color: brand.line } },
    },
    visualMap: {
      min: 0,
      max,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      top: 0,
      itemWidth: 12,
      itemHeight: 90,
      textStyle: { color: brand.muted, fontSize: 12 },
      inRange: { color: ['#eef4fb', '#bcd6f2', '#7fb2e6', '#2f6fd6', '#e0782f'] },
    },
    series: [
      {
        type: 'heatmap',
        data: heatRows.map((r) => [r.hour, idx.get(r.channel_name), r.total]),
        label: { show: false },
      },
    ],
  }
}

/** 各樓層總人流對比（橫條，帶數值標籤） */
export function buildFloorCompareOption(ov: PeopleCountOverview): EChartsCoreOption {
  const f = [...ov.floor].reverse()
  return {
    tooltip: tooltip(),
    grid: gridOpt(),
    xAxis: valAxis(),
    yAxis: {
      type: 'category' as const,
      data: f.map((r) => r.floor),
      axisLabel: { color: brand.muted, fontSize: 13 },
      axisLine: { lineStyle: { color: brand.line } },
    },
    series: [
      {
        type: 'bar',
        data: f.map((r) => r.total),
        barMaxWidth: 26,
        itemStyle: { color: brand.primary, borderRadius: [0, 3, 3, 0] },
        label: {
          show: true,
          position: 'right',
          ...labelStyle(brand.primary, 700, 13),
          formatter: (p: { value: number }) => fmt(p.value),
        },
      },
    ],
  }
}

/** 單樓層 24 時人流（柱狀，帶數值標籤） */
export function buildFloorHourOption(hour: number[]): EChartsCoreOption {
  return {
    tooltip: tooltip(),
    grid: gridOpt(),
    xAxis: catAxis(Array.from({ length: 24 }, (_, h) => `${h}:00`), { interval: 2 }),
    yAxis: valAxis(),
    series: [
      {
        type: 'bar',
        data: hour,
        barMaxWidth: 16,
        itemStyle: { color: brand.primary },
        label: {
          show: true,
          position: 'top',
          ...labelStyle(brand.primary, 700, 12),
          formatter: (p: { value: number }) => (p.value > 0 ? fmt(p.value) : ''),
        },
      },
    ],
  }
}

/** 單樓層每日人流趨勢（面積折線，帶數值標籤） */
export function buildFloorDailyOption(daily: Array<{ date: string; total: number }>): EChartsCoreOption {
  return {
    tooltip: tooltip(),
    grid: gridOpt(),
    xAxis: catAxis(daily.map((r) => r.date.slice(5))),
    yAxis: valAxis(),
    series: [
      {
        type: 'line',
        smooth: true,
        data: daily.map((r) => r.total),
        symbolSize: 7,
        areaStyle: { color: '#2f9e6e', opacity: 0.12 },
        lineStyle: { color: '#2f9e6e', width: 2.5 },
        label: {
          show: true,
          position: 'top',
          ...labelStyle('#2f9e6e', 700, 12),
          formatter: (p: { value: number }) => fmt(p.value),
        },
      },
    ],
  }
}

/** 通道類型 badge 顏色 */
export function channelTypeColor(type: string): string {
  if (type === 'lift') return 'blue'
  if (type === 'stairs') return 'orange'
  return 'green'
}