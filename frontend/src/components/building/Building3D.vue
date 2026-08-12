<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  CELL_SIZE,
  FLOOR_COUNT,
  INTERIOR_CELLS,
  cellToWorld,
  floorName,
  shouldExcludeCell,
} from '@/utils/buildingDemo'
import {
  envColorFor,
  envRange,
  type EnvMetric,
  type FloorEnvValue,
} from '@/utils/envColor'
import {
  createGeometryByType,
  isHiddenType,
  parseRotation,
  type CellShapeConfig,
  type GridType,
} from '@/utils/floorGrid'
import { brand } from '@/theme/colorConfig'

const props = defineProps<{
  selectedFloor: number | null
  /** WingOnIOT 各樓層真實溫度/濕度（key 為 3D 樓棟樓層號） */
  floorEnv?: Record<number, FloorEnvValue>
  /** 當前著色指標 */
  metric?: EnvMetric
  /** 自訂格子形狀設定（由 DB 驅動，無匹配設定時使用預設長方形） */
  cellShapes?: CellShapeConfig[]
}>()

const emit = defineEmits<{
  selectFloor: [floor: number]
}>()

const { t } = useI18n()

const host = ref<HTMLDivElement>()
const hoveredFloor = ref<number | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let raycaster: THREE.Raycaster | null = null
let pointer = new THREE.Vector2()
let animId = 0
/** All pickable floor cell meshes */
let floorMeshes: THREE.Mesh[] = []
/** floor number -> meshes */
const meshesByFloor = new Map<number, THREE.Mesh[]>()
let buildingGroup: THREE.Group | null = null

/**
 * 查詢指定格子的形狀設定
 *
 * 設定由 DB 驅動（:cell-shapes prop），不存在匹配時回退為預設長方形。
 *
 * @param floor - 當前樓層（3D 層號 1~11）
 * @param row   - 格子行號（1-based）
 * @param col   - 格子列號（1-based）
 * @returns 匹配的 CellShapeConfig，未找到則回傳 undefined（使用預設長方形）
 */
function getCellShapeConfig(
  floor: number,
  row: number,
  col: number,
): CellShapeConfig | undefined {
  return props.cellShapes?.find(
    (s) =>
      s.row === row &&
      s.col === col &&
      (s.floor === 0 || s.floor === floor),
  )
}

const FLOOR_H = 0.76
const FLOOR_GAP = 0.08
const SLAB = FLOOR_H + FLOOR_GAP

function floorColor(level: number, selected: number | null, hovered: number | null) {
  if (selected === level || hovered === level) return new THREE.Color(brand.primary)
  // WingOnIOT 真實資料按當前指標著色（溫度/濕度色帶）
  const env = props.floorEnv?.[level]
  const metric = props.metric ?? 'temperature'
  const value = env ? (metric === 'humidity' ? env.humidity : env.temperature) : null
  if (value != null) {
    const [min, max] = envRange(props.floorEnv, metric)
    const color = envColorFor(metric, value, min, max)
    if (color) return new THREE.Color(color)
  }
  // 無資料樓層保持預設漸變
  const t = level / Math.max(1, FLOOR_COUNT - 1)
  return new THREE.Color().setHSL(0.08, 0.12, 0.22 + t * 0.28)
}

function rebuildFloors() {
  if (!buildingGroup) return
  buildingGroup.clear()
  floorMeshes = []
  meshesByFloor.clear()

  const cellSize = CELL_SIZE * 0.96
  const cellGeo = new THREE.BoxGeometry(cellSize, FLOOR_H, cellSize) as THREE.BufferGeometry

  for (let i = 0; i < FLOOR_COUNT; i++) {
    const level = i + 1
    const yBase = i * SLAB
    const mats: THREE.MeshStandardMaterial[] = []
    const levelMeshes: THREE.Mesh[] = []

    for (const cell of INTERIOR_CELLS) {
      if (shouldExcludeCell(level, cell.row, cell.col)) continue
      
      const mat = new THREE.MeshStandardMaterial({
        color: floorColor(level, props.selectedFloor, hoveredFloor.value),
        metalness: 0.12,
        roughness: 0.55,
        transparent: true,
        opacity: 0.95,
      })
      mats.push(mat)
      
      // 根據設定決定形狀：查詢 cellShapes 或使用預設長方形
      const shapeConfig = getCellShapeConfig(level, cell.row, cell.col)
      const shapeType: GridType = shapeConfig?.shape ?? 'Rect'
      
      // Hidden 類型：跳過渲染，不建立 Mesh
      if (isHiddenType(shapeType)) continue
      
      // 長方形復用共享的 cellGeo，其他形狀按需建立（有幾何快取）
      const geo = shapeType === 'Rect'
        ? cellGeo
        : createGeometryByType(shapeType, cellSize, FLOOR_H)
      
      const mesh = new THREE.Mesh(geo, mat)
      const { x, z } = cellToWorld(cell.row, cell.col)
      mesh.position.set(x, yBase + FLOOR_H / 2, z)
      if (shapeConfig?.rotation) {
        mesh.rotation.copy(parseRotation(shapeConfig.rotation))
      }
      mesh.userData.floor = level
      mesh.castShadow = true
      mesh.receiveShadow = true
      buildingGroup.add(mesh)
      floorMeshes.push(mesh)
      levelMeshes.push(mesh)
    }
    meshesByFloor.set(level, levelMeshes)
  }

  // Visual core
  const core = new THREE.Mesh(
    new THREE.BoxGeometry(CELL_SIZE * 1.6, FLOOR_COUNT * SLAB, CELL_SIZE * 1.6),
    new THREE.MeshStandardMaterial({ color: 0x1a1a1a, metalness: 0.3, roughness: 0.4 }),
  )
  core.position.set(CELL_SIZE * 2, (FLOOR_COUNT * SLAB) / 2 - FLOOR_GAP / 2, CELL_SIZE)
  buildingGroup.add(core)

  const ground = new THREE.Mesh(
    new THREE.CircleGeometry(32, 64),
    new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.95 }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.05
  ground.receiveShadow = true
  buildingGroup.add(ground)

  updateFloorAppearance()
}

function updateFloorAppearance() {
  const selected = props.selectedFloor
  const hovered = hoveredFloor.value
  for (const [level, meshes] of meshesByFloor) {
    const isActive = selected === level || hovered === level
    const dimmed = !!(selected && selected !== level && hovered !== level)
    for (const mesh of meshes) {
      const mat = mesh.material as THREE.MeshStandardMaterial
      mat.color = floorColor(level, selected, hovered)
      mat.opacity = dimmed ? 0.28 : 0.95
      mat.emissive = new THREE.Color(isActive ? brand.primary : 0x000000)
      mat.emissiveIntensity = hovered === level ? 0.4 : selected === level ? 0.22 : 0
    }
  }
}

function deviceCountFor(floor: number) {
  // WingOnIOT 真實設備數（無該層資料為 0），不顯示 demo 計數
  return props.floorEnv?.[floor]?.deviceCount ?? 0
}

function updatePointer(ev: PointerEvent) {
  if (!host.value) return null
  const rect = host.value.getBoundingClientRect()
  pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
  return { rect, clientX: ev.clientX, clientY: ev.clientY }
}

function placeToast(clientX: number, clientY: number, rect: DOMRect) {
  const offset = 14
  let left = clientX - rect.left + offset
  let top = clientY - rect.top + offset
  left = Math.max(8, Math.min(left, rect.width - 168))
  top = Math.max(8, Math.min(top, rect.height - 64))
  toastStyle.value = { left: `${left}px`, top: `${top}px` }
}

function onPointerMove(ev: PointerEvent) {
  if (!host.value || !camera || !raycaster) return
  const pos = updatePointer(ev)
  if (!pos) return

  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(floorMeshes, false)
  if (hits.length) {
    const floor = hits[0].object.userData.floor as number
    if (hoveredFloor.value !== floor) {
      hoveredFloor.value = floor
      updateFloorAppearance()
    }
    toastVisible.value = true
    placeToast(pos.clientX, pos.clientY, pos.rect)
    host.value.style.cursor = 'pointer'
  } else {
    if (hoveredFloor.value != null) {
      hoveredFloor.value = null
      updateFloorAppearance()
    }
    toastVisible.value = false
    host.value.style.cursor = 'grab'
  }
}

function onPointerLeave() {
  hoveredFloor.value = null
  toastVisible.value = false
  updateFloorAppearance()
  if (host.value) host.value.style.cursor = 'grab'
}

function onPointerDown(ev: PointerEvent) {
  if (!camera || !raycaster) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(floorMeshes, false)
  if (hits.length) {
    emit('selectFloor', hits[0].object.userData.floor as number)
  }
}

function onResize() {
  if (!host.value || !camera || !renderer) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight
  camera.aspect = w / Math.max(1, h)
  camera.updateProjectionMatrix()
  renderer.setSize(w, h, false)
}

function animate() {
  animId = requestAnimationFrame(animate)
  controls?.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

onMounted(() => {
  if (!host.value) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf7f7f5)
  scene.fog = new THREE.Fog(0xf7f7f5, 55, 120)

  camera = new THREE.PerspectiveCamera(42, w / Math.max(1, h), 0.1, 220)
  camera.position.set(18, 13, 22)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)
  renderer.shadowMap.enabled = true
  host.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, (FLOOR_COUNT * SLAB) / 2, 0)
  controls.maxPolarAngle = Math.PI * 0.48
  controls.minDistance = 8
  controls.maxDistance = 60

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb0a090, 0.85))
  const dir = new THREE.DirectionalLight(0xfff5e6, 1.05)
  dir.position.set(18, 55, 12)
  dir.castShadow = true
  scene.add(dir)
  const fill = new THREE.DirectionalLight(0xc4a574, 0.35)
  fill.position.set(-20, 16, -10)
  scene.add(fill)

  buildingGroup = new THREE.Group()
  scene.add(buildingGroup)
  rebuildFloors()

  raycaster = new THREE.Raycaster()
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', onPointerLeave)
  window.addEventListener('resize', onResize)
  animate()
})

watch(
  () => props.selectedFloor,
  () => updateFloorAppearance(),
)

// 真實資料/指標變化時重新整理樓層顏色
watch(
  () => props.floorEnv,
  () => updateFloorAppearance(),
  { deep: true },
)
watch(
  () => props.metric,
  () => updateFloorAppearance(),
)

// 格子形狀設定變化時重建整個樓層（深比較，新增/刪除設定均觸發）
watch(
  () => props.cellShapes,
  () => rebuildFloors(),
  { deep: true },
)

// 圖例（當前指標色帶）
const legendRange = computed(() => envRange(props.floorEnv, props.metric ?? 'temperature'))
const legendUnit = computed(() => (props.metric === 'humidity' ? '%RH' : '°C'))
const legendLabel = computed(() =>
  props.metric === 'humidity' ? t('building.metricHumidity') : t('building.metricTemperature'),
)
const LEGEND_CELLS = 10

/** 圖例色塊顏色 —— 與 3D 樓層同源（envColorFor 取樣） */
function legendCellColor(i: number) {
  const [min, max] = legendRange.value
  const t = (i - 0.5) / LEGEND_CELLS
  const value = min + t * (max - min)
  return envColorFor(props.metric ?? 'temperature', value, min, max) ?? '#d9d5cc'
}

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  renderer?.domElement.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  controls?.dispose()
  renderer?.dispose()
  if (renderer?.domElement.parentElement) {
    renderer.domElement.parentElement.removeChild(renderer.domElement)
  }
  floorMeshes.forEach((m) => {
    ;(m.material as THREE.Material).dispose()
  })
  scene = null
  camera = null
  renderer = null
})
</script>

<template>
  <div ref="host" class="building3d">
    <div
      v-show="toastVisible && hoveredFloor != null"
      class="floor-toast"
      :style="toastStyle"
    >
      <div class="toast-level">{{ t('building.level', { n: floorName(hoveredFloor ?? 0) }) }}</div>
      <div class="toast-devices">
        {{ t('building.toastDevices', { n: deviceCountFor(hoveredFloor ?? 0) }) }}
      </div>
    </div>
    <div class="env-legend">
      <div class="legend-head">
        <span class="legend-title">{{ legendLabel }}</span>
        <span class="legend-unit">{{ legendUnit }}</span>
        <span class="legend-live" aria-hidden="true" />
      </div>
      <div class="legend-bar" role="img" :aria-label="`${legendLabel} · ${legendRange[0]} – ${legendRange[1]} ${legendUnit}`">
        <span
          v-for="i in LEGEND_CELLS"
          :key="i"
          class="legend-cell"
          :style="{ background: legendCellColor(i) }"
        />
      </div>
      <div class="legend-scale" aria-hidden="true">
        <span>{{ legendRange[0] }}</span>
        <span>{{ legendRange[1] }}</span>
      </div>
      <p class="legend-note">{{ t('building.envNoData') }}</p>
    </div>
  </div>
</template>

<style scoped>
.building3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  border-radius: 2px;
  overflow: hidden;
  background: #f7f7f5;
  cursor: grab;
}

.building3d:active {
  cursor: grabbing;
}

.building3d :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.floor-toast {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  min-width: 132px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(13, 13, 13, 0.62);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(6px);
  color: #fff;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}

.toast-level {
  font-size: 13px;
  font-weight: 650;
  color: #f5ead7;
}

.toast-devices {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
}

.env-legend {
  position: absolute;
  z-index: 4;
  right: 12px;
  bottom: 12px;
  min-width: 150px;
  padding: 10px 12px 9px;
  border-radius: 6px;
  background: rgba(13, 13, 13, 0.72);
  border: 1px solid rgba(196, 165, 116, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.22);
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.92);
  pointer-events: none;
  animation: legend-in 240ms ease-out;
}

.legend-head {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.legend-title {
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.02em;
  color: #fff;
}

.legend-unit {
  font-size: 11px;
  font-weight: 400;
  font-variant-numeric: tabular-nums;
  color: #d4b88a;
}

.legend-live {
  width: 6px;
  height: 6px;
  margin-left: auto;
  align-self: center;
  border-radius: 50%;
  background: #c4a574;
  box-shadow: 0 0 0 3px rgba(196, 165, 116, 0.22);
  animation: legend-pulse 2.4s ease-in-out infinite;
}

.legend-bar {
  display: flex;
  height: 8px;
  margin: 7px 0 5px;
  border-radius: 2px;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.legend-cell {
  flex: 1;
  height: 100%;
}

.legend-scale {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: rgba(255, 255, 255, 0.78);
}

.legend-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0 0;
  padding-top: 6px;
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

@keyframes legend-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

@keyframes legend-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 3px rgba(196, 165, 116, 0.22);
  }
  50% {
    box-shadow: 0 0 0 5px rgba(196, 165, 116, 0.1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .env-legend {
    animation: none;
  }
  .legend-live {
    animation: none;
  }
}
</style>
