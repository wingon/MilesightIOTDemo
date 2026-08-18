<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import FloorModelPanel from '@/components/building/FloorModelPanel.vue'
import DeviceDetailPanel from '@/components/building/DeviceDetailPanel.vue'
import { useBuildingStore } from '@/stores/building'
import { FLOOR_COUNT, buildRoomMeta, floorName, type Cell } from '@/utils/buildingDemo'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useBuildingStore()

const selectedRoom = ref<string | null>(null)
const editMode = ref(false)
const selectedWallIndex = ref<number | null>(null)

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
    // Fetch the DB building structure then the floor rooms (Room / Room_Cell)
    store.fetchBuildingStructure().then(() => store.fetchFloorRooms(n))
    selectedRoom.value = null
    editMode.value = false
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
  const map: Record<string, Cell[]> = {}
  for (const r of dbRooms.value) {
    map[r.room_id] = r.cells.map((c) => ({ row: c.row, col: c.col }))
  }
  return map
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

/** DB device count per room (DB has no room field, so all devices default to room_number=1) */
const deviceCountMap = computed(() => {
  const map: Record<string, number> = {}
  for (const r of dbRooms.value) map[r.room_id] = 0
  if (panelEnvDevices.value.length) {
    const first = dbRooms.value.find((r) => parseInt(r.room_number, 10) === 1)
    if (first) map[first.room_id] = panelEnvDevices.value.length
  }
  return map
})

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

function onToggleCell(payload: { row: number; col: number }) {
  if (!selectedRoom.value) return
  store.assignRoomCell(floor.value, selectedRoom.value, payload.row, payload.col)
}

function onDropCell(payload: { row: number; col: number; roomId: string }) {
  store.assignRoomCell(floor.value, payload.roomId, payload.row, payload.col)
}

function onDropWall(payload: { row: number; col: number; dir: 'v' | 'h' }) {
  const half = 1.15 / 2
  const halfCols = 12 / 2
  const halfRows = 8 / 2
  const x = (payload.col - halfCols - 0.5) * 1.15
  const z = (payload.row - halfRows - 0.5) * 1.15
  if (payload.dir === 'h') {
    // Horizontal wall: placed along the bottom edge of the cell (X direction)
    store.addCustomWall(floor.value, {
      x1: x - half,
      z1: z + half,
      x2: x + half,
      z2: z + half,
    })
    return
  }
  // Vertical wall: placed along the right edge of the cell (Z direction)
  store.addCustomWall(floor.value, {
    x1: x + half,
    z1: z - half,
    x2: x + half,
    z2: z + half,
  })
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
}

function onRemoveWall(index: number) {
  store.removeCustomWall(floor.value, index)
  selectedWallIndex.value = null
}

function onMoveCell(payload: { fromRow: number; fromCol: number; row: number; col: number }) {
  store.moveRoomCell(floor.value, payload.fromRow, payload.fromCol, payload.row, payload.col)
}

function onResetLayout() {
  store.resetFloorLayout(floor.value)
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
          @select-room="onSelectRoom"
          @update:edit-mode="(v) => (editMode = v)"
          @toggle-cell="onToggleCell"
          @drop-cell="onDropCell"
          @drop-wall="onDropWall"
          @reset-layout="onResetLayout"
          @select-wall="onSelectWall"
          @move-wall="onMoveWall"
          @remove-wall="onRemoveWall"
          @move-cell="onMoveCell"
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
          manageable
          @assign-to-room="onAssignToRoom"
          @remove-from-room="onRemoveFromRoom"
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
  height: calc(100vh - 96px);
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
