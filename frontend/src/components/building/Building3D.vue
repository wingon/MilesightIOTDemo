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
  fixedTemperatureColor,
  TEMPERATURE_BAND_COLORS,
  TEMPERATURE_TICKS,
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
  /** Real temperature/humidity per floor from WingOnIOT (key is the 3D building level) */
  floorEnv?: Record<number, FloorEnvValue>
  /** Current coloring metric */
  metric?: EnvMetric
  /** Custom cell shape settings (DB-driven; falls back to default rectangles when no match) */
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
 * Look up the shape config for a given cell.
 *
 * Settings are DB-driven (the :cell-shapes prop); falls back to the default rectangle when no match.
 *
 * @param floor - current floor (3D level 1~11)
 * @param row   - cell row (1-based)
 * @param col   - cell col (1-based)
 * @returns matching CellShapeConfig, or undefined when not found (uses the default rectangle)
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
  // Temperature: uses the fixed 5-band color scale
  const env = props.floorEnv?.[level]
  const metric = props.metric ?? 'temperature'
  if (metric === 'temperature') {
    const value = env?.temperature ?? null
    const color = fixedTemperatureColor(value)
    if (color !== '#d9d5cc') return new THREE.Color(color)
    // No-data fallback gradient
    const t = level / Math.max(1, FLOOR_COUNT - 1)
    return new THREE.Color().setHSL(0.08, 0.12, 0.22 + t * 0.28)
  }
  // Humidity: keeps the original dynamic color scale
  const value = env?.humidity ?? null
  const [min, max] = envRange(props.floorEnv, metric)
  const color = envColorFor(metric, value, min, max)
  if (color) return new THREE.Color(color)
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
      
      // Determine the shape from settings: look up cellShapes or use the default rectangle
      const shapeConfig = getCellShapeConfig(level, cell.row, cell.col)
      const shapeType: GridType = shapeConfig?.shape ?? 'Rect'
      
      // Hidden type: skip rendering, no mesh is created
      if (isHiddenType(shapeType)) continue
      
      // Rectangles reuse the shared cellGeo; other shapes are created on demand (with a geometry cache)
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
  // Real WingOnIOT device count (0 when this floor has no data); demo counts are not shown
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

// Refresh floor colors when real data / metric changes
watch(
  () => props.floorEnv,
  () => updateFloorAppearance(),
  { deep: true },
)
watch(
  () => props.metric,
  () => updateFloorAppearance(),
)

// Rebuild all floors when the cell shape settings change (deep compare; add/remove settings both trigger)
watch(
  () => props.cellShapes,
  () => rebuildFloors(),
  { deep: true },
)

// Legend (current metric color scale)
const legendRange = computed(() => envRange(props.floorEnv, props.metric ?? 'temperature'))
const legendUnit = computed(() => (props.metric === 'humidity' ? '%RH' : '°C'))
const legendLabel = computed(() =>
  props.metric === 'humidity' ? t('building.metricHumidity') : t('building.metricTemperature'),
)
/** Temperature: fixed 4 swatches + 5 tick values (0,25,50,75,100); humidity: 10 swatches */
const LEGEND_BAND_COUNT = 4
const LEGEND_CELLS = computed(() =>
  props.metric === 'humidity' ? 10 : LEGEND_BAND_COUNT,
)

/** Legend swatch color */
function legendCellColor(i: number) {
  if (props.metric === 'humidity') {
    const [min, max] = legendRange.value
    const t = (i - 0.5) / 10
    const value = min + t * (max - min)
    return envColorFor('humidity', value, min, max) ?? '#d9d5cc'
  }
  // Fixed 5-band temperature
  return TEMPERATURE_BAND_COLORS[i - 1] ?? '#d9d5cc'
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
      <div v-if="metric === 'temperature'" class="legend-scale" aria-hidden="true">
        <span v-for="tick in TEMPERATURE_TICKS" :key="tick">{{ tick }}</span>
      </div>
      <div v-else class="legend-scale" aria-hidden="true">
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
