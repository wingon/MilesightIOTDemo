<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  CELL_SIZE,
  FLOOR_COUNT,
  INTERIOR_CELLS,
  cellToWorld,
} from '@/utils/buildingDemo'
import { brand } from '@/theme/colorConfig'

const props = defineProps<{
  selectedFloor: number | null
  floorDeviceCounts?: Record<number, number>
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

const FLOOR_H = 0.76
const FLOOR_GAP = 0.08
const SLAB = FLOOR_H + FLOOR_GAP

function floorColor(level: number, selected: number | null, hovered: number | null) {
  if (selected === level || hovered === level) return new THREE.Color(brand.primary)
  const t = level / Math.max(1, FLOOR_COUNT - 1)
  return new THREE.Color().setHSL(0.08, 0.12, 0.22 + t * 0.28)
}

function rebuildFloors() {
  if (!buildingGroup) return
  buildingGroup.clear()
  floorMeshes = []
  meshesByFloor.clear()

  const cellGeo = new THREE.BoxGeometry(CELL_SIZE * 0.96, FLOOR_H, CELL_SIZE * 0.96)

  for (let i = 0; i < FLOOR_COUNT; i++) {
    const level = i + 1
    const yBase = i * SLAB
    const mats: THREE.MeshStandardMaterial[] = []
    const levelMeshes: THREE.Mesh[] = []

    for (const cell of INTERIOR_CELLS) {
      const mat = new THREE.MeshStandardMaterial({
        color: floorColor(level, props.selectedFloor, hoveredFloor.value),
        metalness: 0.12,
        roughness: 0.55,
        transparent: true,
        opacity: 0.95,
      })
      mats.push(mat)
      const mesh = new THREE.Mesh(cellGeo, mat)
      const { x, z } = cellToWorld(cell.row, cell.col)
      mesh.position.set(x, yBase + FLOOR_H / 2, z)
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
  return props.floorDeviceCounts?.[floor] ?? 0
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
  camera.position.set(28, 38, 32)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)
  renderer.shadowMap.enabled = true
  host.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, (FLOOR_COUNT * SLAB) / 3, 0)
  controls.maxPolarAngle = Math.PI * 0.48
  controls.minDistance = 14
  controls.maxDistance = 95

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
      <div class="toast-level">{{ t('building.level', { n: hoveredFloor }) }}</div>
      <div class="toast-devices">
        {{ t('building.toastDevices', { n: deviceCountFor(hoveredFloor ?? 0) }) }}
      </div>
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
</style>
