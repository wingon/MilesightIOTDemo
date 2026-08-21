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
 * Fixed temperature scale: 0 → 10 → 20 → 30 → 35 (°C)
 * Bands map low → high to a cold → hot gradient (blue → cyan → yellow → red):
 *   0~10:   blue (cold)
 *   10~20:  cyan-green (cool)
 *   20~30:  yellow (warm)
 *   30~35:  red (hot)
 */
export const TEMPERATURE_BANDS: { from: number; to: number; color: string }[] = [
  { from: 0, to: 10, color: hsl(0.60, 0.65, 0.45) },
  { from: 10, to: 20, color: hsl(0.48, 0.60, 0.48) },
  { from: 20, to: 30, color: hsl(0.28, 0.65, 0.50) },
  { from: 30, to: 35, color: hsl(0.06, 0.78, 0.52) },
]

/** Fixed temperature tick values */
export const TEMPERATURE_TICKS = [0, 10, 20, 30, 35]

/** Fixed temperature band colors (for legend swatches / gradient stops) */
export const TEMPERATURE_BAND_COLORS = TEMPERATURE_BANDS.map((b) => b.color)

/** Continuous gradient stops (one color per tick) for the temperature legend bar */
export const TEMPERATURE_GRADIENT_STOPS = [
  hsl(0.60, 0.65, 0.45), // 0
  hsl(0.48, 0.60, 0.48), // 10
  hsl(0.28, 0.65, 0.50), // 20
  hsl(0.12, 0.78, 0.54), // 30
  hsl(0.00, 0.78, 0.50), // 35
]

/** Temperature color scale: blue → cyan → yellow → red (fixed 5 bands) */
export function temperatureColor(value: number | null, _min: number, _max: number): string | null {
  if (value == null) return null
  for (const band of TEMPERATURE_BANDS) {
    if (value >= band.from && value < band.to) return band.color
  }
  if (value >= 35) return TEMPERATURE_BANDS[TEMPERATURE_BANDS.length - 1].color
  return TEMPERATURE_BANDS[0].color
}

/** Fixed temperature band color (for 3D floor coloring; falls back when no data) */
export function fixedTemperatureColor(value: number | null): string {
  if (value == null) return '#d9d5cc'
  for (const band of TEMPERATURE_BANDS) {
    if (value >= band.from && value < band.to) return band.color
  }
  if (value >= 35) return TEMPERATURE_BANDS[TEMPERATURE_BANDS.length - 1].color
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
