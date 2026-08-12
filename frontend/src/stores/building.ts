import { computed, reactive, ref } from 'vue'
import { defineStore } from 'pinia'
import { getFloorEnvironmentSummary, listEnvironmentDevices, type EnvironmentDevice } from '@/api/environment'
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
  /** floor -> 来自 WingOnIOT 库的真实温度/湿度（level 为 3D 楼栋层号） */
  const floorEnv = reactive<
    Record<
      number,
      {
        temperature: number | null
        humidity: number | null
        /** 该层有最新读数的设备数 */
        deviceCount: number
        updatedAt: string | null
      }
    >
  >({})
  const envLoading = ref(false)
  const envError = ref<string | null>(null)
  let envFetched = false

  /** 拉取 WingOnIOT 各楼层最新温度/湿度；失败不阻塞页面（保留 demo 回退） */
  async function fetchFloorEnv() {
    if (envFetched) return
    envFetched = true
    envLoading.value = true
    envError.value = null
    try {
      const { data } = await getFloorEnvironmentSummary()
      for (const row of data) {
        // level 为 3D 楼栋层号（1..FLOOR_COUNT）：B2/F→1、B1/F→2、G/F→3、n/F→n+3；
        // 超出范围的映射（如更深的地下室或更高楼层）无法渲染则跳过
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
      // 失败时复位标记，下次进入页面可重试
      envFetched = false
    } finally {
      envLoading.value = false
    }
  }

  /** WingOnIOT 真实环境设备（含每台最新温度/湿度） */
  const envDevices = ref<EnvironmentDevice[]>([])
  let envDevicesFetched = false

  /** 拉取 WingOnIOT 设备列表（含最新读数）；失败可重试 */
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

  /** 某 3D 层号对应的真实环境设备 */
  function devicesForFloor(level: number): EnvironmentDevice[] {
    return envDevices.value.filter((d) => d.level === level)
  }

  /** floor -> inventory devices registered to that floor */
  const floorInventory = reactive<Record<number, FloorInventoryDevice[]>>({})
  /** floor -> roomId -> inventory device ids assigned to room */
  const roomDeviceIds = reactive<Record<number, Record<string, string[]>>>({})
  /** floor -> roomId -> cells */
  const floorLayouts = reactive<Record<number, Record<string, Cell[]>>>({})

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
    // WingOnIOT 真实数据优先；无该层数据时统计清空，一律不显示 demo 数据
    const env = floorEnv[floor]
    const hasReal = !!env
    stats.temperature = env && env.temperature != null ? env.temperature : null
    stats.humidity = env && env.humidity != null ? env.humidity : null
    // WingOnIOT 只有温度/湿度，其余环境指标（CO₂/PM2.5/电流/占用率等）置空
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
      // 有 WingOnIOT 设备的楼层：设备数 = 真实设备数（有最新读数即视为在线）
      stats.registered = env.deviceCount
      stats.connected = env.deviceCount
      stats.failed = 0
      stats.untested = 0
      stats.assigned = env.deviceCount
      stats.unassigned = 0
      stats.byType = { CT103: 0, AM319: 0, VS135: 0 }
    } else {
      // 无 WingOnIOT 设备的楼层：统计清零
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
    floorInventory,
    roomDeviceIds,
    floorLayouts,
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
    cellToRoomMap,
    roomCellCount,
    listDeviceInstances,
    getFloorStats,
    allFloorStats,
    buildingSummary,
  }
})
