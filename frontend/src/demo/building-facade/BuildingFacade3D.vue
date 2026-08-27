<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js'
import {
  CELL_SIZE,
  FLOOR_COUNT,
  FLOOR_H,
  FLOOR_GAP,
  FLOORS,
  SLAB,
  TRI_ROT_Y,
  cellCenter,
  floorCenterY,
  floorName,
  type SnapCell,
} from './facadeSnapshot'

/*
 * 楼宇幕墙美化 DEMO（参考 thingraph/bim-viewer 的外观风格）
 *
 * 轮廓 1:1：建筑体量由 facadeSnapshot 的格子几何决定（与 /building-viewer
 * 的 Building3D.vue 完全同源：同格子尺寸、同层高、同缺格、同三角形朝向、
 * 同核心筒与地面尺寸），幕墙只是贴在原外表面上的一层"表皮"，
 * 外表面外凸仅 0.012（防 z-fighting），视觉轮廓不变。
 *
 * 美化要点：
 *  1. 整片连续玻璃幕墙（跨格子缝隙，消除"一格一格"感）
 *  2. 楼层 spandrel 带（浅色实体带 + 深色层缝 → 水平楼层线条）
 *  3. 竖向幕墙分隔框（mullion，真实幕墙分格宽度）
 *  4. 三种玻璃色调随机分布 + 环境反射（真实幕墙反射差异）
 *  5. 日间/黄昏/夜间三种光照预设（夜间内透暖光）
 *  6. BIM 线框模式（bim-viewer 的 outline 特征）
 */

// ---- 几何常量（与原页面 Building3D.vue 一致） ----
/** 格子边长 = CELL_SIZE * 0.96（同原组件 cellSize） */
const CELL_W = CELL_SIZE * 0.96
const HALF = CELL_W / 2
/** 幕墙板厚 */
const PANEL_T = 0.05
/** 幕墙外表面外凸量（防 z-fighting，视觉可忽略） */
const PROUD = 0.012
/** 楼层实体带（spandrel）高度 */
const SPANDREL_H = 0.11
/** 玻璃带高度 */
const GLASS_H = FLOOR_H - SPANDREL_H * 2
/** 竖向分隔框截面宽 */
const MULLION_W = 0.055
/** 竖向分隔框截面深 */
const MULLION_D = 0.075
/** 竖向分隔框高（整层高，跨层缝连续） */
const MULLION_H = FLOOR_H + FLOOR_GAP
/** 核心筒尺寸/位置（与原 Building3D 的 Visual core 一致） */
const CORE_W = CELL_SIZE * 1.6
const CORE_H = FLOOR_COUNT * SLAB
const CORE_POS = new THREE.Vector3(CELL_SIZE * 2, CORE_H / 2 - FLOOR_GAP / 2, CELL_SIZE * 1)
/** 建筑总高（不含核心筒凸出） */
const ROOF_Y = (FLOOR_COUNT - 1) * SLAB + FLOOR_H

// ---- 控件状态 ----
const autoRotate = ref(true)
const rotateSpeed = ref(1)
const glassOpacity = ref(0.55)
const showMullions = ref(true)
const showOutline = ref(false)
const preset = ref<'day' | 'dusk' | 'night'>('day')

// ---- 楼层悬停状态 ----（参照 /building-viewer 行为）
const hoveredFloor = ref<number | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })

// ---- 调试提示 ----
const debugInfo = ref<string>('')
const debugVisible = ref(false)

const host = ref<HTMLDivElement>()

// ---- Three.js 句柄 ----
let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let buildingGroup: THREE.Group | null = null
let dirLight: THREE.DirectionalLight | null = null
let hemiLight: THREE.HemisphereLight | null = null
let fillLight: THREE.DirectionalLight | null = null
let animId = 0
let pmrem: THREE.PMREMGenerator | null = null

// 可动态调整的材质
let glassMats: THREE.MeshPhysicalMaterial[] = []
let innerMat: THREE.MeshStandardMaterial | null = null
let mullionMesh: THREE.Mesh | null = null
let outlineLines: THREE.LineSegments | null = null

// 拾取/悬停句柄
let raycaster: THREE.Raycaster | null = null
let pointer = new THREE.Vector2()
/** 每个楼层一个不可见的命中盒（用于 raycast 判定落在哪一层） */
let floorHits: THREE.Mesh[] = []
/** 悬停高亮盒 */
let hoverHighlight: THREE.Mesh | null = null
let hoverHighlightMat: THREE.MeshBasicMaterial | null = null

/** 需要统一释放的资源 */
const disposables: Array<THREE.BufferGeometry | THREE.Material | THREE.Texture> = []

// ---- 光照/天空预设 ----
interface PresetConf {
  dirColor: number
  dirIntensity: number
  dirPos: [number, number, number]
  hemiSky: number
  hemiGround: number
  hemiIntensity: number
  fog: string
  /** 天空渐变：顶 / 地平 */
  sky: [string, string]
  /** 室内透光强度（夜间亮灯） */
  innerLight: number
  /** 环境反射强度 */
  envIntensity: number
  /** 玻璃透明度 */
  glassOpacity: number
  /** 背景亮度 */
  bgIntensity: number
}

const PRESETS: Record<'day' | 'dusk' | 'night', PresetConf> = {
  day: {
    dirColor: 0xfff2df,
    dirIntensity: 1.15,
    dirPos: [18, 55, 12],
    hemiSky: 0xffffff,
    hemiGround: 0xb8a894,
    hemiIntensity: 0.75,
    fog: '#e9e5dc',
    sky: ['#a9c9de', '#f0ece3'],
    innerLight: 0,
    envIntensity: 1.0,
    glassOpacity: 0.68,
    bgIntensity: 1,
  },
  dusk: {
    dirColor: 0xff9a5c,
    dirIntensity: 1.0,
    dirPos: [-26, 13, 20],
    hemiSky: 0x94a4c6,
    hemiGround: 0x6b5a48,
    hemiIntensity: 0.5,
    fog: '#e3c3a4',
    sky: ['#4d5f92', '#f0b47c'],
    innerLight: 0.22,
    envIntensity: 0.55,
    glassOpacity: 0.5,
    bgIntensity: 1,
  },
  night: {
    dirColor: 0x8aa2e0,
    dirIntensity: 0.22,
    dirPos: [12, 40, -18],
    hemiSky: 0x3a4a6b,
    hemiGround: 0x1c2230,
    hemiIntensity: 0.35,
    fog: '#141c2b',
    sky: ['#0a1322', '#1d2839'],
    innerLight: 0.9,
    envIntensity: 0.25,
    glassOpacity: 0.4,
    bgIntensity: 1,
  },
}

/** 生成竖直渐变天空纹理（equirect 映射到背景） */
function makeSkyTexture(top: string, bottom: string): THREE.CanvasTexture {
  const canvas = document.createElement('canvas')
  canvas.width = 16
  canvas.height = 256
  const ctx = canvas.getContext('2d')!
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height)
  grad.addColorStop(0, top)
  grad.addColorStop(0.62, bottom)
  grad.addColorStop(1, bottom)
  ctx.fillStyle = grad
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  const tex = new THREE.CanvasTexture(canvas)
  tex.mapping = THREE.EquirectangularReflectionMapping
  tex.colorSpace = THREE.SRGBColorSpace
  return tex
}

const skyTextures = new Map<string, THREE.CanvasTexture>()

function skyTextureFor(p: PresetConf): THREE.CanvasTexture {
  const key = p.sky.join('|')
  let tex = skyTextures.get(key)
  if (!tex) {
    tex = makeSkyTexture(p.sky[0], p.sky[1])
    skyTextures.set(key, tex)
    disposables.push(tex)
  }
  return tex
}

// ---- 幕墙段计算 ----

/** 一段外墙：面中心（位于格子外表面平面）+ 长度 + 法线方向角 */
interface WallSeg {
  cx: number
  cz: number
  len: number
  /** 板绕 Y 旋转角：板局部 +z（厚度方向）= 外法线 = (sinφ, 0, cosφ) */
  phi: number
}

/**
 * 计算某层的全部外墙段（连续外露面合并成整片，跨格子缝隙）。
 *
 * 外露判定（与原轮廓严格对应）：
 *  - 矩形格子的正交面：邻居缺失（缺格/出界）或邻居是三角形（三角形只占半格）
 *  - 三角形格子：不生成正交面（其正交面均被邻居遮挡），斜边单独成段
 */
function segmentsForFloor(cells: SnapCell[]): WallSeg[] {
  const map = new Map<string, SnapCell>()
  for (const c of cells) map.set(`${c.row},${c.col}`, c)
  const has = (r: number, c: number) => map.has(`${r},${c}`)
  const isTri = (r: number, c: number) => map.get(`${r},${c}`)?.shape === 'Triangle'
  const exposed = (r: number, c: number, nr: number, nc: number) =>
    !has(nr, nc) || isTri(nr, nc)

  const segs: WallSeg[] = []

  // 北面（法线 -z）与南面（法线 +z）：按行扫描连续列段
  for (const dir of ['north', 'south'] as const) {
    const dr = dir === 'north' ? -1 : 1
    for (let r = 1; r <= 7; r++) {
      let start = 0
      for (let c = 1; c <= 13; c++) {
        const ok = c <= 12 && has(r, c) && !isTri(r, c) && exposed(r, c, r + dr, c)
        if (ok && start === 0) start = c
        if (!ok && start > 0) {
          const c0 = start
          const c1 = c - 1
          const a = cellCenter(r, c0)
          const b = cellCenter(r, c1)
          const sign = dir === 'north' ? -1 : 1
          segs.push({
            cx: (a.x + b.x) / 2,
            cz: a.z + sign * HALF,
            len: (c1 - c0 + 1) * CELL_SIZE,
            phi: dir === 'north' ? Math.PI : 0,
          })
          start = 0
        }
      }
    }
  }

  // 西面（法线 -x）与东面（法线 +x）：按列扫描连续行段
  for (const dir of ['west', 'east'] as const) {
    const dc = dir === 'west' ? -1 : 1
    for (let c = 1; c <= 12; c++) {
      let start = 0
      for (let r = 1; r <= 8; r++) {
        const ok = r <= 7 && has(r, c) && !isTri(r, c) && exposed(r, c, r, c + dc)
        if (ok && start === 0) start = r
        if (!ok && start > 0) {
          const r0 = start
          const r1 = r - 1
          const a = cellCenter(r0, c)
          const b = cellCenter(r1, c)
          const sign = dir === 'west' ? -1 : 1
          segs.push({
            cx: a.x + sign * HALF,
            cz: (a.z + b.z) / 2,
            len: (r1 - r0 + 1) * CELL_SIZE,
            phi: dir === 'west' ? -Math.PI / 2 : Math.PI / 2,
          })
          start = 0
        }
      }
    }
  }

  // 三角形斜面（切角处的斜幕墙）
  for (const cell of cells) {
    if (cell.shape !== 'Triangle') continue
    const { x, z } = cellCenter(cell.row, cell.col)
    if (cell.rotY > 0) {
      // B 朝向：斜边西北→东南，法线朝西南
      segs.push({ cx: x, cz: z, len: CELL_W * Math.SQRT2, phi: -Math.PI / 4 })
    } else {
      // A 朝向：斜边西南→东北，法线朝东南
      segs.push({ cx: x, cz: z, len: CELL_W * Math.SQRT2, phi: Math.PI / 4 })
    }
  }

  return segs
}

/** 段的法线方向单位向量 */
function segNormal(seg: WallSeg): THREE.Vector3 {
  return new THREE.Vector3(Math.sin(seg.phi), 0, Math.cos(seg.phi))
}

/** 生成一段幕墙的板材几何（上带 / 玻璃 / 下带），返回后由调用方归入对应材质桶 */
function panelGeometries(seg: WallSeg, yC: number): {
  bands: THREE.BoxGeometry[]
  glass: THREE.BoxGeometry
} {
  const n = segNormal(seg)
  // 板中心：面位置沿法线内移（板外表面 = 格子外表面 + PROUD）
  const px = seg.cx - n.x * (PANEL_T / 2 - PROUD)
  const pz = seg.cz - n.z * (PANEL_T / 2 - PROUD)

  const band = (y: number) => {
    const g = new THREE.BoxGeometry(seg.len, SPANDREL_H, PANEL_T)
    g.rotateY(seg.phi)
    g.translate(px, y, pz)
    return g
  }
  const glass = new THREE.BoxGeometry(seg.len, GLASS_H, PANEL_T - 0.014)
  glass.rotateY(seg.phi)
  glass.translate(px, yC, pz)

  return {
    bands: [band(yC + FLOOR_H / 2 - SPANDREL_H / 2), band(yC - FLOOR_H / 2 + SPANDREL_H / 2)],
    glass,
  }
}

/** 生成一段幕墙的竖向分隔框几何（含段两端） */
function mullionGeometries(seg: WallSeg, yC: number): THREE.BoxGeometry[] {
  const n = segNormal(seg)
  const d = new THREE.Vector3(Math.cos(seg.phi), 0, -Math.sin(seg.phi))
  // 分隔框中心：板外表面再向外凸出
  const px = seg.cx + n.x * (PROUD + MULLION_D / 2 - 0.018)
  const pz = seg.cz + n.z * (PROUD + MULLION_D / 2 - 0.018)
  const count = Math.max(2, Math.round(seg.len / CELL_SIZE) + 1)
  const out: THREE.BoxGeometry[] = []
  for (let i = 0; i < count; i++) {
    const t = -seg.len / 2 + (i / (count - 1)) * seg.len
    const g = new THREE.BoxGeometry(MULLION_W, MULLION_H, MULLION_D)
    g.rotateY(seg.phi)
    g.translate(px + d.x * t, yC, pz + d.z * t)
    out.push(g)
  }
  return out
}

/** 三角形格子几何（与原 floorGridTriangle.createTriangleGeometry 完全一致） */
function triangleGeometry(size: number, height: number): THREE.ExtrudeGeometry {
  const half = size / 2
  const s = new THREE.Shape()
  s.moveTo(-half, -half)
  s.lineTo(-half, half)
  s.lineTo(half, half)
  s.closePath()
  const g = new THREE.ExtrudeGeometry(s, { depth: height, bevelEnabled: false })
  g.rotateX(-Math.PI / 2)
  g.translate(0, -height / 2, 0)
  return g
}

/**
 * 兼容合并：把几何统一转为非索引再合并。
 * BoxGeometry 是有索引的（indexed），ExtrudeGeometry 是非索引的（non-indexed）；
 * mergeGeometries 要求所有几何属性一致（都要有 index 或都没有），否则返回 null。
 */
function mergeCompat(geos: THREE.BufferGeometry[]): THREE.BufferGeometry {
  const nonIndexed = geos.map((g) => (g.index ? g.toNonIndexed() : g))
  const merged = mergeGeometries(nonIndexed, false)
  // 释放 toNonIndexed 产生的副本（merge 已完成数据拷贝）
  for (const g of nonIndexed) if (g !== merged) g.dispose()
  if (!merged) throw new Error('mergeGeometries() failed: incompatible geometries')
  return merged
}

/** 简单字符串哈希（玻璃色调稳定分配） */
function hashStr(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return Math.abs(h)
}

// ---- 建筑构建 ----

function buildBuilding(): THREE.Group {
  const group = new THREE.Group()

  // 材质
  innerMat = new THREE.MeshStandardMaterial({
    color: 0x2b3440,       // 冷灰蓝内衬（透过玻璃看是"室内"）
    roughness: 0.9,
    metalness: 0,
    emissive: 0xffb46b,    // 夜间内透暖光
    emissiveIntensity: 0,
  })
  const spandrelMat = new THREE.MeshStandardMaterial({
    color: 0xd6d0c4,       // 浅暖灰楼层带
    roughness: 0.5,
    metalness: 0.15,
  })
  const mullionMat = new THREE.MeshStandardMaterial({
    color: 0x3b444e,       // 深灰金属分隔框
    roughness: 0.35,
    metalness: 0.75,
  })
  const roofMat = new THREE.MeshStandardMaterial({
    color: 0xc9c4ba,
    roughness: 0.9,
    metalness: 0.05,
  })
  const coreMat = new THREE.MeshStandardMaterial({
    color: 0x2e3640,
    roughness: 0.4,
    metalness: 0.65,
  })
  const GLASS_COLORS = [0x9fc6d6, 0x8fbccf, 0xa9cfd4]
  glassMats = GLASS_COLORS.map(
    (c) =>
      new THREE.MeshPhysicalMaterial({
        color: c,
        metalness: 0.15,
        roughness: 0.05,
        transparent: true,
        opacity: glassOpacity.value,
        clearcoat: 0.8,
        clearcoatRoughness: 0.06,
        envMapIntensity: 1.4,
        side: THREE.DoubleSide,
        depthWrite: false,
      }),
  )
  disposables.push(innerMat, spandrelMat, mullionMat, roofMat, coreMat, ...glassMats)

  // 几何收集桶（按材质分组，最后合并成少量 mesh）
  const innerGeos: THREE.BufferGeometry[] = []
  const bandGeos: THREE.BufferGeometry[] = []
  const mullionGeos: THREE.BufferGeometry[] = []
  const roofGeos: THREE.BufferGeometry[] = []
  const glassBuckets: THREE.BufferGeometry[][] = [[], [], []]
  const outlineGeos: THREE.BufferGeometry[] = []

  for (const floor of FLOORS) {
    const yC = floorCenterY(floor.level)

    // 1) 格子本体（内衬，轮廓 1:1 的决定因素）
    for (const cell of floor.cells) {
      const { x, z } = cellCenter(cell.row, cell.col)
      let geo: THREE.BufferGeometry
      if (cell.shape === 'Rect') {
        geo = new THREE.BoxGeometry(CELL_W, FLOOR_H, CELL_W)
      } else {
        geo = triangleGeometry(CELL_W, FLOOR_H)
        if (cell.rotY > 0) geo.rotateY(TRI_ROT_Y)
      }
      geo.translate(x, yC, z)
      innerGeos.push(geo)
    }

    // 2) 幕墙段（整片玻璃 + 楼层带 + 分隔框）
    const segs = segmentsForFloor(floor.cells)
    segs.forEach((seg, idx) => {
      const { bands, glass } = panelGeometries(seg, yC)
      bandGeos.push(...bands)
      outlineGeos.push(...bands)
      const bucket = hashStr(`${floor.level}-${idx}`) % 3
      glassBuckets[bucket].push(glass)
      mullionGeos.push(...mullionGeometries(seg, yC))
    })

    // 3) 屋顶板（仅顶层，覆盖格子顶面的分缝）
    if (floor.level === FLOOR_COUNT) {
      for (const cell of floor.cells) {
        const { x, z } = cellCenter(cell.row, cell.col)
        const g = new THREE.BoxGeometry(CELL_W, 0.03, CELL_W)
        g.translate(x, ROOF_Y + 0.015, z)
        roofGeos.push(g)
        outlineGeos.push(g)
      }
    }
  }

  // 合并 & 建网格（源几何在最后统一释放）
  const innerMesh = new THREE.Mesh(mergeCompat(innerGeos), innerMat)
  innerMesh.castShadow = true
  innerMesh.receiveShadow = true
  group.add(innerMesh)
  disposables.push(innerMesh.geometry)

  const bandMesh = new THREE.Mesh(mergeCompat(bandGeos), spandrelMat)
  bandMesh.castShadow = true
  bandMesh.receiveShadow = true
  group.add(bandMesh)
  disposables.push(bandMesh.geometry)

  mullionMesh = new THREE.Mesh(mergeCompat(mullionGeos), mullionMat)
  mullionMesh.castShadow = true
  group.add(mullionMesh)
  disposables.push(mullionMesh.geometry)

  const roofMesh = new THREE.Mesh(mergeCompat(roofGeos), roofMat)
  roofMesh.castShadow = true
  roofMesh.receiveShadow = true
  group.add(roofMesh)
  disposables.push(roofMesh.geometry)

  glassBuckets.forEach((geos, i) => {
    if (!geos.length) return
    const mesh = new THREE.Mesh(mergeCompat(geos), glassMats[i])
    mesh.renderOrder = 10
    group.add(mesh)
    disposables.push(mesh.geometry)
  })

  // 核心筒（与原 Building3D 的 Visual core 完全一致）
  const coreGeo = new THREE.BoxGeometry(CORE_W, CORE_H, CORE_W)
  const core = new THREE.Mesh(coreGeo, coreMat)
  core.position.copy(CORE_POS)
  core.castShadow = true
  core.receiveShadow = true
  group.add(core)
  disposables.push(coreGeo)
  const coreOutlineGeo = coreGeo.clone().translate(CORE_POS.x, CORE_POS.y, CORE_POS.z)
  outlineGeos.push(coreOutlineGeo)

  // BIM 线框（bim-viewer outline 风格：体块边线）
  const lineGeos: THREE.BufferGeometry[] = []
  for (const g of outlineGeos) {
    lineGeos.push(new THREE.EdgesGeometry(g, 15))
  }
  const mergedEdges = mergeCompat(lineGeos)
  const lineMat = new THREE.LineBasicMaterial({ color: 0x263241, transparent: true, opacity: 0.7 })
  outlineLines = new THREE.LineSegments(mergedEdges, lineMat)
  outlineLines.visible = showOutline.value
  group.add(outlineLines)
  disposables.push(mergedEdges, lineMat)

  // 统一释放源几何（数据已拷贝进 merge/Edges 结果，不再需要）
  const sourceGeos = [
    ...innerGeos,
    ...bandGeos,
    ...mullionGeos,
    ...roofGeos,
    ...glassBuckets.flat(),
    ...lineGeos,
    coreOutlineGeo,
  ]
  for (const g of sourceGeos) g.dispose()

  return group
}

/** 地面（与原 Building3D 的圆形地面一致 + 广场装饰环） */
function buildGround(): THREE.Group {
  const group = new THREE.Group()
  const groundGeo = new THREE.CircleGeometry(32, 64)
  const groundMat = new THREE.MeshStandardMaterial({ color: 0xe8e4dc, roughness: 0.95 })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.05
  ground.receiveShadow = true
  group.add(ground)
  disposables.push(groundGeo, groundMat)

  // 广场铺装环（仅地面装饰，不影响建筑轮廓）
  const ringSpecs: Array<[number, number, number]> = [
    [10.4, 11.0, 0xdcd7cb],
    [11.15, 11.23, 0xd0cabd],
    [12.4, 12.52, 0xdcd7cb],
  ]
  for (const [r0, r1, color] of ringSpecs) {
    const geo = new THREE.RingGeometry(r0, r1, 96)
    const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.95 })
    const ring = new THREE.Mesh(geo, mat)
    ring.rotation.x = -Math.PI / 2
    ring.position.y = -0.048
    ring.receiveShadow = true
    group.add(ring)
    disposables.push(geo, mat)
  }
  return group
}

// ---- 楼层悬停 & LOGO ----

/** 某层所有格子在 XZ 平面上的外包范围（含半格边），用于命中盒与高亮 */
function floorFootprint(level: number): { minX: number; maxX: number; minZ: number; maxZ: number } {
  const floor = FLOORS.find((f) => f.level === level)
  let minX = Infinity
  let maxX = -Infinity
  let minZ = Infinity
  let maxZ = -Infinity
  if (!floor) return { minX: 0, maxX: 0, minZ: 0, maxZ: 0 }
  for (const c of floor.cells) {
    const { x, z } = cellCenter(c.row, c.col)
    minX = Math.min(minX, x - HALF)
    maxX = Math.max(maxX, x + HALF)
    minZ = Math.min(minZ, z - HALF)
    maxZ = Math.max(maxZ, z + HALF)
  }
  return { minX, maxX, minZ, maxZ }
}

/** 为每个楼层建一个不可见命中盒（raycast 判定落在哪一层；最高层贴屋顶） */
function buildFloorHits() {
  floorHits = []
  for (let level = 1; level <= FLOOR_COUNT; level++) {
    const { minX, maxX, minZ, maxZ } = floorFootprint(level)
    const y0 = (level - 1) * SLAB
    const y1 = level === FLOOR_COUNT ? ROOF_Y : level * SLAB
    const geo = new THREE.BoxGeometry(maxX - minX, y1 - y0, maxZ - minZ)
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ visible: false }))
    mesh.position.set((minX + maxX) / 2, (y0 + y1) / 2, (minZ + maxZ) / 2)
    mesh.userData.floor = level
    mesh.visible = false
    floorHits.push(mesh)
    disposables.push(geo, mesh.material as THREE.Material)
  }
}

/** 悬停高亮盒：盖住被悬停楼层，半透明金色（与 /building-viewer 的悬停效果一致） */
function buildHoverHighlight() {
  hoverHighlightMat = new THREE.MeshBasicMaterial({
    color: 0xc4a574,
    transparent: true,
    opacity: 0.22,
    depthWrite: false,
  })
  const geo = new THREE.BoxGeometry(1, 1, 1)
  hoverHighlight = new THREE.Mesh(geo, hoverHighlightMat)
  hoverHighlight.visible = false
  hoverHighlight.renderOrder = 20
  disposables.push(geo, hoverHighlightMat)
}

/** 更新高亮盒：匹配悬停楼层的外包轮廓 */
function updateHoverHighlight(floor: number | null) {
  if (!hoverHighlight) return
  if (floor == null) {
    hoverHighlight.visible = false
    return
  }
  const { minX, maxX, minZ, maxZ } = floorFootprint(floor)
  const y0 = (floor - 1) * SLAB
  const y1 = floor === FLOOR_COUNT ? ROOF_Y : floor * SLAB
  hoverHighlight.position.set((minX + maxX) / 2, (y0 + y1) / 2, (minZ + maxZ) / 2)
  hoverHighlight.scale.set(maxX - minX, y1 - y0, maxZ - minZ)
  hoverHighlight.visible = true
}

/**
 * 在 1F/2F 的东南切角斜面上放置 LOGO（frontend/public/wingon-logo.png）。
 *
 * 东南角不是直角而是一个连续切角：快照中 (7,12) 缺格，(7,11) 与 (6,12)
 * 是两个 A 朝向三角形，两条斜边共线（外法线朝东南 45°），形成从南墙东端
 * (4.623, 3.427) 到东墙南端 (6.877, 1.173) 的一整条斜面。
 * LOGO 平面贴合该斜面，跨 1F+2F 两层高度。
 */
function buildLogo() {
  // 1F（level 4，P1 布局）的 A 朝向三角形 = 东南切角
  const floor = FLOORS.find((f) => f.level === 4)!
  const tris = floor.cells.filter((c) => c.shape === 'Triangle' && c.rotY === 0)
  // A 三角形斜边端点：西南 (x-h, z+h)、东北 (x+h, z-h)；取整体切角的西南/东北端
  let swX = Infinity
  let swZ = 0
  let neX = -Infinity
  let neZ = 0
  for (const t of tris) {
    const { x, z } = cellCenter(t.row, t.col)
    if (x - HALF < swX) {
      swX = x - HALF
      swZ = z + HALF
    }
    if (x + HALF > neX) {
      neX = x + HALF
      neZ = z - HALF
    }
  }
  // 斜边方向（西南→东北）与外法线（东南 45°）
  const dx = neX - swX
  const dz = neZ - swZ
  const len = Math.hypot(dx, dz)
  const sx = dx / len
  const sz = dz / len
  const nx = -sz
  const nz = sx
  // LOGO 中心沿斜边取用户指定区域中心（约 56% 处），法向外凸超过幕墙板与竖框
  const u = len * 0.56
  const proud = PROUD + (MULLION_D / 2 - 0.018) + MULLION_D / 2 + 0.008 // ≈0.077
  const cx = swX + u * sx + proud * nx
  const cz = swZ + u * sz + proud * nz
  // 高度精确覆盖 1F+2F 两层（含层缝 2×SLAB），宽按图片比例 289/267 保持不变形
  const L1F = 4
  const y0 = (L1F - 1) * SLAB // 1F 底
  const y1 = L1F * SLAB + SLAB // 2F 顶
  const yCenter = (y0 + y1) / 2
  const h = y1 - y0
  const w = h * (289 / 267)

  const tex = new THREE.TextureLoader().load('/wingon-logo.png')
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, depthWrite: false })
  const logo = new THREE.Mesh(new THREE.PlaneGeometry(w, h), mat)
  logo.position.set(cx, yCenter, cz)
  // 平面默认法线 +Z，绕 Y 旋转使法线朝 (nx, nz) = (0.707, 0.707)，即贴合切角斜面
  logo.rotation.y = Math.atan2(nx, nz)
  logo.renderOrder = 21
  disposables.push(tex, mat, logo.geometry as THREE.BufferGeometry)
  return logo
}

/** 楼层名用于提示（bim-viewer 风格：如 G/F、1/F、2/F） */
function floorLabel(level: number): string {
  const n = floorName(level)
  if (level === FLOOR_COUNT) return 'ROOF'
  return `${n}/F`
}

function updatePointer(ev: PointerEvent) {
  if (!host.value) return
  const rect = host.value.getBoundingClientRect()
  pointer.x = ((ev.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((ev.clientY - rect.top) / rect.height) * 2 + 1
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
  // 拖拽中（orbit/pan）不更新悬停，避免误触发
  if (ev.buttons !== 0) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(floorHits, false)
  if (hits.length) {
    const floor = hits[0].object.userData.floor as number
    if (hoveredFloor.value !== floor) {
      hoveredFloor.value = floor
      updateHoverHighlight(floor)
    }
    toastVisible.value = true
    placeToast(ev.clientX, ev.clientY, host.value.getBoundingClientRect())
    host.value.style.cursor = 'pointer'
  } else {
    clearHover()
  }

  // 调试信息：射线与真实墙体相交（排除楼层命中盒/高亮盒/LOGO），转回建筑局部坐标判断面
  if (buildingGroup) {
    const wallRoot = buildingGroup.children[0]
    const buildHits = wallRoot ? raycaster.intersectObject(wallRoot, true) : []
    if (buildHits.length) {
      const hit = buildHits[0]
      // 建筑会自动旋转：命中点/法线先转回建筑局部坐标，方便对照快照格子
      const inv = buildingGroup.matrixWorld.clone().invert()
      const local = hit.point.clone().applyMatrix4(inv)
      const wn = (hit.face?.normal ?? new THREE.Vector3())
        .clone()
        .transformDirection(hit.object.matrixWorld)
        .transformDirection(inv)
      let face = 'unknown'
      const ax = Math.abs(wn.x)
      const az = Math.abs(wn.z)
      if (ax > 0.45 && az > 0.45) {
        face = '斜面 (切角)'
      } else if (ax > az) {
        face = wn.x > 0 ? '东面 (+X)' : '西面 (-X)'
      } else {
        face = wn.z > 0 ? '南面 (+Z)' : '北面 (-Z)'
      }
      const level = Math.floor(local.y / SLAB) + 1
      const fName = floorName(level)
      debugInfo.value = `面: ${face}\n坐标: x=${local.x.toFixed(2)}, z=${local.z.toFixed(2)}\n高度: y=${local.y.toFixed(2)} (约${fName})\n法线: (${wn.x.toFixed(2)}, ${wn.z.toFixed(2)})`
      debugVisible.value = true
    } else {
      debugVisible.value = false
    }
  }
}

function clearHover() {
  hoveredFloor.value = null
  toastVisible.value = false
  updateHoverHighlight(null)
  debugVisible.value = false
  if (host.value) host.value.style.cursor = 'grab'
}

function onPointerLeave() {
  clearHover()
}

// ---- 预设应用 ----

function applyPreset(name: 'day' | 'dusk' | 'night') {
  if (!scene || !dirLight || !hemiLight || !fillLight || !innerMat) return
  const p = PRESETS[name]
  dirLight.color.setHex(p.dirColor)
  dirLight.intensity = p.dirIntensity
  dirLight.position.set(...p.dirPos)
  hemiLight.color.setHex(p.hemiSky)
  hemiLight.groundColor.setHex(p.hemiGround)
  hemiLight.intensity = p.hemiIntensity
  fillLight.color.setHex(name === 'night' ? 0x2c3a55 : 0xc4a574)
  fillLight.intensity = name === 'night' ? 0.12 : 0.35
  scene.background = skyTextureFor(p)
  scene.backgroundIntensity = p.bgIntensity
  scene.fog = new THREE.Fog(new THREE.Color(p.fog).getHex(), 45, 140)
  scene.environmentIntensity = p.envIntensity
  innerMat.emissiveIntensity = p.innerLight
  glassOpacity.value = p.glassOpacity
}

// ---- 初始化 ----

function initThreeJS() {
  if (!host.value || scene) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight

  scene = new THREE.Scene()

  camera = new THREE.PerspectiveCamera(42, w / Math.max(1, h), 0.1, 400)
  camera.position.set(18, 13, 22)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(w, h, false)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  host.value.appendChild(renderer.domElement)

  // 环境反射（幕墙玻璃的反射来源）
  pmrem = new THREE.PMREMGenerator(renderer)
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture
  scene.environment = envTex
  disposables.push(envTex)

  // 灯光（结构与原 Building3D 一致：半球光 + 主平行光 + 补光）
  hemiLight = new THREE.HemisphereLight(0xffffff, 0xb0a090, 0.75)
  scene.add(hemiLight)
  dirLight = new THREE.DirectionalLight(0xfff5e6, 1.05)
  dirLight.position.set(18, 55, 12)
  dirLight.castShadow = true
  dirLight.shadow.mapSize.set(2048, 2048)
  dirLight.shadow.camera.left = -16
  dirLight.shadow.camera.right = 16
  dirLight.shadow.camera.top = 16
  dirLight.shadow.camera.bottom = -10
  dirLight.shadow.camera.near = 1
  dirLight.shadow.camera.far = 90
  dirLight.shadow.bias = -0.0004
  scene.add(dirLight)
  fillLight = new THREE.DirectionalLight(0xc4a574, 0.35)
  fillLight.position.set(-20, 16, -10)
  scene.add(fillLight)

  // 建筑 + 地面
  buildingGroup = new THREE.Group()
  buildingGroup.add(buildBuilding())
  buildingGroup.add(buildGround())
  buildFloorHits()
  buildHoverHighlight()
  for (const h of floorHits) buildingGroup.add(h)
  buildingGroup.add(hoverHighlight!)
  buildingGroup.add(buildLogo())
  scene.add(buildingGroup)

  // 拾取
  raycaster = new THREE.Raycaster()

  // 控制器（参数与原 Building3D 一致）
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, (FLOOR_COUNT * SLAB) / 2, 0)
  controls.maxPolarAngle = Math.PI * 0.48
  controls.minDistance = 8
  controls.maxDistance = 60

  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', onPointerLeave)

  applyPreset(preset.value)
  animate()
}

function animate() {
  animId = requestAnimationFrame(animate)
  if (buildingGroup && autoRotate.value) {
    buildingGroup.rotation.y += 0.004 * rotateSpeed.value
  }
  controls?.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

function onResize() {
  if (!host.value || !camera || !renderer) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight
  camera.aspect = w / Math.max(1, h)
  camera.updateProjectionMatrix()
  renderer.setSize(w, h, false)
}

function resetView() {
  if (!camera || !controls) return
  camera.position.set(18, 13, 22)
  controls.target.set(0, (FLOOR_COUNT * SLAB) / 2, 0)
  controls.update()
}

// ---- 控件联动 ----

watch(preset, (v) => applyPreset(v))

watch(glassOpacity, (v) => {
  for (const m of glassMats) m.opacity = v
})

watch(showMullions, (v) => {
  if (mullionMesh) mullionMesh.visible = v
})

watch(showOutline, (v) => {
  if (outlineLines) outlineLines.visible = v
})

onMounted(() => {
  if (!host.value) return
  initThreeJS()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animId)
  clearHover()
  window.removeEventListener('resize', onResize)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  controls?.dispose()
  pmrem?.dispose()
  renderer?.dispose()
  if (renderer?.domElement.parentElement) {
    renderer.domElement.parentElement.removeChild(renderer.domElement)
  }
  for (const d of disposables) d.dispose()
  disposables.length = 0
  skyTextures.clear()
  scene = null
  camera = null
  renderer = null
  controls = null
  buildingGroup = null
  pmrem = null
  raycaster = null
  glassMats = []
  innerMat = null
  mullionMesh = null
  outlineLines = null
  floorHits = []
  hoverHighlight = null
  hoverHighlightMat = null
})
</script>

<template>
  <div ref="host" class="facade3d">
    <!-- 控制面板 -->
    <div class="ctrl-panel">
      <div class="ctrl-title">幕墙外观 DEMO</div>
      <div class="ctrl-row">
        <label class="ctrl-label">场景</label>
        <div class="seg-group">
          <button
            v-for="p in (['day', 'dusk', 'night'] as const)"
            :key="p"
            class="seg-btn"
            :class="{ active: preset === p }"
            @click="preset = p"
          >
            {{ p === 'day' ? '日间' : p === 'dusk' ? '黄昏' : '夜间' }}
          </button>
        </div>
      </div>
      <div class="ctrl-row">
        <label class="ctrl-label">玻璃透明度</label>
        <input
          v-model.number="glassOpacity"
          class="ctrl-slider"
          type="range"
          min="0.2"
          max="0.95"
          step="0.05"
        />
        <span class="ctrl-value">{{ glassOpacity.toFixed(2) }}</span>
      </div>
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" :class="{ on: showMullions }" @click="showMullions = !showMullions">
          {{ showMullions ? '隐藏竖框' : '显示竖框' }}
        </button>
        <button type="button" class="ctrl-btn" :class="{ on: showOutline }" @click="showOutline = !showOutline">
          {{ showOutline ? '关闭线框' : 'BIM 线框' }}
        </button>
      </div>
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" :class="{ on: autoRotate }" @click="autoRotate = !autoRotate">
          {{ autoRotate ? '暂停旋转' : '自动旋转' }}
        </button>
        <button type="button" class="ctrl-btn" @click="resetView">复位视角</button>
      </div>
      <div v-if="autoRotate" class="ctrl-row">
        <label class="ctrl-label">旋转速度</label>
        <input
          v-model.number="rotateSpeed"
          class="ctrl-slider"
          type="range"
          min="0.5"
          max="4"
          step="0.5"
        />
        <span class="ctrl-value">{{ rotateSpeed.toFixed(1) }}×</span>
      </div>
    </div>
    <!-- 左上角信息 -->
    <div class="info-badge">
      轮廓 1:1 还原自 /building-viewer（building_cell 快照）· 幕墙为 DEMO 美化层
    </div>
    <!-- 楼层悬停提示 -->
    <div
      v-show="toastVisible && hoveredFloor != null"
      class="floor-toast"
      :style="toastStyle"
    >
      <div class="toast-level">{{ floorLabel(hoveredFloor ?? 0) }}</div>
    </div>
    <!-- 调试提示 -->
    <div
      v-show="debugVisible"
      class="debug-tooltip"
    >
      <pre>{{ debugInfo }}</pre>
    </div>
  </div>
</template>

<style scoped>
.facade3d {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 320px;
  overflow: hidden;
  background: #e9e5dc;
  cursor: grab;
}

.facade3d:active {
  cursor: grabbing;
}

.facade3d :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}

.ctrl-panel {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
  width: 252px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(13, 13, 13, 0.88);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(8px);
  color: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  user-select: none;
}

.ctrl-title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 650;
  color: #f5ead7;
}

.ctrl-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.ctrl-row:last-child {
  margin-bottom: 0;
}

.ctrl-label {
  flex: 0 0 70px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.78);
}

.ctrl-slider {
  flex: 1;
  min-width: 0;
  accent-color: #c4a574;
}

.ctrl-value {
  flex: 0 0 38px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  text-align: right;
}

.seg-group {
  display: flex;
  flex: 1;
  gap: 4px;
}

.seg-btn {
  flex: 1;
  padding: 4px 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.seg-btn.active {
  color: #0d0d0d;
  background: #c4a574;
  border-color: #c4a574;
  font-weight: 600;
}

.ctrl-btn {
  flex: 1;
  padding: 5px 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ctrl-btn.on {
  color: #f5ead7;
  background: rgba(196, 165, 116, 0.28);
  border-color: rgba(196, 165, 116, 0.6);
}

.ctrl-btn:hover,
.seg-btn:hover {
  background: rgba(255, 255, 255, 0.16);
}

.info-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  padding: 6px 12px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.92);
  background: rgba(13, 13, 13, 0.62);
  border: 1px solid rgba(196, 165, 116, 0.35);
  border-radius: 4px;
  backdrop-filter: blur(6px);
  pointer-events: none;
}

/* 楼层悬停提示（参照 /building-viewer 的 .floor-toast） */
.floor-toast {
  position: absolute;
  z-index: 5;
  pointer-events: none;
  min-width: 132px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(13, 13, 13, 0.66);
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

/* 调试提示 */
.debug-tooltip {
  position: absolute;
  bottom: 12px;
  left: 12px;
  z-index: 20;
  padding: 10px 14px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.85);
  border: 1px solid #c4a574;
  color: #fff;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
  pointer-events: none;
  white-space: pre;
}
</style>
