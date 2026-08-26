/** WingOnIOT environment data → 3D building floor color mapping utilities (pure functions). */

export type EnvMetric = 'temperature' | 'humidity'

export interface FloorEnvValue {
  temperature: number | null
  humidity: number | null
  /** Number of devices with the latest reading on this floor (0 when no data) */
  deviceCount: number
}

/** Default numeric range when no real data (keeps colors distinguishable) */
export const TEMP_RANGE_DEFAULT: [number, number] = [15, 35]
export const HUMIDITY_RANGE_DEFAULT: [number, number] = [20, 90]

function clamp01(v: number) {
  return Math.min(1, Math.max(0, v))
}

function hsl(h: number, s: number, l: number) {
  return `hsl(${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/** 解析 hsl(...) 字符串 → [h(0-360), s(0-1), l(0-1)] */
function parseHsl(hslStr: string): [number, number, number] {
  const match = hslStr.match(/hsl\((\d+\.?\d*),\s*(\d+\.?\d*)%,\s*(\d+\.?\d*)%\)/)
  if (!match) return [0, 0, 0]
  return [parseFloat(match[1]), parseFloat(match[2]) / 100, parseFloat(match[3]) / 100]
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  h = ((h % 360) + 360) % 360
  s = clamp01(s)
  l = clamp01(l)
  const c = (1 - Math.abs(2 * l - 1)) * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = l - c / 2
  let r = 0, g = 0, b = 0
  if (h < 60) { r = c; g = x }
  else if (h < 120) { r = x; g = c }
  else if (h < 180) { r = 0; g = c; b = x }
  else if (h < 240) { r = 0; g = x; b = c }
  else if (h < 300) { r = x; g = 0; b = c }
  else { r = c; g = 0; b = x }
  return [r + m, g + m, b + m]
}

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  const l = (max + min) / 2
  if (d === 0) return [0, 0, l]
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h = 0
  if (max === r) h = ((g - b) / d + (g < b ? 6 : 0)) / 6
  else if (max === g) h = ((b - r) / d + 2) / 6
  else h = ((r - g) / d + 4) / 6
  // 返回 0-1 范围的色相，与 hsl() 的入参约定一致
  return [h, s, l]
}

/**
 * 在两个颜色间插值。为与 CSS linear-gradient（右下角图例）视觉完全一致，
 * 统一在 sRGB 空间插值。
 */
function lerpColor(color1: string, color2: string, t: number): string {
  const [h1, s1, l1] = parseHsl(color1)
  const [h2, s2, l2] = parseHsl(color2)
  const rgb1 = hslToRgb(h1, s1, l1)
  const rgb2 = hslToRgb(h2, s2, l2)
  const r = lerp(rgb1[0], rgb2[0], t)
  const g = lerp(rgb1[1], rgb2[1], t)
  const b = lerp(rgb1[2], rgb2[2], t)
  const [h, s, l] = rgbToHsl(r, g, b)
  return hsl(h, s, l)
}

/**
 * 温度渐变锚点：温度值 → 图例颜色（与右下角温度图例完全一致）。
 * 0→蓝  10→青  20→黄  30→橙  35→红
 */
export const TEMPERATURE_ANCHORS: { value: number; color: string }[] = [
  { value: 0,  color: hsl(0.60, 0.65, 0.45) },
  { value: 10, color: hsl(0.48, 0.60, 0.48) },
  { value: 20, color: hsl(0.28, 0.65, 0.50) },
  { value: 30, color: hsl(0.12, 0.78, 0.54) },
  { value: 35, color: hsl(0.00, 0.78, 0.50) },
]

/** Fixed temperature tick values */
export const TEMPERATURE_TICKS = TEMPERATURE_ANCHORS.map((a) => a.value)

/** Fixed temperature band colors (for legend swatches / gradient stops) */
export const TEMPERATURE_BAND_COLORS = TEMPERATURE_ANCHORS.map((a) => a.color)

/** Continuous gradient stops (one color per tick) for the temperature legend bar */
export const TEMPERATURE_GRADIENT_STOPS = TEMPERATURE_ANCHORS.map((a) => a.color)

/**
 * 温度颜色映射：在图例渐变（TEMPERATURE_ANCHORS）上按温度值取色，连续插值。
 * 3D 楼层的颜色与右下角图例完全一致。
 */
export function temperatureColor(value: number | null, _min: number, _max: number): string | null {
  if (value == null) return null
  const first = TEMPERATURE_ANCHORS[0]
  const last = TEMPERATURE_ANCHORS[TEMPERATURE_ANCHORS.length - 1]
  if (value <= first.value) return first.color
  if (value >= last.value) return last.color
  for (let i = 0; i < TEMPERATURE_ANCHORS.length - 1; i++) {
    const curr = TEMPERATURE_ANCHORS[i]
    const next = TEMPERATURE_ANCHORS[i + 1]
    if (value >= curr.value && value < next.value) {
      const t = clamp01((value - curr.value) / (next.value - curr.value))
      return lerpColor(curr.color, next.color, t)
    }
  }
  return first.color
}

/** Fixed temperature color (for 3D floor coloring; falls back when no data) */
export function fixedTemperatureColor(value: number | null): string {
  if (value == null) return '#d9d5cc'
  return temperatureColor(value, 0, 35) ?? '#d9d5cc'
}

/** Humidity color scale: light blue → dark blue (low → high) */
export function humidityColor(value: number | null, min: number, max: number): string | null {
  if (value == null || !(max > min)) return null
  const t = clamp01((value - min) / (max - min))
  
  // 使用多个控制点实现更平滑的过渡
  // 低湿度：浅蓝（高亮度，低饱和度）
  // 中湿度：中蓝（中亮度，中饱和度）
  // 高湿度：深蓝（低亮度，高饱和度）
  const h = 210 / 360  // 蓝色色相（0-1 范围）
  const s = lerp(0.35, 0.60, t)  // 饱和度随湿度增加（0-1）
  const l = lerp(0.75, 0.38, t)  // 亮度随湿度降低（0-1）
  return hsl(h, s, l)
}

export function envColorFor(
  metric: EnvMetric,
  value: number | null,
  min: number,
  max: number,
): string | null {
  return metric === 'temperature'
    ? temperatureColor(value, min, max)
    : humidityColor(value, min, max)
}

/** Get min/max of the current metric across floors; temperature uses fixed 0~35, humidity is dynamic */
export function envRange(
  floorEnv: Record<number, FloorEnvValue> | undefined,
  metric: EnvMetric,
): [number, number] {
  if (metric === 'temperature') return [0, 35]
  if (!floorEnv) return HUMIDITY_RANGE_DEFAULT
  let min: number | null = null
  let max: number | null = null
  for (const v of Object.values(floorEnv)) {
    const n = v.humidity
    if (n == null) continue
    if (min == null || n < min) min = n
    if (max == null || n > max) max = n
  }
  if (min == null || max == null) return HUMIDITY_RANGE_DEFAULT
  const span = max - min
  if (span < 1) {
    const pad = (1 - span) / 2
    return [min - pad, max + pad]
  }
  return [min, max]
}
