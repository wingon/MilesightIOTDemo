<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import Floor3D, { type DeviceMarker } from '@/components/building/Floor3D.vue'
import { floorName, type Cell, type DeviceType, type RoomMeta } from '@/utils/buildingDemo'

const props = defineProps<{
  floor: number
  roomDevices: Record<string, DeviceType[]>
  selectedRoom: string | null
  layout: Record<string, Cell[]>
  editMode: boolean
  /** User-defined custom walls */
  customWalls?: { x1: number; z1: number; x2: number; z2: number }[]
  /** DB device count per room (key is roomId; defaults to room-1 when the DB has no room field) */
  deviceCountMap?: Record<string, number>
  /** Index of the selected custom wall in edit mode */
  selectedWallIndex?: number | null
  /** DB floor rooms (room_id + room_number + optional room_name) */
  rooms?: Array<{ room_id: string; room_number: string; room_name?: string | null }>
  /** roomId -> metadata (index + color) resolved from DB rooms */
  roomMeta?: Record<string, RoomMeta>
  /** 设备 3D 标记（已绑定格子的设备） */
  devices?: DeviceMarker[]
  /** 当前待绑定格子的设备 SN（非空时点击格子触发 bindCell） */
  bindSn?: string | null
  /** 面板中悬停的设备 SN（用于3D高亮） */
  hoverSn?: string | null
  /** 大厅/开放区域设备数 */
  lobbyCount?: number
  /** 大厅格子数（未被房间占用的有效格子） */
  lobbyCellCount?: number
}>()

const emit = defineEmits<{
  selectRoom: [roomId: string | null]
  'update:editMode': [value: boolean]
  toggleCell: [payload: { row: number; col: number }]
  dropCell: [payload: { row: number; col: number; roomId: string }]
  dropWall: [payload: { row: number; col: number; dir: 'v' | 'h' }]
  resetLayout: []
  selectWall: [index: number | null]
  moveWall: [payload: { index: number; row: number; col: number }]
  removeWall: [index: number]
  moveCell: [payload: { fromRow: number; fromCol: number; row: number; col: number }]
  bindCell: [payload: { row: number; col: number }]
  createRoom: []
  renameRoom: [roomId: string, name: string]
  deleteRoom: [roomId: string]
  hoverDevice: [sn: string | null]
}>()

const { t } = useI18n()

/** 行内改名状态：正在编辑的房间 id 与临时名称 */
const editingRoomId = ref<string | null>(null)
const editingName = ref('')

/** 房间显示名称：优先自定义 room_name，否则回退「房間 {index}」 */
function roomDisplayName(room: { room_id: string; room_number: string; room_name?: string | null }) {
  if (room.room_name && room.room_name.trim()) return room.room_name
  const meta = props.roomMeta?.[room.room_id]
  if (meta && meta.index) return t('building.roomN', { n: meta.index })
  return room.room_number || t('building.roomN', { n: meta?.index ?? '' })
}

function startEditRoom(room: { room_id: string; room_number: string; room_name?: string | null }) {
  if (!props.editMode) return
  editingRoomId.value = room.room_id
  editingName.value = roomDisplayName(room)
}

function commitEditRoom(roomId: string) {
  if (editingRoomId.value !== roomId) return
  const name = editingName.value.trim()
  editingRoomId.value = null
  if (!name) return
  emit('renameRoom', roomId, name)
}

function cancelEditRoom() {
  editingRoomId.value = null
}

function onRoomClick(roomId: string | null) {
  if (!roomId) {
    emit('selectRoom', null)
    return
  }
  emit('selectRoom', props.selectedRoom === roomId ? null : roomId)
}

function cellCount(roomId: string) {
  return (props.layout[roomId] || []).length
}

function deviceCount(roomId: string) {
  return props.deviceCountMap?.[roomId] ?? 0
}

/** Generate a graphics-only drag image (no text) */
function makeDragImage(color: string | null, dir: 'v' | 'h' | null) {
  const canvas = document.createElement('canvas')
  canvas.width = 36
  canvas.height = 36
  const ctx = canvas.getContext('2d')!
  if (color) {
    ctx.fillStyle = color
    ctx.fillRect(8, 8, 20, 20)
  } else if (dir) {
    ctx.strokeStyle = '#8a6d3b'
    ctx.lineWidth = 6
    ctx.lineCap = 'round'
    if (dir === 'v') {
      ctx.beginPath()
      ctx.moveTo(18, 6)
      ctx.lineTo(18, 30)
    } else {
      ctx.beginPath()
      ctx.moveTo(6, 18)
      ctx.lineTo(30, 18)
    }
    ctx.stroke()
  }
  return canvas
}

/** Room card drag start */
function onRoomDragStart(ev: DragEvent, roomId: string) {
  if (!props.editMode) return
  ev.dataTransfer!.effectAllowed = 'copy'
  ev.dataTransfer!.setData('application/json', JSON.stringify({ type: 'room', roomId }))
  const meta = props.roomMeta?.[roomId]
  if (meta) {
    ev.dataTransfer!.setDragImage(makeDragImage(meta.color, null), 18, 18)
  }
}

/** Wall drag start */
function onWallDragStart(ev: DragEvent, dir: 'v' | 'h') {
  if (!props.editMode) return
  ev.dataTransfer!.effectAllowed = 'copy'
  ev.dataTransfer!.setData('application/json', JSON.stringify({ type: 'wall', dir }))
  ev.dataTransfer!.setDragImage(makeDragImage(null, dir), 18, 18)
}
</script>

<template>
  <div class="floor-model">
    <div class="toolbar">
      <div class="title">
        {{ t('building.level', { n: floorName(floor) }) }}
        <span class="hint">
          {{ editMode ? t('building.floorModelHintEdit') : t('building.floorModelHint3d') }}
        </span>
      </div>
      <div class="toolbar-actions">
        <a-button
          size="small"
          :type="editMode ? 'primary' : 'default'"
          @click="emit('update:editMode', !editMode)"
        >
          {{ editMode ? t('building.doneEditCells') : t('building.editCells') }}
        </a-button>
        <a-button v-if="editMode" size="small" danger @click="emit('resetLayout')">
          {{ t('building.resetLayout') }}
        </a-button>
        <a-button
          v-if="editMode && selectedWallIndex !== null && selectedWallIndex !== undefined"
          size="small"
          danger
          @click="emit('removeWall', selectedWallIndex)"
        >
          {{ t('building.removeSelectedWall') }}
        </a-button>
        <a-button size="small" :disabled="!selectedRoom" @click="emit('selectRoom', null)">
          {{ t('building.clearRoom') }}
        </a-button>
      </div>
    </div>

    <div class="stage">
      <div class="viewport">
        <Floor3D
          :level="floor"
          :selected-room="selectedRoom"
          :room-devices="roomDevices"
          :layout="layout"
          :edit-mode="editMode"
          :custom-walls="customWalls"
          :room-meta="roomMeta"
          :devices="devices"
          :device-count-map="deviceCountMap"
          :bind-sn="bindSn"
          :hover-sn="hoverSn"
          @select-room="(id) => emit('selectRoom', id)"
          @toggle-cell="(p) => emit('toggleCell', p)"
          @drop-cell="(p) => emit('dropCell', p)"
          @drop-wall="(p) => emit('dropWall', p)"
          @select-wall="(i) => emit('selectWall', i)"
          @move-wall="(p) => emit('moveWall', p)"
          @remove-wall="(i) => emit('removeWall', i)"
          @move-cell="(p) => emit('moveCell', p)"
          @bind-cell="(p) => emit('bindCell', p)"
          @hover-device="(sn) => emit('hoverDevice', sn)"
        />
      </div>

      <aside class="legend">
        <div class="legend-title-row">
          <span class="legend-title">{{ t('building.rooms') }}</span>
          <span class="legend-tools">
            <button
              v-if="editMode"
              type="button"
              class="legend-tool"
              :title="t('building.addRoom')"
              @click="emit('createRoom')"
            >
              ＋
            </button>
            <button
              v-if="editMode"
              type="button"
              class="legend-tool danger"
              :title="t('building.deleteRoom')"
              :disabled="!selectedRoom"
              @click="selectedRoom && emit('deleteRoom', selectedRoom)"
            >
              －
            </button>
          </span>
        </div>
        <div
          v-for="room in rooms"
          :key="room.room_id"
          class="legend-item"
          role="button"
          tabindex="0"
          :class="{ active: selectedRoom === room.room_id }"
          :draggable="editMode"
          @click="onRoomClick(room.room_id)"
          @keydown.enter="onRoomClick(room.room_id)"
          @dragstart="(e) => onRoomDragStart(e, room.room_id)"
        >
          <i class="swatch" :style="{ background: roomMeta?.[room.room_id]?.color }" />
          <template v-if="editingRoomId === room.room_id">
            <input
              v-model="editingName"
              class="room-name-input"
              :placeholder="t('building.roomNamePlaceholder')"
              @click.stop
              @keydown.enter.prevent="commitEditRoom(room.room_id)"
              @keydown.esc.prevent="cancelEditRoom"
              @blur="commitEditRoom(room.room_id)"
            />
          </template>
          <span v-else class="room-name" @click.stop="startEditRoom(room)">
            {{ roomDisplayName(room) }}
          </span>
          <span class="count" :title="t('building.cellCount')">{{ cellCount(room.room_id) }}</span>
          <span class="count dim">{{ deviceCount(room.room_id) }}</span>
        </div>
        <div
          v-if="lobbyCount != null && lobbyCount > 0"
          class="legend-item"
          role="button"
          tabindex="0"
          @click="onRoomClick(null)"
        >
          <i class="swatch" :style="{ background: '#9A9A9A' }" />
          <span>{{ t('building.lobby') }}</span>
          <span class="count" :title="t('building.cellCount')">{{ lobbyCellCount ?? 0 }}</span>
          <span class="count dim">{{ lobbyCount }}</span>
        </div>
        <p v-if="bindSn" class="legend-hint">{{ t('building.bindHint') }}</p>
        <p v-else-if="editMode && !selectedRoom" class="legend-hint">{{ t('building.editSelectRoom') }}</p>

        <!-- Wall drag items (shown in edit mode only) -->
        <div v-if="editMode" class="wall-section">
          <div class="wall-divider" />
          <div class="legend-title">{{ t('building.walls') }}</div>
          <div
            class="wall-item"
            draggable="true"
            @dragstart="(e) => onWallDragStart(e, 'v')"
          >
            <span class="wall-icon">┃</span>
            <span>{{ t('building.dragWallV') }}</span>
          </div>
          <div
            class="wall-item"
            draggable="true"
            @dragstart="(e) => onWallDragStart(e, 'h')"
          >
            <span class="wall-icon">─</span>
            <span>{{ t('building.dragWallH') }}</span>
          </div>
          <p class="wall-hint">{{ t('building.dragWallHint') }}</p>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped lang="less">
.floor-model {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--brand-surface, #fff);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #e6e2da;
  flex-wrap: wrap;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.title {
  font-weight: 650;
  color: #0d0d0d;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hint {
  font-weight: 400;
  font-size: 12px;
  color: #6b6b6b;
  user-select: none;
}

.stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 168px;
  gap: 10px;
  padding: 12px;
  background: var(--brand-canvas, #f0eee9);
}

.viewport {
  min-height: 320px;
  height: 100%;
  border: 1px solid #e6e2da;
  background: var(--brand-canvas, #f0eee9);
  overflow: hidden;
}

.legend {
  overflow: auto;
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.legend-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  padding: 0 4px;
  margin-bottom: 6px;
}

.legend-title {
  font-size: 12px;
  font-weight: 650;
  color: #6b6b6b;
}

.legend-tools {
  display: flex;
  gap: 2px;
}

.legend-tool {
  width: 18px;
  height: 18px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #d8d2c4;
  border-radius: 4px;
  background: var(--brand-surface, #fff);
  color: #6b6b6b;
  font-size: 13px;
  cursor: pointer;
  padding: 0;

  &:hover:not(:disabled) {
    border-color: #a88955;
    color: #8a6d3b;
    background: var(--brand-canvas, #f7f7f5);
  }

  &.danger:hover:not(:disabled) {
    border-color: #b42318;
    color: #b42318;
  }

  &:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
}

.room-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border-bottom: 1px dashed transparent;

  &:hover {
    border-bottom-color: #c4a574;
  }
}

.room-name-input {
  min-width: 0;
  flex: 1;
  font-size: 12px;
  color: #0d0d0d;
  border: 1px solid #a88955;
  border-radius: 3px;
  padding: 1px 4px;
  outline: none;
  background: var(--brand-surface, #fff);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: transparent;
  padding: 6px 6px;
  cursor: pointer;
  text-align: left;
  font-size: 12px;
  color: #0d0d0d;

  &:hover,
  &.active {
    background: var(--brand-canvas, #f7f7f5);
  }

  &.active {
    font-weight: 650;
  }
}

.swatch {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.count {
  min-width: 24px;
  text-align: right;
  margin-left: auto;
  color: #0d0d0d;
  font-variant-numeric: tabular-nums;
  font-size: 11px;

  &:first-of-type {
    margin-left: auto;
  }

  &.dim {
    margin-left: 8px;
    color: #6b6b6b;
  }
}

.legend-hint {
  margin: 8px 4px 0;
  font-size: 11px;
  color: #a88955;
  line-height: 1.35;
}

.wall-section {
  margin-top: 4px;
}

.wall-divider {
  height: 1px;
  background: var(--brand-line, #e6e2da);
  margin: 6px 0;
}

.wall-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 6px;
  cursor: grab;
  font-size: 12px;
  color: #0d0d0d;
  border: 1px dashed #c4a574;
  border-radius: 4px;
  background: var(--brand-canvas, #f7f7f5);
}

.wall-item:hover {
  background: var(--brand-canvas, #f0eee9);
}

.wall-hint {
  margin: 6px 4px 0;
  font-size: 11px;
  color: #a88955;
  line-height: 1.35;
}

.wall-icon {
  font-size: 16px;
  color: #8B7355;
  font-weight: 700;
}

@media (max-width: 900px) {
  .stage {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(320px, 1fr) auto;
  }

  .legend {
    max-height: 160px;
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>
