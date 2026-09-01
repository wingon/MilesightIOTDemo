<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  CELL_SIZE,
  FLOOR_COUNT,
  GRID_COLS,
  GRID_ROWS,
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
import {
  listBuildingCellShapes,
  listBuildingFloors,
  updateCellRotation,
  cellEdit,
  undoEdit,
} from '@/api/building'

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
  /** Loading state - when true, shows loading indicator instead of 3D */
  loading?: boolean
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

/**
 * 編輯工具面板位置（可拖動）。
 * 進入編輯模式時顯示在右上角，之後完全由用戶拖動決定。
 */
const panelPos = ref({ x: 0, y: 0 })
/** 工具面板固定寬度 */
const PANEL_W = 248
/** 面板位置只在首次打開時初始化一次（右上角），之後完全由用戶拖動決定 */
let panelInitialized = false
/** 拖拽中的狀態 */
let dragState: { startX: number; startY: number; originX: number; originY: number } | null = null

/** 初始化面板默認位置（右上角，避開建築中心），僅首次生效 */
function ensurePanelPosition() {
  if (panelInitialized || !host.value) return
  const w = host.value.clientWidth
  panelPos.value = { x: Math.max(12, w - PANEL_W - 16), y: 12 }
  panelInitialized = true
}

function startDragPanel(ev: PointerEvent) {
  if (!host.value) return
  ev.preventDefault()
  dragState = {
    startX: ev.clientX,
    startY: ev.clientY,
    originX: panelPos.value.x,
    originY: panelPos.value.y,
  }
  document.addEventListener('pointermove', onDragPanelMove)
  document.addEventListener('pointerup', endDragPanel)
}

function onDragPanelMove(ev: PointerEvent) {
  if (!dragState || !host.value) return
  const rect = host.value.getBoundingClientRect()
  const maxX = Math.max(8, rect.width - PANEL_W - 8)
  const x = Math.min(Math.max(dragState.originX + (ev.clientX - dragState.startX), 8), maxX)
  // 只限制到頂部可達，底部允許面板超出視口（保證標題欄始終可見）
  const maxY = Math.max(8, rect.height - 48)
  const y = Math.min(Math.max(dragState.originY + (ev.clientY - dragState.startY), 8), maxY)
  panelPos.value = { x, y }
}

function endDragPanel() {
  dragState = null
  document.removeEventListener('pointermove', onDragPanelMove)
  document.removeEventListener('pointerup', endDragPanel)
}

/**
 * 編輯模式：普通模式點擊樓層 = 選中／進入樓層；編輯模式點擊格子 = 彈出編輯面板。
 * 開啟方式（由父組件 BuildingViewerView 觸發）：3 秒內在左上角提示文字框連續點擊 3 次。
 */
const editUnlocked = ref(false)
/** 本次編輯會話是否產生過改動（決定退出時是否彈確認框） */
const editDirty = ref(false)
/** 「退出編輯會話」確認框（保存 / 放棄 / 繼續編輯） */
const confirmOpen = ref(false)
/** 撤回上限（後端 _UNDO_STACK 容量一致） */
const UNDO_LIMIT = 10
/** 本次會話中「可撤回操作」計數（增/刪/旋轉成功 +1，撤回成功 -1，封頂 UNDO_LIMIT） */
const undoableOps = ref(0)
/** 進入編輯模式時抓取的格子快照，用於「放棄修改」時回滾本次全部改動 */
const snapshotShapes = ref<CellShapeConfig[]>([])
/** 輕量反饋：進入編輯模式時頂部短暫提示（1.5 秒後自動消失） */
const editModeToast = ref(false)
let editModeToastTimer: ReturnType<typeof setTimeout> | undefined
/**
 * 編輯工具模式（四按鈕面板）：none=未激活 / add=添加模式 / delete=刪除模式。
 * 添加與刪除互斥：激活一個會取消另一個。
 */
const editToolMode = ref<'none' | 'add' | 'delete'>('none')

/** 切換編輯工具模式（添加 / 刪除互斥切換，再點一次退出） */
function toggleToolMode(mode: 'add' | 'delete') {
  if (editToolMode.value === mode) {
    editToolMode.value = 'none'
    if (mode === 'add') hideDragTemplates()
    return
  }
  editToolMode.value = mode
  if (mode === 'add') {
    spawnDragTemplates()
  } else {
    hideDragTemplates()
  }
}

/** 切換編輯模式（由父組件調用）：開啟時抓取格子快照，用於放棄修改時回滾 */
async function toggleEditMode() {
  if (!editUnlocked.value) {
    editUnlocked.value = true
    editDirty.value = false
    undoableOps.value = 0
    panelInitialized = false
    // 記錄修改前快照（整個建築），供「放棄修改」回滾
    if (props.buildingId) {
      try {
        const { data } = await listBuildingCellShapes(props.buildingId)
        snapshotShapes.value = data ?? []
      } catch {
        snapshotShapes.value = []
      }
    } else {
      snapshotShapes.value = []
    }
    // 顯示短暫提示
    editModeToast.value = true
    if (editModeToastTimer) clearTimeout(editModeToastTimer)
    editModeToastTimer = setTimeout(() => { editModeToast.value = false }, 1500)
    editToolMode.value = 'none'
    ensurePanelPosition()
    hideDragTemplates()
    updateHiddenOverlaysVisibility()
    return
  }
  // 請求退出編輯模式：有改動則彈確認框，無改動直接退出
  if (editDirty.value) {
    openExitConfirm()
  } else {
    exitEditSession()
  }
}

/** 對外暴露的方法，供父組件 BuildingViewerView 於提示文字框連點 3 次時調用 */
defineExpose({ toggleEditMode })

/** 打開「退出編輯會話」確認框（保存 / 放棄 / 繼續編輯） */
function openExitConfirm() {
  confirmOpen.value = true
}

/** 統一退出編輯會話：清空快照、工具模式與改動標記 */
function exitEditSession() {
  editUnlocked.value = false
  snapshotShapes.value = []
  editDirty.value = false
  undoableOps.value = 0
  editToolMode.value = 'none'
  hideDragTemplates()
  updateHiddenOverlaysVisibility()
}

/**
 * 「完成」按鈕：僅在本次會話有改動時彈確認框；無改動直接退出編輯模式。
 */
function onDoneClick() {
  if (editDirty.value) {
    openExitConfirm()
  } else {
    exitEditSession()
  }
}

/**
 * 完成編輯會話：save=true 保留改動（操作已即時生效）；save=false 放棄並回滾到快照。
 */
async function finishEditSession(save: boolean) {
  confirmOpen.value = false
  if (save) {
    exitEditSession()
    message.success(t('building.savedSuccess'))
    return
  }
  await discardChanges()
}

/** floor3d (1~11) → DB floor.id（優先從已有格子推斷，其次查 floors 表，緩存結果） */
const floorIdCache = new Map<number, number>()
async function resolveFloorId(floor3d: number): Promise<number | null> {
  const cached = floorIdCache.get(floor3d)
  if (cached != null) return cached
  const s = props.cellShapes?.find((x) => x.floor === floor3d && x.floor_id != null)
  if (s?.floor_id != null) {
    floorIdCache.set(floor3d, s.floor_id)
    return s.floor_id
  }
  if (!props.buildingId) return null
  try {
    const { data } = await listBuildingFloors(props.buildingId)
    const f = data?.find((x) => x.level_3d === floor3d)
    if (f) {
      floorIdCache.set(floor3d, f.id)
      return f.id
    }
  } catch {
    // ignore, fall through to null
  }
  return null
}

/** 放棄本次修改：對比快照與當前 DB 狀態，逆向恢復（還原刪除／移除新增／恢復旋轉），成功後退出編輯會話 */
async function discardChanges() {
  const buildingId = props.buildingId
  if (!buildingId || !snapshotShapes.value.length) {
    message.warning(t('building.changesDiscarded'))
    exitEditSession()
    return
  }
  try {
    const { data: current } = await listBuildingCellShapes(buildingId)
    const cur = current ?? []
    const keyOf = (s: CellShapeConfig) => `${s.floor}-${s.row}-${s.col}`
    const snapMap = new Map(snapshotShapes.value.map((s) => [keyOf(s), s]))
    const curMap = new Map(cur.map((s) => [keyOf(s), s]))

    // 1) 快照存在而當前缺失（本次被刪除）→ 恢復
    for (const s of snapMap.values()) {
      if (!curMap.has(keyOf(s)) && s.floor_id != null) {
        await cellEdit({
          building_id: buildingId,
          row_no: s.row,
          col_no: s.col,
          action: 'add',
          scope: 'single',
          floor_id: s.floor_id,
          // 按快照恢復原形狀（Hidden 由後端歸一化為 Rect，但 re_delete 恢復時 is_active 不變，仍為隱形）
          shape: s.shape === 'Cylinder' || s.shape === 'Triangle' ? s.shape : 'Rect',
        })
      }
    }
    // 2) 當前存在而快照缺失（本次新增）→ 刪除
    for (const c of curMap.values()) {
      if (!snapMap.has(keyOf(c)) && c.floor_id != null) {
        await cellEdit({
          building_id: buildingId,
          row_no: c.row,
          col_no: c.col,
          action: 'delete',
          scope: 'single',
          floor_id: c.floor_id,
        })
      }
    }
    // 3) 旋轉被修改的格子 → 恢復原旋轉
    for (const s of snapMap.values()) {
      const c = curMap.get(keyOf(s))
      if (c && c.floor_id != null && (c.rotation ?? null) !== (s.rotation ?? null)) {
        await updateCellRotation({
          floor_id: c.floor_id,
          row_no: s.row,
          col_no: s.col,
          rotation_xyz: s.rotation ?? null,
        })
      }
    }
    message.success(t('building.changesDiscarded'))
    emit('refreshShapes')
    exitEditSession()
  } catch {
    // 回滾失敗：保留編輯會話，允許用戶重試
    message.error(t('building.discardFailed'))
  }
}

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
  buildHiddenCellOverlays()
}

// ---- 編輯模式：Hidden 格子（is_active=0 的停用格子）以「透明填充 + 黑線邊框」顯示，可點擊選中刪除 ----
let hiddenCellGroup: THREE.Group | null = null
let hiddenCellMaterials: THREE.Material[] = []
let hiddenCellGeos: THREE.BufferGeometry[] = []
/** 可點擊的隱形格子占位 mesh（編輯模式下可選中並刪除） */
let hiddenCellMeshes: THREE.Mesh[] = []

function buildHiddenCellOverlays() {
  if (!scene) return
  if (hiddenCellGroup) {
    scene.remove(hiddenCellGroup)
    hiddenCellGeos.forEach((g) => g.dispose())
    hiddenCellMaterials.forEach((m) => m.dispose())
    hiddenCellGeos = []
    hiddenCellMaterials = []
    hiddenCellGroup = null
  }
  hiddenCellMeshes = []
  hiddenCellGroup = new THREE.Group()
  const cellSize = CELL_SIZE * 0.96
  const boxGeo = new THREE.BoxGeometry(cellSize, FLOOR_H, cellSize)
  const edgeGeo = new THREE.EdgesGeometry(boxGeo)
  const fillMat = new THREE.MeshBasicMaterial({
    color: 0x000000,
    transparent: true,
    opacity: 0.14,
    depthWrite: false,
  })
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x000000 })
  hiddenCellGeos.push(boxGeo, edgeGeo)
  hiddenCellMaterials.push(fillMat, edgeMat)

  for (const s of props.cellShapes ?? []) {
    if (!isHiddenType(s.shape)) continue
    if (s.floor < 1 || s.floor > FLOOR_COUNT) continue
    const level = s.floor
    const yBase = (level - 1) * SLAB
    const { x: wx, z: wz } = cellToWorld(s.row, s.col)
    const hasDbPos = s.x != null && s.y != null && s.z != null
    const px = hasDbPos ? s.x! : wx
    const py = hasDbPos ? s.z! : yBase + FLOOR_H / 2
    const pz = hasDbPos ? s.y! : wz

    const fill = new THREE.Mesh(boxGeo, fillMat)
    fill.position.set(px, py, pz)
    fill.userData = {
      row: s.row,
      col: s.col,
      floor: level,
      floor_id: s.floor_id ?? null,
      isHidden: true,
    }
    const edges = new THREE.LineSegments(edgeGeo, edgeMat)
    edges.position.copy(fill.position)
    if (s.rotation) {
      fill.rotation.copy(parseRotation(s.rotation))
      edges.rotation.copy(fill.rotation)
    }
    hiddenCellGroup.add(fill, edges)
    hiddenCellMeshes.push(fill)
  }
  hiddenCellGroup.visible = editUnlocked.value
  scene.add(hiddenCellGroup)
}

function updateHiddenOverlaysVisibility() {
  if (!hiddenCellGroup) return
  hiddenCellGroup.visible = editUnlocked.value
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
  // 拖拽中：位置與預覽由 onDragMove 處理，此處不更新 hover
  if (activeDragSource) return
  const pos = updatePointer(ev)
  if (!pos) return

  raycaster.setFromCamera(pointer, camera)
  // 編輯模式：hover 到「拖拽模板」時顯示可拖拽光標
  if (editUnlocked.value) {
    const srcHits = raycaster.intersectObjects(dragSourceMeshes, false)
    if (srcHits.length) {
      loggedCellKey = ''
      if (hoveredFloor.value != null) {
        hoveredFloor.value = null
        updateFloorAppearance()
      }
      toastVisible.value = false
      host.value.style.cursor = 'copy'
      return
    }
  }
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

/**
 * 編輯模式：射線與各層水平面求交，反算點擊的網格行列（含該位置是否已有格子）。
 * 供拖拽放置時的目標吸附使用；命中已有格子本身由 mesh 分支處理。
 */
function pickGridCellFromRay(): { row: number; col: number; floor3d: number; exists: boolean } | null {
  if (!raycaster) return null
  let best: { row: number; col: number; floor3d: number; exists: boolean } | null = null
  let bestDist = Infinity
  const hit = new THREE.Vector3()
  const plane = new THREE.Plane()
  for (let level = 1; level <= FLOOR_COUNT; level++) {
    // 每層水平面位於該層樓板底部：y = (level-1) * SLAB
    plane.set(new THREE.Vector3(0, 1, 0), -((level - 1) * SLAB))
    if (!raycaster.ray.intersectPlane(plane, hit)) continue
    const dist = raycaster.ray.origin.distanceTo(hit)
    if (dist >= bestDist) continue // 取離相機最近的命中
    const col = Math.round(hit.x / CELL_SIZE + (GRID_COLS + 1) / 2)
    const row = Math.round(hit.z / CELL_SIZE + (GRID_ROWS + 1) / 2)
    if (row < 1 || row > GRID_ROWS || col < 1 || col > GRID_COLS) continue
    // 「已有格子」判定排除 Hidden 類型（is_active=0 的停用格子不渲染，視覺上等同空位，可重新放置）
    const exists = props.cellShapes?.some(
      (s) =>
        s.floor === level &&
        s.row === row &&
        s.col === col &&
        !isHiddenType(s.shape),
    ) ?? false
    best = { row, col, floor3d: level, exists }
    bestDist = dist
  }
  return best
}

// ---- 拖拽添加格子：點「添加」按鈕後，樓宇旁出現模板格子（圓/方/三角）→ 拖到樓宇上放置 ----
let dragSourceGroup: THREE.Group | null = null
let dragSourceMeshes: THREE.Mesh[] = []
/** 拖拽中的預覽格子（跟隨滑鼠吸附到網格） */
let dragPreviewMesh: THREE.Mesh | null = null
let dragPreviewMat: THREE.MeshStandardMaterial | null = null
/** 當前正在拖拽的模板 mesh（拖拽中非 null，用於抑制 hover 邏輯） */
let activeDragSource: THREE.Mesh | null = null
/** 拖拽目標（每次移動更新，松手時提交；shape 為模板對應的形狀） */
let dragTarget: { row: number; col: number; floor3d: number; exists: boolean; shape: 'Rect' | 'Cylinder' | 'Triangle' } | null = null
/** 拖拽前自動旋轉狀態（拖拽期間暫停，松手恢復） */
let prevAutoRotate = true
/** 模板格子的三種形狀（對應大樓中已有的形狀） */
const DRAG_SHAPES: Array<'Rect' | 'Cylinder' | 'Triangle'> = ['Cylinder', 'Rect', 'Triangle']
const DRAG_SOURCE_COLOR = 0x5fb8b8
/** 拖拽中模板的旋轉角度（度，滚輪 ±15° / R 鍵 ±45°） */
let dragRotationDeg = 0

/** 拖拽中滾輪旋轉模板（±15°/格） */
function onDragWheel(ev: WheelEvent) {
  if (!activeDragSource) return
  ev.preventDefault()
  dragRotationDeg = (dragRotationDeg + (ev.deltaY > 0 ? 15 : -15) + 360) % 360
  applyDragPreviewRotation()
}

/** 拖拽中 R 鍵旋轉模板（+45°，Shift+R 逆時針） */
function onDragKeyDown(ev: KeyboardEvent) {
  if (!activeDragSource) return
  if (ev.key === 'r' || ev.key === 'R') {
    ev.preventDefault()
    dragRotationDeg = (dragRotationDeg + (ev.shiftKey ? -45 : 45) + 360) % 360
    applyDragPreviewRotation()
  }
}

/** 將當前旋轉角度應用到預覽格子 */
function applyDragPreviewRotation() {
  if (!dragPreviewMesh) return
  dragPreviewMesh.rotation.y = (dragRotationDeg * Math.PI) / 180
}

/** 創建樓宇左側的「模板格子」（點「添加」按鈕後才顯示） */
function buildDragSources() {
  if (!scene) return
  dragSourceGroup = new THREE.Group()
  const mat = new THREE.MeshStandardMaterial({
    color: DRAG_SOURCE_COLOR,
    metalness: 0.1,
    roughness: 0.4,
    transparent: true,
    opacity: 0.65,
  })
  const size = CELL_SIZE * 0.96
  const height = 0.5
  for (let i = 0; i < DRAG_SHAPES.length; i++) {
    const shape = DRAG_SHAPES[i]
    const geo = createGeometryByType(shape, size, height)
    const mesh = new THREE.Mesh(geo, mat)
    // 樓宇左側、貼地排成一列（圓/方/三角）
    mesh.position.set(-8.4, height / 2, (i - 1) * 1.8)
    mesh.userData.isDragSource = true
    mesh.userData.shape = shape
    dragSourceGroup.add(mesh)
    dragSourceMeshes.push(mesh)
  }
  dragSourceGroup.visible = false
  scene.add(dragSourceGroup)
}

/** 隱藏所有拖拽模板（進入/退出編輯模式時調用，模板不自動顯示） */
function hideDragTemplates() {
  if (!dragSourceGroup) return
  dragSourceGroup.visible = false
}

/** 點擊「添加」按鈕：顯示一組模板（圓/方/三角），拖走一個用掉一個 */
function spawnDragTemplates() {
  if (!dragSourceGroup) return
  for (const m of dragSourceMeshes) m.visible = true
  dragSourceGroup.visible = true
}

/** 開始拖拽：暫停視角旋轉與自動旋轉，創建跟隨滑鼠的預覽格子（形狀與模板一致） */
function startDragCell(mesh: THREE.Mesh, ev: PointerEvent) {
  if (!scene || !raycaster) return
  activeDragSource = mesh
  dragTarget = null
  dragRotationDeg = 0
  if (controls) controls.enabled = false // 拖拽期間暫停 OrbitControls
  prevAutoRotate = autoRotate.value // 拖拽期間暫停樓宇自動旋轉，避免放置錯位
  autoRotate.value = false
  if (host.value) host.value.style.cursor = 'grabbing'
  const size = CELL_SIZE * 0.96
  const shape = (mesh.userData.shape as 'Rect' | 'Cylinder' | 'Triangle') ?? 'Rect'
  dragPreviewMat = new THREE.MeshStandardMaterial({
    color: 0x4caf50,
    metalness: 0.1,
    roughness: 0.4,
    transparent: true,
    opacity: 0.75,
  })
  dragPreviewMesh = new THREE.Mesh(createGeometryByType(shape, size, 0.5), dragPreviewMat)
  dragPreviewMesh.visible = false
  scene.add(dragPreviewMesh)
  updateDragPreview(ev)
  document.addEventListener('pointermove', onDragMove)
  document.addEventListener('pointerup', endDragCell)
  // 拖拽期間支持滾輪 / R 鍵旋轉模板
  document.addEventListener('wheel', onDragWheel, { passive: false })
  document.addEventListener('keydown', onDragKeyDown)
}

function onDragMove(ev: PointerEvent) {
  updatePointer(ev)
  if (raycaster && camera) raycaster.setFromCamera(pointer, camera)
  updateDragPreview(ev)
}

/** 更新預覽格子：吸附到滑鼠所指網格位，綠色=可放置，紅色=已有格子 */
function updateDragPreview(_ev: PointerEvent) {
  if (!raycaster || !dragPreviewMesh || !dragPreviewMat) return
  const cell = pickGridCellFromRay()
  dragTarget = cell
    ? { ...cell, shape: (activeDragSource?.userData.shape as 'Rect' | 'Cylinder' | 'Triangle') ?? 'Rect' }
    : null
  if (!cell) {
    dragPreviewMesh.visible = false
    return
  }
  const { x, z } = cellToWorld(cell.row, cell.col)
  // 懸浮在目標層樓板上方（高於上層樓板頂面），確保完全可見、不嵌入樓板
  const y = (cell.floor3d - 1) * SLAB + FLOOR_H + 0.9
  dragPreviewMesh.position.set(x, y, z)
  dragPreviewMesh.visible = true
  applyDragPreviewRotation()
  dragPreviewMat.color.set(cell.exists ? 0xe53935 : 0x4caf50)
}

/** 松手：目標合法（網格內且無格子）則按模板形狀添加，否則取消 */
async function endDragCell() {
  document.removeEventListener('pointermove', onDragMove)
  document.removeEventListener('pointerup', endDragCell)
  document.removeEventListener('wheel', onDragWheel)
  document.removeEventListener('keydown', onDragKeyDown)
  if (controls) controls.enabled = true
  autoRotate.value = prevAutoRotate // 恢復自動旋轉
  if (host.value) host.value.style.cursor = 'grab'
  if (scene && dragPreviewMesh) {
    scene.remove(dragPreviewMesh)
    dragPreviewMat?.dispose() // 預覽 geometry 來自共享緩存，不 dispose
    dragPreviewMesh = null
    dragPreviewMat = null
  }
  const src = activeDragSource
  const target = dragTarget
  const placedRotationDeg = dragRotationDeg
  dragTarget = null
  activeDragSource = null
  dragRotationDeg = 0
  if (!src) return
  if (!target || target.exists) return // 不在網格上 / 已有格子 → 取消，模板保留
  if (!props.buildingId) return
  const floorId = await resolveFloorId(target.floor3d)
  if (!floorId) {
    message.warning(t('building.addCellFloorNotFound'))
    return
  }
  try {
    const res = await cellEdit({
      building_id: props.buildingId,
      row_no: target.row,
      col_no: target.col,
      action: 'add',
      scope: 'single',
      floor_id: floorId,
      shape: target.shape,
    })
    const n = res?.data?.affected ?? 0
    if (n > 0) {
      editDirty.value = true
      undoableOps.value = Math.min(undoableOps.value + 1, UNDO_LIMIT)
      // 拖拽中旋轉過：放置後寫入旋轉角度（旋轉也會進撤回棧，可單獨撤回）
      if (placedRotationDeg !== 0) {
        const rad = `0,${(placedRotationDeg * Math.PI / 180).toFixed(4)},0`
        try {
          await updateCellRotation({
            floor_id: floorId,
            row_no: target.row,
            col_no: target.col,
            rotation_xyz: rad,
          })
        } catch {
          // 旋轉寫入失敗不阻礙放置（格子已添加，角度保持默認）
          console.warn('[Building3D] Failed to write placed rotation:', placedRotationDeg)
        }
      }
      message.success(t('building.addCellSuccess'))
      // 模板無限使用：放置成功後模板保留在原處，可繼續拖拽下一個
    } else {
      message.warning(t('building.addCellExists'))
    }
  } catch {
    // 網絡/服務異常：模板保留，提示用戶重試
    message.error(t('building.addCellFailed'))
  }
  emit('refreshShapes')
}

function onPointerDown(ev: PointerEvent) {
  if (!camera || !raycaster) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  // 編輯模式
  if (editUnlocked.value) {
    // 添加模式：拖拽樓宇旁的模板格子
    if (editToolMode.value === 'add') {
      const srcHits = raycaster.intersectObjects(dragSourceMeshes, false)
      if (srcHits.length) {
        startDragCell(srcHits[0].object as THREE.Mesh, ev)
        return
      }
      return // 添加模式下點擊其他位置無操作
    }
    // 刪除模式：點擊格子（含隱形占位格子）立即刪除，可連續點擊
    if (editToolMode.value === 'delete') {
      const hiddenHits = raycaster.intersectObjects(hiddenCellMeshes, false)
      if (hiddenHits.length) {
        const ud = hiddenHits[0].object.userData
        if (ud.floor_id != null) {
          void deleteCellAt(ud.floor_id, ud.row, ud.col)
        }
        return
      }
      const hits = raycaster.intersectObjects(floorMeshes, false)
      if (hits.length) {
        const ud = hits[0].object.userData
        const shape = props.cellShapes?.find(
          (s) => s.row === ud.row && s.col === ud.col && s.floor === ud.floor,
        )
        if (shape?.floor_id != null) {
          void deleteCellAt(shape.floor_id, ud.row, ud.col)
        }
        return
      }
      return // 刪除模式下點擊空白無操作
    }
    // 未激活任何工具模式（none）：編輯模式下點擊不觸發普通選樓層
    return
  }
  const hits = raycaster.intersectObjects(floorMeshes, false)
  if (hits.length) {
    const mesh = hits[0].object as THREE.Mesh
    const ud = mesh.userData
    // 普通模式：點擊樓層 → 選中／進入該樓層（恢復最初的交互）
    const floor = ud.floor as number
    emit('selectFloor', floor)
  }
}

/** 刪除模式：刪除指定格子（單格），可連續調用 */
async function deleteCellAt(floor_id: number, row: number, col: number) {
  if (!props.buildingId) return
  try {
    const res = await cellEdit({
      building_id: props.buildingId,
      row_no: row,
      col_no: col,
      action: 'delete',
      scope: 'single',
      floor_id,
    })
    const n = res?.data?.affected ?? 0
    if (n > 0) {
      editDirty.value = true
      undoableOps.value = Math.min(undoableOps.value + 1, UNDO_LIMIT)
      showFeedback(t('building.cellDeleted', { row, col }))
    } else {
      showFeedback(t('building.noDeleteChange'))
    }
  } catch {
    message.error(t('building.addCellFailed'))
  }
  emit('refreshShapes')
}

/** Operation feedback shown near the edit buttons */
const editFeedback = ref('')
let feedbackTimer: ReturnType<typeof setTimeout> | undefined

function showFeedback(msg: string) {
  editFeedback.value = msg
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => { editFeedback.value = '' }, 2500)
}

async function handleUndo() {
  const res = await undoEdit()
  if (res && res.data && res.data.ok) {
    if ((res.data.affected ?? 0) > 0) {
      editDirty.value = true
      undoableOps.value = Math.max(0, undoableOps.value - 1)
    }
    showFeedback(t('building.undone', { n: res.data.affected }))
    emit('refreshShapes')
  } else if (undoableOps.value > 0) {
    // 本會話有過操作但後端已無可撤回內容 → 達到撤回上限
    showFeedback(t('building.undoLimitReached'))
  } else {
    showFeedback(t('building.noUndo'))
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
  // 編輯模式：模板格子輕微上下浮動，提示「可拖拽」
  if (dragSourceGroup && dragSourceGroup.visible && !activeDragSource) {
    dragSourceGroup.position.y = Math.sin(Date.now() * 0.002) * 0.06
  }
  controls?.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

onMounted(() => {
  if (!host.value) return
  // Defer initialization until loading is false (all data ready)
  if (props.loading) return
  initThreeJS()
})

/** Initialize Three.js scene and start rendering */
function initThreeJS() {
  if (!host.value || scene) return // Already initialized
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
  buildDragSources()
  hideDragTemplates()
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
}

// Initialize Three.js when loading becomes false (all data ready)
watch(
  () => props.loading,
  (newVal) => {
    if (newVal === false && !scene) {
      initThreeJS()
    }
  },
)

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
  if (editModeToastTimer) clearTimeout(editModeToastTimer)
  window.removeEventListener('resize', onResize)
  document.removeEventListener('pointermove', onDragPanelMove)
  document.removeEventListener('pointerup', endDragPanel)
  document.removeEventListener('pointermove', onDragMove)
  document.removeEventListener('pointerup', endDragCell)
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
  // 釋放拖拽模板資源（geometry 來自 createGeometryByType 的共享緩存，不能 dispose，只釋放材質）
  if (scene && dragSourceGroup) {
    scene.remove(dragSourceGroup)
    dragSourceGroup.traverse((o) => {
      const m = (o as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined
      if (Array.isArray(m)) m.forEach((x) => x.dispose())
      else if (m) m.dispose()
    })
  }
  if (scene && dragPreviewMesh) {
    scene.remove(dragPreviewMesh)
    dragPreviewMat?.dispose() // 預覽 geometry 亦為共享緩存，不 dispose
  }
  // 釋放 Hidden 格子佔位資源
  if (scene && hiddenCellGroup) {
    scene.remove(hiddenCellGroup)
    hiddenCellGeos.forEach((g) => g.dispose())
    hiddenCellMaterials.forEach((m) => m.dispose())
  }
  scene = null
  camera = null
  renderer = null
})
</script>

<template>
  <div ref="host" class="building3d">
    <!-- Loading overlay while data is being fetched -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">加载中...</div>
    </div>
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
    <!-- 編輯工具面板（四按鈕常駐：添加 / 刪除 / 撤回 / 關閉，可拖動） -->
    <div
      v-if="editUnlocked"
      class="edit-tool-panel"
      :style="{ left: `${panelPos.x}px`, top: `${panelPos.y}px` }"
    >
      <div
        class="edit-tool-header drag-handle"
        :title="t('building.panelDragHint')"
        @pointerdown="startDragPanel"
      >
        <span class="edit-tool-title">{{ t('building.cellEditor') }}</span>
      </div>
      <div class="edit-tool-actions">
        <button
          class="edit-tool-btn edit-tool-btn-add"
          :class="{ active: editToolMode === 'add' }"
          @click="toggleToolMode('add')"
        >
          {{ t('building.addBtn') }}
        </button>
        <button
          class="edit-tool-btn edit-tool-btn-del"
          :class="{ active: editToolMode === 'delete' }"
          @click="toggleToolMode('delete')"
        >
          {{ t('building.deleteBtn') }}
        </button>
        <button class="edit-tool-btn edit-tool-btn-undo" @click="handleUndo">{{ t('building.undoBtn') }}</button>
        <button class="edit-tool-btn edit-tool-btn-close" @click="onDoneClick">{{ t('building.doneBtn') }}</button>
      </div>
      <div v-if="editToolMode === 'add'" class="edit-tool-hint">
        {{ t('building.editAddHint') }}
      </div>
      <div v-else-if="editToolMode === 'delete'" class="edit-tool-hint">
        {{ t('building.editDeleteHint') }}
      </div>
      <div v-if="editFeedback" class="edit-feedback">{{ editFeedback }}</div>
    </div>
    <!-- 退出編輯會話確認框：保存 / 放棄 / 繼續編輯 -->
    <a-modal
      :open="confirmOpen"
      :title="t('building.saveChangesTitle')"
      :footer="null"
      width="460px"
      @cancel="confirmOpen = false"
    >
      <p class="confirm-content">{{ t('building.saveChangesContent') }}</p>
      <div class="confirm-actions">
        <a-button @click="confirmOpen = false">{{ t('building.saveChangesKeep') }}</a-button>
        <a-button danger @click="finishEditSession(false)">{{ t('building.saveChangesDiscard') }}</a-button>
        <a-button type="primary" @click="finishEditSession(true)">{{ t('building.saveChangesOk') }}</a-button>
      </div>
    </a-modal>
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
    <!-- 編輯模式短暫提示（進入編輯模式時出現，1.5 秒後自動消失） -->
    <transition name="fade">
      <div v-if="editModeToast" class="edit-mode-toast">
        {{ t('building.editModeOn') }}
      </div>
    </transition>
    <!-- 編輯模式：拖拽模板（進入添加模式後在樓宇左側顯示，可無限使用） -->
    <div v-if="editUnlocked && editToolMode === 'add'" class="drag-source-toolbar">
      <span class="drag-source-hint">{{ t('building.dragSourceHint') }}</span>
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
  background: var(--brand-canvas, #f7f7f5);
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

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--brand-canvas, #f7f7f5);
  z-index: 100;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e0e0e0;
  border-top-color: #c4a574;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 12px;
  font-size: 14px;
  color: #6b6b6b;
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

/* 編輯工具面板（四按鈕常駐：添加 / 刪除 / 撤回 / 關閉，可拖動） */
.edit-tool-panel {
  position: absolute;
  z-index: 10;
  width: 248px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(13, 13, 13, 0.9);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(8px);
  color: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  animation: edit-tool-in 180ms ease-out;
  user-select: none;
  touch-action: none;
}

.edit-tool-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding: 2px 0;
  cursor: move;
  border-radius: 4px;
}

.edit-tool-header:hover {
  background: rgba(255, 255, 255, 0.05);
}

.edit-tool-title {
  font-size: 14px;
  font-weight: 650;
  color: #f5ead7;
  pointer-events: none;
}

.edit-tool-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.edit-tool-btn {
  padding: 9px 12px;
  border-radius: 5px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.edit-tool-btn-add {
  background: rgba(76, 175, 80, 0.22);
  border-color: rgba(76, 175, 80, 0.5);
  color: #81c784;
}

.edit-tool-btn-add:hover,
.edit-tool-btn-add.active {
  background: rgba(76, 175, 80, 0.45);
  border-color: #4caf50;
  color: #fff;
}

.edit-tool-btn-del {
  background: rgba(244, 67, 54, 0.18);
  border-color: rgba(244, 67, 54, 0.45);
  color: #e57373;
}

.edit-tool-btn-del:hover,
.edit-tool-btn-del.active {
  background: rgba(244, 67, 54, 0.4);
  border-color: #f44336;
  color: #fff;
}

.edit-tool-btn-undo {
  background: rgba(156, 39, 176, 0.18);
  border-color: rgba(156, 39, 176, 0.45);
  color: #ce93d8;
}

.edit-tool-btn-undo:hover {
  background: rgba(156, 39, 176, 0.4);
  border-color: #9c27b0;
  color: #fff;
}

.edit-tool-btn-close {
  background: rgba(196, 165, 116, 0.22);
  border-color: rgba(196, 165, 116, 0.55);
  color: #f5ead7;
}

.edit-tool-btn-close:hover {
  background: rgba(196, 165, 116, 0.5);
  border-color: #c4a574;
  color: #fff;
}

.edit-tool-hint {
  margin-top: 10px;
  padding: 6px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cfe9e9;
  font-size: 11px;
  line-height: 1.5;
  text-align: center;
}

/* 退出編輯會話確認框 */
.confirm-content {
  margin: 0 0 4px;
  color: rgba(0, 0, 0, 0.75);
  font-size: 13px;
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
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

@keyframes edit-tool-in {
  from { opacity: 0; transform: translateY(-6px); }
  to   { opacity: 1; transform: translateY(0); }
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

/* 編輯模式短暫提示 */
.edit-mode-toast {
  position: absolute;
  z-index: 8;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  padding: 6px 18px;
  border-radius: 6px;
  background: rgba(13, 13, 13, 0.78);
  border: 1px solid rgba(196, 165, 116, 0.4);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  font-size: 12px;
  color: #f5ead7;
  white-space: nowrap;
  pointer-events: none;
}

/* 編輯模式：添加格子按鈕 + 拖拽提示（左下角） */
.drag-source-toolbar {
  position: absolute;
  z-index: 7;
  left: 10px;
  bottom: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.drag-source-hint {
  max-width: 260px;
  padding: 6px 12px;
  border-radius: 6px;
  background: rgba(13, 13, 13, 0.72);
  border: 1px solid rgba(95, 184, 184, 0.45);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  font-size: 12px;
  line-height: 1.5;
  color: #cfe9e9;
  pointer-events: none;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
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
