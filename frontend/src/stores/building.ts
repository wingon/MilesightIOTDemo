import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { getFloorEnvironmentSummary, listEnvironmentDevices, type EnvironmentDevice } from '@/api/environment'

/** 阈值常量：温度 >28℃ 或湿度 >75% 视为超标 */
export const TEMP_THRESHOLD = 28
export const HUMIDITY_THRESHOLD = 75

/** 每层楼的设备级统计（基于各设备最新中位值） */
export interface FloorDeviceStats {
  level: number
  temperature: { max: number | null; min: number | null; avg: number | null }
  humidity: { max: number | null; min: number | null; avg: number | null }
  /** 超温传感器 SN 列表 */
  tempExceeding: string[]
  /** 超湿传感器 SN 列表 */
  humidityExceeding: string[]
  /** 是否有任一指标超标 */
  hasAlert: boolean
}
import {
  listBuildings,
  listBuildingFloors,
  listFloorRooms,
  type BuildingInfo,
  type FloorInfo,
  type FloorRoom,
} from '@/api/building'
import {
  buildCellToRoomMap,
  computeFloorStats,
  createDefaultFloorInventory,
  createDefaultRoomLayout,
  FLOOR_COUNT,
  FLOOR_ROOMS,
  isInterior,
  newDeviceId,
  type Cell,
  type DeviceType,
  type FloorInventoryDevice,
  type FloorStats,
} from '@/utils/buildingDemo'

export const useBuildingStore = defineStore('building', () => {
  /** floor -> real temperature/humidity from the WingOnIOT DB (level is the 3D building level) */
  const floorEnv = reactive<
    Record<
      number,
      {
        temperature: number | null
        humidity: number | null
        /** Number of devices with the latest reading on this floor */
        deviceCount: number
        updatedAt: string | null
      }
    >
  >({})
  const envLoading = ref(false)
  const envError = ref<string | null>(null)
  let envFetched = false

  /** Fetch the latest temperature/humidity per floor from WingOnIOT; failures must not block the page (keeps demo fallback) */
  async function fetchFloorEnv() {
    if (envFetched) return
    envFetched = true
    envLoading.value = true
    envError.value = null
    try {
      const { data } = await getFloorEnvironmentSummary()
      for (const row of data) {
        // level is the 3D building level (1..FLOOR_COUNT): B2/F→1, B1/F→2, G/F→3, n/F→n+3;
        // mappings out of range (e.g. deeper basements or higher floors) cannot render and are skipped
        if (row.level == null || row.level < 1 || row.level > FLOOR_COUNT) continue
        floorEnv[row.level] = {
          temperature: row.temperature,
          humidity: row.humidity,
          deviceCount: row.device_count,
          updatedAt: row.updated_at,
        }
      }
    } catch (err) {
      envError.value = err instanceof Error ? err.message : String(err)
      console.warn('[building] fetchFloorEnv failed:', envError.value)
      // Reset the flag on failure so the next page entry can retry
      envFetched = false
    } finally {
      envLoading.value = false
    }
  }

  /** Real WingOnIOT environment devices (including the latest reading per device) */
  const envDevices = ref<EnvironmentDevice[]>([])
  let envDevicesFetched = false

  /** Fetch the WingOnIOT device list (including the latest reading); retriable on failure */
  async function fetchEnvDevices() {
    if (envDevicesFetched) return
    envDevicesFetched = true
    try {
      const { data } = await listEnvironmentDevices()
      envDevices.value = data
    } catch (err) {
      console.warn('[building] fetchEnvDevices failed:', err)
      envDevicesFetched = false
    }
  }

  /** Real environment devices for a given 3D level */
  function devicesForFloor(level: number): EnvironmentDevice[] {
    return envDevices.value.filter((d) => d.level === level)
  }

  /** DB-driven building structure: building / floor (level_3d maps to 3D level 1..11) */
  const buildings = ref<BuildingInfo[]>([])
  const floors = ref<FloorInfo[]>([])
  let structureFetched = false

  /** floor_id -> rooms with their occupied cells (from room / room_cell) */
  const floorRooms = reactive<Record<number, FloorRoom[]>>({})

  /** Fetch the building + floor list once; retriable on failure */
  async function fetchBuildingStructure() {
    if (structureFetched) return
    structureFetched = true
    try {
      const { data: b } = await listBuildings()
      buildings.value = b ?? []
      const { data: f } = await listBuildingFloors(buildings.value[0]?.id)
      floors.value = f ?? []
    } catch (err) {
      console.warn('[building] fetchBuildingStructure failed:', err)
      structureFetched = false
    }
  }

  /** Map a 3D level (1..11) to the DB floor id */
  function floorIdByLevel(level3d: number): number | null {
    const f = floors.value.find((x) => x.level_3d === level3d)
    return f?.id ?? null
  }

  /** Fetch rooms (with occupied cells) of a 3D level into floorRooms */
  async function fetchFloorRooms(level3d: number) {
    const fid = floorIdByLevel(level3d)
    if (fid == null) return
    try {
      const { data } = await listFloorRooms(fid)
      floorRooms[fid] = data ?? []
    } catch (err) {
      console.warn('[building] fetchFloorRooms failed:', err)
    }
  }

  /** Rooms of a 3D level (empty when the DB has no data for this floor) */
  function getFloorRooms(level3d: number): FloorRoom[] {
    const fid = floorIdByLevel(level3d)
    if (fid == null) return []
    return floorRooms[fid] ?? []
  }

  /** floor -> inventory devices registered to that floor */
  const floorInventory = reactive<Record<number, FloorInventoryDevice[]>>({})
  /** floor -> roomId -> inventory device ids assigned to room */
  const roomDeviceIds = reactive<Record<number, Record<string, string[]>>>({})
  /** floor -> roomId -> cells */
  const floorLayouts = reactive<Record<number, Record<string, Cell[]>>>({})
  /** floor -> custom walls (manually added by the user in edit mode) */
  const floorCustomWalls = reactive<Record<number, { x1: number; z1: number; x2: number; z2: number }[]>>({})

  function ensureFloor(floor: number) {
    if (!floorInventory[floor]) {
      const seeded = createDefaultFloorInventory(floor)
      floorInventory[floor] = seeded.inventory
      roomDeviceIds[floor] = seeded.roomAssignments
    }
    if (!floorLayouts[floor]) {
      floorLayouts[floor] = createDefaultRoomLayout()
    }
    if (!roomDeviceIds[floor]) {
      roomDeviceIds[floor] = {}
    }
    if (!floorCustomWalls[floor]) {
      floorCustomWalls[floor] = []
    }
  }

  function getInventory(floor: number) {
    ensureFloor(floor)
    return floorInventory[floor]
  }

  function getRoomAssignments(floor: number) {
    ensureFloor(floor)
    return roomDeviceIds[floor]
  }

  /** Devices on floor not yet assigned to any room (or optionally include all) */
  function getUnassignedInventory(floor: number) {
    ensureFloor(floor)
    const assigned = new Set<string>()
    for (const ids of Object.values(roomDeviceIds[floor])) {
      ids.forEach((id) => assigned.add(id))
    }
    return floorInventory[floor].filter((d) => !assigned.has(d.id))
  }

  /** Inventory available to add to a room = unassigned only */
  function getAssignableToRoom(floor: number, _roomId: string) {
    return getUnassignedInventory(floor)
  }

  function addInventoryDevice(
    floor: number,
    payload: { sn: string; type: DeviceType; mqttOk?: boolean | null },
  ): FloorInventoryDevice | null {
    ensureFloor(floor)
    const sn = payload.sn.trim()
    if (!sn) return null
    if (floorInventory[floor].some((d) => d.sn.toLowerCase() === sn.toLowerCase())) {
      return null
    }
    const device: FloorInventoryDevice = {
      id: newDeviceId(),
      sn,
      type: payload.type,
      floor,
      mqttOk: payload.mqttOk ?? null,
    }
    floorInventory[floor].push(device)
    return device
  }

  function removeInventoryDevice(floor: number, deviceId: string) {
    ensureFloor(floor)
    floorInventory[floor] = floorInventory[floor].filter((d) => d.id !== deviceId)
    for (const roomId of Object.keys(roomDeviceIds[floor])) {
      roomDeviceIds[floor][roomId] = (roomDeviceIds[floor][roomId] || []).filter((id) => id !== deviceId)
    }
  }

  function setInventoryMqttOk(floor: number, deviceId: string, ok: boolean) {
    ensureFloor(floor)
    const d = floorInventory[floor].find((x) => x.id === deviceId)
    if (d) d.mqttOk = ok
  }

  function assignDeviceToRoom(floor: number, roomId: string, deviceId: string): boolean {
    ensureFloor(floor)
    const exists = floorInventory[floor].some((d) => d.id === deviceId)
    if (!exists) return false
    // Remove from any room first
    for (const rid of Object.keys(roomDeviceIds[floor])) {
      roomDeviceIds[floor][rid] = (roomDeviceIds[floor][rid] || []).filter((id) => id !== deviceId)
    }
    if (!roomDeviceIds[floor][roomId]) roomDeviceIds[floor][roomId] = []
    if (!roomDeviceIds[floor][roomId].includes(deviceId)) {
      roomDeviceIds[floor][roomId].push(deviceId)
    }
    return true
  }

  function removeDeviceFromRoom(floor: number, roomId: string, deviceId: string) {
    ensureFloor(floor)
    roomDeviceIds[floor][roomId] = (roomDeviceIds[floor][roomId] || []).filter((id) => id !== deviceId)
  }

  function getFloorMap(floor: number): Record<string, DeviceType[]> {
    ensureFloor(floor)
    const map: Record<string, DeviceType[]> = {}
    for (const [roomId, ids] of Object.entries(roomDeviceIds[floor])) {
      map[roomId] = ids
        .map((id) => floorInventory[floor].find((d) => d.id === id)?.type)
        .filter((t): t is DeviceType => !!t)
    }
    return map
  }

  function getFloorLayout(floor: number) {
    ensureFloor(floor)
    return floorLayouts[floor]
  }

  function getCellOwner(floor: number, row: number, col: number): string | null {
    ensureFloor(floor)
    for (const [rid, cells] of Object.entries(floorLayouts[floor])) {
      if (cells.some((c) => c.row === row && c.col === col)) return rid
    }
    return null
  }

  function assignRoomCell(
    floor: number,
    roomId: string,
    row: number,
    col: number,
  ): 'added' | 'removed' | 'invalid' {
    if (!isInterior(row, col)) return 'invalid'
    ensureFloor(floor)
    const layout = floorLayouts[floor]
    if (!layout[roomId]) layout[roomId] = []

    const ownedBy = getCellOwner(floor, row, col)

    if (ownedBy === roomId) {
      layout[roomId] = layout[roomId].filter((c) => !(c.row === row && c.col === col))
      return 'removed'
    }

    if (ownedBy) {
      layout[ownedBy] = layout[ownedBy].filter((c) => !(c.row === row && c.col === col))
    }
    layout[roomId] = [...layout[roomId], { row, col }]
    return 'added'
  }

  function resetFloorLayout(floor: number) {
    floorLayouts[floor] = createDefaultRoomLayout()
    floorCustomWalls[floor] = []
  }

  /** Move a cell from its source position to a target position (keeping room ownership) */
  function moveRoomCell(floor: number, fromRow: number, fromCol: number, toRow: number, toCol: number) {
    if (!isInterior(toRow, toCol)) return
    ensureFloor(floor)
    const layout = floorLayouts[floor]
    const owner = getCellOwner(floor, fromRow, fromCol)
    if (!owner) return
    // If the target is occupied by another room, release its original ownership first
    const targetOwner = getCellOwner(floor, toRow, toCol)
    if (targetOwner && targetOwner !== owner) {
      layout[targetOwner] = layout[targetOwner].filter((c) => !(c.row === toRow && c.col === toCol))
    }
    // Remove from the source room and add to the target position
    layout[owner] = layout[owner].filter((c) => !(c.row === fromRow && c.col === fromCol))
    if (!layout[owner].some((c) => c.row === toRow && c.col === toCol)) {
      layout[owner].push({ row: toRow, col: toCol })
    }
  }

  /** Get the custom walls of a floor */
  function getCustomWalls(floor: number) {
    ensureFloor(floor)
    return floorCustomWalls[floor]
  }

  /** Add a custom wall */
  function addCustomWall(floor: number, wall: { x1: number; z1: number; x2: number; z2: number }) {
    ensureFloor(floor)
    floorCustomWalls[floor].push(wall)
  }

  /** Remove a custom wall (by index) */
  function removeCustomWall(floor: number, index: number) {
    ensureFloor(floor)
    floorCustomWalls[floor].splice(index, 1)
  }

  /** Move a custom wall (update coordinates by index) */
  function moveCustomWall(
    floor: number,
    index: number,
    wall: { x1: number; z1: number; x2: number; z2: number },
  ) {
    ensureFloor(floor)
    if (index >= 0 && index < floorCustomWalls[floor].length) {
      floorCustomWalls[floor][index] = wall
    }
  }

  function cellToRoomMap(floor: number) {
    ensureFloor(floor)
    return buildCellToRoomMap(floorLayouts[floor])
  }

  function roomCellCount(floor: number, roomId: string) {
    ensureFloor(floor)
    return (floorLayouts[floor][roomId] || []).length
  }

  function listDeviceInstances(
    floor: number,
    roomId: string | null,
  ): Array<{
    type: DeviceType
    roomKey: string
    seed: number
    deviceId: string
    sn: string
  }> {
    ensureFloor(floor)
    const entries: Array<{
      type: DeviceType
      roomKey: string
      seed: number
      deviceId: string
      sn: string
    }> = []

    const pushRoom = (rid: string) => {
      const room = FLOOR_ROOMS.find((r) => r.id === rid)
      const idx = room?.index ?? 0
      for (const id of roomDeviceIds[floor][rid] || []) {
        const dev = floorInventory[floor].find((d) => d.id === id)
        if (!dev) continue
        entries.push({
          type: dev.type,
          roomKey: rid,
          deviceId: id,
          sn: dev.sn,
          seed: floor * 100 + idx * 10 + dev.type.charCodeAt(0) + id.length,
        })
      }
    }

    if (roomId) pushRoom(roomId)
    else {
      for (const rid of Object.keys(roomDeviceIds[floor])) pushRoom(rid)
    }
    return entries
  }

  function getFloorStats(floor: number): FloorStats {
    ensureFloor(floor)
    const stats = computeFloorStats(floor, floorInventory[floor], roomDeviceIds[floor])
    // Real WingOnIOT data takes priority; without floor data, stats are cleared and demo data is never shown
    const env = floorEnv[floor]
    const hasReal = !!env
    stats.temperature = env && env.temperature != null ? env.temperature : null
    stats.humidity = env && env.humidity != null ? env.humidity : null
    // WingOnIOT only provides temperature/humidity; clear the other environment metrics (CO₂/PM2.5/current/occupancy etc.)
    stats.current = null
    stats.cableTemp = null
    stats.co2 = null
    stats.pm25 = null
    stats.periodIn = null
    stats.periodOut = null
    stats.occupancy = null
    stats.co2High = false
    stats.metricAlert = false
    if (hasReal) {
      // Floors with WingOnIOT devices: device count = real device count (a device with a latest reading counts as online)
      stats.registered = env.deviceCount
      stats.connected = env.deviceCount
      stats.failed = 0
      stats.untested = 0
      stats.assigned = env.deviceCount
      stats.unassigned = 0
      stats.byType = { CT103: 0, AM319: 0, VS135: 0 }
    } else {
      // Floors without WingOnIOT devices: stats are zeroed
      stats.registered = 0
      stats.connected = 0
      stats.failed = 0
      stats.untested = 0
      stats.assigned = 0
      stats.unassigned = 0
      stats.byType = { CT103: 0, AM319: 0, VS135: 0 }
    }
    stats.mqttAlert = false
    stats.abnormal = false
    return stats
  }

  const allFloorStats = computed(() => {
    const list: FloorStats[] = []
    for (let i = 1; i <= FLOOR_COUNT; i++) list.push(getFloorStats(i))
    return list
  })

  /** 每层楼设备级温湿度统计（max/min/avg + 超标设备列表） */
  const floorDeviceStats = computed<FloorDeviceStats[]>(() => {
    const statsMap: Record<number, { temps: { val: number; sn: string }[]; humids: { val: number; sn: string }[] }> = {}
    for (const d of envDevices.value) {
      if (d.level == null || d.level < 1 || d.level > FLOOR_COUNT) continue
      if (!statsMap[d.level]) statsMap[d.level] = { temps: [], humids: [] }
      if (d.temperatureMedian != null) {
        statsMap[d.level].temps.push({ val: d.temperatureMedian, sn: d.sn })
      }
      if (d.humidityMedian != null) {
        statsMap[d.level].humids.push({ val: d.humidityMedian, sn: d.sn })
      }
    }
    const result: FloorDeviceStats[] = []
    for (let level = 1; level <= FLOOR_COUNT; level++) {
      const entry = statsMap[level]
      if (!entry || (entry.temps.length === 0 && entry.humids.length === 0)) {
        result.push({
          level,
          temperature: { max: null, min: null, avg: null },
          humidity: { max: null, min: null, avg: null },
          tempExceeding: [],
          humidityExceeding: [],
          hasAlert: false,
        })
        continue
      }
      // 温度统计
      let tMax: number | null = null
      let tMin: number | null = null
      let tSum = 0
      const tempExceeding: string[] = []
      for (const t of entry.temps) {
        if (tMax === null || t.val > tMax) tMax = t.val
        if (tMin === null || t.val < tMin) tMin = t.val
        tSum += t.val
        if (t.val > TEMP_THRESHOLD) tempExceeding.push(t.sn)
      }
      const tAvg = entry.temps.length > 0 ? Math.round((tSum / entry.temps.length) * 10) / 10 : null
      // 湿度统计
      let hMax: number | null = null
      let hMin: number | null = null
      let hSum = 0
      const humidityExceeding: string[] = []
      for (const h of entry.humids) {
        if (hMax === null || h.val > hMax) hMax = h.val
        if (hMin === null || h.val < hMin) hMin = h.val
        hSum += h.val
        if (h.val > HUMIDITY_THRESHOLD) humidityExceeding.push(h.sn)
      }
      const hAvg = entry.humids.length > 0 ? Math.round((hSum / entry.humids.length) * 10) / 10 : null
      result.push({
        level,
        temperature: { max: tMax, min: tMin, avg: tAvg },
        humidity: { max: hMax, min: hMin, avg: hAvg },
        tempExceeding,
        humidityExceeding,
        hasAlert: tempExceeding.length > 0 || humidityExceeding.length > 0,
      })
    }
    return result
  })

  const buildingSummary = computed(() => {
    const floors = allFloorStats.value
    const byType: Record<DeviceType, number> = { CT103: 0, AM319: 0, VS135: 0 }
    let registered = 0
    let connected = 0
    let failed = 0
    let untested = 0
    let assigned = 0
    let mqttAlertFloors = 0
    let metricAlertFloors = 0
    for (const f of floors) {
      registered += f.registered
      connected += f.connected
      failed += f.failed
      untested += f.untested
      assigned += f.assigned
      byType.CT103 += f.byType.CT103
      byType.AM319 += f.byType.AM319
      byType.VS135 += f.byType.VS135
      if (f.mqttAlert) mqttAlertFloors += 1
      if (f.metricAlert) metricAlertFloors += 1
    }
    return {
      registered,
      connected,
      failed,
      untested,
      assigned,
      unassigned: Math.max(0, registered - assigned),
      byType,
      mqttAlertFloors,
      metricAlertFloors,
      /** Floors with either alert type */
      abnormalFloors: floors.filter((f) => f.abnormal).length,
      floors,
    }
  })

  return {
    floorEnv,
    envLoading,
    envError,
    fetchFloorEnv,
    envDevices,
    fetchEnvDevices,
    devicesForFloor,
    floorDeviceStats,
    buildings,
    floors,
    fetchBuildingStructure,
    floorIdByLevel,
    fetchFloorRooms,
    getFloorRooms,
    floorInventory,
    roomDeviceIds,
    floorLayouts,
    floorCustomWalls,
    ensureFloor,
    getInventory,
    getRoomAssignments,
    getUnassignedInventory,
    getAssignableToRoom,
    addInventoryDevice,
    removeInventoryDevice,
    setInventoryMqttOk,
    assignDeviceToRoom,
    removeDeviceFromRoom,
    getFloorMap,
    getFloorLayout,
    getCellOwner,
    assignRoomCell,
    resetFloorLayout,
    moveRoomCell,
    getCustomWalls,
    addCustomWall,
    removeCustomWall,
    moveCustomWall,
    cellToRoomMap,
    roomCellCount,
    listDeviceInstances,
    getFloorStats,
    allFloorStats,
    buildingSummary,
  }
})
