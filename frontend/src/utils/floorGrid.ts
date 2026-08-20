/**
 * Floor-plan-data-driven geometry primitives (Rect / Cylinder / Triangle / Hidden).
 *
 * Geometry shapes are split into per-type tool files:
 *  - ./floorGridRect     → createRectGeometry (box)
 *  - ./floorGridCylinder → createCylinderGeometry (cylinder)
 *  - ./floorGridTriangle → createTriangleGeometry (triangle)
 *  - ./floorGridHidden   → isHiddenType (hidden-type check)
 * This file keeps the common parts and re-exports them so external import paths stay unchanged.
 *
 * Responsibilities (this file):
 *  - decorationGeometry: only handles "appearance" — colors from temperature/humidity or a fixed color, producing a MeshStandardMaterial.
 *  - gridCellToWorld / parseRotation: convert griddata's xAxis/yAxis/rotate to world coordinates and rotation.
 *  - createGeometryByType: dynamically create a geometry from a GridType (used by Building3D).
 *  - disposeGeometryCache: release the shared geometries of all four types.
 *
 * The data (griddata) only decides: what to place (type), where (xAxis/yAxis), and how to rotate (rotate).
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

/** Cell shape type: 'Rect'(rectangle) | 'Cylinder' | 'Triangle' | 'Hidden'(not rendered) */
export type GridType = 'Rect' | 'Cylinder' | 'Triangle' | 'Hidden'

/**
 * Cell shape config interface
 *
 * Defines a cell's shape on a given floor. Used for the Building3D :cell-shapes prop,
 * replacing the old hard-coded triangle logic.
 *
 * Example:
 *   { row: 8, col: 11, floor: 3, shape: 'Triangle' }  // cell (8,11) on floor 3 (G/F) renders as a triangle
 *   { row: 5, col: 5, floor: 0, shape: 'Cylinder' }   // cell (5,5) on every floor renders as a cylinder
 */
export interface CellShapeConfig {
  /** Row number (1-based, 1~8, south to north) */
  row: number
  /** Column number (1-based, 1~12, west to east) */
  col: number
  /**
   * Floor (3D level):
   *   0 = all floors
   *   1 = B2/F, 2 = B1/F, 3 = G/F, 4 = 1/F ... 10 = 7/F, 11 = ROOF
   */
  floor: number
  /** DB floor.id (used for operations such as updating rotation_xyz) */
  floor_id?: number
  /** Shape type: 'Rect'(rectangle) | 'Cylinder' | 'Triangle' | 'Hidden'(not rendered) */
  shape: GridType
  /** Optional: custom color (e.g. '#4CAF50', 'red'); when absent, uses the floor default color */
  color?: string
  /** Optional: rotation 'x,y,z' (radians), e.g. '0,1.57,0' rotates 90° around the Y axis */
  rotation?: string
  /** Optional: custom height (world units); when absent, uses the default floor height */
  height?: number
  /** Optional: world coordinate x (column direction), from building_cell.x */
  x?: number
  /** Optional: world coordinate y (row direction), from building_cell.y */
  y?: number
  /** Optional: world coordinate z (vertical height), from building_cell.z */
  z?: number
}

/** A cell: coordinates as strings (matching the data source), rotate is 'x,y,z' in radians ('0,0,0' = no rotation) */
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
/* Geometry tools for the four shapes split into separate files:       */
/*   floorGridRect / floorGridCylinder / floorGridTriangle / floorGridHidden */
/* ------------------------------------------------------------------ */

/**
 * Release all shared geometries (call on beforeUnmount).
 * Note: each type cache is module-level and assumes only one Floor3D instance
 * is mounted at a time; with multiple instances, hoist the cache to instance level.
 */
export function disposeGeometryCache(): void {
  disposeRectGeometryCache()
  disposeCylinderGeometryCache()
  disposeTriangleGeometryCache()
}

/* ------------------------------------------------------------------ */
/* Appearance: temperature/humidity or fixed color → MeshStandardMaterial (material only) */
/* ------------------------------------------------------------------ */

export interface DecorationOptions {
  /** Temperature (°C); null/undefined is excluded from color mapping */
  temperature?: number | null
  /** Humidity (%); null/undefined is excluded from color mapping */
  humidity?: number | null
  /** Fixed color takes priority over temperature/humidity; when absent, falls back to them, and to the fallback color if no data */
  fixedColor?: string
}

/** Fallback color when no data is available */
export const FALLBACK_COLOR = '#d8d2c8'

/**
 * Build a material from sensor data (temperature/humidity) or a fixed color.
 * Priority: fixedColor > temperature > humidity > fallback color.
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
/* Coordinates & rotation                                              */
/* ------------------------------------------------------------------ */

/**
 * griddata coordinates → world coordinates.
 * Convention: xAxis maps to the building row (north-south/z), yAxis maps to the column (east-west/x);
 * griddata is 0-based and internally reuses buildingDemo's 1-based cellToWorld.
 */
export function gridCellToWorld(cell: Pick<GridCell, 'xAxis' | 'yAxis'>): { x: number; z: number } {
  const row = Number(cell.xAxis) + 1
  const col = Number(cell.yAxis) + 1
  return cellToWorld(row, col)
}

/** 'x,y,z' (radians) → THREE.Euler; '0,0,0' means no rotation. */
export function parseRotation(rotate: string): THREE.Euler {
  const toNum = (s: string): number => {
    const n = Number(s.trim())
    return Number.isFinite(n) ? n : 0
  }
  const [x = 0, y = 0, z = 0] = rotate.split(',').map(toNum)
  return new THREE.Euler(x, y, z)
}

/* ------------------------------------------------------------------ */
/* Default floor data: floor '8' (3D level 8 = 5F) example, replaceable with API data */
/* ------------------------------------------------------------------ */

const CYLINDER_DEMO_CELLS: Array<[row: number, col: number]> = [
  [4, 9],
  [5, 9],
  [5, 5],
  [5, 6],
  [7, 8],
]

/** Build example data for floor '8' from the existing floor plan; some cells demo the Cylinder primitive. */
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

/** Default room height (world units) */
export const ROOM_H = 1.35

/**
 * Dynamically create a geometry from a GridType (generic factory).
 *
 * Used by Building3D to build the matching 3D shape from a CellShapeConfig setting.
 * Internally calls the corresponding createXxxGeometry function with a shared geometry cache.
 *
 * @param type   - shape type: 'Rect' | 'Cylinder' | 'Triangle' ('Hidden' should be filtered by isHiddenType first)
 * @param size   - cell size (world units), usually cellSize = CELL_SIZE * 0.96
 * @param height - extrusion height (world units), usually FLOOR_H
 * @returns the matching BufferGeometry (cached & reused)
 *
 * Example (Building3D.vue):
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
