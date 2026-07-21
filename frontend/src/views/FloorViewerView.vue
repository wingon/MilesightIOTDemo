<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import FloorModelPanel from '@/components/building/FloorModelPanel.vue'
import DeviceDetailPanel from '@/components/building/DeviceDetailPanel.vue'
import { useBuildingStore } from '@/stores/building'
import { FLOOR_COUNT, FLOOR_ROOMS } from '@/utils/buildingDemo'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useBuildingStore()

const selectedRoom = ref<string | null>(null)
const editMode = ref(false)

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
    selectedRoom.value = null
    editMode.value = false
  },
  { immediate: true },
)

const roomDevices = computed(() => {
  if (!floorValid.value) return {}
  return store.getFloorMap(floor.value)
})

const layout = computed(() => {
  if (!floorValid.value) return {}
  return store.getFloorLayout(floor.value)
})

const panelDevices = computed(() => {
  if (!floorValid.value) return []
  return store.listDeviceInstances(floor.value, selectedRoom.value)
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

function onResetLayout() {
  store.resetFloorLayout(floor.value)
}

function backToBuilding() {
  router.push({ name: 'building-viewer', query: { floor: String(floor.value) } })
}

const roomLabel = computed(() => {
  if (!selectedRoom.value) return null
  const room = FLOOR_ROOMS.find((r) => r.id === selectedRoom.value)
  return room ? t('building.roomN', { n: room.index }) : selectedRoom.value
})
</script>

<template>
  <div v-if="floorValid" class="floor-viewer">
    <div class="page-intro">
      <div>
        <h1>{{ t('building.floorTitle', { n: floor }) }}</h1>
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
          @select-room="onSelectRoom"
          @update:edit-mode="(v) => (editMode = v)"
          @toggle-cell="onToggleCell"
          @reset-layout="onResetLayout"
        />
      </div>
      <div class="right">
        <DeviceDetailPanel
          :floor="floor"
          :room-key="selectedRoom"
          :room-label="roomLabel"
          :devices="panelDevices"
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
