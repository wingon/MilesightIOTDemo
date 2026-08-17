<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import Floor3D from '@/components/building/Floor3D.vue'
import { FLOOR_ROOMS, floorName, type Cell, type DeviceType } from '@/utils/buildingDemo'

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
}>()

const { t } = useI18n()

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
  const room = FLOOR_ROOMS.find((r) => r.id === roomId)
  if (room) {
    ev.dataTransfer!.setDragImage(makeDragImage(room.color, null), 18, 18)
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
          @select-room="(id) => emit('selectRoom', id)"
          @toggle-cell="(p) => emit('toggleCell', p)"
          @drop-cell="(p) => emit('dropCell', p)"
          @drop-wall="(p) => emit('dropWall', p)"
          @select-wall="(i) => emit('selectWall', i)"
          @move-wall="(p) => emit('moveWall', p)"
          @remove-wall="(i) => emit('removeWall', i)"
          @move-cell="(p) => emit('moveCell', p)"
        />
      </div>

      <aside class="legend">
        <div class="legend-title">{{ t('building.rooms') }}</div>
        <button
          v-for="room in FLOOR_ROOMS"
          :key="room.id"
          type="button"
          class="legend-item"
          :class="{ active: selectedRoom === room.id }"
          :draggable="editMode"
          @click="onRoomClick(room.id)"
          @dragstart="(e) => onRoomDragStart(e, room.id)"
        >
          <i class="swatch" :style="{ background: room.color }" />
          <span>{{ t('building.roomN', { n: room.index }) }}</span>
          <span class="count" :title="t('building.cellCount')">{{ cellCount(room.id) }}</span>
          <span class="count dim">{{ deviceCount(room.id) }}</span>
        </button>
        <p v-if="editMode && !selectedRoom" class="legend-hint">{{ t('building.editSelectRoom') }}</p>

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
  background: #fff;
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
}

.stage {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 168px;
  gap: 10px;
  padding: 12px;
  background: #f0eee9;
}

.viewport {
  min-height: 320px;
  height: 100%;
  border: 1px solid #e6e2da;
  background: #f0eee9;
  overflow: hidden;
}

.legend {
  overflow: auto;
  background: #fff;
  border: 1px solid #e6e2da;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.legend-title {
  font-size: 12px;
  font-weight: 650;
  color: #6b6b6b;
  margin-bottom: 6px;
  padding: 0 4px;
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
    background: #f7f7f5;
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
  margin-left: auto;
  color: #0d0d0d;
  font-variant-numeric: tabular-nums;
  font-size: 11px;

  &.dim {
    margin-left: 4px;
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
  background: #e6e2da;
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
  background: #faf8f5;
}

.wall-item:hover {
  background: #f0eee9;
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
