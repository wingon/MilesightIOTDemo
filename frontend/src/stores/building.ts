import { computed, reactive } from 'vue'
import { defineStore } from 'pinia'
import {
  buildCellToRoomMap,
  computeFloorStats,
  countAssignedIds,
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

  const floorDeviceCounts = computed(() => {
    const counts: Record<number, number> = {}
    for (let i = 1; i <= FLOOR_COUNT; i++) {
      if (floorInventory[i]) {
        counts[i] = countAssignedIds(roomDeviceIds[i] || {})
      } else {
        const seeded = createDefaultFloorInventory(i)
        counts[i] = countAssignedIds(seeded.roomAssignments)
      }
    }
    return counts
  })

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
    return computeFloorStats(floor, floorInventory[floor], roomDeviceIds[floor])
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
    floorDeviceCounts,
    listDeviceInstances,
    getFloorStats,
    allFloorStats,
    buildingSummary,
  }
})
