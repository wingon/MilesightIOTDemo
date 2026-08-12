import type { EChartsCoreOption } from 'echarts/core'
import { brand } from '@/theme/colorConfig'

export type DeviceType = 'CT103' | 'AM319' | 'VS135'

export const DEVICE_TYPES: DeviceType[] = ['CT103', 'AM319', 'VS135']

/**
 * 楼层数按建筑剖面图（SECTION A-A）：
 * 地下 2 层（B2/F、B1/F）+ 地上 8 层（G/F、1/F…7/F）+ 屋顶层（ROOF）= 11 层。
 * 3D 层号 1..11 自下而上：1→B2/F、2→B1/F、3→G/F、4→1/F … 10→7/F、11→ROOF。
 */
export const FLOOR_COUNT = 11
/** 地下层数（位于 3D 楼栋底部） */
export const BASEMENT_COUNT = 2
/** 地面层（G/F）对应的 3D 层号 */
export const GROUND_LEVEL = BASEMENT_COUNT + 1

/** 3D 层号 → 建筑图楼层名（1→'B2'、2→'B1'、3→'G'、4→'1' … 10→'7'、11→'ROOF'） */
export function floorName(level: number): string {
  if (level <= BASEMENT_COUNT) return `B${BASEMENT_COUNT - level + 1}`
  if (level === GROUND_LEVEL) return 'G'
  if (level === FLOOR_COUNT) return 'ROOF'
  return String(level - GROUND_LEVEL)
}

export const GRID_ROWS = 8
export const GRID_COLS = 12
/** World-unit size of one grid cell (metres-ish) */
export const CELL_SIZE = 1.15

export type Cell = { row: number; col: number }

export interface FloorRoomDef {
  id: string
  index: number
  /** 1-based row/col cells belonging to this room */
  cells: Cell[]
  color: string
}

function cellKey(row: number, col: number) {
  return `${row}-${col}`
}

export function makeCellKey(row: number, col: number) {
  return cellKey(row, col)
}

export function parseCellKey(key: string): Cell {
  const [row, col] = key.split('-').map(Number)
  return { row, col }
}

function rangeCells(row: number, colFrom: number, colTo: number): Cell[] {
  const out: Cell[] = []
  for (let c = colFrom; c <= colTo; c++) out.push({ row, col: c })
  return out
}

/** Building interior from user outline (1-based). */
function outlineInteriorCells(): Cell[] {
  const cells: Cell[] = []
  for (let r = 1; r <= GRID_ROWS; r++) {
    cells.push(...rangeCells(r, 1, GRID_COLS))
  }
  return cells
}

/**
 * Eleven named rooms (1-based coordinates).
 * Room 7 row-6: user wrote "9、10" which overlaps room 8; interpreted as 5、6 to keep rooms contiguous.
 */
export const FLOOR_ROOMS: FloorRoomDef[] = [
  {
    id: 'room-1',
    index: 1,
    color: '#C4A574',
    cells: [
      { row: 1, col: 1 },
      { row: 1, col: 2 },
      { row: 2, col: 1 },
      { row: 2, col: 2 },
      { row: 3, col: 1 },
      { row: 3, col: 2 },
    ],
  },
  {
    id: 'room-2',
    index: 2,
    color: '#8B6B4A',
    cells: [
      { row: 2, col: 3 },
      { row: 2, col: 4 },
      { row: 3, col: 3 },
      { row: 3, col: 4 },
      { row: 3, col: 5 },
    ],
  },
  {
    id: 'room-3',
    index: 3,
    color: '#5B7C99',
    cells: [
      { row: 2, col: 5 },
      { row: 2, col: 6 },
    ],
  },
  {
    id: 'room-4',
    index: 4,
    color: '#3D7A5A',
    cells: [
      { row: 2, col: 7 },
      { row: 2, col: 8 },
    ],
  },
  {
    id: 'room-5',
    index: 5,
    color: '#A88955',
    cells: [
      { row: 3, col: 6 },
      { row: 3, col: 7 },
      { row: 3, col: 8 },
    ],
  },
  {
    id: 'room-6',
    index: 6,
    color: '#6B6B6B',
    cells: [
      { row: 2, col: 9 },
      { row: 2, col: 10 },
      { row: 2, col: 11 },
      { row: 3, col: 10 },
      { row: 3, col: 11 },
      { row: 3, col: 12 },
    ],
  },
  {
    id: 'room-7',
    index: 7,
    color: '#B42318',
    cells: [
      { row: 4, col: 5 },
      { row: 4, col: 6 },
      { row: 5, col: 5 },
      { row: 5, col: 6 },
      { row: 6, col: 5 },
      { row: 6, col: 6 },
    ],
  },
  {
    id: 'room-8',
    index: 8,
    color: '#7A5C8A',
    cells: [
      { row: 4, col: 9 },
      { row: 4, col: 10 },
      { row: 5, col: 9 },
      { row: 5, col: 10 },
      { row: 6, col: 9 },
      { row: 6, col: 10 },
    ],
  },
  {
    id: 'room-9',
    index: 9,
    color: '#2F5D50',
    cells: [
      { row: 7, col: 5 },
      { row: 7, col: 6 },
      { row: 8, col: 5 },
      { row: 8, col: 6 },
    ],
  },
  {
    id: 'room-10',
    index: 10,
    color: '#8B5A2B',
    cells: [
      { row: 7, col: 8 },
      { row: 7, col: 9 },
      { row: 8, col: 8 },
      { row: 8, col: 9 },
    ],
  },
  {
    id: 'room-11',
    index: 11,
    color: '#4A6FA5',
    cells: [
      { row: 7, col: 10 },
      { row: 7, col: 11 },
      { row: 7, col: 12 },
      { row: 8, col: 10 },
      { row: 8, col: 11 },
      { row: 8, col: 12 },
    ],
  },
]

/** Default room → cells snapshot (mutable layouts clone from this). */
export function createDefaultRoomLayout(): Record<string, Cell[]> {
  const map: Record<string, Cell[]> = {}
  for (const room of FLOOR_ROOMS) {
    map[room.id] = room.cells.map((c) => ({ ...c }))
  }
  return map
}

/** Build exclusive cellKey → roomId map from a layout. Later rooms overwrite if duplicate (should not happen). */
export function buildCellToRoomMap(layout: Record<string, Cell[]>): Map<string, string> {
  const map = new Map<string, string>()
  for (const [roomId, cells] of Object.entries(layout)) {
    for (const c of cells) {
      map.set(cellKey(c.row, c.col), roomId)
    }
  }
  return map
}

/** Interior = outline ∪ all default room cells (so room 7/8/9 footprint is complete). */
export const INTERIOR_CELLS: Cell[] = (() => {
  const map = new Map<string, Cell>()
  for (const c of outlineInteriorCells()) map.set(cellKey(c.row, c.col), c)
  for (const room of FLOOR_ROOMS) {
    for (const c of room.cells) map.set(cellKey(c.row, c.col), c)
  }
  return Array.from(map.values())
})()

export const INTERIOR_CELL_SET = new Set(INTERIOR_CELLS.map((c) => cellKey(c.row, c.col)))

/** @deprecated Use buildCellToRoomMap(layout) — kept for Building3D static fallback */
export const CELL_TO_ROOM = (() => {
  const map = new Map<string, string>()
  for (const room of FLOOR_ROOMS) {
    for (const c of room.cells) map.set(cellKey(c.row, c.col), room.id)
  }
  return map
})()

export function getRoomById(id: string) {
  return FLOOR_ROOMS.find((r) => r.id === id)
}

export function isInterior(row: number, col: number) {
  return INTERIOR_CELL_SET.has(cellKey(row, col))
}

/**
 * 判断指定楼层的单元格是否应被排除（不渲染）。
 * 1. G/F（3D层号3）到ROOF（3D层号11），8,12 不渲染
 * 2. 5F（3D层号8）到ROOF（3D层号11），8,11、7,11、7,12 不渲染
 */
export function shouldExcludeCell(level: number, row: number, col: number): boolean {
  // G/F到ROOF：8,12不渲染
  if (level >= 3 && level <= FLOOR_COUNT) {
    if (row === 8 && col === 12) {
      return true
    }
  }
  // 5F到ROOF：8,11、7,11、7,12不渲染
  if (level >= 8 && level <= FLOOR_COUNT) {
    if ((row === 7 || row === 8) && (col === 11 || col === 12)) {
      return true
    }
  }
  return false
}

/** Convert grid cell (1-based) to world XZ center (building centered at origin). */
export function cellToWorld(row: number, col: number) {
  const x = (col - (GRID_COLS + 1) / 2) * CELL_SIZE
  const z = (row - (GRID_ROWS + 1) / 2) * CELL_SIZE
  return { x, z }
}

/**
 * Outer polygon of the building footprint in XZ (for optional outline use).
 * Built by union of interior cell rectangles → axis-aligned boundary points are not needed
 * when slabs are cell-merged; kept for utilities.
 */
export function buildFootprintPolygon(): [number, number][] {
  // Bounding outline of all interior cells as a coarse rectangle list → convex hull-ish
  // For Extrude fallback: walk min/max per row
  const points: [number, number][] = []
  for (let row = 1; row <= GRID_ROWS; row++) {
    let minC = Infinity
    let maxC = -Infinity
    for (let col = 1; col <= GRID_COLS; col++) {
      if (!isInterior(row, col)) continue
      minC = Math.min(minC, col)
      maxC = Math.max(maxC, col)
    }
    if (minC === Infinity) continue
    const z0 = (row - 0.5 - (GRID_ROWS + 1) / 2) * CELL_SIZE - CELL_SIZE / 2
    const z1 = z0 + CELL_SIZE
    const x0 = (minC - 0.5 - (GRID_COLS + 1) / 2) * CELL_SIZE - CELL_SIZE / 2
    const x1 = (maxC - 0.5 - (GRID_COLS + 1) / 2) * CELL_SIZE + CELL_SIZE / 2
    // store as row strips — consumers that need a single shape should use cell meshes
    void z1
    points.push([x0, z0], [x1, z0])
  }
  return points
}

export function roomDeviceId(floor: number, roomId: string, type: DeviceType) {
  return `${type}-L${floor}-${roomId.toUpperCase()}`
}

export function deviceId(floor: number, roomId: string, type: DeviceType) {
  return roomDeviceId(floor, roomId, type)
}

function seededNoise(seed: number, i: number) {
  const x = Math.sin(seed * 12.9898 + i * 78.233) * 43758.5453
  return x - Math.floor(x)
}

function hoursLabels(n = 24) {
  return Array.from({ length: n }, (_, i) => `${String(i).padStart(2, '0')}:00`)
}

function series(seed: number, base: number, amp: number, n = 24) {
  return Array.from({ length: n }, (_, i) => {
    const wave = Math.sin((i / n) * Math.PI * 2 + seed) * amp
    const noise = (seededNoise(seed, i) - 0.5) * amp * 0.35
    return Math.round((base + wave + noise) * 10) / 10
  })
}

export function buildCt103Option(seed: number, labels: { current: string; total: string }): EChartsCoreOption {
  const hours = hoursLabels()
  const current = series(seed + 1, 18, 8)
  let acc = 0
  const total = current.map((v) => {
    acc += v
    return Math.round(acc * 10) / 10
  })
  return {
    color: [brand.primary, '#8B5A2B'],
    tooltip: { trigger: 'axis' },
    legend: { data: [labels.current, labels.total], bottom: 0 },
    grid: { left: 48, right: 24, top: 28, bottom: 48 },
    xAxis: { type: 'category', data: hours, axisLabel: { interval: 3 } },
    yAxis: { type: 'value', name: 'A' },
    series: [
      { name: labels.current, type: 'line', smooth: true, data: current, showSymbol: false },
      { name: labels.total, type: 'line', smooth: true, data: total, showSymbol: false },
    ],
  }
}

export function buildAm319Option(
  seed: number,
  labels: { co2: string; temp: string; humidity: string; pm25: string },
): EChartsCoreOption {
  const hours = hoursLabels()
  return {
    color: [brand.primary, '#8B5A2B', '#5B7C99', '#6B6B6B'],
    tooltip: { trigger: 'axis' },
    legend: { data: [labels.co2, labels.temp, labels.humidity, labels.pm25], bottom: 0 },
    grid: { left: 48, right: 24, top: 28, bottom: 56 },
    xAxis: { type: 'category', data: hours, axisLabel: { interval: 3 } },
    yAxis: { type: 'value' },
    series: [
      { name: labels.co2, type: 'line', smooth: true, data: series(seed + 2, 620, 120), showSymbol: false },
      { name: labels.temp, type: 'line', smooth: true, data: series(seed + 3, 23, 2.5), showSymbol: false },
      { name: labels.humidity, type: 'line', smooth: true, data: series(seed + 4, 48, 10), showSymbol: false },
      { name: labels.pm25, type: 'line', smooth: true, data: series(seed + 5, 12, 6), showSymbol: false },
    ],
  }
}

export function buildVs135Option(
  seed: number,
  labels: { periodIn: string; periodOut: string; cumulative: string },
): EChartsCoreOption {
  const hours = hoursLabels()
  const periodIn = series(seed + 6, 14, 10).map((v) => Math.max(0, Math.round(v)))
  const periodOut = series(seed + 7, 12, 9).map((v) => Math.max(0, Math.round(v)))
  let cin = 0
  let cout = 0
  const cumIn = periodIn.map((v) => {
    cin += v
    return cin
  })
  const cumOut = periodOut.map((v) => {
    cout += v
    return cout
  })
  return {
    color: [brand.primary, '#5B7C99', '#A88955', '#8B5A2B'],
    tooltip: { trigger: 'axis' },
    legend: {
      data: [labels.periodIn, labels.periodOut, `${labels.cumulative} In`, `${labels.cumulative} Out`],
      bottom: 0,
    },
    grid: { left: 48, right: 24, top: 28, bottom: 56 },
    xAxis: { type: 'category', data: hours, axisLabel: { interval: 3 } },
    yAxis: { type: 'value' },
    series: [
      { name: labels.periodIn, type: 'bar', data: periodIn },
      { name: labels.periodOut, type: 'bar', data: periodOut },
      { name: `${labels.cumulative} In`, type: 'line', data: cumIn, showSymbol: false },
      { name: `${labels.cumulative} Out`, type: 'line', data: cumOut, showSymbol: false },
    ],
  }
}

export function latestSnapshot(type: DeviceType, seed: number) {
  if (type === 'CT103') {
    return [
      { label: 'Current', value: `${(16 + seededNoise(seed, 1) * 10).toFixed(1)} A` },
      { label: 'Temp', value: `${(28 + seededNoise(seed, 2) * 6).toFixed(1)} °C` },
    ]
  }
  if (type === 'AM319') {
    return [
      { label: 'CO₂', value: `${Math.round(550 + seededNoise(seed, 3) * 200)} ppm` },
      { label: 'Temp', value: `${(22 + seededNoise(seed, 4) * 4).toFixed(1)} °C` },
      { label: 'Humidity', value: `${Math.round(40 + seededNoise(seed, 5) * 25)} %` },
      { label: 'PM2.5', value: `${(8 + seededNoise(seed, 6) * 15).toFixed(1)} µg/m³` },
    ]
  }
  return [
    { label: 'Period In', value: `${Math.round(8 + seededNoise(seed, 7) * 20)}` },
    { label: 'Period Out', value: `${Math.round(6 + seededNoise(seed, 8) * 18)}` },
    { label: 'Occupancy', value: `${Math.round(12 + seededNoise(seed, 9) * 30)}` },
  ]
}

/** Registered device on a floor inventory (not yet necessarily in a room). */
export interface FloorInventoryDevice {
  id: string
  sn: string
  type: DeviceType
  floor: number
  mqttOk: boolean | null
}

export function newDeviceId() {
  return `dev-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

/** Demo: at most 3 floors raise environmental / metric alerts (B1/F、2/F、5/F) */
export const ENV_ALERT_FLOORS = [2, 5, 8] as const

export const CO2_WARN_PPM = 1000

/** Seed floor inventory + room assignments for demo */
export function createDefaultFloorInventory(floor: number): {
  inventory: FloorInventoryDevice[]
  roomAssignments: Record<string, string[]>
} {
  const inventory: FloorInventoryDevice[] = []
  const roomAssignments: Record<string, string[]> = {}

  const seed: Array<{ room: string; type: DeviceType; sn: string }> = [
    { room: 'room-1', type: 'AM319', sn: `AM319-L${floor}-A1` },
    { room: 'room-1', type: 'VS135', sn: `VS135-L${floor}-A1` },
    { room: 'room-2', type: 'CT103', sn: `CT103-L${floor}-B1` },
    { room: 'room-3', type: 'AM319', sn: `AM319-L${floor}-C1` },
    { room: 'room-5', type: 'VS135', sn: `VS135-L${floor}-E1` },
    { room: 'room-6', type: 'AM319', sn: `AM319-L${floor}-F1` },
    { room: 'room-6', type: 'CT103', sn: `CT103-L${floor}-F2` },
    { room: 'room-8', type: 'VS135', sn: `VS135-L${floor}-H1` },
    { room: 'room-8', type: 'AM319', sn: `AM319-L${floor}-H2` },
    { room: 'room-11', type: 'CT103', sn: `CT103-L${floor}-K1` },
    { room: 'room-11', type: 'AM319', sn: `AM319-L${floor}-K2` },
    { room: 'room-11', type: 'VS135', sn: `VS135-L${floor}-K3` },
  ]
  if (floor % 2 === 0) {
    seed.push(
      { room: 'room-4', type: 'CT103', sn: `CT103-L${floor}-D1` },
      { room: 'room-9', type: 'AM319', sn: `AM319-L${floor}-I1` },
    )
  }
  if (floor % 3 === 0) {
    seed.push(
      { room: 'room-7', type: 'VS135', sn: `VS135-L${floor}-G1` },
      { room: 'room-10', type: 'CT103', sn: `CT103-L${floor}-J1` },
      { room: 'room-10', type: 'AM319', sn: `AM319-L${floor}-J2` },
    )
  }

  for (let i = 0; i < seed.length; i++) {
    const item = seed[i]
    const id = newDeviceId()
    // ~3% MQTT fail — independent of metric alerts (never on ENV_ALERT floors)
    const envFloor = (ENV_ALERT_FLOORS as readonly number[]).includes(floor)
    const fail = !envFloor && (floor * 31 + i * 17) % 100 < 3
    const mqttOk: boolean | null = fail ? false : true
    inventory.push({
      id,
      sn: item.sn,
      type: item.type,
      floor,
      mqttOk,
    })
    if (!roomAssignments[item.room]) roomAssignments[item.room] = []
    roomAssignments[item.room].push(id)
  }

  return { inventory, roomAssignments }
}

/** @deprecated Prefer inventory model */
export function createDefaultRoomDevices(floor: number): Record<string, DeviceType[]> {
  const { inventory, roomAssignments } = createDefaultFloorInventory(floor)
  const map: Record<string, DeviceType[]> = {}
  for (const [roomId, ids] of Object.entries(roomAssignments)) {
    map[roomId] = ids.map((id) => inventory.find((d) => d.id === id)!.type)
  }
  return map
}

export function countDevicesInMap(map: Record<string, DeviceType[]>) {
  return Object.values(map).reduce((sum, list) => sum + list.length, 0)
}

export function countAssignedIds(map: Record<string, string[]>) {
  return Object.values(map).reduce((sum, list) => sum + list.length, 0)
}

export interface FloorEnvMetrics {
  /** CT103 */
  current: number
  cableTemp: number
  /** AM319 */
  co2: number
  temperature: number
  humidity: number
  pm25: number
  co2High: boolean
  /** VS135 */
  periodIn: number
  periodOut: number
  occupancy: number
}

/** Deterministic per-floor env / device snapshot for overview list */
export function demoFloorEnv(floor: number): FloorEnvMetrics {
  const alert = (ENV_ALERT_FLOORS as readonly number[]).includes(floor)
  const co2 = alert ? 1180 + (floor % 7) * 25 : 420 + ((floor * 37) % 380)
  const temperature = Math.round((21.5 + ((floor * 11) % 40) / 10) * 10) / 10
  const humidity = 40 + ((floor * 9) % 25)
  const current = Math.round((8 + ((floor * 13) % 90) / 10) * 10) / 10
  const cableTemp = Math.round((26 + ((floor * 7) % 50) / 10) * 10) / 10
  const pm25 = Math.round((6 + ((floor * 19) % 28)) * 10) / 10
  const periodIn = 5 + ((floor * 5) % 22)
  const periodOut = 4 + ((floor * 7) % 18)
  const occupancy = Math.max(0, 10 + ((floor * 3) % 40) + periodIn - periodOut)
  return {
    current,
    cableTemp,
    co2,
    temperature,
    humidity,
    pm25,
    co2High: co2 >= CO2_WARN_PPM,
    periodIn,
    periodOut,
    occupancy,
  }
}

export interface FloorStats {
  floor: number
  registered: number
  connected: number
  failed: number
  untested: number
  assigned: number
  unassigned: number
  byType: Record<DeviceType, number>
  /** MQTT disconnect alert (device link) — independent of metricAlert */
  mqttAlert: boolean
  /** Sensor reading over threshold (e.g. CO₂) — independent of mqttAlert */
  metricAlert: boolean
  /** Either alert type */
  abnormal: boolean
  connectivityRatio: number
  current: number | null
  cableTemp: number | null
  co2: number | null
  /** WingOnIOT 真实温度（无数据为 null，面板显示 --） */
  temperature: number | null
  /** WingOnIOT 真实湿度（无数据为 null，面板显示 --） */
  humidity: number | null
  pm25: number | null
  co2High: boolean
  periodIn: number | null
  periodOut: number | null
  occupancy: number | null
}

export function computeFloorStats(
  floor: number,
  inventory: FloorInventoryDevice[],
  assignments: Record<string, string[]>,
): FloorStats {
  const registered = inventory.length
  const connected = inventory.filter((d) => d.mqttOk === true).length
  const failed = inventory.filter((d) => d.mqttOk === false).length
  const untested = inventory.filter((d) => d.mqttOk == null).length
  const assigned = countAssignedIds(assignments)
  const unassigned = Math.max(0, registered - assigned)
  const byType: Record<DeviceType, number> = { CT103: 0, AM319: 0, VS135: 0 }
  for (const d of inventory) byType[d.type] += 1
  const connectivityRatio = registered > 0 ? connected / registered : 1
  const env = demoFloorEnv(floor)
  const mqttAlert = failed > 0
  const metricAlert = env.co2High
  return {
    floor,
    registered,
    connected,
    failed,
    untested,
    assigned,
    unassigned,
    byType,
    mqttAlert,
    metricAlert,
    abnormal: mqttAlert || metricAlert,
    connectivityRatio,
    current: env.current,
    cableTemp: env.cableTemp,
    co2: env.co2,
    temperature: env.temperature,
    humidity: env.humidity,
    pm25: env.pm25,
    co2High: env.co2High,
    periodIn: env.periodIn,
    periodOut: env.periodOut,
    occupancy: env.occupancy,
  }
}
