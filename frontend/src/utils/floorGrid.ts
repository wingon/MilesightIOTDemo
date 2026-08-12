/**
 * 樓層平面資料驅動的幾何原型（Rect / Cylinder / Triangle / Hidden）。
 *
 * 幾何形狀已按類型拆分為獨立工具檔：
 *  - ./floorGridRect     → createRectGeometry（長方體）
 *  - ./floorGridCylinder → createCylinderGeometry（圓柱）
 *  - ./floorGridTriangle → createTriangleGeometry（三角形）
 *  - ./floorGridHidden   → isHiddenType（隱藏類型判斷）
 * 本檔保留公共部分並統一轉發（re-export），對外 import 路徑不變。
 *
 * 職責劃分（本檔）：
 *  - decorationGeometry：只管「外觀」，按溫濕度算顏色或用固定色，產出 MeshStandardMaterial。
 *  - gridCellToWorld / parseRotation：把 griddata 的 xAxis/yAxis/rotate 轉成世界座標與旋轉。
 *  - createGeometryByType：根據 GridType 動態建立幾何體（Building3D 使用）。
 *  - disposeGeometryCache：統一釋放四種類型的共享幾何。
 *
 * 資料（griddata）只決定：放什麼（type）、放哪（xAxis/yAxis）、怎麼轉（rotate）。
 */
import * as THREE from 'three'
import {
  INTERIOR_CELLS,
  cellToWorld,
  shouldExcludeCell,
} from '@/utils/buildingDemo'
import {
  HUMIDITY_RANGE_DEFAULT,
  TEMP_RANGE_DEFAULT,
  humidityColor,
  temperatureColor,
} from '@/utils/envColor'
import {
  createRectGeometry,
  RECT_LENGTH,
  RECT_WIDTH,
  disposeRectGeometryCache,
} from './floorGridRect'
import {
  createCylinderGeometry,
  CYLINDER_RADIUS,
  disposeCylinderGeometryCache,
} from './floorGridCylinder'
import {
  createTriangleGeometry,
  disposeTriangleGeometryCache,
} from './floorGridTriangle'
import { isHiddenType } from './floorGridHidden'

export {
  createRectGeometry,
  RECT_LENGTH,
  RECT_WIDTH,
  disposeRectGeometryCache,
  createCylinderGeometry,
  CYLINDER_RADIUS,
  disposeCylinderGeometryCache,
  createTriangleGeometry,
  disposeTriangleGeometryCache,
  isHiddenType,
}

/** 格子形狀類型：'Rect'(長方形) | 'Cylinder'(圓柱) | 'Triangle'(三角形) | 'Hidden'(隱藏不渲染) */
export type GridType = 'Rect' | 'Cylinder' | 'Triangle' | 'Hidden'

/**
 * 格子形狀設定接口
 *
 * 定義某個格子在某一層的形狀。用於 Building3D 的 :cell-shapes prop，
 * 取代原本的硬編碼三角形邏輯。
 *
 * 使用示例：
 *   { row: 8, col: 11, floor: 3, shape: 'Triangle' }  // 3樓(G/F) 的 (8,11) 顯示為三角形
 *   { row: 5, col: 5, floor: 0, shape: 'Cylinder' }   // 所有樓層的 (5,5) 顯示為圓柱
 */
export interface CellShapeConfig {
  /** 行號（1-based，1~8，從南到北） */
  row: number
  /** 列號（1-based，1~12，從西到東） */
  col: number
  /**
   * 樓層（3D 層號）：
   *   0 = 所有樓層
   *   1 = B2/F, 2 = B1/F, 3 = G/F, 4 = 1/F ... 10 = 7/F, 11 = ROOF
   */
  floor: number
  /** 形狀類型：'Rect'(長方形) | 'Cylinder'(圓柱) | 'Triangle'(三角形) | 'Hidden'(隱藏不渲染) */
  shape: GridType
  /** 可選：自訂顏色（如 '#4CAF50'、'red'），不傳則使用樓層預設色 */
  color?: string
  /** 可選：旋轉角度 'x,y,z'（弧度），如 '0,1.57,0' 表示繞 Y 軸旋轉 90° */
  rotation?: string
  /** 可選：自訂高度（世界單位），不傳則使用預設樓層高度 */
  height?: number
}

/** 一個格子：座標用字串（與資料來源一致），rotate 為弧度 'x,y,z'（'0,0,0' 表示不轉） */
export interface GridCell {
  xAxis: string
  yAxis: string
  type: GridType
  rotate: string
}

export interface FloorGridData {
  floor: string
  griddata: GridCell[]
}

/* ------------------------------------------------------------------ */
/* 四種形狀的幾何工具已拆分至獨立檔：                                  */
/*   floorGridRect / floorGridCylinder / floorGridTriangle / floorGridHidden */
/* ------------------------------------------------------------------ */

/**
 * 釋放全部共享幾何（onBeforeUnmount 時調用）。
 * 註：各類型快取為模組層級，假定同一頁面同時只掛載一個 Floor3D 實例；
 * 若多實例並存，請把快取提升為實例層級。
 */
export function disposeGeometryCache(): void {
  disposeRectGeometryCache()
  disposeCylinderGeometryCache()
  disposeTriangleGeometryCache()
}

/* ------------------------------------------------------------------ */
/* 外觀：溫濕度 / 固定色 → MeshStandardMaterial（只管材質）             */
/* ------------------------------------------------------------------ */

export interface DecorationOptions {
  /** 溫度（℃），null/undefined 時不參與配色 */
  temperature?: number | null
  /** 濕度（%），null/undefined 時不參與配色 */
  humidity?: number | null
  /** 固定色優先於溫濕度；不傳時按溫濕度計算，都無資料時用回退色 */
  fixedColor?: string
}

/** 無任何資料時的回退色 */
export const FALLBACK_COLOR = '#d8d2c8'

/**
 * 依感測資料（溫/濕度）或固定色產生材質。
 * 優先級：fixedColor > temperature > humidity > 回退色。
 */
export function decorationGeometry(opts: DecorationOptions = {}): THREE.MeshStandardMaterial {
  const { temperature, humidity, fixedColor } = opts

  let color: string
  if (fixedColor) {
    color = fixedColor
  } else if (temperature != null) {
    color = temperatureColor(temperature, TEMP_RANGE_DEFAULT[0], TEMP_RANGE_DEFAULT[1]) ?? FALLBACK_COLOR
  } else if (humidity != null) {
    color = humidityColor(humidity, HUMIDITY_RANGE_DEFAULT[0], HUMIDITY_RANGE_DEFAULT[1]) ?? FALLBACK_COLOR
  } else {
    color = FALLBACK_COLOR
  }

  return new THREE.MeshStandardMaterial({
    color,
    roughness: 0.45,
    metalness: 0.12,
    transparent: true,
    opacity: 0.92,
  })
}

/* ------------------------------------------------------------------ */
/* 座標與旋轉                                                          */
/* ------------------------------------------------------------------ */

/**
 * griddata 座標 → 世界座標。
 * 約定：xAxis 對應建築的行（南北/z 方向），yAxis 對應列（東西/x 方向）；
 * griddata 為 0-based，內部復用 buildingDemo 的 1-based cellToWorld。
 */
export function gridCellToWorld(cell: Pick<GridCell, 'xAxis' | 'yAxis'>): { x: number; z: number } {
  const row = Number(cell.xAxis) + 1
  const col = Number(cell.yAxis) + 1
  return cellToWorld(row, col)
}

/** 'x,y,z'（弧度）→ THREE.Euler，'0,0,0' 表示不轉。 */
export function parseRotation(rotate: string): THREE.Euler {
  const toNum = (s: string): number => {
    const n = Number(s.trim())
    return Number.isFinite(n) ? n : 0
  }
  const [x = 0, y = 0, z = 0] = rotate.split(',').map(toNum)
  return new THREE.Euler(x, y, z)
}

/* ------------------------------------------------------------------ */
/* 預設樓層資料：floor '8'（3D 層號 8 = 5F）示例，可整體替換為接口資料 */
/* ------------------------------------------------------------------ */

const CYLINDER_DEMO_CELLS: Array<[row: number, col: number]> = [
  [4, 9],
  [5, 9],
  [5, 5],
  [5, 6],
  [7, 8],
]

/** 由現有樓層平面產生 floor '8' 的示例資料；部分格子演示 Cylinder 原型。 */
function buildDefaultGridData(): FloorGridData {
  const cells: GridCell[] = []
  for (const c of INTERIOR_CELLS) {
    if (shouldExcludeCell(8, c.row, c.col)) continue
    cells.push({
      xAxis: String(c.row - 1),
      yAxis: String(c.col - 1),
      type: 'Rect',
      rotate: '0,0,0',
    })
  }
  for (const [row, col] of CYLINDER_DEMO_CELLS) {
    const index = cells.findIndex(
      (c) => Number(c.xAxis) === row - 1 && Number(c.yAxis) === col - 1,
    )
    if (index >= 0) cells[index] = { ...cells[index], type: 'Cylinder' }
  }
  return { floor: '8', griddata: cells }
}

export const DEFAULT_GRIDDATA: FloorGridData = buildDefaultGridData()

/** 預設房間高度（世界單位） */
export const ROOM_H = 1.35

/**
 * 根據 GridType 動態建立幾何體（通用工廠函數）
 *
 * 用於 Building3D 根據 CellShapeConfig 設定產生對應的 3D 形狀。
 * 內部調用對應的 createXxxGeometry 函數，共享幾何快取。
 *
 * @param type   - 形狀類型：'Rect' | 'Cylinder' | 'Triangle'（'Hidden' 應先以 isHiddenType 過濾）
 * @param size   - 格子尺寸（世界單位），通常為 cellSize = CELL_SIZE * 0.96
 * @param height - 拉伸高度（世界單位），通常為 FLOOR_H
 * @returns 對應類型的 BufferGeometry（已快取復用）
 *
 * 使用示例（Building3D.vue）：
 *   const geo = createGeometryByType('Triangle', cellSize, FLOOR_H)
 *   const mesh = new THREE.Mesh(geo, material)
 */
export function createGeometryByType(
  type: GridType,
  size: number,
  height: number,
): THREE.BufferGeometry {
  switch (type) {
    case 'Cylinder':
      return createCylinderGeometry(size / 2, height)
    case 'Triangle':
      return createTriangleGeometry(size, height)
    case 'Rect':
    default:
      return createRectGeometry(size, size, height)
  }
}
