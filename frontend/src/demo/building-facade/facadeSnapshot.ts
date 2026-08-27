/**
 * 1:1 建筑轮廓快照 —— 与 /building-viewer 页面的 3D 楼宇完全一致。
 *
 * 数据来源：WingOnIOT.building_cell（MariaDB，2026-08-27 导出），
 * 即 /building-viewer 页面 GET /api/v1/building/cell-shapes 的同一份数据。
 *
 * - 网格：7 行（row 1~7，南→北）× 12 列（col 1~12，西→东）
 * - 楼层：11 层（3D level 1~11，自下而上），层高 0.76 + 层缝 0.08
 * - 格子尺寸：CELL_SIZE × 0.96（与原 Building3D.vue 的 cellSize 一致，含 4% 格缝）
 * - 世界坐标：x = (col-6.5)×CELL_SIZE，z = (row-4.5)×CELL_SIZE（与 DB 的 x/y 一致）
 */

/** 与原页面 buildingDemo.ts 的 CELL_SIZE 一致 */
export const CELL_SIZE = 1.15
/** 楼层总数（B2/B1/G/1F~7F/ROOF） */
export const FLOOR_COUNT = 11
/** 楼层高度（格子高度） */
export const FLOOR_H = 0.76
/** 楼层间隙 */
export const FLOOR_GAP = 0.08
/** 楼层步进（层高 + 层缝） */
export const SLAB = FLOOR_H + FLOOR_GAP
/** DB 中 (7,1) 三角形的 Y 轴旋转（弧度，约 270°） */
export const TRI_ROT_Y = 4.7124

/** 格子形状：矩形 | 三角形 */
export type CellShape = 'Rect' | 'Triangle'

export interface SnapCell {
  row: number
  col: number
  shape: CellShape
  /** 三角形绕 Y 轴旋转角（弧度），矩形为 0 */
  rotY: number
}

export interface SnapFloor {
  /** 3D 层号 1~11 */
  level: number
  cells: SnapCell[]
}

/** 格子中心的世界坐标（与 DB building_cell.x / .y 完全一致） */
export function cellCenter(row: number, col: number) {
  return { x: (col - 6.5) * CELL_SIZE, z: (row - 4.5) * CELL_SIZE }
}

/** 楼层中心的 y 坐标（与 DB building_cell.z 一致：0.38, 1.22, 2.06 ...） */
export function floorCenterY(level: number) {
  return (level - 1) * SLAB + FLOOR_H / 2
}

/** 3D 层号 → 楼层名（与原页面 floorName 一致） */
export function floorName(level: number): string {
  if (level <= 2) return `B${3 - level}`
  if (level === 3) return 'G'
  if (level === FLOOR_COUNT) return 'ROOF'
  return String(level - 3)
}

/*
 * 三种楼层布局模式（逐层从 building_cell 导出的精确快照）：
 *  字符含义：'#'=Rect  'A'=Triangle(无旋转)  'B'=Triangle(rotY=270°)  '.'=无格子
 *
 * P1（83 格）：仅缺 (7,12)；三角形 (6,12)A、(7,1)B、(7,11)A —— 用于 3D 层 1、2、4
 * P2（82 格）：缺 (5,4)、(7,12)；三角形同 P1                  —— 用于 3D 层 3、5、6、7
 * P3（78 格）：缺 (6,1)、(6,11)、(6,12)、(7,1)、(7,11)、(7,12)；无三角形 —— 用于 3D 层 8~11
 */
const P1 = [
  '############',
  '############',
  '############',
  '############',
  '############',
  '###########A',
  'B#########A.',
]

const P2 = [
  '############',
  '############',
  '############',
  '############',
  '###.########',
  '###########A',
  'B#########A.',
]

const P3 = [
  '############',
  '############',
  '############',
  '############',
  '############',
  '.#########..',
  '.#########..',
]

/** 3D 层号 → 布局模式（对照 building_cell 每层导出结果） */
const LAYOUT_BY_LEVEL: Record<number, string[]> = {
  1: P1,
  2: P1,
  3: P2,
  4: P1,
  5: P2,
  6: P2,
  7: P2,
  8: P3,
  9: P3,
  10: P3,
  11: P3,
}

/** 全部 11 层的格子快照（合计 889 格，与 building_cell 导出数一致） */
export const FLOORS: SnapFloor[] = Array.from({ length: FLOOR_COUNT }, (_, i) => {
  const level = i + 1
  const pattern = LAYOUT_BY_LEVEL[level]
  const cells: SnapCell[] = []
  for (let r = 0; r < pattern.length; r++) {
    const line = pattern[r]
    for (let c = 0; c < line.length; c++) {
      const ch = line[c]
      if (ch === '.') continue
      cells.push({
        row: r + 1,
        col: c + 1,
        shape: ch === '#' ? 'Rect' : 'Triangle',
        rotY: ch === 'B' ? TRI_ROT_Y : 0,
      })
    }
  }
  return { level, cells }
})
