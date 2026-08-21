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
  TEMPERATURE_GRADIENT_STOPS,
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
import { updateCellRotation, updateColCellsRotation, cellEdit, undoEdit, resetGridExtras } from '@/api/building'

const props = defineProps<{
  selectedFloor: number | null
  /** Real temperature/humidity per floor from WingOnIOT (key is the 3D building level) */
  floorEnv?: Record<number, FloorEnvValue>
  /** Current coloring metric */
  metric?: EnvMetric
  /** Custom cell shape settings (DB-driven; falls back to default rectangles when no match) */
  cellShapes?: CellShapeConfig[]
  /** Building ID (for batch rotation) */
  buildingId?: number
}>()

const emit = defineEmits<{
  selectFloor: [floor: number]
  refreshShapes: []
}>()

const { t } = useI18n()

const host = ref<HTMLDivElement>()
const hoveredFloor = ref<number | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
/** Key of the cell currently logged (row/col), so hover logs once per cell */
let loggedCellKey = ''

/** Auto-rotate the building body around the Y axis */
const autoRotate = ref(true)
/** Rotate speed multiplier (0.5× ~ 4×) */
const rotateSpeed = ref(1)

/** 大屏模式：每圈旋转时间（秒），硬编码配置 */
const LS_ROTATION_PERIOD = 45

/** Currently selected cell for rotation editing */
const selectedCell = ref<{
  floor_id: number
  row: number
  col: number
  floor3d: number
  rotation: string | null
} | null>(null)

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

  // DB-driven cell list: group cellShapes by 3D floor. When the DB returns no
  // shapes, fall back to the hard-coded interior cells (default rectangles).
  const shapesByFloor = new Map<number, CellShapeConfig[]>()
  for (const s of props.cellShapes ?? []) {
    if (s.floor < 1 || s.floor > FLOOR_COUNT) continue
    const list = shapesByFloor.get(s.floor) ?? []
    list.push(s)
    shapesByFloor.set(s.floor, list)
  }
  const dbDriven = shapesByFloor.size > 0

  for (let i = 0; i < FLOOR_COUNT; i++) {
    const level = i + 1
    const yBase = i * SLAB
    const mats: THREE.MeshStandardMaterial[] = []
    const levelMeshes: THREE.Mesh[] = []

    // Build the cell list for this floor: DB-driven when available, else interior cells
    const renderCells: CellShapeConfig[] = []
    if (dbDriven) {
      for (const s of shapesByFloor.get(level) ?? []) renderCells.push(s)
    } else {
      for (const cell of INTERIOR_CELLS) {
        if (shouldExcludeCell(level, cell.row, cell.col)) continue
        renderCells.push({ row: cell.row, col: cell.col, floor: level, shape: 'Rect' })
      }
    }

    for (const shapeConfig of renderCells) {
      // Determine the shape from settings: use DB shape or the default rectangle
      const shapeType: GridType = shapeConfig?.shape ?? 'Rect'

      // Hidden type: skip rendering, no mesh is created
      if (isHiddenType(shapeType)) continue

      // Custom color takes priority over the environment (temperature/humidity) color
      const customColor = shapeConfig?.color ?? null
      const mat = new THREE.MeshStandardMaterial({
        color: customColor ? new THREE.Color(customColor) : floorColor(level, props.selectedFloor, hoveredFloor.value),
        metalness: 0.12,
        roughness: 0.55,
        transparent: true,
        opacity: 0.95,
      })
      mats.push(mat)

      // Custom render height (render_height) overrides the default floor slab height
      const cellHeight = shapeConfig?.height && shapeConfig.height > 0 ? shapeConfig.height : FLOOR_H

      // Rectangles reuse the shared cellGeo; other shapes are created on demand (with a geometry cache)
      const geo = shapeType === 'Rect'
        ? (cellHeight === FLOOR_H ? cellGeo : createGeometryByType('Rect', cellSize, cellHeight))
        : createGeometryByType(shapeType, cellSize, cellHeight)

      const mesh = new THREE.Mesh(geo, mat)
      // DB world position takes priority; falls back to row/col grid calculation
      const { x: wx, z: wz } = cellToWorld(shapeConfig.row, shapeConfig.col)
      const hasDbPos = shapeConfig?.x != null && shapeConfig?.y != null && shapeConfig?.z != null
      const px = hasDbPos ? shapeConfig.x! : wx
      const py = hasDbPos ? shapeConfig.z! : yBase + FLOOR_H / 2
      const pz = hasDbPos ? shapeConfig.y! : wz
      mesh.position.set(px, py, pz)
      if (shapeConfig?.rotation) {
        mesh.rotation.copy(parseRotation(shapeConfig.rotation))
      }
      mesh.userData.floor = level
      mesh.userData.row = shapeConfig.row
      mesh.userData.col = shapeConfig.col
      mesh.userData.customColor = customColor
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
      // Custom-colored cells keep their fixed color; others follow temperature/humidity
      if (!mesh.userData.customColor) {
        mat.color = floorColor(level, selected, hovered)
      }
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

/** Print the hovered cell info to the console: row, col, center position and geometry size. */
function logCellInfo(mesh: THREE.Mesh) {
  const { row, col } = mesh.userData
  if (row == null || col == null) return
  const geo = mesh.geometry
  geo.computeBoundingBox()
  const size = new THREE.Vector3()
  geo.boundingBox?.getSize(size)
  const { x, y, z } = mesh.position
  console.log(
    `格子 行=${row} 列=${col} x=${x.toFixed(2)} y=${y.toFixed(2)} z=${z.toFixed(2)} 长度=${size.z.toFixed(2)} 宽度=${size.x.toFixed(2)} 高度=${size.y.toFixed(2)}`,
  )
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
    const mesh = hits[0].object as THREE.Mesh
    const floor = mesh.userData.floor as number
    // Print row/col/position/size once when hovering a new cell
    const key = `${floor}-${mesh.userData.row}-${mesh.userData.col}`
    if (loggedCellKey !== key) {
      loggedCellKey = key
      logCellInfo(mesh)
    }
    if (hoveredFloor.value !== floor) {
      hoveredFloor.value = floor
      updateFloorAppearance()
    }
    toastVisible.value = true
    placeToast(pos.clientX, pos.clientY, pos.rect)
    host.value.style.cursor = 'pointer'
  } else {
    loggedCellKey = ''
    if (hoveredFloor.value != null) {
      hoveredFloor.value = null
      updateFloorAppearance()
    }
    toastVisible.value = false
    host.value.style.cursor = 'grab'
  }
}

function onPointerLeave() {
  loggedCellKey = ''
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
    const mesh = hits[0].object as THREE.Mesh
    const ud = mesh.userData
    // Find the matching cellShape to get floor_id
    const shape = props.cellShapes?.find(
      (s) => s.row === ud.row && s.col === ud.col && s.floor === ud.floor,
    )
    if (shape?.floor_id != null) {
      selectedCell.value = {
        floor_id: shape.floor_id,
        row: ud.row,
        col: ud.col,
        floor3d: ud.floor,
        rotation: shape.rotation ?? null,
      }
    }
  } else {
    selectedCell.value = null
  }
}

async function applyRotation(deg: number) {
  if (!selectedCell.value) return
  const rad = deg === 0 ? null : `0,${(deg * Math.PI / 180).toFixed(4)},0`
  const { floor_id, row, col } = selectedCell.value
  await updateCellRotation({ floor_id, row_no: row, col_no: col, rotation_xyz: rad })
  selectedCell.value = { ...selectedCell.value, rotation: rad }
  emit('refreshShapes')
}

function isRotationActive(deg: number): boolean {
  const rot = selectedCell.value?.rotation
  if (!rot) return deg === 0
  const parts = rot.split(',').map(Number)
  const y = parts[1] ?? 0
  return Math.abs(y - deg * Math.PI / 180) < 0.01
}

function formatRotation(rot: string | null): string {
  if (!rot) return '0°'
  const parts = rot.split(',').map(Number)
  const y = parts[1] ?? 0
  return `${Math.round(y * 180 / Math.PI)}°`
}

/** Edit scope: single cell / entire row / entire column */
const editScope = ref<'single' | 'row' | 'col'>('single')

/** Operation feedback shown near the edit buttons */
const editFeedback = ref('')
let feedbackTimer: ReturnType<typeof setTimeout> | undefined

function showFeedback(msg: string) {
  editFeedback.value = msg
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => { editFeedback.value = '' }, 2500)
}

async function handleCellEdit(action: 'add' | 'delete') {
  if (!props.buildingId || !selectedCell.value) return
  const { row, col, floor_id } = selectedCell.value
  const res = await cellEdit({
    building_id: props.buildingId,
    row_no: row,
    col_no: col,
    action,
    scope: editScope.value,
    floor_id,
  })
  const n = res?.data?.affected ?? 0
  if (n > 0) {
    showFeedback(action === 'add' ? `已添加 ${n} 个格子` : `已删除 ${n} 个格子`)
  } else {
    showFeedback(action === 'add' ? '无变化：格子已存在' : '无变化：没有可删除的格子')
  }
  emit('refreshShapes')
}

async function handleAppend(scope: 'append_row' | 'append_col') {
  if (!props.buildingId || !selectedCell.value) return
  const { row, col, floor_id } = selectedCell.value
  const res = await cellEdit({
    building_id: props.buildingId,
    row_no: row,
    col_no: col,
    action: 'add',
    scope,
    floor_id,
  })
  const n = res?.data?.affected ?? 0
  if (n > 0) {
    showFeedback(scope === 'append_row' ? `已追加一行，共 ${n} 个格子` : `已追加一列，共 ${n} 个格子`)
  } else {
    showFeedback('追加失败或没有变化')
  }
  emit('refreshShapes')
}

async function handleResetGrid() {
  if (!props.buildingId) return
  const res = await resetGridExtras(props.buildingId)
  const n = res?.data?.affected ?? 0
  if (n > 0) {
    showFeedback(`已还原网格，删除 ${n} 个追加格子`)
  } else {
    showFeedback('当前无超出网格的格子')
  }
  emit('refreshShapes')
}

async function handleUndo() {
  const res = await undoEdit()
  if (res && res.data && res.data.ok) {
    showFeedback(`已撤回 ${res.data.affected} 个格子`)
    emit('refreshShapes')
  } else {
    showFeedback('没有可撤回的操作')
  }
}

async function applyColRotation(deg: number) {
  if (!props.buildingId || !selectedCell.value) return
  const rad = deg === 0 ? null : `0,${(deg * Math.PI / 180).toFixed(4)},0`
  await updateColCellsRotation({ building_id: props.buildingId, col_no: selectedCell.value.col, rotation_xyz: rad })
  if (selectedCell.value) {
    selectedCell.value = { ...selectedCell.value, rotation: rad }
  }
  emit('refreshShapes')
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
  // Slow auto-rotation of the building body (rate adjustable via rotateSpeed)
  if (buildingGroup && autoRotate.value) {
    // 大屏模式：使用固定的旋转周期；PC端：使用用户控制的速度
    const isLsMode = document.documentElement.classList.contains('ls-on')
    if (isLsMode) {
      // 大屏模式：每帧旋转角度 = 2π / (周期 × 帧率)，约60fps
      const radiansPerFrame = (2 * Math.PI) / (LS_ROTATION_PERIOD * 60)
      buildingGroup.rotation.y += radiansPerFrame
    } else {
      buildingGroup.rotation.y += 0.004 * rotateSpeed.value
    }
  }
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
  // Respect reduced-motion: start without auto-rotation (大屏模式下强制开启)
  const isLsMode = document.documentElement.classList.contains('ls-on')
  if (!isLsMode && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    autoRotate.value = false
  }
  // 大屏模式下强制开启自动旋转
  if (isLsMode) {
    autoRotate.value = true
  }
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

/** Continuous temperature gradient (0 → 10 → 20 → 30 → 35) for the legend bar */
const legendGradientStyle = computed(() => {
  if (props.metric === 'humidity') return ''
  return `linear-gradient(90deg, ${TEMPERATURE_GRADIENT_STOPS.join(', ')})`
})

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
      v-show="toastVisible && hoveredFloor != null && !selectedCell"
      class="floor-toast"
      :style="toastStyle"
    >
      <div class="toast-level">{{ t('building.level', { n: floorName(hoveredFloor ?? 0) }) }}</div>
      <div class="toast-devices">
        {{ t('building.toastDevices', { n: deviceCountFor(hoveredFloor ?? 0) }) }}
      </div>
    </div>
    <!-- Cell rotation panel -->
    <div v-if="selectedCell" class="rotate-panel">
      <div class="rotate-header">
        <span class="rotate-title">格子 ({{ selectedCell.row }}, {{ selectedCell.col }}) · {{ floorName(selectedCell.floor3d) }}F</span>
        <button class="rotate-close" @click="selectedCell = null">&times;</button>
      </div>
      <div class="rotate-presets">
        <button
          v-for="deg in [0, 45, 90, 135, 180, 225, 270, 315]"
          :key="deg"
          class="rotate-btn"
          :class="{ active: isRotationActive(deg) }"
          @click="applyRotation(deg)"
        >
          {{ deg }}°
        </button>
      </div>
      <div class="rotate-current">
        当前旋转: {{ formatRotation(selectedCell.rotation) }}
      </div>
      <div class="rotate-divider" />
      <div class="rotate-all-label">旋转第{{ selectedCell.col }}列全部格子</div>
      <div class="rotate-presets">
        <button
          v-for="deg in [0, 45, 90, 135, 180, 225, 270, 315]"
          :key="'col-' + deg"
          class="rotate-btn rotate-btn-all"
          @click="applyColRotation(deg)"
        >
          {{ deg }}°
        </button>
      </div>
      <div class="rotate-divider" />
      <div class="rotate-all-label">添加 / 删除格子</div>
      <div class="edit-scope-row">
        <button
          v-for="s in (['single', 'row', 'col'] as const)"
          :key="s"
          class="scope-btn"
          :class="{ active: editScope === s }"
          @click="editScope = s"
        >
          {{ s === 'single' ? '单格' : s === 'row' ? '整行' : '整列' }}
        </button>
      </div>
      <div class="edit-actions">
        <button class="edit-btn edit-btn-add" @click="handleCellEdit('add')">添加</button>
        <button class="edit-btn edit-btn-del" @click="handleCellEdit('delete')">删除</button>
        <button class="edit-btn edit-btn-undo" @click="handleUndo">撤回</button>
      </div>
      <div class="edit-actions">
        <button class="edit-btn edit-btn-append" @click="handleAppend('append_row')">追加一行</button>
        <button class="edit-btn edit-btn-append" @click="handleAppend('append_col')">追加一列</button>
      </div>
      <div class="edit-actions">
        <button class="edit-btn edit-btn-reset" @click="handleResetGrid">还原网格</button>
      </div>
      <div v-if="editFeedback" class="edit-feedback">{{ editFeedback }}</div>
    </div>
    <div class="auto-rotate">
      <button
        type="button"
        class="ar-toggle"
        :class="{ on: autoRotate }"
        @click="autoRotate = !autoRotate"
      >
        {{ autoRotate ? t('building.rotatePause') : t('building.rotatePlay') }}
      </button>
      <span class="ar-label">{{ t('building.rotateSpeed') }}</span>
      <input
        v-model.number="rotateSpeed"
        class="ar-slider"
        type="range"
        min="0.5"
        max="4"
        step="0.5"
        :aria-label="t('building.rotateSpeed')"
      />
      <span class="ar-value">{{ rotateSpeed.toFixed(1) }}×</span>
    </div>
    <div class="env-legend">
      <div class="legend-head">
        <span class="legend-title">{{ legendLabel }}</span>
        <span class="legend-unit">{{ legendUnit }}</span>
        <span class="legend-live" aria-hidden="true" />
      </div>
      <div
        v-if="metric === 'temperature'"
        class="legend-bar legend-bar-gradient"
        role="img"
        :aria-label="`${legendLabel} · ${TEMPERATURE_TICKS[0]} – ${TEMPERATURE_TICKS[TEMPERATURE_TICKS.length - 1]} ${legendUnit}`"
        :style="{ background: legendGradientStyle }"
      />
      <div
        v-else
        class="legend-bar"
        role="img"
        :aria-label="`${legendLabel} · ${legendRange[0]} – ${legendRange[1]} ${legendUnit}`"
      >
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

/* Cell rotation panel */
.rotate-panel {
  position: absolute;
  z-index: 10;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  min-width: 300px;
  padding: 10px 14px;
  border-radius: 6px;
  background: rgba(13, 13, 13, 0.85);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(8px);
  color: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  animation: rotate-panel-in 180ms ease-out;
}

.rotate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.rotate-title {
  font-size: 13px;
  font-weight: 650;
  color: #f5ead7;
}

.rotate-close {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}

.rotate-close:hover {
  color: #fff;
}

.rotate-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.rotate-btn {
  flex: 1 1 auto;
  min-width: 52px;
  padding: 5px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.rotate-btn:hover {
  background: rgba(196, 165, 116, 0.3);
  border-color: rgba(196, 165, 116, 0.5);
}

.rotate-btn.active {
  background: rgba(196, 165, 116, 0.5);
  border-color: #c4a574;
  color: #fff;
  font-weight: 600;
}

.rotate-current {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.65);
  text-align: center;
}

.rotate-divider {
  height: 1px;
  margin: 8px 0;
  background: rgba(255, 255, 255, 0.12);
}

.rotate-all-label {
  font-size: 11px;
  font-weight: 600;
  color: #c4a574;
  margin-bottom: 6px;
  text-align: center;
}

.rotate-btn-all {
  background: rgba(196, 165, 116, 0.12);
  border-color: rgba(196, 165, 116, 0.25);
  color: #c4a574;
}

.rotate-btn-all:hover {
  background: rgba(196, 165, 116, 0.35);
  border-color: #c4a574;
  color: #fff;
}

.edit-scope-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.scope-btn {
  flex: 1;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.scope-btn:hover {
  background: rgba(255, 255, 255, 0.12);
}

.scope-btn.active {
  background: rgba(196, 165, 116, 0.4);
  border-color: #c4a574;
  color: #fff;
}

.edit-actions {
  display: flex;
  gap: 8px;
}

.edit-feedback {
  margin-top: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #81d4fa;
  font-size: 11px;
  text-align: center;
}

.edit-btn {
  flex: 1;
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.15);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.edit-btn-add {
  background: rgba(76, 175, 80, 0.25);
  border-color: rgba(76, 175, 80, 0.5);
  color: #81c784;
}

.edit-btn-add:hover {
  background: rgba(76, 175, 80, 0.45);
  border-color: #4caf50;
  color: #fff;
}

.edit-btn-del {
  background: rgba(244, 67, 54, 0.2);
  border-color: rgba(244, 67, 54, 0.45);
  color: #e57373;
}

.edit-btn-del:hover {
  background: rgba(244, 67, 54, 0.4);
  border-color: #f44336;
  color: #fff;
}

.edit-btn-undo {
  background: rgba(156, 39, 176, 0.2);
  border-color: rgba(156, 39, 176, 0.45);
  color: #ce93d8;
}

.edit-btn-undo:hover {
  background: rgba(156, 39, 176, 0.4);
  border-color: #9c27b0;
  color: #fff;
}

.edit-btn-append {
  background: rgba(0, 150, 136, 0.2);
  border-color: rgba(0, 150, 136, 0.45);
  color: #80cbc4;
}

.edit-btn-append:hover {
  background: rgba(0, 150, 136, 0.4);
  border-color: #009688;
  color: #fff;
}

.edit-btn-reset {
  background: rgba(255, 87, 34, 0.2);
  border-color: rgba(255, 87, 34, 0.45);
  color: #ffab91;
}

.edit-btn-reset:hover {
  background: rgba(255, 87, 34, 0.4);
  border-color: #ff5722;
  color: #fff;
}

@keyframes rotate-panel-in {
  from { opacity: 0; transform: translateX(-50%) translateY(-6px); }
  to   { opacity: 1; transform: translateX(-50%) translateY(0); }
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

.auto-rotate {
  position: absolute;
  z-index: 6;
  right: 12px;
  top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(13, 13, 13, 0.72);
  border: 1px solid rgba(196, 165, 116, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.22);
  font-size: 12px;
  line-height: 1.5;
  color: rgba(255, 255, 255, 0.92);
  animation: legend-in 240ms ease-out;
}

.ar-toggle {
  padding: 2px 10px;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.85);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.ar-toggle:hover {
  background: rgba(196, 165, 116, 0.3);
  border-color: rgba(196, 165, 116, 0.5);
}

.ar-toggle.on {
  background: rgba(196, 165, 116, 0.5);
  border-color: #c4a574;
  color: #fff;
}

.ar-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.7);
}

.ar-slider {
  width: 88px;
  height: 4px;
  accent-color: #c4a574;
  cursor: pointer;
}

.ar-value {
  min-width: 34px;
  text-align: right;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: #d4b88a;
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
