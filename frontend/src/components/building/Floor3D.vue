<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  buildCellToRoomMap,
  CELL_SIZE,
  INTERIOR_CELLS,
  cellToWorld,
  shouldExcludeCell,
  type Cell,
  type DeviceType,
  type RoomMeta,
} from '@/utils/buildingDemo'
import {
  CYLINDER_RADIUS,
  DEFAULT_GRIDDATA,
  FALLBACK_COLOR,
  RECT_LENGTH,
  RECT_WIDTH,
  createCylinderGeometry,
  createRectGeometry,
  decorationGeometry,
  disposeGeometryCache,
  gridCellToWorld,
  parseRotation,
  type FloorGridData,
} from '@/utils/floorGrid'
import {
  computeWalls,
  WALL_THICKNESS,
  WALL_HEIGHT,
  type WallSegment,
} from '@/utils/floorGridWall'

/** 设备 3D 标记（已绑定格子的设备） */
export interface DeviceMarker {
  sn: string
  name: string
  row: number
  col: number
  abnormal: boolean
}

const props = defineProps<{
  level: number
  selectedRoom: string | null
  roomDevices: Record<string, DeviceType[]>
  layout: Record<string, Cell[]>
  editMode: boolean
  /** User-defined custom walls */
  customWalls?: { x1: number; z1: number; x2: number; z2: number }[]
  /** griddata floor layout; falls back to DEFAULT_GRIDDATA when not provided */
  gridData?: FloorGridData
  /** roomId -> metadata (index + color) resolved from DB rooms */
  roomMeta?: Record<string, RoomMeta>
  /** 设备标记（已绑定格子；按 cell 坐标渲染，含大厅格子） */
  devices?: DeviceMarker[]
  /** 当前待绑定格子的设备 SN（非空时点击格子触发 bindCell） */
  bindSn?: string | null
  /** DB 实际接入设备数（roomId -> count；提供时悬停提示以此为准） */
  deviceCountMap?: Record<string, number>
}>()

const emit = defineEmits<{
  selectRoom: [roomId: string | null]
  toggleCell: [payload: { row: number; col: number }]
  dropCell: [payload: { row: number; col: number; roomId: string }]
  dropWall: [payload: { row: number; col: number; dir: 'v' | 'h' }]
  selectWall: [index: number | null]
  moveWall: [payload: { index: number; row: number; col: number }]
  removeWall: [index: number]
  moveCell: [payload: { fromRow: number; fromCol: number; row: number; col: number }]
  bindCell: [payload: { row: number; col: number }]
}>()

const { t } = useI18n()
const host = ref<HTMLDivElement>()

const hoveredRoom = ref<string | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })
/** Index of the selected custom wall in edit mode */
const selectedWallIndex = ref<number | null>(null)

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let raycaster: THREE.Raycaster | null = null
let pointer = new THREE.Vector2()
let animId = 0
let pickMeshes: THREE.Mesh[] = []
const meshesByKey = new Map<string, THREE.Mesh[]>()
let floorGroup: THREE.Group | null = null

const CORRIDOR_H = 0.18
const SLAB_H = 0.12
/** Room cell display height (matches the exterior walls) */
const CELL_H = WALL_HEIGHT * 1.2

/** Shared outline cache (each geometry derives its EdgesGeometry only once) */
const edgesCache = new Map<string, THREE.EdgesGeometry>()

function edgesGeometryFor(geometry: THREE.BufferGeometry): THREE.EdgesGeometry {
  let edges = edgesCache.get(geometry.uuid)
  if (!edges) {
    edges = new THREE.EdgesGeometry(geometry)
    edgesCache.set(geometry.uuid, edges)
  }
  return edges
}

/** Ground disc geometry: module-level cache to avoid rebuild leaks */
let groundGeo: THREE.CircleGeometry | null = null

/** Device marker geometries: module-level cache to avoid rebuild leaks */
let deviceStemGeo: THREE.CylinderGeometry | null = null
let deviceHeadGeo: THREE.SphereGeometry | null = null

function disposeObject(obj: THREE.Object3D) {
  obj.traverse((child) => {
    const mesh = child as THREE.Mesh
    if (mesh.isMesh) {
      const mat = mesh.material
      if (Array.isArray(mat)) mat.forEach((m) => m.dispose())
      else mat?.dispose()
      return
    }
    const line = child as THREE.LineSegments
    if (line.isLineSegments) {
      const mat = line.material as THREE.Material
      mat?.dispose()
    }
  })
}

function clearFloorGroup() {
  if (!floorGroup) return
  while (floorGroup.children.length) {
    const child = floorGroup.children[0]
    floorGroup.remove(child)
    disposeObject(child)
  }
  pickMeshes = []
  meshesByKey.clear()
}

function rebuildScene() {
  if (!floorGroup) return
  clearFloorGroup()

  const layout = props.layout
  const cellToRoom = buildCellToRoomMap(layout)

  // Draw floor slabs (clickable floor cells)
  const slabGeo = createRectGeometry(CELL_SIZE * 0.98, SLAB_H, CELL_SIZE * 0.98)
  const roomGeo = createRectGeometry(CELL_SIZE * 0.92, CELL_H, CELL_SIZE * 0.92)
  for (const cell of INTERIOR_CELLS) {
    if (shouldExcludeCell(props.level, cell.row, cell.col)) continue

    // First draw the base slab
    const mat = new THREE.MeshStandardMaterial({
      color: 0xd8d2c8,
      roughness: 0.9,
      metalness: 0.05,
    })
    const mesh = new THREE.Mesh(slabGeo, mat)
    const { x, z } = cellToWorld(cell.row, cell.col)
    mesh.position.set(x, SLAB_H / 2, z)
    mesh.userData.row = cell.row
    mesh.userData.col = cell.col
    mesh.userData.kind = 'slab'
    floorGroup.add(mesh)
    pickMeshes.push(mesh)

    // If the cell is assigned to a room, draw the 3D room block
    const roomId = cellToRoom.get(`${cell.row}-${cell.col}`)
    if (roomId) {
      const meta = props.roomMeta?.[roomId]
      if (meta) {
        const baseY = SLAB_H + CELL_H / 2
        const colorMat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(meta.color),
          roughness: 0.7,
          metalness: 0.1,
          transparent: true,
          opacity: 0.85,
        })
        const colorMesh = new THREE.Mesh(roomGeo, colorMat)
        colorMesh.position.set(x, baseY, z)
        colorMesh.castShadow = false
        colorMesh.receiveShadow = false
        colorMesh.userData.row = cell.row
        colorMesh.userData.col = cell.col
        colorMesh.userData.roomId = roomId
        colorMesh.userData.kind = 'room-cell'
        colorMesh.userData.baseY = baseY
        colorMesh.userData.baseColor = new THREE.Color(meta.color)
        floorGroup.add(colorMesh)
        pickMeshes.push(colorMesh)

        const key = roomId
        const list = meshesByKey.get(key) || []
        list.push(colorMesh)
        meshesByKey.set(key, list)
      }
    }
  }

  // Draw device markers (devices bound to grid cells, incl. lobby cells)
  if (props.devices?.length) {
    deviceStemGeo ??= new THREE.CylinderGeometry(0.05, 0.05, 0.5, 8)
    deviceHeadGeo ??= new THREE.SphereGeometry(0.14, 12, 10)
    for (const dev of props.devices) {
      const { x, z } = cellToWorld(dev.row, dev.col)
      const color = dev.abnormal ? 0xb42318 : 0x2f8f46
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: dev.abnormal ? 0.4 : 0.18,
        roughness: 0.5,
        metalness: 0.2,
      })
      const baseY = SLAB_H + CELL_H + 0.05
      const stem = new THREE.Mesh(deviceStemGeo, mat)
      stem.position.set(x, baseY + 0.25, z)
      stem.userData.deviceSn = dev.sn
      stem.userData.kind = 'device-marker'
      const head = new THREE.Mesh(deviceHeadGeo, mat)
      head.position.set(x, baseY + 0.6, z)
      head.userData.deviceSn = dev.sn
      head.userData.kind = 'device-marker'
      floorGroup.add(stem, head)
    }
  }

  // Draw walls (interior intersecting walls hidden in edit mode)
  const walls = computeWalls(layout, props.editMode, props.customWalls ?? [])

  for (const wall of walls) {
    const dx = wall.x2 - wall.x1
    const dz = wall.z2 - wall.z1
    const length = Math.sqrt(dx * dx + dz * dz)
    if (length < 0.01) continue

    const isExterior = wall.isExterior
    const isCustom = wall.isCustom ?? false
    const thickness = isExterior ? WALL_THICKNESS * 1.5 : WALL_THICKNESS
    const height = isExterior ? WALL_HEIGHT * 1.2 : WALL_HEIGHT

    const geometry = new THREE.BoxGeometry(length, height, thickness)
    const isSelectedWall = isCustom && wall.wallIndex === selectedWallIndex.value
    const mat = new THREE.MeshStandardMaterial({
      color: isSelectedWall ? 0xe0783c : isExterior ? 0x8B7355 : 0x9E9589,
      roughness: isExterior ? 0.7 : 0.8,
      metalness: 0.1,
    })
    const mesh = new THREE.Mesh(geometry, mat)

    // Center point
    const cx = (wall.x1 + wall.x2) / 2
    const cz = (wall.z1 + wall.z2) / 2
    const baseY = SLAB_H + height / 2
    mesh.position.set(cx, baseY, cz)

    // Rotation: horizontal segments along the X axis, vertical segments along the Z axis
    if (Math.abs(dz) > Math.abs(dx)) {
      mesh.rotation.y = Math.PI / 2
    }

    mesh.castShadow = isExterior
    mesh.receiveShadow = isExterior
    mesh.userData.roomId = wall.roomId
    mesh.userData.kind = isExterior ? 'exterior-wall' : 'interior-wall'
    mesh.userData.isCustom = isCustom
    mesh.userData.wallIndex = wall.wallIndex
    mesh.userData.baseY = baseY
    mesh.userData.baseColor = new THREE.Color(isExterior ? 0x8B7355 : 0x9E9589)
    floorGroup.add(mesh)
    pickMeshes.push(mesh)

    const key = wall.roomId ?? '__corridor__'
    const list = meshesByKey.get(key) || []
    list.push(mesh)
    meshesByKey.set(key, list)

    // Wall edge lines
    if (isExterior) {
      const edges = new THREE.EdgesGeometry(geometry)
      const line = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({
          color: 0x5a4a3a,
          transparent: true,
          opacity: props.editMode ? 0.6 : 0.3,
        }),
      )
      line.position.copy(mesh.position)
      line.rotation.copy(mesh.rotation)
      floorGroup.add(line)
    }
  }

  const ground = new THREE.Mesh(
    groundGeo ?? (groundGeo = new THREE.CircleGeometry(22, 64)),
    new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.95 }),
  )
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.02
  ground.receiveShadow = true
  floorGroup.add(ground)

  updateAppearance()
}

function updateAppearance() {
  const selected = props.selectedRoom
  const hovered = hoveredRoom.value

  for (const [key, meshes] of meshesByKey) {
    const isRoom = key !== '__corridor__'
    const isActive = isRoom && (selected === key || hovered === key)
    const dimOthers = isRoom && !!selected && selected !== key
    for (const mesh of meshes) {
      const mat = mesh.material as THREE.MeshStandardMaterial
      const baseColor = (mesh.userData.baseColor as THREE.Color) ?? new THREE.Color(0xd8d2c8)
      mat.color = baseColor
      if (!isRoom) {
        // Corridor: color already computed by rebuildScene per editMode, just reset
        mat.opacity = 1
        mat.emissive = new THREE.Color(0x000000)
        mat.emissiveIntensity = 0
        continue
      }
      mat.opacity = dimOthers && !isActive ? 0.28 : 0.92
      mat.emissive = new THREE.Color(isActive ? baseColor : 0x000000)
      mat.emissiveIntensity = hovered === key ? 0.45 : selected === key ? 0.28 : 0
      const baseY = (mesh.userData.baseY as number) ?? SLAB_H + CELL_H / 2
      mesh.position.y = isActive ? baseY + CELL_H * 0.1 : baseY
    }
  }
}

function deviceCount(roomId: string) {
  // Pull real DB device count when available; fall back to demo room assignments.
  return props.deviceCountMap?.[roomId] ?? (props.roomDevices[roomId] || []).length
}

function updatePointer(ev: PointerEvent) {
  if (!host.value) return null
  const rect = host.value.getBoundingClientRect()
  pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
  return { rect, clientX: ev.clientX, clientY: ev.clientY }
}

function placeToast(clientX: number, clientY: number, rect: DOMRect) {
  let left = clientX - rect.left + 14
  let top = clientY - rect.top + 14
  left = Math.max(8, Math.min(left, rect.width - 160))
  top = Math.max(8, Math.min(top, rect.height - 56))
  toastStyle.value = { left: `${left}px`, top: `${top}px` }
}

function onPointerMove(ev: PointerEvent) {
  if (!host.value || !camera || !raycaster) return
  const pos = updatePointer(ev)
  if (!pos) return

  // Dragging: show the target-cell ghost preview
  if (pointerDownAt && dragSource) {
    const dx = ev.clientX - pointerDownAt.x
    const dy = ev.clientY - pointerDownAt.y
    if (Math.hypot(dx, dy) > 6) {
      const target = screenToCell(ev.clientX, ev.clientY)
      showDragGhost(target, dragSource.type)
      host.value.style.cursor = 'grabbing'
      return
    }
  }

  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(pickMeshes, false)
  if (hits.length) {
    const hit = hits[0].object
    const roomId = (hit.userData.roomId as string | null) || null
    if (props.bindSn) {
      toastVisible.value = true
      placeToast(pos.clientX, pos.clientY, pos.rect)
      host.value.style.cursor = 'cell'
      if (roomId && hoveredRoom.value !== roomId) {
        hoveredRoom.value = roomId
        updateAppearance()
      } else if (!roomId && hoveredRoom.value) {
        hoveredRoom.value = null
        updateAppearance()
      }
      return
    }
    if (props.editMode) {
      toastVisible.value = true
      placeToast(pos.clientX, pos.clientY, pos.rect)
      host.value.style.cursor = props.selectedRoom ? 'cell' : 'not-allowed'
      if (roomId && hoveredRoom.value !== roomId) {
        hoveredRoom.value = roomId
        updateAppearance()
      } else if (!roomId && hoveredRoom.value) {
        hoveredRoom.value = null
        updateAppearance()
      }
      return
    }
    if (roomId) {
      if (hoveredRoom.value !== roomId) {
        hoveredRoom.value = roomId
        updateAppearance()
      }
      toastVisible.value = true
      placeToast(pos.clientX, pos.clientY, pos.rect)
      host.value.style.cursor = 'pointer'
      return
    }
  }
  if (hoveredRoom.value != null) {
    hoveredRoom.value = null
    updateAppearance()
  }
  toastVisible.value = false
  host.value.style.cursor = 'grab'
}

function onPointerLeave() {
  pointerDownAt = null
  dragSource = null
  hideDragGhost()
  if (controls) controls.enabled = true
  hoveredRoom.value = null
  toastVisible.value = false
  updateAppearance()
  if (host.value) host.value.style.cursor = 'grab'
}

/** Convert screen coordinates to a grid cell coordinate (for drag & drop) */
function screenToCell(clientX: number, clientY: number): { row: number; col: number } | null {
  if (!host.value || !camera || !raycaster) return null
  const rect = host.value.getBoundingClientRect()
  const x = ((clientX - rect.left) / rect.width) * 2 - 1
  const y = -((clientY - rect.top) / rect.height) * 2 + 1
  const vec = new THREE.Vector2(x, y)
  raycaster.setFromCamera(vec, camera)
  // Intersection of the ray with the ground plane (y=0)
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0)
  const intersection = new THREE.Vector3()
  raycaster.ray.intersectPlane(plane, intersection)
  if (!intersection) return null
  // Convert to grid cell
  const halfCols = 12 / 2
  const halfRows = 8 / 2
  const col = Math.round(intersection.x / 1.15 + halfCols + 0.5)
  const row = Math.round(intersection.z / 1.15 + halfRows + 0.5)
  if (row < 1 || row > 8 || col < 1 || col > 12) return null
  return { row, col }
}

/** Show the drag preview on the target cell */
function showDragGhost(target: { row: number; col: number } | null, type: 'cell' | 'wall') {
  if (!scene) return
  if (!dragGhost) {
    const geo = new THREE.BoxGeometry(CELL_SIZE * 0.92, CELL_H, CELL_SIZE * 0.92)
    const mat = new THREE.MeshBasicMaterial({
      color: type === 'cell' ? 0x2f8f46 : 0xe0783c,
      transparent: true,
      opacity: 0.45,
      depthWrite: false,
    })
    dragGhost = new THREE.Mesh(geo, mat)
    scene.add(dragGhost)
  }
  if (!target) {
    dragGhost.visible = false
    return
  }
  const { x, z } = cellToWorld(target.row, target.col)
  dragGhost.position.set(x, SLAB_H + CELL_H / 2, z)
  dragGhost.visible = true
}

function hideDragGhost() {
  if (!dragGhost) return
  dragGhost.visible = false
}

function onDragOver(ev: DragEvent) {
  if (!props.editMode) return
  ev.preventDefault()
  ev.dataTransfer!.dropEffect = 'copy'
}

function onDrop(ev: DragEvent) {
  if (!props.editMode) return
  ev.preventDefault()
  const data = ev.dataTransfer?.getData('application/json')
  if (!data) return
  try {
    const parsed = JSON.parse(data)
    const cell = screenToCell(ev.clientX, ev.clientY)
    if (!cell) return
    if (parsed.type === 'room' && parsed.roomId) {
      emit('dropCell', { row: cell.row, col: cell.col, roomId: parsed.roomId })
    } else if (parsed.type === 'wall') {
      emit('dropWall', { row: cell.row, col: cell.col, dir: parsed.dir === 'h' ? 'h' : 'v' })
    }
  } catch { /* invalid data */ }
}

let pointerDownAt: { x: number; y: number } | null = null
/** Source object being dragged (cell/wall hit at pointerdown) */
let dragSource: { type: 'cell'; fromRow: number; fromCol: number } | { type: 'wall'; index: number } | null = null
/** Ghost preview mesh at the drag target position */
let dragGhost: THREE.Mesh | null = null

function onPointerDown(ev: PointerEvent) {
  pointerDownAt = { x: ev.clientX, y: ev.clientY }
  if (!props.editMode || !camera || !raycaster) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(pickMeshes, false)
  if (!hits.length) return
  const hit = hits[0].object
  if (hit.userData.isCustom && typeof hit.userData.wallIndex === 'number') {
    dragSource = { type: 'wall', index: hit.userData.wallIndex }
    if (controls) controls.enabled = false
  } else if (hit.userData.kind === 'room-cell' && hit.userData.roomId) {
    dragSource = { type: 'cell', fromRow: hit.userData.row, fromCol: hit.userData.col }
    if (controls) controls.enabled = false
  }
}

function onPointerUp(ev: PointerEvent) {
  if (!camera || !raycaster || !pointerDownAt) return
  const dx = ev.clientX - pointerDownAt.x
  const dy = ev.clientY - pointerDownAt.y
  const source = dragSource
  pointerDownAt = null
  dragSource = null
  const isDrag = Math.hypot(dx, dy) > 6
  hideDragGhost()
  if (controls) controls.enabled = true

  // Drag-move (cell/wall)
  if (isDrag && props.editMode && source) {
    const target = screenToCell(ev.clientX, ev.clientY)
    if (target) {
      if (source.type === 'wall') {
        selectedWallIndex.value = null
        emit('selectWall', null)
        emit('moveWall', { index: source.index, row: target.row, col: target.col })
        rebuildScene()
        return
      }
      if (source.fromRow !== target.row || source.fromCol !== target.col) {
        emit('moveCell', {
          fromRow: source.fromRow,
          fromCol: source.fromCol,
          row: target.row,
          col: target.col,
        })
        return
      }
    }
    return
  }

  if (isDrag) return

  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(pickMeshes, false)
  if (!hits.length) {
    if (!props.editMode) emit('selectRoom', null)
    else if (selectedWallIndex.value !== null) {
      selectedWallIndex.value = null
      emit('selectWall', null)
      rebuildScene()
    }
    return
  }

  const hit = hits[0].object
  const row = hit.userData.row as number
  const col = hit.userData.col as number
  const roomId = (hit.userData.roomId as string | null) || null

  // Binding a device to a cell takes precedence (works in normal mode too)
  if (props.bindSn) {
    if (hit.userData.kind === 'slab' || hit.userData.kind === 'room-cell') {
      emit('bindCell', { row, col })
    }
    return
  }

  if (props.editMode) {
    // Click a custom wall → select/deselect
    if (hit.userData.isCustom && typeof hit.userData.wallIndex === 'number') {
      const idx = hit.userData.wallIndex as number
      if (selectedWallIndex.value === idx) {
        // Clicking an already-selected wall again → delete it directly
        selectedWallIndex.value = null
        emit('selectWall', null)
        emit('removeWall', idx)
        rebuildScene()
        return
      }
      selectedWallIndex.value = idx
      emit('selectWall', idx)
      rebuildScene()
      return
    }
    // With a wall selected, clicking a cell moves the wall
    if (selectedWallIndex.value !== null && (hit.userData.kind === 'slab' || hit.userData.kind === 'room-cell')) {
      const idx = selectedWallIndex.value
      emit('moveWall', { index: idx, row, col })
      selectedWallIndex.value = null
      emit('selectWall', null)
      return
    }
    // Exterior outline is fixed and not editable
    if (hit.userData.kind === 'exterior-wall') return
    // Click a cell belonging to another room → select that room, without changing cell ownership
    const cellRoomId = (hit.userData.roomId as string | null) || null
    if (cellRoomId && cellRoomId !== props.selectedRoom) {
      emit('selectRoom', cellRoomId)
      return
    }
    if (!props.selectedRoom) return
    emit('toggleCell', { row, col })
    return
  }

  if (!roomId) {
    emit('selectRoom', null)
    return
  }
  emit('selectRoom', props.selectedRoom === roomId ? null : roomId)
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

const toastTitle = () => {
  if (props.bindSn) {
    const dev = props.devices?.find((d) => d.sn === props.bindSn)
    return t('building.bindClickCell', { name: dev?.name ?? props.bindSn })
  }
  if (props.editMode) {
    if (!props.selectedRoom) return t('building.editSelectRoom')
    const meta = props.roomMeta?.[props.selectedRoom]
    return t('building.editClickCell', { n: meta?.index ?? '' })
  }
  if (!hoveredRoom.value) return ''
  return t('building.roomN', { n: props.roomMeta?.[hoveredRoom.value]?.index ?? '' })
}

onMounted(() => {
  if (!host.value) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf0eee9)
  scene.fog = new THREE.Fog(0xf0eee9, 28, 55)

  camera = new THREE.PerspectiveCamera(45, w / Math.max(1, h), 0.1, 120)
  camera.position.set(10, 14, 14)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)
  renderer.shadowMap.enabled = true
  host.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, 0.5, 0)
  controls.maxPolarAngle = Math.PI * 0.48
  controls.minDistance = 8
  controls.maxDistance = 36

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb0a090, 0.9))
  const dir = new THREE.DirectionalLight(0xfff5e6, 1.1)
  dir.position.set(12, 20, 8)
  dir.castShadow = true
  scene.add(dir)
  const fill = new THREE.DirectionalLight(0xc4a574, 0.35)
  fill.position.set(-10, 8, -8)
  scene.add(fill)

  floorGroup = new THREE.Group()
  scene.add(floorGroup)
  rebuildScene()

  raycaster = new THREE.Raycaster()
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', onPointerLeave)
  host.value.addEventListener('dragover', onDragOver)
  host.value.addEventListener('drop', onDrop)
  window.addEventListener('resize', onResize)
  animate()
})

watch(
  () => props.selectedRoom,
  () => updateAppearance(),
)

watch(
  () => props.editMode,
  (v) => {
    if (!v) {
      selectedWallIndex.value = null
      emit('selectWall', null)
    }
    rebuildScene()
  },
)

watch(
  () => props.layout,
  () => rebuildScene(),
  { deep: true },
)

watch(
  () => props.gridData,
  () => rebuildScene(),
  { deep: true },
)

watch(
  () => props.devices,
  () => rebuildScene(),
  { deep: true },
)

watch(
  () => props.bindSn,
  () => {
    if (props.bindSn && !props.editMode) return
    updateAppearance()
  },
)

watch(
  () => props.customWalls,
  () => {
    if (selectedWallIndex.value !== null && props.customWalls) {
      const maxIndex = props.customWalls.length - 1
      if (selectedWallIndex.value > maxIndex) {
        selectedWallIndex.value = null
        emit('selectWall', null)
      }
    }
    rebuildScene()
  },
  { deep: true },
)

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  renderer?.domElement.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement.removeEventListener('pointerup', onPointerUp)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  host.value?.removeEventListener('dragover', onDragOver)
  host.value?.removeEventListener('drop', onDrop)
  controls?.dispose()
  clearFloorGroup()
  disposeGeometryCache()
  for (const edges of edgesCache.values()) edges.dispose()
  edgesCache.clear()
  groundGeo?.dispose()
  groundGeo = null
  deviceStemGeo?.dispose()
  deviceStemGeo = null
  deviceHeadGeo?.dispose()
  deviceHeadGeo = null
  renderer?.dispose()
  if (renderer?.domElement.parentElement) {
    renderer.domElement.parentElement.removeChild(renderer.domElement)
  }
  scene = null
  camera = null
  renderer = null
})
</script>

<template>
  <div ref="host" class="floor3d" :class="{ editing: editMode }">
    <div v-if="editMode" class="edit-banner">{{ t('building.editBanner') }}</div>
    <div
      v-show="toastVisible || (editMode && selectedRoom)"
      class="room-toast"
      :style="editMode && selectedRoom && !toastVisible ? { left: '12px', top: '40px' } : toastStyle"
    >
      <div class="toast-title">{{ toastTitle() }}</div>
      <div v-if="!editMode && hoveredRoom" class="toast-meta">
        {{ t('building.toastDevices', { n: deviceCount(hoveredRoom) }) }}
      </div>
      <div v-else-if="editMode && selectedRoom" class="toast-meta">
        {{ t('building.editExclusive') }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.floor3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  overflow: hidden;
  background: var(--brand-canvas, #f0eee9);
  cursor: grab;
}

.floor3d.editing {
  outline: 2px solid rgba(196, 165, 116, 0.65);
  outline-offset: -2px;
}

.floor3d:active {
  cursor: grabbing;
}

.floor3d :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.edit-banner {
  position: absolute;
  z-index: 6;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  pointer-events: none;
  font-size: 12px;
  font-weight: 600;
  color: #0d0d0d;
  background: var(--brand-surface, rgba(255, 255, 255, 0.9));
  border: 1px solid #c4a574;
  padding: 4px 10px;
}

.room-toast {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  min-width: 120px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(13, 13, 13, 0.62);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(6px);
  color: #fff;
}

.toast-title {
  font-size: 13px;
  font-weight: 650;
  color: #f5ead7;
}

.toast-meta {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
}
</style>
