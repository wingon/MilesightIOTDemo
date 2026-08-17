import {
  GRID_ROWS,
  GRID_COLS,
  CELL_SIZE,
  INTERIOR_CELLS,
  shouldExcludeCell,
  buildCellToRoomMap,
  type Cell,
} from './buildingDemo'

/**
 * Wall segment definition.
 */
export interface WallSegment {
  /** Start x coordinate */
  x1: number
  /** Start z coordinate */
  z1: number
  /** End x coordinate */
  x2: number
  /** End z coordinate */
  z2: number
  /** Owning room ID (null means unowned wall) */
  roomId: string | null
  /** Whether this is an exterior wall */
  isExterior: boolean
  /** Whether this is a user-defined wall */
  isCustom?: boolean
  /** Index of this custom wall in the customWalls array */
  wallIndex?: number
}

/** Wall thickness (world units) */
export const WALL_THICKNESS = 0.06

/** Wall height (world units) */
export const WALL_HEIGHT = 0.5

/** cellToWorld: convert (row, col) to the world-space center point */
function cellToWorld(row: number, col: number): { x: number; z: number } {
  const halfCols = GRID_COLS / 2
  const halfRows = GRID_ROWS / 2
  const x = (col - halfCols - 0.5) * CELL_SIZE
  const z = (row - halfRows - 0.5) * CELL_SIZE
  return { x, z }
}

/** Whether a cell exists (not excluded and within bounds) */
function cellExists(row: number, col: number): boolean {
  if (row < 1 || row > GRID_ROWS || col < 1 || col > GRID_COLS) return false
  return !shouldExcludeCell(0, row, col)
}

/**
 * Compute all wall segments.
 *
 * @param layout - room cell layout
 * @param editMode - edit mode (when true, interior walls are hidden, exterior walls only)
 * @param customWalls - user-defined walls (manually added in edit mode)
 */
export function computeWalls(
  layout: Record<string, Cell[]>,
  editMode = false,
  customWalls: { x1: number; z1: number; x2: number; z2: number }[] = [],
): WallSegment[] {
  const cellToRoom = buildCellToRoomMap(layout)
  const walls: WallSegment[] = []
  const seen = new Set<string>()

  function addWall(
    x1: number,
    z1: number,
    x2: number,
    z2: number,
    roomId: string | null,
    isExterior: boolean,
    isCustom = false,
    wallIndex?: number,
  ) {
    const key = [
      Math.min(x1, x2).toFixed(3),
      Math.min(z1, z2).toFixed(3),
      Math.max(x1, x2).toFixed(3),
      Math.max(z1, z2).toFixed(3),
    ].join('|')
    if (seen.has(key)) return
    seen.add(key)
    walls.push({ x1, z1, x2, z2, roomId, isExterior, isCustom, wallIndex })
  }

  // Add user-defined custom walls
  for (let i = 0; i < customWalls.length; i++) {
    const cw = customWalls[i]
    addWall(cw.x1, cw.z1, cw.x2, cw.z2, null, false, true, i)
  }

  for (const cell of INTERIOR_CELLS) {
    const { row, col } = cell
    if (!cellExists(row, col)) continue

    const { x: cx, z: cz } = cellToWorld(row, col)
    const half = CELL_SIZE / 2
    const roomId = cellToRoom.get(`${row}-${col}`) ?? null

    // Left edge (col-1 direction)
    const leftExists = cellExists(row, col - 1)
    if (!leftExists) {
      addWall(
        cx - half,
        cz - half,
        cx - half,
        cz + half,
        roomId,
        true,
      )
    }

    // Right edge (col+1 direction)
    const rightExists = cellExists(row, col + 1)
    if (!rightExists) {
      addWall(
        cx + half,
        cz - half,
        cx + half,
        cz + half,
        roomId,
        true,
      )
    }

    // Top edge (row-1 direction)
    const upExists = cellExists(row - 1, col)
    if (!upExists) {
      addWall(
        cx - half,
        cz - half,
        cx + half,
        cz - half,
        roomId,
        true,
      )
    }

    // Bottom edge (row+1 direction)
    const downExists = cellExists(row + 1, col)
    if (!downExists) {
      addWall(
        cx - half,
        cz + half,
        cx + half,
        cz + half,
        roomId,
        true,
      )
    }
  }

  return walls
}
