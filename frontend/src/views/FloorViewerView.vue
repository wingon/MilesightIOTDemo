<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import FloorModelPanel from '@/components/building/FloorModelPanel.vue'
import DeviceDetailPanel from '@/components/building/DeviceDetailPanel.vue'
import { useBuildingStore, TEMP_THRESHOLD, HUMIDITY_THRESHOLD } from '@/stores/building'
import { FLOOR_COUNT, buildRoomMeta, floorName, isInterior, GRID_ROWS, GRID_COLS, shouldExcludeCell, type Cell } from '@/utils/buildingDemo'
import type { EnvironmentDevice } from '@/api/environment'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useBuildingStore()

const selectedRoom = ref<string | null>(null)
const editMode = ref(false)
const editDirty = ref(false)
const selectedWallIndex = ref<number | null>(null)
/** 当前处于「绑定到格子」状态的设备 SN（在 3D 中点击格子完成绑定） */
const pendingBindSn = ref<string | null>(null)

const floor = computed(() => {
  const n = Number(route.params.floor)
  return Number.isFinite(n) ? n : NaN
})

const floorValid = computed(
  () => Number.isInteger(floor.value) && floor.value >= 1 && floor.value <= FLOOR_COUNT,
)

watch(
  floor,
  (n) => {
    if (!floorValid.value) {
      router.replace({ name: 'building-viewer' })
      return
    }
    store.ensureFloor(n)
    // Fetch real WingOnIOT environment devices (this page must show DB devices, not demo)
    store.fetchEnvDevices()
    // Fetch the DB building structure then the floor rooms (room / room_cell)
    store.fetchBuildingStructure().then(() => store.fetchFloorRooms(n))
    selectedRoom.value = null
    editMode.value = false
    editDirty.value = false
    selectedWallIndex.value = null
  },
  { immediate: true },
)

const roomDevices = computed(() => {
  if (!floorValid.value) return {}
  return store.getFloorMap(floor.value)
})

/** DB floor rooms (Room table, with occupied cells) */
const dbRooms = computed(() => {
  if (!floorValid.value) return []
  return store.getFloorRooms(floor.value)
})

/** roomId -> metadata (index + color) resolved from DB rooms */
const roomMeta = computed(() => buildRoomMeta(dbRooms.value))

const layout = computed(() => {
  if (!floorValid.value) return {}
  return store.getFloorLayout(floor.value)
})

const customWalls = computed(() => {
  if (!floorValid.value) return []
  return store.getCustomWalls(floor.value)
})

const panelDevices = computed(() => {
  if (!floorValid.value) return []
  return store.listDeviceInstances(floor.value, selectedRoom.value)
})

/** Real WingOnIOT environment devices for the selected floor (empty when no data; panel shows empty state instead of demo) */
const panelEnvDevices = computed(() => {
  if (!floorValid.value) return []
  return store.devicesForFloor(floor.value)
})

/** 本层房间业务键集合（用于判断格子归属） */
const deviceRoomIds = computed(() => new Set(dbRooms.value.map((r) => r.room_id)))

/** 每台真实设备归属统计：按设备绑定格子反查所属房间。
 *  优先使用当前 3D layout 的格子归属（用户编辑后的状态），
 *  仅当格子在本地 layout 中无归属时才回退到 API 返回的 room_id。 */
const deviceCountMap = computed(() => {
  const map: Record<string, number> = {}
  for (const r of dbRooms.value) map[r.room_id] = 0

  // cell key -> roomId from the current layout (same source as the 3D room blocks)
  const cellToRoom = new Map<string, string>()
  for (const [rid, cells] of Object.entries(layout.value)) {
    for (const c of cells) cellToRoom.set(`${c.row}-${c.col}`, rid)
  }

  for (const d of panelEnvDevices.value) {
    if (!d.cell) continue
    const key = `${d.cell.row_no}-${d.cell.col_no}`
    // 优先使用本地 layout 映射（反映用户编辑后的最新状态），
    // 仅当本地无映射时回退到 API room_id（兜底）
    const roomId =
      cellToRoom.get(key) ??
      (d.room_id && deviceRoomIds.value.has(d.room_id) ? d.room_id : null)
    if (roomId && deviceRoomIds.value.has(roomId)) {
      map[roomId] = (map[roomId] || 0) + 1
    }
  }
  return map
})

/** 大厅/开放区域设备（已绑定到非房间格子） */
const lobbyDevices = computed(() => {
  // 构建本地 layout 的格子→房间映射
  const cellToRoom = new Map<string, string>()
  for (const [rid, cells] of Object.entries(layout.value)) {
    for (const c of cells) cellToRoom.set(`${c.row}-${c.col}`, rid)
  }
  return panelEnvDevices.value.filter((d) => {
    if (!d.cell) return false
    const key = `${d.cell.row_no}-${d.cell.col_no}`
    // 本地 layout 有归属 → 不是大厅
    if (cellToRoom.has(key)) return false
    // 本地无归属，但 API room_id 有效 → 不是大厅
    if (d.room_id && deviceRoomIds.value.has(d.room_id)) return false
    // 本地无归属 且 API 也无有效 room_id → 大厅设备
    return true
  })
})

/** 大厅格子数：所有有效格子中，不属于任何房间的格子数量 */
const lobbyCellCount = computed(() => {
  // 收集所有属于房间的格子
  const roomCellSet = new Set<string>()
  for (const cells of Object.values(layout.value)) {
    for (const c of cells) roomCellSet.add(`${c.row}-${c.col}`)
  }
  // 统计所有有效格子（内部格子且未被排除）中不属于任何房间的数量
  let count = 0
  for (let row = 1; row <= GRID_ROWS; row++) {
    for (let col = 1; col <= GRID_COLS; col++) {
      if (!isInterior(row, col)) continue
      if (shouldExcludeCell(floor.value, row, col)) continue
      if (!roomCellSet.has(`${row}-${col}`)) count++
    }
  }
  return count
})

/** 未绑定格子的设备（尚无位置；不含绑定已失效的设备） */
const unboundDevices = computed(() => panelEnvDevices.value.filter((d) => !d.cell && !d.cell_lost))

/** 绑定已失效的设备（device_cell 残留但目标格子已删/不存在） */
const lostDevices = computed(() => panelEnvDevices.value.filter((d) => d.cell_lost))

/** 设备 3D 标记（仅已绑定格子的设备；x/z 前端由 cellToWorld 计算） */
const deviceMarkers = computed(() =>
  panelEnvDevices.value
    .filter((d) => d.cell)
    .map((d) => ({
      sn: d.sn,
      name: d.deviceName || d.name || d.sn,
      row: d.cell!.row_no,
      col: d.cell!.col_no,
      abnormal: isEnvAbnormal(d),
    })),
)

/** 设备温度或湿度任一超标即异常 */
function isEnvAbnormal(d: EnvironmentDevice): boolean {
  return (
    (d.temperatureMedian != null && d.temperatureMedian > TEMP_THRESHOLD) ||
    (d.humidityMedian != null && d.humidityMedian > HUMIDITY_THRESHOLD)
  )
}

const assignableOptions = computed(() => {
  if (!floorValid.value) return []
  return store.getAssignableToRoom(floor.value, selectedRoom.value || '').map((d) => ({
    value: d.id,
    label: d.sn,
    type: d.type,
  }))
})

function onSelectRoom(roomId: string | null) {
  selectedRoom.value = roomId
}

function onAssignToRoom(deviceId: string) {
  if (!selectedRoom.value) {
    message.warning(t('building.selectRoomToAssign'))
    return
  }
  const ok = store.assignDeviceToRoom(floor.value, selectedRoom.value, deviceId)
  if (ok) message.success(t('building.assignedToRoom'))
}

function onRemoveFromRoom(payload: { roomId: string; deviceId: string }) {
  store.removeDeviceFromRoom(floor.value, payload.roomId, payload.deviceId)
}

/** 切换设备的「待绑定格子」状态（再点一次取消） */
function onSelectDeviceForBind(sn: string) {
  pendingBindSn.value = pendingBindSn.value === sn ? null : sn
}

/** 3D 点击格子 → 将待绑定设备绑到该格子（含大厅格子） */
async function onBindCell(payload: { row: number; col: number }) {
  const sn = pendingBindSn.value
  if (!sn) return
  const ok = await store.bindDeviceToCell(sn, floor.value, payload.row, payload.col)
  if (ok) message.success(t('building.deviceBound', { sn }))
  else message.error(t('building.deviceBindFailed'))
  pendingBindSn.value = null
}

/** 解绑设备的所有格子绑定 */
async function onUnbindDevice(sn: string) {
  const ok = await store.unbindDeviceFromCell(sn)
  if (ok) message.success(t('building.deviceUnbound', { sn }))
  else message.error(t('building.deviceUnbindFailed'))
  pendingBindSn.value = null
}

function onToggleCell(payload: { row: number; col: number }) {
  if (!selectedRoom.value) return
  store.assignRoomCell(floor.value, selectedRoom.value, payload.row, payload.col)
  editDirty.value = true
}

function onDropCell(payload: { row: number; col: number; roomId: string }) {
  store.assignRoomCell(floor.value, payload.roomId, payload.row, payload.col)
  editDirty.value = true
}

function onDropWall(payload: { row: number; col: number; dir: 'v' | 'h' }) {
  const half = 1.15 / 2
  const halfCols = 12 / 2
  const halfRows = 8 / 2
  const x = (payload.col - halfCols - 0.5) * 1.15
  const z = (payload.row - halfRows - 0.5) * 1.15
  if (payload.dir === 'h') {
    store.addCustomWall(floor.value, {
      x1: x - half,
      z1: z + half,
      x2: x + half,
      z2: z + half,
    })
    editDirty.value = true
    return
  }
  store.addCustomWall(floor.value, {
    x1: x + half,
    z1: z - half,
    x2: x + half,
    z2: z + half,
  })
  editDirty.value = true
}

function onSelectWall(index: number | null) {
  selectedWallIndex.value = index
}

function onMoveWall(payload: { index: number; row: number; col: number }) {
  const wall = store.getCustomWalls(floor.value)[payload.index]
  if (!wall) return
  const half = 1.15 / 2
  const halfCols = 12 / 2
  const halfRows = 8 / 2
  const x = (payload.col - halfCols - 0.5) * 1.15
  const z = (payload.row - halfRows - 0.5) * 1.15
  const horizontal = Math.abs(wall.z1 - wall.z2) < 0.01
  const moved: { x1: number; z1: number; x2: number; z2: number } = horizontal
    ? { x1: x - half, z1: z + half, x2: x + half, z2: z + half }
    : { x1: x + half, z1: z - half, x2: x + half, z2: z + half }
  store.moveCustomWall(floor.value, payload.index, moved)
  selectedWallIndex.value = null
  editDirty.value = true
}

function onRemoveWall(index: number) {
  store.removeCustomWall(floor.value, index)
  selectedWallIndex.value = null
  editDirty.value = true
}

function onMoveCell(payload: { fromRow: number; fromCol: number; row: number; col: number }) {
  store.moveRoomCell(floor.value, payload.fromRow, payload.fromCol, payload.row, payload.col)
  editDirty.value = true
}

function onResetLayout() {
  store.resetFloorLayout(floor.value)
  editDirty.value = true
}

/** 请求退出编辑模式：有变更时弹出确认框 */
function onRequestExitEdit() {
  if (!editDirty.value) {
    editMode.value = false
    return
  }
  Modal.confirm({
    title: t('building.saveChangesTitle'),
    content: t('building.saveChangesContent'),
    okText: t('building.saveChangesOk'),
    cancelText: t('building.saveChangesCancel'),
    async onOk() {
      // 保存布局到后端数据库
      const saving = message.loading(t('building.savingLayout') || '保存中...', 0)
      try {
        const ok = await store.saveFloorLayoutToDb(floor.value)
        if (ok) {
          message.success(t('building.savedSuccess'))
        } else {
          message.error(t('building.saveFailed') || '保存失败')
        }
      } finally {
        saving()
        editMode.value = false
        editDirty.value = false
      }
    },
    onCancel() {
      store.restoreLayoutSnapshot(floor.value)
      selectedRoom.value = null
      editDirty.value = false
    },
  })
}

function backToBuilding() {
  router.push({ name: 'building-viewer', query: { floor: String(floor.value) } })
}

const roomLabel = computed(() => {
  if (!selectedRoom.value) return null
  const meta = roomMeta.value[selectedRoom.value]
  return meta ? t('building.roomN', { n: meta.index }) : selectedRoom.value
})
</script>

<template>
  <div v-if="floorValid" class="floor-viewer">
    <div class="page-intro">
      <div>
        <h1>{{ t('building.floorTitle', { n: floorName(floor) }) }}</h1>
        <p>{{ t('building.floorSubtitle') }}</p>
      </div>
      <div class="intro-actions">
        <a-button @click="backToBuilding">{{ t('building.backBuilding') }}</a-button>
      </div>
    </div>

    <div class="workspace">
      <div class="left">
        <FloorModelPanel
          :floor="floor"
          :room-devices="roomDevices"
          :selected-room="selectedRoom"
          :layout="layout"
          :edit-mode="editMode"
          :custom-walls="customWalls"
          :device-count-map="deviceCountMap"
          :selected-wall-index="selectedWallIndex"
          :rooms="dbRooms"
          :room-meta="roomMeta"
          :devices="deviceMarkers"
          :bind-sn="pendingBindSn"
          :lobby-count="lobbyDevices.length"
          :lobby-cell-count="lobbyCellCount"
          @select-room="onSelectRoom"
          @update:edit-mode="(v) => { if (v) { store.saveLayoutSnapshot(floor); editMode = true; editDirty = false } else { onRequestExitEdit() } }"
          @toggle-cell="onToggleCell"
          @drop-cell="onDropCell"
          @drop-wall="onDropWall"
          @reset-layout="onResetLayout"
          @select-wall="onSelectWall"
          @move-wall="onMoveWall"
          @remove-wall="onRemoveWall"
          @move-cell="onMoveCell"
          @bind-cell="onBindCell"
        />
      </div>
      <div class="right">
        <DeviceDetailPanel
          :floor="floor"
          :room-key="selectedRoom"
          :room-label="roomLabel"
          :devices="panelDevices"
          :env-devices="panelEnvDevices"
          :assignable-options="assignableOptions"
          :can-enter="false"
          :bind-sn="pendingBindSn"
          :lobby-count="lobbyDevices.length"
          :unbound-count="unboundDevices.length"
          :room-meta="roomMeta"
          manageable
          @assign-to-room="onAssignToRoom"
          @remove-from-room="onRemoveFromRoom"
          @bind-device="onSelectDeviceForBind"
          @unbind-device="onUnbindDevice"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
.floor-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc((100vh / var(--ls-scale, 1)) - var(--ls-content-offset, 96px));
  min-height: 560px;
}

.page-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;

  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 650;
    color: #0d0d0d;
  }

  p {
    margin: 4px 0 0;
    color: #6b6b6b;
    font-size: 13px;
  }
}

.intro-actions {
  display: flex;
  gap: 8px;
}

.workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.9fr);
  gap: 12px;
}

.left,
.right {
  min-height: 0;
  min-width: 0;
  height: 100%;
  border: 1px solid #e6e2da;
  background: #fff;
}

@media (max-width: 1100px) {
  .floor-viewer {
    height: auto;
  }

  .workspace {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(420px, 55vh) minmax(360px, auto);
  }
}
</style>
