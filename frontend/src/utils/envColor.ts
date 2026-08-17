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

/**
 * Fixed 5-band temperature scale: 0 → 25 → 50 → 75 → 100
 * Each band maps to a color range (low → high):
 *   0~25:   blue (cold)
 *   25~50:  cyan-green (cool)
 *   50~75:  yellow (warm)
 *   75~100: red (hot)
 */
export const TEMPERATURE_BANDS: { from: number; to: number; color: string }[] = [
  { from: 0, to: 25, color: hsl(0.60, 0.65, 0.50) },
  { from: 25, to: 50, color: hsl(0.45, 0.55, 0.48) },
  { from: 50, to: 75, color: hsl(0.14, 0.70, 0.52) },
  { from: 75, to: 100, color: hsl(0.00, 0.72, 0.50) },
]

/** Fixed temperature band tick values */
export const TEMPERATURE_TICKS = [0, 25, 50, 75, 100]

/** Fixed temperature band colors (for legend swatches, 4 bands) */
export const TEMPERATURE_BAND_COLORS = TEMPERATURE_BANDS.map((b) => b.color)

/** Temperature color scale: blue → cyan-green → yellow → red (fixed 5 bands) */
export function temperatureColor(value: number | null, _min: number, _max: number): string | null {
  if (value == null) return null
  for (const band of TEMPERATURE_BANDS) {
    if (value >= band.from && value < band.to) return band.color
  }
  if (value >= 100) return TEMPERATURE_BANDS[TEMPERATURE_BANDS.length - 1].color
  return TEMPERATURE_BANDS[0].color
}

/** Fixed temperature band color (for 3D floor coloring; falls back when no data) */
export function fixedTemperatureColor(value: number | null): string {
  if (value == null) return '#d9d5cc'
  for (const band of TEMPERATURE_BANDS) {
    if (value >= band.from && value < band.to) return band.color
  }
  if (value >= 100) return TEMPERATURE_BANDS[TEMPERATURE_BANDS.length - 1].color
  return TEMPERATURE_BANDS[0].color
}

/** Humidity color scale: light blue → dark blue (low → high) */
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

/** Get min/max of the current metric across floors; temperature uses fixed 0~100, humidity is dynamic */
export function envRange(
  floorEnv: Record<number, FloorEnvValue> | undefined,
  metric: EnvMetric,
): [number, number] {
  if (metric === 'temperature') return [0, 100]
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
