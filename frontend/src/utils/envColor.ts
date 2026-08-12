/** WingOnIOT 环境数据 → 3D 楼栋楼层颜色映射工具（纯函数）。 */

export type EnvMetric = 'temperature' | 'humidity'

export interface FloorEnvValue {
  temperature: number | null
  humidity: number | null
  /** 该层有最新读数的设备数（无数据为 0） */
  deviceCount: number
}

/** 无真实数据时的默认数值范围（保证颜色可区分） */
export const TEMP_RANGE_DEFAULT: [number, number] = [15, 35]
export const HUMIDITY_RANGE_DEFAULT: [number, number] = [20, 90]

function clamp01(v: number) {
  return Math.min(1, Math.max(0, v))
}

function hsl(h: number, s: number, l: number) {
  return `hsl(${Math.round(h * 360)}, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`
}

/** 温度色带：蓝 → 青 → 黄 → 红（低 → 高） */
export function temperatureColor(value: number | null, min: number, max: number): string | null {
  if (value == null || !(max > min)) return null
  const t = clamp01((value - min) / (max - min))
  return hsl(0.62 - t * 0.62, 0.5 + t * 0.35, 0.48)
}

/** 湿度色带：浅蓝 → 深蓝（低 → 高） */
export function humidityColor(value: number | null, min: number, max: number): string | null {
  if (value == null || !(max > min)) return null
  const t = clamp01((value - min) / (max - min))
  return hsl(0.58, 0.5, 0.72 - t * 0.38)
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

/** 取各层当前指标的实际 min/max；数据不足时回退默认范围 */
export function envRange(
  floorEnv: Record<number, FloorEnvValue> | undefined,
  metric: EnvMetric,
): [number, number] {
  const fallback = metric === 'temperature' ? TEMP_RANGE_DEFAULT : HUMIDITY_RANGE_DEFAULT
  if (!floorEnv) return fallback
  let min: number | null = null
  let max: number | null = null
  for (const v of Object.values(floorEnv)) {
    const n = metric === 'temperature' ? v.temperature : v.humidity
    if (n == null) continue
    if (min == null || n < min) min = n
    if (max == null || n > max) max = n
  }
  if (min == null || max == null) return fallback
  // 数值差异过小时稍微外扩，保证色差可见
  const span = max - min
  if (span < 1) {
    const pad = (1 - span) / 2
    return [min - pad, max + pad]
  }
  return [min, max]
}
