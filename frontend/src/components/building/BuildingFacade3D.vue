<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
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
} from '@/utils/facadeSnapshot'
import { getFacadeConfig, saveFacadeConfig, type FacadeConfig } from '../../api/facade'
import { getFloorEnvironmentSummary } from '../../api/environment'
import {
  INTERIOR_CELLS,
  cellToWorld,
  shouldExcludeCell,
} from '../../utils/buildingDemo'
import {
  listBuildingCellShapes,
  listBuildingFloors,
  updateCellRotation,
  cellEdit,
  undoEdit,
} from '../../api/building'
import {
  createGeometryByType,
  isHiddenType,
  parseRotation,
  type CellShapeConfig,
  type GridType,
} from '../../utils/floorGrid'
import {
  envColorFor,
  envRange,
  TEMPERATURE_BAND_COLORS,
  TEMPERATURE_GRADIENT_STOPS,
  TEMPERATURE_TICKS,
  type EnvMetric,
  type FloorEnvValue,
} from '../../utils/envColor'

const { t } = useI18n()

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
/**
 * 地下层下沉量：G/F（3D level 3）对齐地面 y=0，B2/B1 为负楼层。
 * 所有楼层 Y 统一加该偏移（B2 底 ≈ -1.68、B1 底 ≈ -0.84、G 底 = 0）。
 */
const UNDERGROUND_OFFSET = -2 * SLAB
/** 幕墙外表面外凸量（防 z-fighting，视觉可忽略） */
const PROUD = 0.012
/** 竖向分隔框截面深（LOGO 定位用） */
const MULLION_D = 0.075
/** 核心筒尺寸/位置（与原 Building3D 的 Visual core 一致） */
const CORE_W = CELL_SIZE * 1.6
const CORE_H = FLOOR_COUNT * SLAB
const CORE_POS = new THREE.Vector3(
  CELL_SIZE * 2,
  CORE_H / 2 - FLOOR_GAP / 2 + UNDERGROUND_OFFSET,
  CELL_SIZE * 1,
)
/** 建筑总高（不含核心筒凸出），G/F 对齐地面 y=0 起算 */
const ROOF_Y = (FLOOR_COUNT - 3) * SLAB + FLOOR_H

// ---- 父组件接口（与 /building-viewer 的 Building3D 对齐：选中楼层 / 着色指标 / 加载态 / 编辑数据） ----
const props = defineProps<{
  /** 当前选中的 3D 楼层（1..11），用于高亮显示 */
  selectedFloor?: number | null
  /** 外部着色指标（温度/湿度）；控制面板内部按钮亦会同步回传 */
  metric?: EnvMetric
  /** 数据加载完成前不初始化 3D */
  loading?: boolean
  /** 编辑模式用的格子设置（building_cell，DB 驱动） */
  cellShapes?: CellShapeConfig[]
  /** 楼栋 ID（用于添加/删除/撤回格子） */
  buildingId?: number
}>()

const emit = defineEmits<{
  selectFloor: [floor: number]
  'update:metric': [v: EnvMetric]
  refreshShapes: []
}>()

// ---- 控件状态 ----
/** 默认不自动旋转；需要时由控制面板手动开启（大屏模式不再默认旋转） */
const autoRotate = ref(false)
/** 控制面板显示状态（左上角提示文字连点 3 次弹出/收起） */
const panelVisible = ref(false)
const rotateSpeed = ref(1)
const glassOpacity = ref(0.55)
const showOutline = ref(false)
const preset = ref<'day' | 'dusk' | 'night'>('day')
/** 自动场景：按本地实时日出/日落时间自动切换 日间/黄昏/夜间；关闭时回到日间 */
const autoPreset = ref(false)
/** 自动场景检测定时器 */
let autoSceneTimer: ReturnType<typeof setInterval> | undefined
/** 楼宇位置（永安貨倉大廈，香港）用于日出日落计算 */
const SUN_LAT = 22.3
const SUN_LNG = 114.2
/** 黄昏窗口：日落前后各 1 小时 */
const DUSK_WINDOW_H = 1

// ---- 幕墙窗户配置 ----
const windowOrientation = ref<'vertical' | 'horizontal'>('vertical')
const windowWidthRatio = ref(0.4)
const windowHeightRatio = ref(0.7)
const cellWindows = ref<Record<string, boolean>>({})
const showFloorLines = ref(true)
const showColLines = ref(false)
/** 原始状态：建筑渲成独立格子体块（绿/灰分层、带格缝），复刻 /building-viewer 外观 */
const rawMode = ref(false)
/** 原始状态下按温湿度着色的指标 */
const metric = ref<EnvMetric>('temperature')
/** 各楼层温湿度（level 为 3D 层号 1..11） */
const floorEnv = ref<Record<number, FloorEnvValue>>({})
/** 是否允许点击墙面创建窗户 */
const cellClickEnabled = ref(false)
const windowMeshes: THREE.Mesh[] = []
let windowGlassMat: THREE.MeshPhysicalMaterial | null = null
let windowFrameMat: THREE.MeshStandardMaterial | null = null

// ---- 楼层悬停状态 ----（参照 /building-viewer 行为）
const hoveredFloor = ref<number | null>(null)
const toastVisible = ref(false)
const toastStyle = ref<Record<string, string>>({ left: '0px', top: '0px' })

// ---- 调试提示（由控制面板「调试信息」开关控制）----
const debugEnabled = ref(false)
const debugInfo = ref<string>('')
const debugVisible = ref(false)

// ---- 格子编辑模式（整合自 /building-viewer 的 Building3D 编辑面板，入口放入控制面板）----
const editUnlocked = ref(false)
const editDirty = ref(false)
const confirmOpen = ref(false)
const UNDO_LIMIT = 10
const undoableOps = ref(0)
const snapshotShapes = ref<CellShapeConfig[]>([])
const editToolMode = ref<'none' | 'add' | 'delete'>('none')
const editFeedback = ref('')
let feedbackTimer: ReturnType<typeof setTimeout> | undefined
const editModeToast = ref(false)
let editModeToastTimer: ReturnType<typeof setTimeout> | undefined
/** 进入编辑模式前的外观状态（退出时恢复） */
const prevRawMode = ref(false)

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
let innerMat: THREE.MeshStandardMaterial | null = null
let outlineLines: THREE.LineSegments | null = null
let logoMesh: THREE.Mesh | null = null
/** 美化状态各楼层 inner 材质（按温湿度着色；夜间预设需逐层调整 emissiveIntensity） */
let floorInnerMats: THREE.MeshStandardMaterial[] = []

// 拾取/悬停句柄
let raycaster: THREE.Raycaster | null = null
let pointer = new THREE.Vector2()
/** 每个楼层一个不可见的命中盒（用于 raycast 判定落在哪一层） */
let floorHits: THREE.Mesh[] = []
/** 悬停高亮盒 */
let hoverHighlight: THREE.Mesh | null = null
let hoverHighlightMat: THREE.MeshBasicMaterial | null = null
/** 选中楼层高亮盒 */
let selectedHighlight: THREE.Mesh | null = null
let selectedHighlightMat: THREE.MeshBasicMaterial | null = null
/** 按楼层分组的建筑 mesh（用于悬停凸出动画） */
let floorGroups: THREE.Group[] = []
/** 当前凸出目标楼层（0 = 无） */
let hoverScaleFloor = 0

// ---- 编辑模式拾取/渲染句柄（与 Building3D 一致） ----
/** 编辑模式下所有可拾取的格子 mesh */
let floorMeshes: THREE.Mesh[] = []
/** floor number -> meshes */
const meshesByFloor = new Map<number, THREE.Mesh[]>()
/** 编辑模式下隐藏格子（is_active=0）的占位组 */
let hiddenCellGroup: THREE.Group | null = null
let hiddenCellMaterials: THREE.Material[] = []
let hiddenCellGeos: THREE.BufferGeometry[] = []
let hiddenCellMeshes: THREE.Mesh[] = []
/** 拖拽模板组（添加模式：楼宇旁的圆/方/三角） */
let dragSourceGroup: THREE.Group | null = null
let dragSourceMeshes: THREE.Mesh[] = []
let dragPreviewMesh: THREE.Mesh | null = null
let dragPreviewMat: THREE.MeshStandardMaterial | null = null
let activeDragSource: THREE.Mesh | null = null
let dragTarget: { row: number; col: number; floor3d: number; exists: boolean; shape: 'Rect' | 'Cylinder' | 'Triangle' } | null = null
let prevAutoRotate = true
const DRAG_SHAPES: Array<'Rect' | 'Cylinder' | 'Triangle'> = ['Cylinder', 'Rect', 'Triangle']
const DRAG_SOURCE_COLOR = 0x5fb8b8
let dragRotationDeg = 0
/** 编辑模式使用的几何集合（含 createGeometryByType 的共享缓存，重建时不得 dispose） */
let editGeos = new Set<THREE.BufferGeometry>()
/** 编辑模式每层 Rect 复用的 BoxGeometry（每次新建，下次编辑前释放） */
let lastEditCellGeo: THREE.BufferGeometry | null = null

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
    dirColor: 0xffe8c8,
    dirIntensity: 1.05,
    dirPos: [18, 55, 12],
    hemiSky: 0xc8d8f0,
    hemiGround: 0xa08870,
    hemiIntensity: 0.65,
    fog: '#c8d4e0',
    sky: ['#5b8ab8', '#d8cfc0'],
    innerLight: 0,
    envIntensity: 0.85,
    glassOpacity: 0.72,
    bgIntensity: 0.92,
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
 * 顶层（ROOF 层）的外轮廓点（XZ 平面）。
 *
 * 方法：枚举每个顶层格子的暴露边（四邻缺格/出界），按"共线相邻段合并"
 * 消除格子分缝造成的小断点，再以有向边首尾相接闭合出轮廓环。
 * 结果精确贴合幕墙外边缘，含 P3 布局西南/东南角的阶梯缺角。
 */
function topFloorOutline(): THREE.Vector2[] {
  const floor = FLOORS.find((f) => f.level === FLOOR_COUNT)
  if (!floor) return []
  const cells = new Set(floor.cells.map((c) => `${c.row},${c.col}`))
  const has = (r: number, c: number) => cells.has(`${r},${c}`)

  // 暴露边（在格子中心坐标体系下）：dir=方向, line=固定坐标线, from/to=沿线的起止
  interface RawEdge { dir: 'N' | 'S' | 'E' | 'W'; line: number; from: number; to: number }
  const raw: RawEdge[] = []
  for (const cell of floor.cells) {
    const { x, z } = cellCenter(cell.row, cell.col)
    if (!has(cell.row - 1, cell.col)) raw.push({ dir: 'N', line: z - HALF, from: x - HALF, to: x + HALF })
    if (!has(cell.row + 1, cell.col)) raw.push({ dir: 'S', line: z + HALF, from: x - HALF, to: x + HALF })
    if (!has(cell.row, cell.col - 1)) raw.push({ dir: 'W', line: x - HALF, from: z - HALF, to: z + HALF })
    if (!has(cell.row, cell.col + 1)) raw.push({ dir: 'E', line: x + HALF, from: z - HALF, to: z + HALF })
  }

  // 共线相邻段合并（跨格子缝隙，容忍 4% 格缝）
  const GAP_TOL = 0.05
  const groups = new Map<string, RawEdge[]>()
  for (const e of raw) {
    const key = `${e.dir}|${e.line.toFixed(4)}`
    const arr = groups.get(key) ?? []
    arr.push(e)
    groups.set(key, arr)
  }
  const merged: RawEdge[] = []
  for (const arr of groups.values()) {
    arr.sort((a, b) => a.from - b.from)
    let cur: RawEdge = { ...arr[0] }
    for (let i = 1; i < arr.length; i++) {
      if (arr[i].from - cur.to < GAP_TOL) {
        cur.to = Math.max(cur.to, arr[i].to)
      } else {
        merged.push(cur)
        cur = { ...arr[i] }
      }
    }
    merged.push(cur)
  }

  // 生成有向边（俯视逆时针闭合：北西→东、东西→南、南东→西、西南→北）
  interface Edge { bx: number; bz: number; ex: number; ez: number }
  const edges: Edge[] = []
  for (const m of merged) {
    if (m.dir === 'N') edges.push({ bx: m.from, bz: m.line, ex: m.to, ez: m.line })
    else if (m.dir === 'E') edges.push({ bx: m.line, bz: m.from, ex: m.line, ez: m.to })
    else if (m.dir === 'S') edges.push({ bx: m.to, bz: m.line, ex: m.from, ez: m.line })
    else edges.push({ bx: m.line, bz: m.to, ex: m.line, ez: m.from })
  }

  const nextMap = new Map<string, Edge>()
  for (const e of edges) nextMap.set(`${e.bx.toFixed(4)},${e.bz.toFixed(4)}`, e)

  // 追踪闭合环；阶梯缺角处（两段暴露边端点错位 <0.08）就近连接
  const pts: THREE.Vector2[] = []
  const startKey = `${edges[0].bx.toFixed(4)},${edges[0].bz.toFixed(4)}`
  let cur = edges[0]
  for (let i = 0; i <= edges.length; i++) {
    pts.push(new THREE.Vector2(cur.bx, cur.bz))
    const key = `${cur.ex.toFixed(4)},${cur.ez.toFixed(4)}`
    if (key === startKey) break
    let nxt = nextMap.get(key)
    if (!nxt) {
      let best: Edge | undefined = undefined
      let bestD = 0.08
      for (const e of edges) {
        const d = Math.hypot(e.bx - cur.ex, e.bz - cur.ez)
        if (d < bestD) {
          bestD = d
          best = e
        }
      }
      nxt = best
    }
    if (!nxt) break
    cur = nxt
  }
  return pts
}

/**
 * 计算某层的全部外墙段（连续外露面合并成整片，跨格子缝隙）。
 *
 * 外露判定（与原轮廓严格对应）：
 *  - 矩形格子的正交面：邻居缺失（缺格/出界）或邻居是三角形（三角形只占半格）
 *  - 三角形格子：不生成正交面（其正交面均被邻居遮挡），斜边单独成段
 */function segmentsForFloor(cells: SnapCell[]): WallSeg[] {
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

/**
 * 生成单个格子的窗户（窗框 + 深色玻璃）。
 * 检查四邻是否缺失（暴露面），在每个暴露面上生成一扇竖向/横向窗户。
 */
function buildCellWindows(
  cell: SnapCell,
  level: number,
  yC: number,
  cellSet: Set<string>,
  has: (r: number, c: number) => boolean,
): { frames: THREE.BufferGeometry[]; glass: THREE.BufferGeometry[] } {
  const key = `${level},${cell.row},${cell.col}`
  if (!cellWindows.value[key]) return { frames: [], glass: [] }
  const { x, z } = cellCenter(cell.row, cell.col)

  const glassW = cellWidthRatio() * CELL_SIZE
  const glassH = cellHeightRatio() * FLOOR_H
  const frames: THREE.BufferGeometry[] = []
  const glass: THREE.BufferGeometry[] = []

  const addWindow = (
    o: number, // 0=北(-z) 1=南(+z) 2=西(-x) 3=东(+x)
    winW: number,
    winH: number,
  ) => {
    const t = 0.018
    const frameT = 0.04
    const frameD = 0.05
    const HW = CELL_SIZE / 2 // 墙体半宽（外表面 = 中心 ± HW）
    // 法线单位向量
    let nx = 0, nz = 0
    if (o === 0) nz = -1
    else if (o === 1) nz = 1
    else if (o === 2) nx = -1
    else nx = 1
    // 玻璃中心：贴墙外表面（外表面在中心+法线*HW），略凸出 PROUD
    const gx = x + nx * (HW + t / 2 - PROUD)
    const gz = z + nz * (HW + t / 2 - PROUD)
    const fx = x + nx * (HW + frameD / 2 - PROUD)
    const fz = z + nz * (HW + frameD / 2 - PROUD)
    const horiz = (o === 0 || o === 1) // 法线沿 z，窗平面沿 x

    // 玻璃（凸出墙外，成"开窗"感）
    const g = horiz
      ? new THREE.BoxGeometry(winW, winH, t)
      : new THREE.BoxGeometry(t, winH, winW)
    g.translate(gx, yC, gz)
    glass.push(g)

    // 四根窗框条（面板外缘）
    const bars: THREE.BoxGeometry[] = []
    if (horiz) {
      bars.push(new THREE.BoxGeometry(winW + frameT, frameT, frameD))
      bars.push(new THREE.BoxGeometry(winW + frameT, frameT, frameD))
      bars.push(new THREE.BoxGeometry(frameT, winH + frameT, frameD))
      bars.push(new THREE.BoxGeometry(frameT, winH + frameT, frameD))
      bars[0].translate(fx, yC + winH / 2, fz)
      bars[1].translate(fx, yC - winH / 2, fz)
      bars[2].translate(fx, yC + frameT / 2, fz)
      bars[3].translate(fx, yC - frameT / 2, fz)
    } else {
      bars.push(new THREE.BoxGeometry(frameD, frameT, winW + frameT))
      bars.push(new THREE.BoxGeometry(frameD, frameT, winW + frameT))
      bars.push(new THREE.BoxGeometry(frameD, winH + frameT, frameT))
      bars.push(new THREE.BoxGeometry(frameD, winH + frameT, frameT))
      bars[0].translate(fx, yC + winH / 2, fz)
      bars[1].translate(fx, yC - winH / 2, fz)
      bars[2].translate(fx, yC + frameT / 2, fz)
      bars[3].translate(fx, yC - frameT / 2, fz)
    }
    frames.push(...bars)
  }

  if (cell.shape === 'Rect') {
    if (!has(cell.row - 1, cell.col)) addWindow(0, glassW, glassH)
    if (!has(cell.row + 1, cell.col)) addWindow(1, glassW, glassH)
    if (!has(cell.row, cell.col - 1)) addWindow(2, glassW, glassH)
    if (!has(cell.row, cell.col + 1)) addWindow(3, glassW, glassH)
  } else {
    // 三角形：斜面 45°，在斜面上开一扇窗
    const t = 0.018
    const diagW = glassW * 1.1
    const g = new THREE.BoxGeometry(diagW, glassH, t)
    if (cell.rotY > 0) g.rotateY(-Math.PI / 4)
    else g.rotateY(Math.PI / 4)
    // 斜面外表面：沿法线（±π/4）外移，凸出墙面
    const d = CELL_SIZE / 2
    const ang = cell.rotY > 0 ? -Math.PI / 4 : Math.PI / 4
    const nx = Math.sin(ang) * -1
    const nz = Math.cos(ang)
    g.translate(x + nx * d, yC, z + nz * d)
    glass.push(g)
  }

  return { frames, glass }
}

function cellWidthRatio() {
  // 窗户占格子宽度的比例：竖向=滑块值；横向=滑块值向上取到较宽
  const v = windowOrientation.value === 'vertical' ? windowWidthRatio.value : windowWidthRatio.value * 2.2
  return Math.min(v, 0.92)
}

function cellHeightRatio() {
  // 窗户占楼层高度的比例：竖向=滑块值向上取到较高；横向=滑块值
  const v = windowOrientation.value === 'vertical' ? windowHeightRatio.value * 1.15 : windowHeightRatio.value
  return Math.min(v, 0.92)
}

/**
 * 通用楼层外轮廓（与 topFloorOutline 同源算法，适用于任意楼层布局）。
 * 返回 XZ 平面闭合多边形（逆时针），用于 ExtrudeGeometry 生成连续墙面。
 */
function computeFloorOutline(cells: SnapCell[]): THREE.Vector2[] {
  if (!cells.length) return []
  const cellSet = new Set(cells.map((c) => `${c.row},${c.col}`))
  const has = (r: number, c: number) => cellSet.has(`${r},${c}`)
  const HW = CELL_SIZE / 2

  interface RawEdge { dir: 'N' | 'S' | 'E' | 'W'; line: number; from: number; to: number }
  const raw: RawEdge[] = []
  for (const cell of cells) {
    const { x, z } = cellCenter(cell.row, cell.col)
    if (cell.shape === 'Rect') {
      if (!has(cell.row - 1, cell.col)) raw.push({ dir: 'N', line: z - HW, from: x - HW, to: x + HW })
      if (!has(cell.row + 1, cell.col)) raw.push({ dir: 'S', line: z + HW, from: x - HW, to: x + HW })
      if (!has(cell.row, cell.col - 1)) raw.push({ dir: 'W', line: x - HW, from: z - HW, to: z + HW })
      if (!has(cell.row, cell.col + 1)) raw.push({ dir: 'E', line: x + HW, from: z - HW, to: z + HW })
    } else {
      if (cell.rotY > 0) {
        if (!has(cell.row - 1, cell.col)) raw.push({ dir: 'N', line: z - HW, from: x - HW, to: x + HW })
        if (!has(cell.row, cell.col - 1)) raw.push({ dir: 'W', line: x - HW, from: z - HW, to: z + HW })
      } else {
        if (!has(cell.row + 1, cell.col)) raw.push({ dir: 'S', line: z + HW, from: x - HW, to: x + HW })
        if (!has(cell.row, cell.col - 1)) raw.push({ dir: 'W', line: x - HW, from: z - HW, to: z + HW })
      }
    }
  }

  const GAP_TOL = 0.05
  const groups = new Map<string, RawEdge[]>()
  for (const e of raw) {
    const key = `${e.dir}|${e.line.toFixed(4)}`
    const arr = groups.get(key) ?? []
    arr.push(e)
    groups.set(key, arr)
  }
  const merged: RawEdge[] = []
  for (const arr of groups.values()) {
    arr.sort((a, b) => a.from - b.from)
    let cur: RawEdge = { ...arr[0] }
    for (let i = 1; i < arr.length; i++) {
      if (arr[i].from - cur.to < GAP_TOL) {
        cur.to = Math.max(cur.to, arr[i].to)
      } else {
        merged.push(cur)
        cur = { ...arr[i] }
      }
    }
    merged.push(cur)
  }

  interface Edge { bx: number; bz: number; ex: number; ez: number }
  const edges: Edge[] = []
  for (const m of merged) {
    if (m.dir === 'N') edges.push({ bx: m.from, bz: m.line, ex: m.to, ez: m.line })
    else if (m.dir === 'E') edges.push({ bx: m.line, bz: m.from, ex: m.line, ez: m.to })
    else if (m.dir === 'S') edges.push({ bx: m.to, bz: m.line, ex: m.from, ez: m.line })
    else edges.push({ bx: m.line, bz: m.to, ex: m.line, ez: m.from })
  }

  for (const cell of cells) {
    if (cell.shape !== 'Triangle') continue
    const { x, z } = cellCenter(cell.row, cell.col)
    if (cell.rotY > 0) {
      edges.push({ bx: x - HW, bz: z + HW, ex: x + HW, ez: z - HW })
    } else {
      edges.push({ bx: x + HW, bz: z + HW, ex: x - HW, ez: z - HW })
    }
  }

  if (!edges.length) return []

  const nextMap = new Map<string, Edge>()
  for (const e of edges) nextMap.set(`${e.bx.toFixed(4)},${e.bz.toFixed(4)}`, e)

  const pts: THREE.Vector2[] = []
  const startKey = `${edges[0].bx.toFixed(4)},${edges[0].bz.toFixed(4)}`
  let cur = edges[0]
  for (let i = 0; i <= edges.length; i++) {
    pts.push(new THREE.Vector2(cur.bx, cur.bz))
    const key = `${cur.ex.toFixed(4)},${cur.ez.toFixed(4)}`
    if (key === startKey) break
    let nxt = nextMap.get(key)
    if (!nxt) {
      let best: Edge | undefined = undefined
      let bestD = 0.08
      for (const e of edges) {
        const d = Math.hypot(e.bx - cur.ex, e.bz - cur.ez)
        if (d < bestD) { bestD = d; best = e }
      }
      nxt = best
    }
    if (!nxt) break
    cur = nxt
  }
  return pts
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

// ---- 建筑构建 ----

/**
 * 原始状态：复刻 /building-viewer 的格子化建筑。
 * 每格独立 Box（CELL_W 留 4% 格缝），绿/灰按楼层交替，顶部灰色网格盖板，
 * 屋顶中央黑色核心筒，东南/西南切角保持。
 */
function buildRawBuilding(): THREE.Group {
  const group = new THREE.Group()
  const rawGeos: THREE.BufferGeometry[] = []
  const outlineGeos: THREE.BufferGeometry[] = []
  floorGroups = []
  floorInnerMats = []

  const coreMat = new THREE.MeshStandardMaterial({ color: 0x1c1c1c, roughness: 0.8, metalness: 0.2 })
  disposables.push(coreMat)

  // 温湿度范围（温度固定 0~35，湿度按数据动态）—— 与 /building-viewer 一致
  const [min, max] = envRange(floorEnv.value, metric.value)
  const FALLBACK = '#8a8f93'

  for (const floor of FLOORS) {
    const yC = floorCenterY(floor.level) + UNDERGROUND_OFFSET
    const env = floorEnv.value[floor.level]
    const value = metric.value === 'temperature' ? env?.temperature ?? null : env?.humidity ?? null
    const color = envColorFor(metric.value, value, min, max)
    const floorMat = new THREE.MeshStandardMaterial({
      color: new THREE.Color(color ?? FALLBACK),
      roughness: 0.6,
      metalness: 0.05,
      emissive: color ? new THREE.Color(color) : new THREE.Color(0x000000),
      emissiveIntensity: 0.15,    // 颜色自发光提亮（与右下图例色一致）
    })
    disposables.push(floorMat)

    let fminX = Infinity, fmaxX = -Infinity, fminZ = Infinity, fmaxZ = -Infinity
    for (const c of floor.cells) {
      const p = cellCenter(c.row, c.col)
      fminX = Math.min(fminX, p.x); fmaxX = Math.max(fmaxX, p.x)
      fminZ = Math.min(fminZ, p.z); fmaxZ = Math.max(fmaxZ, p.z)
    }
    const fcx = (fminX + fmaxX) / 2
    const fcz = (fminZ + fmaxZ) / 2
    const fcy = yC

    const localGeos: THREE.BufferGeometry[] = []
    // 原始状态格缝更明显（每格四周留 0.07 缝）
    const gsz = Math.max(0.1, CELL_W - 0.07)
    for (const cell of floor.cells) {
      const { x, z } = cellCenter(cell.row, cell.col)
      let geo: THREE.BufferGeometry
      if (cell.shape === 'Rect') {
        geo = new THREE.BoxGeometry(gsz, FLOOR_H, gsz)
      } else {
        geo = triangleGeometry(gsz, FLOOR_H)
        if (cell.rotY > 0) geo.rotateY(TRI_ROT_Y)
      }
      geo.translate(x - fcx, 0, z - fcz)
      localGeos.push(geo)
      rawGeos.push(geo)
      const absGeo = geo.clone().translate(fcx, 0, fcz)
      outlineGeos.push(absGeo)
    }

    // 独立楼层 group（保留楼层凸出缩放能力）
    const fg = new THREE.Group()
    fg.position.set(fcx, fcy, fcz)
    const fmesh = new THREE.Mesh(mergeCompat(localGeos), floorMat)
    fmesh.castShadow = true
    fmesh.receiveShadow = true
    fg.add(fmesh)
    disposables.push(fmesh.geometry)
    group.add(fg)
    floorGroups.push(fg)
  }

  // 核心筒（黑色方块，屋顶中央，与参考图一致）
  const coreGeo = new THREE.BoxGeometry(CORE_W * 0.7, CORE_H, CORE_W * 0.7)
  const core = new THREE.Mesh(coreGeo, coreMat)
  core.position.set(CELL_SIZE * 2, CORE_H / 2 + UNDERGROUND_OFFSET, CELL_SIZE * 1)
  group.add(core)
  disposables.push(coreGeo)
  outlineGeos.push(coreGeo.clone().translate(core.position.x, core.position.y, core.position.z))

  // 木色线条（BIM 线框风格，可选）
  const lineGeos: THREE.BufferGeometry[] = []
  for (const g of outlineGeos) lineGeos.push(new THREE.EdgesGeometry(g, 15))
  const mergedEdges = mergeCompat(lineGeos)
  const lineMat = new THREE.LineBasicMaterial({ color: 0x263241, transparent: true, opacity: 0.7 })
  outlineLines = new THREE.LineSegments(mergedEdges, lineMat)
  outlineLines.visible = showOutline.value
  group.add(outlineLines)
  disposables.push(mergedEdges, lineMat)

  for (const g of rawGeos) g.dispose()
  return group
}

function buildBuilding(): THREE.Group {
  // 原始状态：复刻 /building-viewer 的独立格子体块（绿/灰分层、带格缝）
  if (rawMode.value) return buildRawBuilding()
  const group = new THREE.Group()

  // 材质
  innerMat = new THREE.MeshStandardMaterial({
    color: 0x857c70,       // 深米灰墙面
    roughness: 0.9,
    metalness: 0.02,
    emissive: 0xffb46b,    // 夜间内透暖光
    emissiveIntensity: 0,
  })
  windowGlassMat = new THREE.MeshPhysicalMaterial({
    color: 0x4a6a80,       // 深灰蓝玻璃（与浅色混凝土形成对比）
    metalness: 0.25,
    roughness: 0.08,
    transparent: true,
    opacity: 0.82,
    clearcoat: 0.8,
    clearcoatRoughness: 0.06,
    envMapIntensity: 1.3,
    side: THREE.DoubleSide,
    depthWrite: false,
  })
  windowFrameMat = new THREE.MeshStandardMaterial({
    color: 0x54595f,       // 金属窗框
    roughness: 0.4,
    metalness: 0.7,
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
  disposables.push(innerMat, windowGlassMat!, windowFrameMat!, roofMat, coreMat)

  // 几何收集桶（源几何统一释放用；线框用 outlineGeos）
  const innerGeos: THREE.BufferGeometry[] = []
  const windowGeos: THREE.BufferGeometry[] = []
  const frameGeos: THREE.BufferGeometry[] = []
  const roofGeos: THREE.BufferGeometry[] = []
  const outlineGeos: THREE.BufferGeometry[] = []
  floorGroups = []
  floorInnerMats = []

  // 温湿度范围（温度固定 0~35，湿度按数据动态）——与 /building-viewer 一致
  const [rawMin, rawMax] = envRange(floorEnv.value, metric.value)
  const BASE_GRAY = 0x857c70

  for (const floor of FLOORS) {
const yC = floorCenterY(floor.level) + UNDERGROUND_OFFSET

    // 本楼层温湿度着色（美化墙面保留混凝土质感，但颜色跟随温湿度；无数据回退米灰）
    const env = floorEnv.value[floor.level]
    const value = metric.value === 'temperature' ? env?.temperature ?? null : env?.humidity ?? null
    let envColor = envColorFor(metric.value, value, rawMin, rawMax)
    // 弱化切角处连续大色块：把着色颜色向混凝土米灰靠拢（保留可辨识的温湿度倾向，但不再浓烈扎眼），
    // 并显著降低自发光，避免同色楼层在切角凹槽处连成一片刺眼的黄绿色块。
    if (envColor) {
      const c = new THREE.Color(envColor)
      const gray = new THREE.Color(BASE_GRAY)
      c.lerp(gray, 0.55)
      envColor = `#${c.getHexString()}`
    }
    const floorMat = new THREE.MeshStandardMaterial({
      color: envColor ? new THREE.Color(envColor) : new THREE.Color(BASE_GRAY),
      roughness: 0.8,
      metalness: 0.02,
      emissive: envColor ? new THREE.Color(envColor) : new THREE.Color(0x000000),
      emissiveIntensity: 0.05,    // 颜色自发光提亮（与右下图例色一致，柔和清晰）
    })
    floorInnerMats.push(floorMat)
    disposables.push(floorMat)

    // 计算本楼层中心（XZ 取格子中心范围中点，作为凸出缩放的原点）
    let fminX = Infinity, fmaxX = -Infinity, fminZ = Infinity, fmaxZ = -Infinity
    for (const c of floor.cells) {
      const p = cellCenter(c.row, c.col)
      fminX = Math.min(fminX, p.x); fmaxX = Math.max(fmaxX, p.x)
      fminZ = Math.min(fminZ, p.z); fmaxZ = Math.max(fmaxZ, p.z)
    }
    const fcx = (fminX + fmaxX) / 2
    const fcz = (fminZ + fmaxZ) / 2

    // 墙盒子中心：开启横线时留缝（用层中心 yC）；关闭时填满层缝（中心下移 FLOOR_GAP/2）。
    // 顶层恒用 FLOOR_H（顶面固定 ROOF_Y），因盖板在上，避免格子顶面与盖板 z-fighting
    const isTop = floor.level === FLOOR_COUNT
    const boxH = showFloorLines.value || isTop ? FLOOR_H : FLOOR_H + FLOOR_GAP
    const cy = showFloorLines.value || isTop ? yC : yC + FLOOR_GAP / 2
    // 竖线开关：开启时用 CELL_W（留 4% 列缝显示竖线）；关闭时用全尺寸 CELL_SIZE（无缝）
    const bw = showColLines.value ? CELL_W : CELL_SIZE

    const floorGroup = new THREE.Group()
    floorGroup.position.set(fcx, cy, fcz)
    const fInnerGeos: THREE.BufferGeometry[] = []
    const fWindowGeos: THREE.BufferGeometry[] = []
    const fFrameGeos: THREE.BufferGeometry[] = []

    const floorCellSet = new Set(floor.cells.map((c) => `${c.row},${c.col}`))
    const hasCell = (r: number, c: number) => floorCellSet.has(`${r},${c}`)
    for (const cell of floor.cells) {
      const { x, z } = cellCenter(cell.row, cell.col)
      let geo: THREE.BufferGeometry
      if (cell.shape === 'Rect') {
        geo = new THREE.BoxGeometry(bw, boxH, bw)
      } else {
        geo = triangleGeometry(bw, boxH)
        if (cell.rotY > 0) geo.rotateY(TRI_ROT_Y)
      }
      // 相对楼层中心构建（便于围绕中心缩放凸出）
      geo.translate(x - fcx, 0, z - fcz)
      fInnerGeos.push(geo)
      innerGeos.push(geo)
      // 线框用绝对坐标副本
      const absGeo = geo.clone().translate(fcx, 0, fcz)
      outlineGeos.push(absGeo)

      // 逐格窗户（窗框 + 玻璃）—— 每层独立，一格一格
      const win = buildCellWindows(cell, floor.level, cy, floorCellSet, hasCell)
      for (const g of win.glass) { g.translate(-fcx, -cy, -fcz); fWindowGeos.push(g); windowGeos.push(g) }
      for (const f of win.frames) { f.translate(-fcx, -cy, -fcz); fFrameGeos.push(f); frameGeos.push(f) }
    }

    // 顶层格子顶面线框（供 BIM outline）
    if (isTop) {
      for (const cell of floor.cells) {
        const { x, z } = cellCenter(cell.row, cell.col)
        const g = new THREE.BoxGeometry(CELL_SIZE, 0.03, CELL_SIZE)
        g.translate(x, ROOF_Y + 0.015, z)
        roofGeos.push(g)
        outlineGeos.push(g)
      }
    }

    // 层内合并为少量 mesh（随楼层凸出一起缩放）
    const fInnerMesh = new THREE.Mesh(mergeCompat(fInnerGeos), floorMat)
    fInnerMesh.castShadow = true
    fInnerMesh.receiveShadow = true
    floorGroup.add(fInnerMesh)
    disposables.push(fInnerMesh.geometry)

    if (fWindowGeos.length) {
      const fWindowMesh = new THREE.Mesh(mergeCompat(fWindowGeos), windowGlassMat)
      fWindowMesh.renderOrder = 10
      floorGroup.add(fWindowMesh)
      disposables.push(fWindowMesh.geometry)
    }
    if (fFrameGeos.length) {
      const fFrameMesh = new THREE.Mesh(mergeCompat(fFrameGeos), windowFrameMat)
      fFrameMesh.renderOrder = 9
      floorGroup.add(fFrameMesh)
      disposables.push(fFrameMesh.geometry)
    }

    group.add(floorGroup)
    floorGroups.push(floorGroup)
  }

  // 整片灰色屋顶盖板：边追踪生成精确轮廓（含西南/东南阶梯缺角），贴合幕墙外轮廓
  const coverPts = topFloorOutline()
  const coverShape = new THREE.Shape(coverPts)
  // 盖板底面 = ROOF_Y+0.02（略高于顶层格子顶面 9.16），顶面 = ROOF_Y+0.14；
  // 核心筒顶部(y=9.20)被盖板完全包住，消除与格子顶面的 z-fighting
  const coverGeo = new THREE.ExtrudeGeometry(coverShape, { depth: 0.12, bevelEnabled: false })
  // rotateX(π/2)：shape 的 y（=建筑 z）→ 世界 +z，避免南北镜像
  coverGeo.rotateX(Math.PI / 2)
  coverGeo.translate(0, ROOF_Y + 0.14, 0)
  const coverMat = new THREE.MeshStandardMaterial({ color: 0xb8b0a4, roughness: 0.85, metalness: 0.05, side: THREE.DoubleSide })
  const roofCover = new THREE.Mesh(coverGeo, coverMat)
  roofCover.receiveShadow = true
  group.add(roofCover)
  disposables.push(coverGeo, coverMat)

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
    ...windowGeos,
    ...frameGeos,
    ...roofGeos,
    ...lineGeos,
    coreOutlineGeo,
  ]
  for (const g of sourceGeos) g.dispose()

  return group
}

/** 地面（与原 Building3D 的圆形地面一致 + 广场装饰环） */
/** 矩形环几何（外环 - 内孔），旋转到 XZ 平面（shape 的 y → 世界 +z，无镜像） */
function makeRectRing(
  outer: { x0: number; z0: number; x1: number; z1: number },
  inner: { x0: number; z0: number; x1: number; z1: number },
  color: number,
  y: number,
): THREE.Mesh {
  const shape = new THREE.Shape()
  shape.moveTo(outer.x0, outer.z0)
  shape.lineTo(outer.x1, outer.z0)
  shape.lineTo(outer.x1, outer.z1)
  shape.lineTo(outer.x0, outer.z1)
  shape.closePath()
  const hole = new THREE.Path()
  hole.moveTo(inner.x1, inner.z0)
  hole.lineTo(inner.x0, inner.z0)
  hole.lineTo(inner.x0, inner.z1)
  hole.lineTo(inner.x1, inner.z1)
  hole.closePath()
  shape.holes.push(hole)
  const geo = new THREE.ShapeGeometry(shape, 1)
  geo.rotateX(Math.PI / 2)
  geo.translate(0, y, 0)
  // envMapIntensity 调低：避免环境反射把地面/道路洗白，保持材质固有色
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 0.95, metalness: 0, envMapIntensity: 0.12, side: THREE.DoubleSide })
  const mesh = new THREE.Mesh(geo, mat)
  mesh.receiveShadow = true
  disposables.push(geo, mat)
  return mesh
}

/** 沿某层外墙幕墙段拼出的闭合轮廓（XZ 平面，贴合墙体，含切角/阶梯） */
function wallOutline(level: number): THREE.Vector2[] {
  const floor = FLOORS.find((f) => f.level === level)
  if (!floor) return []
  const segs = segmentsForFloor(floor.cells)
  interface Edge { bx: number; bz: number; ex: number; ez: number }
  const edges: Edge[] = []
  for (const seg of segs) {
    const dx = Math.cos(seg.phi)
    const dz = -Math.sin(seg.phi)
    const hx = (dx * seg.len) / 2
    const hz = (dz * seg.len) / 2
    edges.push({ bx: seg.cx - hx, bz: seg.cz - hz, ex: seg.cx + hx, ez: seg.cz + hz })
  }
  const nextMap = new Map<string, Edge>()
  for (const e of edges) nextMap.set(`${e.bx.toFixed(4)},${e.bz.toFixed(4)}`, e)
  const pts: THREE.Vector2[] = []
  const visited = new Set<string>()
  const startKey = `${edges[0].bx.toFixed(4)},${edges[0].bz.toFixed(4)}`
  let cur = edges[0]
  for (let i = 0; i <= edges.length * 2; i++) {
    const k = `${cur.bx.toFixed(4)},${cur.bz.toFixed(4)}`
    if (visited.has(k)) break
    visited.add(k)
    pts.push(new THREE.Vector2(cur.bx, cur.bz))
    const key = `${cur.ex.toFixed(4)},${cur.ez.toFixed(4)}`
    if (key === startKey) break
    let nxt = nextMap.get(key)
    if (!nxt) {
      let best: Edge | undefined = undefined
      let bestD = 0.2
      for (const e of edges) {
        const d = Math.hypot(e.bx - cur.ex, e.bz - cur.ez)
        if (d < bestD) {
          bestD = d
          best = e
        }
      }
      nxt = best
    }
    if (!nxt) break
    cur = nxt
  }
  return pts
}

/** 多边形外扩（miter 尖角，保持切角），dist 向外为正 */
function offsetPolygon(pts: THREE.Vector2[], dist: number): THREE.Vector2[] {
  const n = pts.length
  const center = new THREE.Vector2()
  for (const p of pts) center.add(p)
  center.divideScalar(n)
  const out: THREE.Vector2[] = []
  for (let i = 0; i < n; i++) {
    const prev = pts[(i - 1 + n) % n]
    const cur = pts[i]
    const next = pts[(i + 1) % n]
    const v1 = cur.clone().sub(prev)
    const v2 = next.clone().sub(cur)
    const l1 = v1.length() || 1
    const l2 = v2.length() || 1
    const e1 = v1.divideScalar(l1)
    const e2 = v2.divideScalar(l2)
    const bis = e1.clone().add(e2)
    if (bis.lengthSq() < 1e-6) bis.set(-e1.y, e1.x)
    bis.normalize()
    const away = cur.clone().sub(center)
    if (bis.dot(away) < 0) bis.multiplyScalar(-1)
    const cosA = Math.max(-1, Math.min(1, e1.dot(e2)))
    let mlen = dist / Math.cos(Math.acos(cosA) / 2)
    // 尖角处 miter 过长会导致多边形自交，ShapeGeometry 三角化失败露出背景色（白带）。
    // 限制 miter 长度上限，防止自交。
    mlen = Math.min(mlen, dist * 2.5)
    out.push(cur.clone().addScaledVector(bis, mlen))
  }
  return out
}

/** 任意多边形环（外轮廓 - 内孔），旋转到 XZ 平面 */
function makePolygonRing(
  outer: THREE.Vector2[],
  inner: THREE.Vector2[],
  color: number,
  y: number,
): THREE.Mesh {
  const shape = new THREE.Shape(outer)
  const hole = new THREE.Path()
  for (let i = inner.length - 1; i >= 0; i--) {
    const p = inner[i]
    if (i === inner.length - 1) hole.moveTo(p.x, p.y)
    else hole.lineTo(p.x, p.y)
  }
  hole.closePath()
  shape.holes.push(hole)
  const geo = new THREE.ShapeGeometry(shape, 1)
  geo.rotateX(Math.PI / 2)
  geo.translate(0, y, 0)
  const mat = new THREE.MeshStandardMaterial({ color, roughness: 1, metalness: 0, envMapIntensity: 0.03, side: THREE.DoubleSide })
  const mesh = new THREE.Mesh(geo, mat)
  mesh.receiveShadow = true
  disposables.push(geo, mat)
  return mesh
}

/** 一棵简单行道树（树干 + 双层树冠） */
function buildTree(x: number, z: number): THREE.Group {
  const g = new THREE.Group()
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6b4f2f, roughness: 0.9, envMapIntensity: 0.15 })
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.07, 0.1, 1.0, 8),
    trunkMat,
  )
  trunk.position.y = 0.45
  const crownMat1 = new THREE.MeshStandardMaterial({ color: 0x4c7a3d, roughness: 0.85, envMapIntensity: 0.2 })
  const crown1 = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 10, 8),
    crownMat1,
  )
  crown1.position.y = 1.35
  crown1.scale.set(1, 1.15, 1)
  const crownMat2 = new THREE.MeshStandardMaterial({ color: 0x5c8a46, roughness: 0.85, envMapIntensity: 0.2 })
  const crown2 = new THREE.Mesh(
    new THREE.SphereGeometry(0.34, 10, 8),
    crownMat2,
  )
  crown2.position.y = 1.85
  g.add(trunk, crown1, crown2)
  g.position.set(x, -0.05, z)
  g.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) o.castShadow = true
  })
  disposables.push(...[trunk, crown1, crown2].map((m) => m.geometry), trunkMat, crownMat1, crownMat2)
  return g
}

function buildGround(): THREE.Group {
  const group = new THREE.Group()
  ;(group as any).__isGround = true
  const groundGeo = new THREE.CircleGeometry(32, 64)
  // 不透明浅白色地坪（行人道色）：G/F 对齐地面，地面不可看穿；地下层从侧面低角度可见
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0xefede6,
    roughness: 0.9,
    metalness: 0,
    envMapIntensity: 0.12,
  })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -0.05
  ground.receiveShadow = true
  group.add(ground)
  disposables.push(groundGeo, groundMat)

  // 建筑底部外包矩形（所有层最外：x∈[-6.877,6.877], z∈[-4.577,3.427]）
  const bX0 = -6.877
  const bX1 = 6.877
  const bZ0 = -4.577
  const bZ1 = 3.427

  // 道路系统尺寸：行人道宽 1.2；双车道道路宽 4.8
  const SIDE_WALK = 1.2
  const ROAD_W = 4.8

  // 行人道 / 道路均用简单【矩形环】（凸多边形，earcut 稳定，绝无自交产生的白色缺陷区）。
  // （原实现用 offsetPolygon 沿含切角的凹轮廓外扩，在东南/西南尖角处自交，
  //   ShapeGeometry 三角化失败露出白色背景，无法直视 —— 已弃用。）
  const swRect = { x0: bX0 - 0.08 - SIDE_WALK, z0: bZ0 - 0.08 - SIDE_WALK, x1: bX1 + 0.08 + SIDE_WALK, z1: bZ1 + 0.08 + SIDE_WALK }
  const innerRect = { x0: bX0 - 0.08, z0: bZ0 - 0.08, x1: bX1 + 0.08, z1: bZ1 + 0.08 }
  const roadRect = { x0: swRect.x0 - ROAD_W, z0: swRect.z0 - ROAD_W, x1: swRect.x1 + ROAD_W, z1: swRect.z1 + ROAD_W }
  const rectPts = (r: { x0: number; z0: number; x1: number; z1: number }) => [
    new THREE.Vector2(r.x0, r.z0),
    new THREE.Vector2(r.x1, r.z0),
    new THREE.Vector2(r.x1, r.z1),
    new THREE.Vector2(r.x0, r.z1),
  ]
  const mkRing = (o: { x0: number; z0: number; x1: number; z1: number }, i: { x0: number; z0: number; x1: number; z1: number }, color: number, y: number) =>
    group.add(makePolygonRing(rectPts(o), rectPts(i), color, y))

  // 1) 行人道铺装面（灰色矩形环）
  mkRing(swRect, innerRect, 0x9d9d9d, 0.006)
  // 2) 路缘石：行人道与道路交界凸起条（灰色石材）
  mkRing(swRect, { x0: swRect.x0 + 0.14, z0: swRect.z0 + 0.14, x1: swRect.x1 - 0.14, z1: swRect.z1 - 0.14 }, 0x8f8f8f, 0.03)
  // 3) 双车道道路（黑灰沥青矩形环）
  mkRing(roadRect, swRect, 0x333333, 0.006)

  // 4) 车道标线
  const lineY = 0.013
  const rectLines = (
    rx0: number, rz0: number, rx1: number, rz1: number,
    dash: number, gap: number, color: number,
  ) => {
    const mat = new THREE.LineBasicMaterial({ color })
    const pts: number[] = []
    const seg = (ax: number, az: number, bx: number, bz: number) => {
      const dx = bx - ax
      const dz = bz - az
      const len = Math.hypot(dx, dz)
      const nx = dx / len
      const nz = dz / len
      let d = 0
      while (d < len) {
        const e = Math.min(d + dash, len)
        pts.push(ax + nx * d, lineY, az + nz * d, ax + nx * e, lineY, az + nz * e)
        d += dash + gap
      }
    }
    seg(rx0, rz0, rx1, rz0)
    seg(rx1, rz0, rx1, rz1)
    seg(rx1, rz1, rx0, rz1)
    seg(rx0, rz1, rx0, rz0)
    const geo = new THREE.BufferGeometry()
    geo.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    const line = new THREE.LineSegments(geo, mat)
    disposables.push(geo, mat)
    return line
  }

  // 车道边缘实线（道路内缘贴路缘石、外缘，白色实线）
  const edgeIn = { x0: bX0 - 0.08 - SIDE_WALK - 0.22, z0: bZ0 - 0.08 - SIDE_WALK - 0.22, x1: bX1 + 0.08 + SIDE_WALK + 0.22, z1: bZ1 + 0.08 + SIDE_WALK + 0.22 }
  const edgeOut = { x0: roadRect.x0 + 0.22, z0: roadRect.z0 + 0.22, x1: roadRect.x1 - 0.22, z1: roadRect.z1 - 0.22 }
  group.add(rectLines(edgeIn.x0, edgeIn.z0, edgeIn.x1, edgeIn.z1, 1e6, 1e6, 0xe8e6e0))
  group.add(rectLines(edgeOut.x0, edgeOut.z0, edgeOut.x1, edgeOut.z1, 1e6, 1e6, 0xe8e6e0))

  // 双车道中线（白色虚线）
  const midOff = 0.08 + SIDE_WALK + ROAD_W / 2
  const mX0 = bX0 - midOff
  const mX1 = bX1 + midOff
  const mZ0 = bZ0 - midOff
  const mZ1 = bZ1 + midOff
  group.add(rectLines(mX0, mZ0, mX1, mZ1, 1.2, 0.6, 0xf0eee8))

  // 5) 行人道铺装砖缝（暖灰细线，沿矩形行人道带四边各两条）
  const jointY = 0.009
  const jointColor = 0x6f675a
  const walkRect = { x0: bX0 - 0.08 - SIDE_WALK, z0: bZ0 - 0.08 - SIDE_WALK, x1: bX1 + 0.08 + SIDE_WALK, z1: bZ1 + 0.08 + SIDE_WALK }
  const j1 = 0.35
  const j2 = 0.75
  group.add(rectLines(walkRect.x0, walkRect.z0 + j1, walkRect.x1, walkRect.z0 + j1, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x0, walkRect.z0 + j2, walkRect.x1, walkRect.z0 + j2, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x0, walkRect.z1 - j1, walkRect.x1, walkRect.z1 - j1, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x0, walkRect.z1 - j2, walkRect.x1, walkRect.z1 - j2, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x0 + j1, walkRect.z0, walkRect.x0 + j1, walkRect.z1, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x0 + j2, walkRect.z0, walkRect.x0 + j2, walkRect.z1, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x1 - j1, walkRect.z0, walkRect.x1 - j1, walkRect.z1, 0.95, 0.18, jointColor))
  group.add(rectLines(walkRect.x1 - j2, walkRect.z0, walkRect.x1 - j2, walkRect.z1, 0.95, 0.18, jointColor))

  // 6) 南面行道树：一排 4 棵，沿行人道外侧
  const treeZ = bZ1 + 0.08 + SIDE_WALK + 0.15
  const TREE_X = [-4.5, -1.5, 1.5, 4.5]
  for (const tx of TREE_X) group.add(buildTree(tx, treeZ))

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
    const y0 = (level - 3) * SLAB
    const y1 = level === FLOOR_COUNT ? ROOF_Y : (level - 3) * SLAB + SLAB
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

/** 选中楼层高亮盒：盖住被选中楼层，金色半透明（常驻，供右侧设备面板联动） */
function buildSelectedHighlight() {
  selectedHighlightMat = new THREE.MeshBasicMaterial({
    color: 0xc4a574,
    transparent: true,
    opacity: 0.34,
    depthWrite: false,
  })
  const geo = new THREE.BoxGeometry(1, 1, 1)
  selectedHighlight = new THREE.Mesh(geo, selectedHighlightMat)
  selectedHighlight.visible = false
  selectedHighlight.renderOrder = 19
  disposables.push(geo, selectedHighlightMat)
}

/** 更新选中楼层高亮盒：匹配选中楼层的外包轮廓 */
function updateSelectedHighlight(floor: number | null) {
  if (!selectedHighlight) return
  if (floor == null) {
    selectedHighlight.visible = false
    return
  }
  const { minX, maxX, minZ, maxZ } = floorFootprint(floor)
  const y0 = (floor - 3) * SLAB
  const y1 = floor === FLOOR_COUNT ? ROOF_Y : (floor - 3) * SLAB + SLAB
  selectedHighlight.position.set((minX + maxX) / 2, (y0 + y1) / 2, (minZ + maxZ) / 2)
  selectedHighlight.scale.set(maxX - minX, y1 - y0, maxZ - minZ)
  selectedHighlight.visible = true
}

// ---- 格子编辑模式（整合自 /building-viewer 的 Building3D 编辑面板） ----

/** 编辑模式下格子材质颜色：温湿度着色；无数据回退灰阶 */
function floorColorFor(level: number, min: number, max: number, fallback: string): THREE.Color {
  const env = floorEnv.value[level]
  const value = metric.value === 'temperature' ? env?.temperature ?? null : env?.humidity ?? null
  const color = envColorFor(metric.value, value, min, max)
  if (color) return new THREE.Color(color)
  const t = level / Math.max(1, FLOOR_COUNT - 1)
  return new THREE.Color(fallback)
}

/** 编辑模式：hover/选中楼层时格子高亮、其余楼层变暗 */
function updateFloorAppearance() {
  const selected = props.selectedFloor ?? null
  const hovered = hoveredFloor.value
  for (const [level, meshes] of meshesByFloor) {
    const isActive = selected === level || hovered === level
    const dimmed = !!(selected && selected !== level && hovered !== level)
    for (const mesh of meshes) {
      const mat = mesh.material as THREE.MeshStandardMaterial
      if (!mesh.userData.customColor) {
        const [min, max] = envRange(floorEnv.value, metric.value)
        mat.color = floorColorFor(level, min, max, '#8a8f93')
      }
      mat.opacity = dimmed ? 0.28 : 0.95
      mat.emissive = new THREE.Color(isActive ? 0xc4a574 : 0x000000)
      mat.emissiveIntensity = hovered === level ? 0.4 : selected === level ? 0.22 : 0
    }
  }
}

/**
 * 编辑模式建筑：按 DB building_cell（:cell-shapes）渲染独立格子，
 * 无 DB 数据时回退到快照（轮廓 1:1）。每个格子可拾取（row/col/floor/floor_id）。
 */
function buildEditingBuilding(): THREE.Group {
  const group = new THREE.Group()
  floorMeshes = []
  meshesByFloor.clear()
  floorGroups = []
  floorInnerMats = []
  if (lastEditCellGeo) {
    lastEditCellGeo.dispose()
    lastEditCellGeo = null
  }
  editGeos = new Set()
  if (hiddenCellGroup) {
    scene?.remove(hiddenCellGroup)
    hiddenCellGeos.forEach((g) => g.dispose())
    hiddenCellMaterials.forEach((m) => m.dispose())
    hiddenCellGeos = []
    hiddenCellMaterials = []
    hiddenCellGroup = null
  }
  hiddenCellMeshes = []

  const cellSize = CELL_SIZE * 0.96
  const cellGeo = new THREE.BoxGeometry(cellSize, FLOOR_H, cellSize) as THREE.BufferGeometry
  lastEditCellGeo = cellGeo
  editGeos.add(cellGeo)

  const shapesByFloor = new Map<number, CellShapeConfig[]>()
  const dbDriven = !!(props.cellShapes && props.cellShapes.length)
  for (const s of props.cellShapes ?? []) {
    if (s.floor < 1 || s.floor > FLOOR_COUNT) continue
    if (isHiddenType(s.shape)) continue
    const list = shapesByFloor.get(s.floor) ?? []
    list.push(s)
    shapesByFloor.set(s.floor, list)
  }

  const [min, max] = envRange(floorEnv.value, metric.value)
  const FALLBACK = '#8a8f93'

  for (let i = 0; i < FLOOR_COUNT; i++) {
    const level = i + 1
    const yBase = (i - 2) * SLAB
    const levelMeshes: THREE.Mesh[] = []

    const renderCells: CellShapeConfig[] = []
    if (dbDriven) {
      for (const s of shapesByFloor.get(level) ?? []) renderCells.push(s)
    } else {
      const floor = FLOORS.find((f) => f.level === level)
      for (const c of floor?.cells ?? []) {
        renderCells.push({
          row: c.row,
          col: c.col,
          floor: level,
          shape: c.shape === 'Triangle' ? 'Triangle' : 'Rect',
        })
      }
    }

    for (const shapeConfig of renderCells) {
      const shapeType: GridType = shapeConfig?.shape ?? 'Rect'
      if (isHiddenType(shapeType)) continue
      const customColor = shapeConfig?.color ?? null
      const mat = new THREE.MeshStandardMaterial({
        color: customColor ? new THREE.Color(customColor) : floorColorFor(level, min, max, FALLBACK),
        metalness: 0.12,
        roughness: 0.55,
        transparent: true,
        opacity: 0.95,
      })
      const cellHeight = shapeConfig?.height && shapeConfig.height > 0 ? shapeConfig.height : FLOOR_H
      const geo = shapeType === 'Rect' && cellHeight === FLOOR_H
        ? cellGeo
        : createGeometryByType(shapeType, cellSize, cellHeight)
      editGeos.add(geo)
      const mesh = new THREE.Mesh(geo, mat)
      const { x: wx, z: wz } = cellToWorld(shapeConfig.row, shapeConfig.col)
      const hasDbPos = shapeConfig?.x != null && shapeConfig?.y != null && shapeConfig?.z != null
      const px = hasDbPos ? shapeConfig.x! : wx
      const py = hasDbPos ? shapeConfig.z! + UNDERGROUND_OFFSET : yBase + FLOOR_H / 2
      const pz = hasDbPos ? shapeConfig.y! : wz
      mesh.position.set(px, py, pz)
      if (shapeConfig?.rotation) mesh.rotation.copy(parseRotation(shapeConfig.rotation))
      mesh.userData.floor = level
      mesh.userData.row = shapeConfig.row
      mesh.userData.col = shapeConfig.col
      mesh.userData.floor_id = shapeConfig?.floor_id ?? null
      mesh.userData.customColor = customColor
      mesh.castShadow = true
      mesh.receiveShadow = true
      group.add(mesh)
      floorMeshes.push(mesh)
      levelMeshes.push(mesh)
    }
    meshesByFloor.set(level, levelMeshes)
  }

  // 核心筒（与原始状态一致）
  const coreMat = new THREE.MeshStandardMaterial({ color: 0x1c1c1c, roughness: 0.8, metalness: 0.2 })
  disposables.push(coreMat)
  const coreGeo = new THREE.BoxGeometry(CORE_W * 0.7, CORE_H, CORE_W * 0.7)
  const core = new THREE.Mesh(coreGeo, coreMat)
  core.position.set(CELL_SIZE * 2, CORE_H / 2 + UNDERGROUND_OFFSET, CELL_SIZE * 1)
  group.add(core)
  disposables.push(coreGeo)

  updateFloorAppearance()
  return group
}

/** 编辑模式：隐藏格子（is_active=0）以「透明填充 + 黑线边框」显示，可点击选中删除 */
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
  const fillMat = new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.14, depthWrite: false })
  const edgeMat = new THREE.LineBasicMaterial({ color: 0x000000 })
  hiddenCellGeos.push(boxGeo, edgeGeo)
  hiddenCellMaterials.push(fillMat, edgeMat)

  for (const s of props.cellShapes ?? []) {
    if (!isHiddenType(s.shape)) continue
    if (s.floor < 1 || s.floor > FLOOR_COUNT) continue
    const level = s.floor
    const yBase = (level - 3) * SLAB
    const { x: wx, z: wz } = cellToWorld(s.row, s.col)
    const hasDbPos = s.x != null && s.y != null && s.z != null
    const px = hasDbPos ? s.x! : wx
    const py = hasDbPos ? s.z! + UNDERGROUND_OFFSET : yBase + FLOOR_H / 2
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

/** floor3d (1~11) → DB floor.id（优先从已有格子推断，其次查 floors 表，缓存结果） */
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

/** 切换编辑模式：进入时抓取格子快照（供放弃修改回滚），退出时有改动则弹确认框 */
async function toggleEditMode() {
  if (!editUnlocked.value) {
    editUnlocked.value = true
    editDirty.value = false
    undoableOps.value = 0
    editToolMode.value = 'none'
    prevRawMode.value = rawMode.value
    rawMode.value = true
    hoveredFloor.value = null
    toastVisible.value = false
    updateSelectedHighlight(null)
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
    editModeToast.value = true
    if (editModeToastTimer) clearTimeout(editModeToastTimer)
    editModeToastTimer = setTimeout(() => { editModeToast.value = false }, 1800)
    scheduleRebuild()
    return
  }
  if (editDirty.value) openExitConfirm()
  else exitEditSession()
}

/** 统一退出编辑会话：清空快照、工具模式与改动标记，恢复外观 */
function exitEditSession() {
  editUnlocked.value = false
  snapshotShapes.value = []
  editDirty.value = false
  undoableOps.value = 0
  editToolMode.value = 'none'
  hideDragTemplates()
  rawMode.value = prevRawMode.value
  updateHiddenOverlaysVisibility()
  updateSelectedHighlight(props.selectedFloor ?? null)
  scheduleRebuild()
}

function openExitConfirm() {
  confirmOpen.value = true
}

function onDoneClick() {
  if (editDirty.value) openExitConfirm()
  else exitEditSession()
}

/** 完成编辑会话：save=true 保留改动；save=false 放弃并回滚到快照 */
async function finishEditSession(save: boolean) {
  confirmOpen.value = false
  if (save) {
    exitEditSession()
    message.success(t('building.savedSuccess'))
    return
  }
  await discardChanges()
}

/** 放弃本次修改：对快照与当前 DB 状态逆向恢复 */
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

    for (const s of snapMap.values()) {
      if (!curMap.has(keyOf(s)) && s.floor_id != null) {
        await cellEdit({
          building_id: buildingId,
          row_no: s.row,
          col_no: s.col,
          action: 'add',
          scope: 'single',
          floor_id: s.floor_id,
          shape: s.shape === 'Cylinder' || s.shape === 'Triangle' ? s.shape : 'Rect',
        })
      }
    }
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
    message.error(t('building.discardFailed'))
  }
}

/** 切换编辑工具模式（添加 / 删除互斥） */
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

/** 射线与各层水平面求交，反算点击的网格行列（含该位置是否已有格子） */
function pickGridCellFromRay(): { row: number; col: number; floor3d: number; exists: boolean } | null {
  if (!raycaster) return null
  let best: { row: number; col: number; floor3d: number; exists: boolean } | null = null
  let bestDist = Infinity
  const hit = new THREE.Vector3()
  const plane = new THREE.Plane()
  for (let level = 1; level <= FLOOR_COUNT; level++) {
    plane.set(new THREE.Vector3(0, 1, 0), -((level - 3) * SLAB))
    if (!raycaster.ray.intersectPlane(plane, hit)) continue
    const dist = raycaster.ray.origin.distanceTo(hit)
    if (dist >= bestDist) continue
    const col = Math.round(hit.x / CELL_SIZE + 6.5)
    const row = Math.round(hit.z / CELL_SIZE + 4.5)
    if (row < 1 || row > 8 || col < 1 || col > 12) continue
    const exists = props.cellShapes?.some(
      (s) => s.floor === level && s.row === row && s.col === col && !isHiddenType(s.shape),
    ) ?? false
    best = { row, col, floor3d: level, exists }
    bestDist = dist
  }
  return best
}

// ---- 拖拽添加格子：点击「添加」后楼宇旁出现模板格子（圆/方/三角）→ 拖到楼宇上放置 ----

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
    mesh.position.set(-8.4, height / 2, (i - 1) * 1.8)
    mesh.userData.isDragSource = true
    mesh.userData.shape = shape
    dragSourceGroup.add(mesh)
    dragSourceMeshes.push(mesh)
  }
  dragSourceGroup.visible = false
  scene.add(dragSourceGroup)
}

function hideDragTemplates() {
  if (!dragSourceGroup) return
  dragSourceGroup.visible = false
}

function spawnDragTemplates() {
  if (!dragSourceGroup) return
  for (const m of dragSourceMeshes) m.visible = true
  dragSourceGroup.visible = true
}

function startDragCell(mesh: THREE.Mesh, ev: PointerEvent) {
  if (!scene || !raycaster) return
  activeDragSource = mesh
  dragTarget = null
  dragRotationDeg = 0
  if (controls) controls.enabled = false
  prevAutoRotate = autoRotate.value
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
  updateDragPreview()
  document.addEventListener('pointermove', onDragMove)
  document.addEventListener('pointerup', endDragCell)
  document.addEventListener('wheel', onDragWheel, { passive: false })
  document.addEventListener('keydown', onDragKeyDown)
}

function onDragMove(ev: PointerEvent) {
  updatePointer(ev)
  if (raycaster && camera) raycaster.setFromCamera(pointer, camera)
  updateDragPreview()
}

function updateDragPreview() {
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
  const y = (cell.floor3d - 3) * SLAB + FLOOR_H + 0.9
  dragPreviewMesh.position.set(x, y, z)
  dragPreviewMesh.visible = true
  applyDragPreviewRotation()
  dragPreviewMat.color.set(cell.exists ? 0xe53935 : 0x4caf50)
}

async function endDragCell() {
  document.removeEventListener('pointermove', onDragMove)
  document.removeEventListener('pointerup', endDragCell)
  document.removeEventListener('wheel', onDragWheel)
  document.removeEventListener('keydown', onDragKeyDown)
  if (controls) controls.enabled = true
  autoRotate.value = prevAutoRotate
  if (host.value) host.value.style.cursor = 'grab'
  if (scene && dragPreviewMesh) {
    scene.remove(dragPreviewMesh)
    dragPreviewMat?.dispose()
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
  if (!target || target.exists) return
  if (!props.buildingId) {
    message.warning(t('building.missingBuildingId'))
    return
  }
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
          // 旋轉寫入失敗不阻礙放置
          console.warn('[BuildingFacade3D] Failed to write placed rotation:', placedRotationDeg)
        }
      }
      message.success(t('building.addCellSuccess'))
    } else {
      message.warning(t('building.addCellExists'))
    }
  } catch {
    message.error(t('building.addCellFailed'))
  }
  emit('refreshShapes')
}

function onDragWheel(ev: WheelEvent) {
  if (!activeDragSource) return
  ev.preventDefault()
  dragRotationDeg = (dragRotationDeg + (ev.deltaY > 0 ? 15 : -15) + 360) % 360
  applyDragPreviewRotation()
}

function onDragKeyDown(ev: KeyboardEvent) {
  if (!activeDragSource) return
  if (ev.key === 'r' || ev.key === 'R') {
    ev.preventDefault()
    dragRotationDeg = (dragRotationDeg + (ev.shiftKey ? -45 : 45) + 360) % 360
    applyDragPreviewRotation()
  }
}

function applyDragPreviewRotation() {
  if (!dragPreviewMesh) return
  dragPreviewMesh.rotation.y = (dragRotationDeg * Math.PI) / 180
}

/** 删除模式：删除指定格子（单格），可连续调用 */
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
    message.error(t('building.deleteFailed'))
  }
  emit('refreshShapes')
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
    showFeedback(t('building.undoLimitReached'))
  } else {
    showFeedback(t('building.noUndo'))
  }
}

function showFeedback(msg: string) {
  editFeedback.value = msg
  if (feedbackTimer) clearTimeout(feedbackTimer)
  feedbackTimer = setTimeout(() => { editFeedback.value = '' }, 2500)
}

/** 编辑模式：pointerdown 处理添加（拖拽模板）/删除（点击格子）；none 模式无操作 */
function onPointerDown(ev: PointerEvent) {
  if (!camera || !raycaster || !editUnlocked.value) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)
  if (editToolMode.value === 'add') {
    const srcHits = raycaster.intersectObjects(dragSourceMeshes, false)
    if (srcHits.length) {
      startDragCell(srcHits[0].object as THREE.Mesh, ev)
      return
    }
    return
  }
  if (editToolMode.value === 'delete') {
    const hiddenHits = raycaster.intersectObjects(hiddenCellMeshes, false)
    if (hiddenHits.length) {
      const ud = hiddenHits[0].object.userData
      if (ud.floor_id != null) void deleteCellAt(ud.floor_id, ud.row, ud.col)
      return
    }
    const hits = raycaster.intersectObjects(floorMeshes, false)
    if (hits.length) {
      const ud = hits[0].object.userData
      const shape = props.cellShapes?.find(
        (s) => s.row === ud.row && s.col === ud.col && s.floor === ud.floor,
      )
      if (shape?.floor_id != null) void deleteCellAt(shape.floor_id, ud.row, ud.col)
      return
    }
    return
  }
}

/** 更新高亮盒：匹配悬停楼层的外包轮廓，并标记凸出目标楼层 */
function updateHoverHighlight(_floor: number | null) {
  // 只在选中时凸出：去掉鼠标悬停的即时凸出（楼层不再缩放放大、不再显示金色高亮盒）。
  // 悬停仍保留楼层提示 toast 与指针变化，但建筑本体保持静止。
  hoverScaleFloor = 0
  if (hoverHighlight) hoverHighlight.visible = false
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
  const y0 = (L1F - 1) * SLAB + UNDERGROUND_OFFSET // 1F 底（含地下偏移）
  const y1 = L1F * SLAB + SLAB + UNDERGROUND_OFFSET // 2F 顶（含地下偏移）
  const yCenter = (y0 + y1) / 2
  const h = y1 - y0
  const w = h * (289 / 267)

  const tex = new THREE.TextureLoader().load('/wingon-logo.png')
  tex.colorSpace = THREE.SRGBColorSpace
  tex.anisotropy = 8
  // 自定义 emboss 材质：基于透明度梯度生成法线，产生高光/阴影的 3D 凸起感
  const embossMat = new THREE.ShaderMaterial({
    uniforms: {
      uTex: { value: tex },
      uTexel: { value: new THREE.Vector2(1 / w, 1 / h) },
      uLightDir: { value: new THREE.Vector3(-0.45, 0.75, 0.45).normalize() },
      uSpecPower: { value: 32.0 },
      uEmboss: { value: 0.55 },
      uAmbient: { value: 0.35 },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() {
        vUv = uv;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform sampler2D uTex;
      uniform vec2 uTexel;
      uniform vec3 uLightDir;
      uniform float uSpecPower;
      uniform float uEmboss;
      uniform float uAmbient;
      varying vec2 vUv;
      void main() {
        vec4 c = texture2D(uTex, vUv);
        float aL = texture2D(uTex, vUv + vec2(-uTexel.x, 0.0)).a;
        float aR = texture2D(uTex, vUv + vec2( uTexel.x, 0.0)).a;
        float aU = texture2D(uTex, vUv + vec2(0.0,  uTexel.y)).a;
        float aD = texture2D(uTex, vUv + vec2(0.0, -uTexel.y)).a;
        vec3 grad = vec3((aR - aL) * uEmboss, (aU - aD) * uEmboss, 1.0);
        vec3 N = normalize(grad);
        float diff = max(dot(N, uLightDir), 0.0);
        float spec = pow(max(diff, 0.0), uSpecPower);
        float light = uAmbient + diff * (1.0 - uAmbient) + spec * 0.3;
        float shadow = max(0.0, dot(N, normalize(vec3(0.4, -0.3, 0.8))));
        light = mix(light, 0.18, clamp(shadow * 0.6, 0.0, 1.0));
        vec3 rgb = c.rgb * light;
        gl_FragColor = vec4(rgb, c.a);
      }
    `,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  })
  const logo = new THREE.Mesh(new THREE.PlaneGeometry(w, h), embossMat)
  ;(logo as any).__isLogo = true
  logo.position.set(cx, yCenter, cz)
  logo.rotation.y = Math.atan2(nx, nz)
  logo.renderOrder = 22
  disposables.push(tex, embossMat, logo.geometry as THREE.BufferGeometry)
  return logo
}

/** 楼层名用于提示（bim-viewer 风格：如 G/F、1/F、2/F） */
function floorLabel(level: number): string {
  const n = floorName(level)
  if (level === FLOOR_COUNT) return 'ROOF'
  return `${n}/F`
}

/** 指定楼层的真实设备数（无数据为 0） */
function deviceCountFor(floor: number): number {
  return floorEnv.value[floor]?.deviceCount ?? 0
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

  // 编辑模式：hover 模板 → 可拖拽光标；hover 格子 → 高亮楼层
  if (editUnlocked.value) {
    const srcHits = raycaster.intersectObjects(dragSourceMeshes, false)
    if (srcHits.length) {
      if (hoveredFloor.value != null) {
        hoveredFloor.value = null
        updateFloorAppearance()
      }
      toastVisible.value = false
      host.value.style.cursor = 'copy'
      debugVisible.value = false
      return
    }
    const hits = raycaster.intersectObjects(floorMeshes, false)
    if (hits.length) {
      const floor = hits[0].object.userData.floor as number
      if (hoveredFloor.value !== floor) {
        hoveredFloor.value = floor
        updateFloorAppearance()
      }
      toastVisible.value = true
      placeToast(ev.clientX, ev.clientY, host.value.getBoundingClientRect())
      host.value.style.cursor = 'pointer'
    } else {
      if (hoveredFloor.value != null) {
        hoveredFloor.value = null
        updateFloorAppearance()
      }
      toastVisible.value = false
      host.value.style.cursor = 'grab'
    }
    debugVisible.value = false
    return
  }

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

  // 调试信息（控制面板「调试信息」开关开启时显示）：射线与真实墙体相交，转回建筑局部坐标判断面
  if (debugEnabled.value && buildingGroup) {
    const wallRoot = buildingGroup.children[0]
    const buildHits = wallRoot ? raycaster.intersectObject(wallRoot, true) : []
    // 排除 LineSegments（BIM 线框无 face），取第一个实体 Mesh 命中
    const hit = buildHits.find((h) => h.object.type === 'Mesh')
    if (hit && hit.face) {
      // 建筑会自动旋转：命中点/法线先转回建筑局部坐标，方便对照快照格子
      const inv = buildingGroup.matrixWorld.clone().invert()
      const local = hit.point.clone().applyMatrix4(inv)
      const wn = hit.face.normal
        .clone()
        .transformDirection(hit.object.matrixWorld)
        .transformDirection(inv)
      let face = t('building.faceUnknown')
      const ax = Math.abs(wn.x)
      const az = Math.abs(wn.z)
      if (Math.abs(wn.y) > 0.7) {
        face = t('building.faceRoof')
      } else if (ax > 0.45 && az > 0.45) {
        face = t('building.faceSlope')
      } else if (ax > az) {
        face = wn.x > 0 ? t('building.faceEast') : t('building.faceWest')
      } else {
        face = wn.z > 0 ? t('building.faceSouth') : t('building.faceNorth')
      }
      const level = Math.floor(local.y / SLAB) + 3
      const fName = floorName(level)
      debugInfo.value = `${t('building.debugFace')}: ${face}\n${t('building.debugCoord')}: x=${local.x.toFixed(2)}, z=${local.z.toFixed(2)}\n${t('building.debugHeight')}: y=${local.y.toFixed(2)} (${t('building.debugApprox')}${fName})\n${t('building.debugNormal')}: (${wn.x.toFixed(2)}, ${wn.z.toFixed(2)})`
      debugVisible.value = true
    } else {
      debugVisible.value = false
    }
  } else {
    debugVisible.value = false
  }
}

function clearHover() {
  hoveredFloor.value = null
  toastVisible.value = false
  updateHoverHighlight(null)
  updateFloorAppearance()
  debugVisible.value = false
  if (host.value) host.value.style.cursor = 'grab'
}

function onPointerLeave() {
  clearHover()
}

/** 点击建筑表面：编辑模式下由 pointerdown 处理；否则「点击创建窗户」开关开启时开关窗户，未开启时按楼层选中/进入 */
function onPointerClick(ev: PointerEvent) {
  if (!host.value || !camera || !raycaster || !buildingGroup) return
  // 编辑模式：格子交互由 pointerdown 处理，click 不再选楼层/开窗
  if (editUnlocked.value) return
  updatePointer(ev)
  raycaster.setFromCamera(pointer, camera)

  // 未开启「点击创建窗户」：点击楼层 → 选中/进入该楼层（与 /building-viewer 一致）
  if (!cellClickEnabled.value) {
    const hits = raycaster.intersectObjects(floorHits, false)
    if (hits.length) {
      emit('selectFloor', hits[0].object.userData.floor as number)
    }
    return
  }

  // 射线与建筑本体相交（第一个子对象 = buildBuilding 返回的 group）
  const wallRoot = buildingGroup.children.find(
    (c) => c !== hoverHighlight && !floorHits.includes(c as THREE.Mesh) && !(c as any).__isGround && !(c as any).__isLogo,
  )
  if (!wallRoot) return
  const hits = raycaster.intersectObject(wallRoot, true)
  const hit = hits.find((h) => h.object.type === 'Mesh')
  if (!hit) return

  // 命中点转回建筑局部坐标
  const inv = buildingGroup.matrixWorld.clone().invert()
  const local = hit.point.clone().applyMatrix4(inv)

  // 反推格子行列号：x = (col-6.5)*CELL_SIZE, z = (row-4.5)*CELL_SIZE
  const col = Math.round(local.x / CELL_SIZE + 6.5)
  const row = Math.round(local.z / CELL_SIZE + 4.5)
  // 外墙表面的浮点误差可能让边界格子圆整出界，clamp 回有效范围
  const cr = Math.min(7, Math.max(1, row))
  const cc = Math.min(12, Math.max(1, col))
  if ((cr < 1 || cr > 7 || cc < 1 || cc > 12)) return

  // 反推 3D 楼层：G/F(level3) 对齐地面 y=0，地下层为负
  const level = Math.min(FLOOR_COUNT, Math.max(1, Math.round((local.y - FLOOR_H / 2) / SLAB) + 3))

  const key = `${level},${cr},${cc}`
  const next = { ...cellWindows.value }
  if (next[key]) {
    delete next[key]
  } else {
    next[key] = true
  }
  cellWindows.value = next
}

// ---- 自动场景（按本地日出/日落时间切换 日间/黄昏/夜间） ----

function dayOfYear(date: Date): number {
  const start = new Date(date.getFullYear(), 0, 1)
  return Math.floor((date.getTime() - start.getTime()) / 86400000)
}

/** NOAA 简化算法：计算当日日出/日落时间（UTC 小时，含小数）；极昼/极夜返回 null */
function computeSunTimes(
  date: Date,
  lat: number,
  lng: number,
): { sunrise: number; sunset: number } | null {
  const rad = Math.PI / 180
  const zenith = 90.833 * rad
  const lngHour = lng / 15
  const N = dayOfYear(date)

  const calc = (isSunset: boolean): number => {
    const hour = isSunset ? 18 : 6
    let t = N + (hour - lngHour) / 24
    const M = (0.9856 * t - 3.289) * rad
    let L = M + (1.916 * Math.sin(M)) * rad + (0.02 * Math.sin(2 * M)) * rad + 282.634 * rad
    L = L % (2 * Math.PI)
    if (L < 0) L += 2 * Math.PI
    const RA = Math.atan(0.91764 * Math.tan(L))
    const Lq = Math.floor(L / (Math.PI / 2)) * (Math.PI / 2)
    const RAq = Math.floor(RA / (Math.PI / 2)) * (Math.PI / 2)
    const RAn = RA + (Lq - RAq)
    const sinDec = 0.39782 * Math.sin(L)
    const cosDec = Math.cos(Math.asin(sinDec))
    const cosH = (Math.cos(zenith) - sinDec * Math.sin(lat * rad)) / (cosDec * Math.cos(lat * rad))
    if (cosH > 1 || cosH < -1) return -1
    const H = (isSunset ? 1 : -1) * Math.acos(cosH)
    let T = (H * 180) / Math.PI + (RAn * 180) / Math.PI - 0.06571 * t - 6.622
    let UT = (T - lngHour) % 24
    if (UT < 0) UT += 24
    return UT
  }

  const sunrise = calc(false)
  const sunset = calc(true)
  if (sunrise < 0 || sunset < 0) return null
  return { sunrise, sunset }
}

/** 按当前时刻计算应使用的场景预设，并应用到 preset */
function updateAutoPreset() {
  if (!autoPreset.value) return
  const times = computeSunTimes(new Date(), SUN_LAT, SUN_LNG)
  if (!times) {
    if (preset.value !== 'day') preset.value = 'day'
    return
  }
  const now = new Date()
  const utcNow = now.getUTCHours() + now.getUTCMinutes() / 60
  // 日出可能落在前一日 UTC（跨午夜）：用「当前时刻是否在日出~日落之间」判断白天
  const dayActive = times.sunrise <= times.sunset
    ? utcNow >= times.sunrise && utcNow < times.sunset
    : utcNow >= times.sunrise || utcNow < times.sunset
  // 当前时刻与日落的环形距离（小时，24 小时环）
  const ringDist = (a: number, b: number) => {
    const d = Math.abs(a - b) % 24
    return d <= 12 ? d : 24 - d
  }
  const distToSunset = ringDist(utcNow, times.sunset)
  let next: 'day' | 'dusk' | 'night'
  if (distToSunset <= DUSK_WINDOW_H) {
    next = 'dusk'
  } else if (dayActive) {
    next = 'day'
  } else {
    next = 'night'
  }
  if (preset.value !== next) preset.value = next
}

watch(autoPreset, (v) => {
  if (v) {
    updateAutoPreset()
    autoSceneTimer = setInterval(updateAutoPreset, 60000)
  } else {
    if (autoSceneTimer) {
      clearInterval(autoSceneTimer)
      autoSceneTimer = undefined
    }
    preset.value = 'day'
  }
})

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
  // 楼层颜色：白天/黄昏用材质色自发光提亮（跟随右下图例色）；夜晚切换为内透暖光
  for (const m of floorInnerMats) {
    if (name === 'night') {
      m.emissive.setHex(0xffb46b)
      m.emissiveIntensity = p.innerLight
    } else {
      m.emissive.set(m.color)
      m.emissiveIntensity = name === 'dusk' ? 0.2 : 0.15
    }
  }
  glassOpacity.value = p.glassOpacity
}

// ---- 初始化 ----

function initThreeJS() {
  if (!host.value || scene) return
  const w = host.value.clientWidth
  const h = host.value.clientHeight

  scene = new THREE.Scene()
  ;(window as any).__dbg = {
    scene,
    camera,
    get cam() { return camera },
    get raycaster() { return raycaster },
    get groups() { return floorGroups },
  }
  ;(window as any).__ray = (nx: number, ny: number) => {
    if (!raycaster || !camera) return []
    raycaster.setFromCamera(new THREE.Vector2(nx, ny), camera!)
    const hits = raycaster.intersectObject(buildingGroup!, true)
    return hits.slice(0, 15).map((h) => ({
      obj: h.object.type,
      name: h.object.name || '',
      matColor: (h.object as THREE.Mesh).material ? ((h.object as THREE.Mesh).material as THREE.MeshBasicMaterial).color?.getHexString?.() : undefined,
      matTransparent: ((h.object as THREE.Mesh).material as THREE.MeshBasicMaterial | undefined)?.transparent,
      matVisible: ((h.object as THREE.Mesh).material as THREE.MeshBasicMaterial | undefined)?.visible,
      objVisible: h.object.visible,
      geo: (h.object as THREE.Mesh).geometry?.type,
      dist: +h.distance.toFixed(2),
      world: [+h.point.x.toFixed(2), +h.point.y.toFixed(2), +h.point.z.toFixed(2)],
      parent: h.object.parent?.type,
      parentName: h.object.parent?.name || '',
    }))
  }

  camera = new THREE.PerspectiveCamera(42, w / Math.max(1, h), 0.1, 400)
  // 初始视角：东南 45° 正对 LOGO 切角面（正面朝向观察者），默认不旋转
  camera.position.set(15.5, 10.5, 15.5)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true })
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
  buildSelectedHighlight()
  for (const h of floorHits) buildingGroup.add(h)
  buildingGroup.add(hoverHighlight!)
  buildingGroup.add(selectedHighlight!)
  updateSelectedHighlight(props.selectedFloor ?? null)
  logoMesh = buildLogo()
  logoMesh.visible = !rawMode.value
  buildingGroup.add(logoMesh)
  scene.add(buildingGroup)

  // 拾取
  raycaster = new THREE.Raycaster()
  buildDragSources()
  hideDragTemplates()

  // 控制器（参数与原 Building3D 一致）
  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.target.set(0, (FLOOR_COUNT - 5) * SLAB / 2 + FLOOR_H / 2, 0)
  controls.maxPolarAngle = Math.PI * 0.6
  controls.minDistance = 8
  controls.maxDistance = 60

  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', onPointerLeave)
  renderer.domElement.addEventListener('click', onPointerClick)

  applyPreset(preset.value)
  animate()
}

function animate() {
  animId = requestAnimationFrame(animate)
  if (buildingGroup && autoRotate.value) {
    buildingGroup.rotation.y += 0.004 * rotateSpeed.value
  }
  // 编辑模式：模板格子轻微上下浮动，提示「可拖拽」
  if (dragSourceGroup && dragSourceGroup.visible && !activeDragSource) {
    dragSourceGroup.position.y = Math.sin(Date.now() * 0.002) * 0.06
  }
  // 楼层悬停凸出动画：悬停层水平放大（Y 固定），其余层平滑缩回
  const TARGET_SCALE = 1.06
  for (let i = 0; i < floorGroups.length; i++) {
    const g = floorGroups[i]
    if (!g) continue
    const level = i + 1
    const target = level === hoverScaleFloor ? TARGET_SCALE : 1
    // 平滑插值逼近（指数缓动）
    const k = 0.16
    g.scale.x += (target - g.scale.x) * k
    g.scale.z += (target - g.scale.z) * k
    g.scale.y = 1
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
  // 复位回到东南正面（LOGO 面），目标点对准建筑中心（含地下层）
  camera.position.set(15.5, 10.5, 15.5)
  controls.target.set(0, (FLOOR_COUNT - 5) * SLAB / 2 + FLOOR_H / 2, 0)
  controls.update()
}

/** 切换控制面板显隐（由父组件左上角提示文字连点 3 次触发） */
function togglePanel() {
  panelVisible.value = !panelVisible.value
}

defineExpose({ togglePanel })

// ---- 控制面板状态跨页面同步（PC 端 ↔ 大屏 ?ls=） ----
/** localStorage 键：控制面板所有功能状态，供大屏实时同步 */
const FACADE_STATE_KEY = '333-iot-console-facade-state'

interface FacadeState {
  autoRotate: boolean
  rotateSpeed: number
  glassOpacity: number
  showOutline: boolean
  preset: 'day' | 'dusk' | 'night'
  autoPreset: boolean
  windowOrientation: 'vertical' | 'horizontal'
  windowWidthRatio: number
  windowHeightRatio: number
  cellWindows: Record<string, boolean>
  showFloorLines: boolean
  showColLines: boolean
  rawMode: boolean
  metric: EnvMetric
  cellClickEnabled: boolean
  debugEnabled: boolean
}

function persistFacadeState() {
  try {
    const s: FacadeState = {
      autoRotate: autoRotate.value,
      rotateSpeed: rotateSpeed.value,
      glassOpacity: glassOpacity.value,
      showOutline: showOutline.value,
      preset: preset.value,
      autoPreset: autoPreset.value,
      windowOrientation: windowOrientation.value,
      windowWidthRatio: windowWidthRatio.value,
      windowHeightRatio: windowHeightRatio.value,
      cellWindows: cellWindows.value,
      showFloorLines: showFloorLines.value,
      showColLines: showColLines.value,
      rawMode: rawMode.value,
      metric: metric.value,
      cellClickEnabled: cellClickEnabled.value,
      debugEnabled: debugEnabled.value,
    }
    localStorage.setItem(FACADE_STATE_KEY, JSON.stringify(s))
  } catch { /* 静默 */ }
}

function applyFacadeState(s: Partial<FacadeState>) {
  if (typeof s.autoRotate === 'boolean') autoRotate.value = s.autoRotate
  if (typeof s.rotateSpeed === 'number') rotateSpeed.value = s.rotateSpeed
  if (typeof s.glassOpacity === 'number') glassOpacity.value = s.glassOpacity
  if (typeof s.showOutline === 'boolean') showOutline.value = s.showOutline
  if (s.preset === 'day' || s.preset === 'dusk' || s.preset === 'night') preset.value = s.preset
  if (typeof s.autoPreset === 'boolean') autoPreset.value = s.autoPreset
  if (s.windowOrientation === 'vertical' || s.windowOrientation === 'horizontal') windowOrientation.value = s.windowOrientation
  if (typeof s.windowWidthRatio === 'number') windowWidthRatio.value = s.windowWidthRatio
  if (typeof s.windowHeightRatio === 'number') windowHeightRatio.value = s.windowHeightRatio
  if (s.cellWindows && typeof s.cellWindows === 'object') cellWindows.value = { ...s.cellWindows }
  if (typeof s.showFloorLines === 'boolean') showFloorLines.value = s.showFloorLines
  if (typeof s.showColLines === 'boolean') showColLines.value = s.showColLines
  if (typeof s.rawMode === 'boolean') rawMode.value = s.rawMode
  if (s.metric === 'temperature' || s.metric === 'humidity') metric.value = s.metric
  if (typeof s.cellClickEnabled === 'boolean') cellClickEnabled.value = s.cellClickEnabled
  if (typeof s.debugEnabled === 'boolean') debugEnabled.value = s.debugEnabled
}

function loadFacadeState() {
  try {
    const raw = localStorage.getItem(FACADE_STATE_KEY)
    if (!raw) return
    applyFacadeState(JSON.parse(raw))
  } catch { /* 静默 */ }
}

/** 大屏 / 另一标签页修改控制面板状态时实时同步 */
function onFacadeStorage(e: StorageEvent) {
  if (e.key !== FACADE_STATE_KEY || e.newValue == null) return
  try {
    applyFacadeState(JSON.parse(e.newValue))
  } catch { /* 静默 */ }
}

// 控制面板任意功能变化都持久化，供大屏同步
watch(
  [autoRotate, rotateSpeed, glassOpacity, showOutline, preset, autoPreset, windowOrientation, windowWidthRatio, windowHeightRatio, showFloorLines, showColLines, rawMode, metric, cellClickEnabled, debugEnabled],
  () => persistFacadeState(),
)
watch(cellWindows, () => persistFacadeState(), { deep: true })

// ---- 控件联动 ----

watch(preset, (v) => applyPreset(v))

watch(glassOpacity, (v) => {
  if (windowGlassMat) windowGlassMat.opacity = v
})

watch(showOutline, (v) => {
  if (outlineLines) outlineLines.visible = v
})

// ---- 幕墙窗户配置变更触发重建 ----
let rebuildTimer: ReturnType<typeof setTimeout> | null = null

function scheduleRebuild() {
  if (rebuildTimer) clearTimeout(rebuildTimer)
  rebuildTimer = setTimeout(() => {
    rebuildTimer = null
    rebuildBuilding()
  }, 60)
}

watch([windowOrientation, windowWidthRatio, windowHeightRatio], () => {
  scheduleRebuild()
  persistConfig()
})

watch(showFloorLines, () => {
  scheduleRebuild()
})

watch(showColLines, () => {
  scheduleRebuild()
})

watch(rawMode, () => {
  scheduleRebuild()
})

watch(cellWindows, () => {
  scheduleRebuild()
  persistConfig()
}, { deep: true })

function rebuildBuilding() {
  if (!scene || !buildingGroup) return
  // 移除旧建筑 mesh（保留 ground、floorHits、hoverHighlight、logo）
  const toRemove: THREE.Object3D[] = []
  for (const child of buildingGroup.children) {
    if (child === hoverHighlight || child === selectedHighlight) continue
    if (floorHits.includes(child as THREE.Mesh)) continue
    if ((child as any).__isGround || (child as any).__isLogo) continue
    toRemove.push(child)
  }
  const editing = editUnlocked.value
  for (const obj of toRemove) {
    buildingGroup.remove(obj)
    // 编辑模式的格子几何来自共享缓存（editGeos），不能 dispose；美化/原始状态幕墙几何为新建，可 dispose
    const geo = (obj as THREE.Mesh).geometry
    if (!editing && geo && !editGeos.has(geo)) geo.dispose()
  }
  // 编辑模式：用 DB building_cell 渲染可编辑格子；否则用快照（美化/原始状态）
  if (editing) {
    buildingGroup.add(buildEditingBuilding())
    buildHiddenCellOverlays()
    if (logoMesh) logoMesh.visible = false
  } else {
    buildingGroup.add(buildBuilding())
    if (logoMesh) logoMesh.visible = !rawMode.value
  }
}

async function loadConfig() {
  try {
    const { data } = await getFacadeConfig()
    if (data) {
      windowOrientation.value = data.orientation || 'vertical'
      windowWidthRatio.value = data.widthRatio ?? 0.4
      windowHeightRatio.value = data.heightRatio ?? 0.7
      cellWindows.value = data.cellWindows || {}
    }
  } catch { /* 后端未启动时静默 */ }
}

async function persistConfig() {  try {
    await saveFacadeConfig({
      orientation: windowOrientation.value,
      widthRatio: windowWidthRatio.value,
      heightRatio: windowHeightRatio.value,
      cellWindows: cellWindows.value,
    })
  } catch { /* 静默 */ }
}

function clearAllWindows() {
  cellWindows.value = {}
}

/** 拉取各楼层温湿度（level 为 3D 层号 1..11），供原始状态着色 */
async function fetchFloorEnv() {
  try {
    const { data } = await getFloorEnvironmentSummary()
    const env: Record<number, FloorEnvValue> = {}
    for (const row of data ?? []) {
      if (row.level == null || row.level < 1 || row.level > FLOOR_COUNT) continue
      env[row.level] = {
        temperature: row.temperature,
        humidity: row.humidity,
        deviceCount: row.device_count,
      }
    }
    floorEnv.value = env
    // 数据到达后重建（美化 / 原始状态均按温湿度着色）
    scheduleRebuild()
  } catch { /* 未接入数据时保持空，回退灰色 */ }
}

watch(metric, (v) => {
  emit('update:metric', v)
  scheduleRebuild()
})

watch(
  () => props.metric,
  (v) => {
    if (v && v !== metric.value) metric.value = v
  },
)

watch(
  () => props.selectedFloor,
  (v) => updateSelectedHighlight(v ?? null),
)

// 编辑模式下 DB 格子设置变化（增/删/撤回后父组件刷新）→ 重建可编辑建筑
watch(
  () => props.cellShapes,
  () => {
    if (editUnlocked.value) {
      scheduleRebuild()
      buildHiddenCellOverlays()
    }
  },
  { deep: true },
)

// ---- 温湿度图例（仿 /building-viewer 的 env-legend） ----
const legendRange = computed(() => envRange(floorEnv.value, metric.value))
const legendUnit = computed(() => (metric.value === 'humidity' ? '%RH' : '°C'))
const legendLabel = computed(() =>
  metric.value === 'humidity' ? t('building.metricHumidity') : t('building.metricTemperature'),
)
const LEGEND_BAND_COUNT = 4
const LEGEND_CELLS = computed(() =>
  metric.value === 'humidity' ? 10 : LEGEND_BAND_COUNT,
)
function legendCellColor(i: number) {
  if (metric.value === 'humidity') {
    const [min, max] = legendRange.value
    const t = (i - 0.5) / 10
    const value = min + t * (max - min)
    return envColorFor('humidity', value, min, max) ?? '#d9d5cc'
  }
  return TEMPERATURE_BAND_COLORS[i - 1] ?? '#d9d5cc'
}
const legendGradientStyle = computed(() => {
  if (metric.value === 'humidity') return ''
  return `linear-gradient(90deg, ${TEMPERATURE_GRADIENT_STOPS.join(', ')})`
})

function startDemo() {
  if (!host.value || scene) return
  loadFacadeState()
  initThreeJS()
  window.addEventListener('resize', onResize)
  loadConfig()
  fetchFloorEnv()
}

onMounted(() => {
  if (!host.value) return
  // 跨页面状态同步（PC 端 ↔ 大屏）：另一页面修改控制面板状态时实时应用
  window.addEventListener('storage', onFacadeStorage)
  if (props.loading) return
  startDemo()
})

watch(
  () => props.loading,
  (v) => {
    if (v === false) startDemo()
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('storage', onFacadeStorage)
  cancelAnimationFrame(animId)
  clearHover()
  if (feedbackTimer) clearTimeout(feedbackTimer)
  if (editModeToastTimer) clearTimeout(editModeToastTimer)
  if (autoSceneTimer) {
    clearInterval(autoSceneTimer)
    autoSceneTimer = undefined
  }
  window.removeEventListener('resize', onResize)
  document.removeEventListener('pointermove', onDragMove)
  document.removeEventListener('pointerup', endDragCell)
  document.removeEventListener('wheel', onDragWheel)
  document.removeEventListener('keydown', onDragKeyDown)
  renderer?.domElement.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement.removeEventListener('pointerleave', onPointerLeave)
  renderer?.domElement.removeEventListener('click', onPointerClick)
  controls?.dispose()
  pmrem?.dispose()
  renderer?.dispose()
  if (renderer?.domElement.parentElement) {
    renderer.domElement.parentElement.removeChild(renderer.domElement)
  }
  // 编辑模式隐藏格子占位资源
  if (scene && hiddenCellGroup) {
    scene.remove(hiddenCellGroup)
    hiddenCellGeos.forEach((g) => g.dispose())
    hiddenCellMaterials.forEach((m) => m.dispose())
  }
  // 编辑模式拖拽模板资源（geometry 来自共享缓存，不 dispose）
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
    dragPreviewMat?.dispose()
  }
  if (lastEditCellGeo) {
    lastEditCellGeo.dispose()
    lastEditCellGeo = null
  }
  editGeos = new Set()
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
  floorGroups = []
  floorInnerMats = []
  floorMeshes = []
  meshesByFloor.clear()
  hiddenCellGeos = []
  hiddenCellMaterials = []
  hiddenCellMeshes = []
  dragSourceMeshes = []
  hoverScaleFloor = 0
  innerMat = null
  windowGlassMat = null
  windowFrameMat = null
  outlineLines = null
  floorHits = []
  hoverHighlight = null
  hoverHighlightMat = null
  selectedHighlight = null
  selectedHighlightMat = null
})
</script>

<template>
  <div ref="host" class="facade3d">
    <!-- Loading overlay while data is being fetched -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <div class="loading-text">{{ t('building.loading') }}</div>
    </div>
    <!-- 控制面板 -->
    <div v-show="panelVisible" class="ctrl-panel">
      <div class="ctrl-title">{{ t('building.panelTitle') }}</div>
      <div class="ctrl-row">
        <label class="ctrl-label">{{ t('building.scene') }}</label>
        <div class="seg-group">
          <button
            v-for="p in (['day', 'dusk', 'night'] as const)"
            :key="p"
            class="seg-btn"
            :class="{ active: preset === p }"
            @click="preset = p"
          >
            {{ p === 'day' ? t('building.sceneDay') : p === 'dusk' ? t('building.sceneDusk') : t('building.sceneNight') }}
          </button>
        </div>
      </div>

      <!-- 自动场景：按本地日出/日落时间自动切换；关闭后回到日间 -->
      <div class="ctrl-row">
        <label class="ctrl-check">
          <input v-model="autoPreset" type="checkbox" />
          <span class="check-box"></span>
          <span class="check-text">{{ t('building.autoScene') }}</span>
        </label>
      </div>

      <!-- 窗户方向 -->
      <div class="ctrl-row">
        <label class="ctrl-label">{{ t('building.windowDirection') }}</label>
        <div class="seg-group">
          <button
            class="seg-btn"
            :class="{ active: windowOrientation === 'vertical' }"
            @click="windowOrientation = 'vertical'"
          >{{ t('building.windowVertical') }}</button>
          <button
            class="seg-btn"
            :class="{ active: windowOrientation === 'horizontal' }"
            @click="windowOrientation = 'horizontal'"
          >{{ t('building.windowHorizontal') }}</button>
        </div>
      </div>

      <!-- 窗户宽度 -->
      <div class="ctrl-row">
        <label class="ctrl-label">{{ t('building.windowWidth') }}</label>
        <input
          v-model.number="windowWidthRatio"
          class="ctrl-slider"
          type="range"
          min="0.15"
          max="0.9"
          step="0.05"
        />
        <span class="ctrl-value">{{ (windowWidthRatio * 100).toFixed(0) }}%</span>
      </div>

      <!-- 窗户高度 -->
      <div class="ctrl-row">
        <label class="ctrl-label">{{ t('building.windowHeight') }}</label>
        <input
          v-model.number="windowHeightRatio"
          class="ctrl-slider"
          type="range"
          min="0.15"
          max="0.95"
          step="0.05"
        />
        <span class="ctrl-value">{{ (windowHeightRatio * 100).toFixed(0) }}%</span>
      </div>

      <!-- 原始状态 -->
      <div class="ctrl-row">
        <label class="ctrl-check">
          <input v-model="rawMode" type="checkbox" />
          <span class="check-box"></span>
          <span class="check-text">{{ t('building.rawMode') }}</span>
        </label>
      </div>

      <!-- 按温湿度着色（美化 / 原始状态通用） -->
      <div class="ctrl-row">
        <label class="ctrl-label">{{ t('building.coloring') }}</label>
        <div class="seg-group">
          <button
            class="seg-btn"
            :class="{ active: metric === 'temperature' }"
            @click="metric = 'temperature'"
          >{{ t('building.metricTemperature') }}</button>
          <button
            class="seg-btn"
            :class="{ active: metric === 'humidity' }"
            @click="metric = 'humidity'"
          >{{ t('building.metricHumidity') }}</button>
        </div>
      </div>

      <!-- 点击墙面创建窗户 开关 -->
      <div class="ctrl-row">
        <label class="ctrl-check">
          <input v-model="cellClickEnabled" type="checkbox" />
          <span class="check-box"></span>
          <span class="check-text">{{ t('building.clickCreateWindows') }}</span>
        </label>
      </div>

      <!-- 批量操作 -->
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" :class="{ on: showFloorLines }" @click="showFloorLines = !showFloorLines">
          {{ showFloorLines ? t('building.hideFloorLines') : t('building.showFloorLines') }}
        </button>
        <button type="button" class="ctrl-btn" :class="{ on: showColLines }" @click="showColLines = !showColLines">
          {{ showColLines ? t('building.hideColLines') : t('building.showColLines') }}
        </button>
      </div>
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" @click="clearAllWindows">{{ t('building.clearAll') }}</button>
      </div>

      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" :class="{ on: showOutline }" @click="showOutline = !showOutline">
          {{ showOutline ? t('building.outlineOff') : t('building.outlineOn') }}
        </button>
        <button type="button" class="ctrl-btn" :class="{ on: autoRotate }" @click="autoRotate = !autoRotate">
          {{ autoRotate ? t('building.rotatePause') : t('building.rotatePlay') }}
        </button>
      </div>
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" @click="resetView">{{ t('building.resetView') }}</button>
      </div>
      <div v-if="autoRotate" class="ctrl-row">
        <label class="ctrl-label">{{ t('building.rotateSpeed') }}</label>
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
      <div class="ctrl-hint">{{ t('building.clickFloorHint') }}</div>

      <div class="ctrl-divider"></div>

      <!-- 调试信息开关（控制左下角坐标信息） -->
      <div class="ctrl-row">
        <label class="ctrl-check">
          <input v-model="debugEnabled" type="checkbox" />
          <span class="check-box"></span>
          <span class="check-text">{{ t('building.debugInfo') }}</span>
        </label>
      </div>

      <!-- 格子编辑（整合自 /building-viewer 编辑面板：添加 / 删除 / 撤回 / 完成） -->
      <div class="ctrl-title edit-title">{{ t('building.cellEditor') }}</div>
      <div class="ctrl-row">
        <button type="button" class="ctrl-btn" :class="{ on: editUnlocked }" @click="toggleEditMode">
          {{ editUnlocked ? t('building.exitEdit') : t('building.editCells') }}
        </button>
      </div>
      <div v-if="editUnlocked" class="edit-actions">
        <button type="button" class="edit-btn add" :class="{ active: editToolMode === 'add' }" @click="toggleToolMode('add')">{{ t('building.addBtn') }}</button>
        <button type="button" class="edit-btn del" :class="{ active: editToolMode === 'delete' }" @click="toggleToolMode('delete')">{{ t('building.deleteBtn') }}</button>
        <button type="button" class="edit-btn undo" @click="handleUndo">{{ t('building.undoBtn') }}</button>
        <button type="button" class="edit-btn close" @click="onDoneClick">{{ t('building.doneBtn') }}</button>
      </div>
      <div v-if="editUnlocked && editToolMode === 'add'" class="edit-hint">{{ t('building.editAddHint') }}</div>
      <div v-else-if="editUnlocked && editToolMode === 'delete'" class="edit-hint">{{ t('building.editDeleteHint') }}</div>
      <div v-if="editFeedback" class="edit-feedback">{{ editFeedback }}</div>
    </div>
    <!-- 楼层悬停提示 -->
    <div
      v-show="toastVisible && hoveredFloor != null"
      class="floor-toast"
      :style="toastStyle"
    >
      <div class="toast-level">{{ floorLabel(hoveredFloor ?? 0) }}</div>
      <div class="toast-devices">{{ t('building.toastDevices', { n: deviceCountFor(hoveredFloor ?? 0) }) }}</div>
    </div>
    <!-- 调试提示 -->
    <div
      v-show="debugVisible"
      class="debug-tooltip"
    >
      <pre>{{ debugInfo }}</pre>
    </div>
    <!-- 温湿度图例（仿 /building-viewer 的 env-legend） -->
    <div v-if="!editUnlocked" class="env-legend">
      <div class="legend-head">
        <span class="legend-title">{{ legendLabel }}</span>
        <span class="legend-unit">{{ legendUnit }}</span>
        <span class="legend-live" aria-hidden="true" />
      </div>
      <div
        v-if="metric === 'temperature'"
        class="legend-bar legend-bar-gradient"
        role="img"
        :style="{ background: legendGradientStyle }"
      />
      <div v-else class="legend-bar" role="img">
        <span v-for="i in LEGEND_CELLS" :key="i" class="legend-cell" :style="{ background: legendCellColor(i) }" />
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
    <!-- 编辑模式提示 -->
    <transition name="fade">
      <div v-if="editModeToast" class="edit-mode-toast">
        {{ t('building.editModeOn') }}
      </div>
    </transition>
    <!-- 添加模式拖拽提示 -->
    <div v-if="editUnlocked && editToolMode === 'add'" class="drag-source-toolbar">
      <span class="drag-source-hint">{{ t('building.dragSourceHint') }}</span>
    </div>
    <!-- 退出编辑确认框 -->
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
  max-height: calc(100% - 24px);
  overflow-y: auto;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(13, 13, 13, 0.88);
  border: 1px solid rgba(196, 165, 116, 0.45);
  backdrop-filter: blur(8px);
  color: #fff;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
  user-select: none;
}

.ctrl-panel::-webkit-scrollbar {
  width: 6px;
}

.ctrl-panel::-webkit-scrollbar-thumb {
  background: rgba(196, 165, 116, 0.35);
  border-radius: 3px;
}

.ctrl-panel::-webkit-scrollbar-track {
  background: transparent;
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

.ctrl-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.ctrl-check input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.check-box {
  width: 16px;
  height: 16px;
  border-radius: 4px;
  border: 1px solid rgba(196, 165, 116, 0.7);
  background: rgba(255, 255, 255, 0.06);
  position: relative;
  flex: 0 0 auto;
  transition: background 0.15s;
}

.ctrl-check input:checked + .check-box {
  background: #c4a574;
}

.ctrl-check input:checked + .check-box::after {
  content: '';
  position: absolute;
  left: 5px;
  top: 2px;
  width: 4px;
  height: 8px;
  border: solid #20201c;
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.check-text {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.85);
}

.ctrl-check input:checked ~ .check-text {
  color: #f5ead7;
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

.ctrl-hint {
  margin-top: 6px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.5);
  text-align: center;
}

/* 加载遮罩（等待父组件数据就绪后再初始化 3D） */
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
  background: #e9e5dc;
  z-index: 100;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(196, 165, 116, 0.25);
  border-top-color: #c4a574;
  border-radius: 50%;
  animation: facade-spin 1s linear infinite;
}

@keyframes facade-spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  margin-top: 12px;
  font-size: 14px;
  color: #6b6b6b;
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

.toast-devices {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.82);
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

/* 控制面板分隔线与编辑区块 */
.ctrl-divider {
  height: 1px;
  margin: 10px 0;
  background: rgba(255, 255, 255, 0.12);
}

.ctrl-title.edit-title {
  margin-top: 10px;
  color: #d4b88a;
}

.edit-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}

.edit-btn {
  padding: 6px 0;
  font-size: 12px;
  font-weight: 600;
  border-radius: 4px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  cursor: pointer;
  transition: all 0.15s ease;
}

.edit-btn.add {
  background: rgba(76, 175, 80, 0.22);
  border-color: rgba(76, 175, 80, 0.5);
  color: #81c784;
}

.edit-btn.add:hover,
.edit-btn.add.active {
  background: rgba(76, 175, 80, 0.45);
  border-color: #4caf50;
  color: #fff;
}

.edit-btn.del {
  background: rgba(244, 67, 54, 0.18);
  border-color: rgba(244, 67, 54, 0.45);
  color: #e57373;
}

.edit-btn.del:hover,
.edit-btn.del.active {
  background: rgba(244, 67, 54, 0.4);
  border-color: #f44336;
  color: #fff;
}

.edit-btn.undo {
  background: rgba(156, 39, 176, 0.18);
  border-color: rgba(156, 39, 176, 0.45);
  color: #ce93d8;
}

.edit-btn.undo:hover {
  background: rgba(156, 39, 176, 0.4);
  border-color: #9c27b0;
  color: #fff;
}

.edit-btn.close {
  background: rgba(196, 165, 116, 0.22);
  border-color: rgba(196, 165, 116, 0.55);
  color: #f5ead7;
}

.edit-btn.close:hover {
  background: rgba(196, 165, 116, 0.5);
  border-color: #c4a574;
  color: #fff;
}

.edit-hint {
  margin-bottom: 8px;
  padding: 5px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #cfe9e9;
  font-size: 11px;
  line-height: 1.5;
  text-align: center;
}

.edit-feedback {
  margin-bottom: 8px;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #81d4fa;
  font-size: 11px;
  text-align: center;
}

/* 温湿度图例（仿 /building-viewer 的 env-legend） */
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

/* 编辑模式提示 */
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

/* 添加模式拖拽提示（左下角） */
.drag-source-toolbar {
  position: absolute;
  z-index: 7;
  left: 10px;
  bottom: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  pointer-events: none;
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
}

/* 退出编辑确认框 */
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

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
