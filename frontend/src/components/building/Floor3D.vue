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
  getRoomById,
  shouldExcludeCell,
  type Cell,
  type DeviceType,
} from '@/utils/buildingDemo'
import {
  CYLINDER_RADIUS,
  DEFAULT_GRIDDATA,
  FALLBACK_COLOR,
  RECT_LENGTH,
  RECT_WIDTH,
  ROOM_H,
  createCylinderGeometry,
  createRectGeometry,
  decorationGeometry,
  disposeGeometryCache,
  gridCellToWorld,
  parseRotation,
  type FloorGridData,
} from '@/utils/floorGrid'

const props = defineProps<{
  level: number
  selectedRoom: string | null
  roomDevices: Record<string, DeviceType[]>
  layout: Record<string, Cell[]>
  editMode: boolean
  /** griddata 楼层布局；缺省用 DEFAULT_GRIDDATA */
  gridData?: FloorGridData
}>()

const emit = defineEmits<{
  selectRoom: [roomId: string | null]
  toggleCell: [payload: { row: number; col: number }]
}>()

const { t } = useI18n()
const host = ref<HTMLDivElement>()

const hoveredRoom = ref<string | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })

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

/** 共享轮廓线缓存（同一 geometry 只派生一次 EdgesGeometry） */
const edgesCache = new Map<string, THREE.EdgesGeometry>()

function edgesGeometryFor(geometry: THREE.BufferGeometry): THREE.EdgesGeometry {
  let edges = edgesCache.get(geometry.uuid)
  if (!edges) {
    edges = new THREE.EdgesGeometry(geometry)
    edgesCache.set(geometry.uuid, edges)
  }
  return edges
}

/** ground 圆盘几何：模块级缓存，避免每次 rebuild 新建泄漏 */
let groundGeo: THREE.CircleGeometry | null = null

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

  const gridData = props.gridData ?? DEFAULT_GRIDDATA
  const cellToRoom = buildCellToRoomMap(props.layout)
  const slabGeo = createRectGeometry(CELL_SIZE * 0.98, SLAB_H, CELL_SIZE * 0.98)

  for (const cell of INTERIOR_CELLS) {
    if (shouldExcludeCell(props.level, cell.row, cell.col)) continue
    const mat = new THREE.MeshStandardMaterial({
      color: 0xd8d2c8,
      roughness: 0.9,
      metalness: 0.05,
    })
    const mesh = new THREE.Mesh(slabGeo, mat)
    const { x, z } = cellToWorld(cell.row, cell.col)
    mesh.position.set(x, SLAB_H / 2, z)
    mesh.receiveShadow = true
    floorGroup.add(mesh)
  }

  // 格子：griddata 决定放什么（type）、放哪（xAxis/yAxis）、怎么转（rotate）
  // 注：DEFAULT_GRIDDATA 是 floor '8' 的演示数据；接入真实数据后请按楼层传入对应 gridData
  for (const cell of gridData.griddata) {
    const row = Number(cell.xAxis) + 1
    const col = Number(cell.yAxis) + 1
    if (!Number.isFinite(row) || !Number.isFinite(col)) continue
    const roomId = cellToRoom.get(`${row}-${col}`) ?? null
    const isRoom = !!roomId

    // 房间格高块、走廊格矮块；几何按尺寸共享，不重复 new
    const height = isRoom ? ROOM_H : CORRIDOR_H
    const geometry =
      cell.type === 'Cylinder'
        ? createCylinderGeometry(CYLINDER_RADIUS, height)
        : createRectGeometry(RECT_LENGTH, RECT_WIDTH, height)

    const baseColor = isRoom
      ? getRoomById(roomId)?.color ?? FALLBACK_COLOR
      : props.editMode
        ? '#d6e4ff'
        : '#f2efe8'
    const mat = decorationGeometry({ fixedColor: baseColor })

    const { x, z } = gridCellToWorld(cell)
    const baseY = SLAB_H + height / 2
    const mesh = new THREE.Mesh(geometry, mat)
    mesh.rotation.copy(parseRotation(cell.rotate))
    mesh.position.set(x, baseY, z)
    mesh.castShadow = true
    mesh.receiveShadow = true
    mesh.userData.roomId = roomId
    mesh.userData.row = row
    mesh.userData.col = col
    mesh.userData.kind = isRoom ? 'room' : 'corridor'
    mesh.userData.baseColor = new THREE.Color(baseColor)
    mesh.userData.baseY = baseY
    floorGroup.add(mesh)
    pickMeshes.push(mesh)

    const key = roomId ?? '__corridor__'
    const list = meshesByKey.get(key) || []
    list.push(mesh)
    meshesByKey.set(key, list)

    // 房间格轮廓线：仅 Rect（圆柱是光滑体，不画线框）
    if (isRoom && cell.type === 'Rect') {
      const line = new THREE.LineSegments(
        edgesGeometryFor(geometry),
        new THREE.LineBasicMaterial({
          color: 0xffffff,
          transparent: true,
          opacity: props.editMode ? 0.65 : 0.35,
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
        // 走廊：颜色已由 rebuildScene 按 editMode 算好，仅复位
        mat.opacity = 1
        mat.emissive = new THREE.Color(0x000000)
        mat.emissiveIntensity = 0
        continue
      }
      mat.opacity = dimOthers && !isActive ? 0.28 : 0.92
      mat.emissive = new THREE.Color(isActive ? baseColor : 0x000000)
      mat.emissiveIntensity = hovered === key ? 0.45 : selected === key ? 0.28 : 0
      const baseY = (mesh.userData.baseY as number) ?? SLAB_H + ROOM_H / 2
      mesh.position.y = isActive ? baseY + 0.12 : baseY
    }
  }
}

function deviceCount(roomId: string) {
  return (props.roomDevices[roomId] || []).length
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

  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(pickMeshes, false)
  if (hits.length) {
    const hit = hits[0].object
    const roomId = (hit.userData.roomId as string | null) || null
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
  hoveredRoom.value = null
  toastVisible.value = false
  updateAppearance()
  if (host.value) host.value.style.cursor = 'grab'
}

let pointerDownAt: { x: number; y: number } | null = null

function onPointerDown(ev: PointerEvent) {
  pointerDownAt = { x: ev.clientX, y: ev.clientY }
}

function onPointerUp(ev: PointerEvent) {
  if (!camera || !raycaster || !pointerDownAt) return
  const dx = ev.clientX - pointerDownAt.x
  const dy = ev.clientY - pointerDownAt.y
  pointerDownAt = null
  if (Math.hypot(dx, dy) > 6) return

  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(pickMeshes, false)
  if (!hits.length) {
    if (!props.editMode) emit('selectRoom', null)
    return
  }

  const hit = hits[0].object
  const row = hit.userData.row as number
  const col = hit.userData.col as number
  const roomId = (hit.userData.roomId as string | null) || null

  if (props.editMode) {
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
  if (props.editMode) {
    if (!props.selectedRoom) return t('building.editSelectRoom')
    const room = getRoomById(props.selectedRoom)
    return t('building.editClickCell', { n: room?.index ?? '' })
  }
  if (!hoveredRoom.value) return ''
  return t('building.roomN', { n: getRoomById(hoveredRoom.value)?.index ?? '' })
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
  window.addEventListener('resize', onResize)
  animate()
})

watch(
  () => props.selectedRoom,
  () => updateAppearance(),
)

watch(
  () => props.editMode,
  () => rebuildScene(),
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

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)
  renderer?.domElement.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement.removeEventListener('pointerup', onPointerUp)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  controls?.dispose()
  clearFloorGroup()
  disposeGeometryCache()
  for (const edges of edgesCache.values()) edges.dispose()
  edgesCache.clear()
  groundGeo?.dispose()
  groundGeo = null
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
  background: #f0eee9;
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
  background: rgba(255, 255, 255, 0.9);
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
