import api from './http'
import type { CellShapeConfig } from '@/utils/floorGrid'

/** Building information */
export interface BuildingInfo {
  id: number
  name: string
  code: string | null
  address: string | null
  description: string | null
}

/** Floor information (level is the real floor number, level_3d is the frontend 3D level 1..11) */
export interface FloorInfo {
  id: number
  building_id: number
  row_amount: number
  column_amount: number
  level: number
  floor_name: string
  level_3d: number
}

/** Floor cell */
export interface FloorCell {
  id: number
  building_id: number
  floor_id: number
  row_no: number
  col_no: number
  x: number
  y: number
  z: number
  length: number
  width: number
  cell_height: number
  rotation_xyz: string | null
  is_active: number
  shape: string
  color: string | null
  render_height: number | null
}

/** Floor room (including occupied cells row/col) */
export interface FloorRoom {
  id: number
  room_id: string
  building_id: number
  floor_id: number
  room_number: string
  room_type: string | null
  area: number | null
  cells: Array<{ row: number; col: number }>
}

/** List buildings */
export function listBuildings() {
  return api.get<BuildingInfo[]>('/api/v1/building/list')
}

/** List building floors */
export function listBuildingFloors(buildingId?: number) {
  return api.get<FloorInfo[]>('/api/v1/building/floors', {
    params: { building_id: buildingId },
  })
}

/** Fetch 3D building cell shape settings (driven by Building_Cell, replaces Building_Cell_Shape) */
export function listBuildingCellShapes(buildingId?: number) {
  return api.get<CellShapeConfig[]>('/api/v1/building/cell-shapes', {
    params: { building_id: buildingId },
  })
}

/** List floor cells */
export function listFloorCells(floorId: number) {
  return api.get<FloorCell[]>(`/api/v1/building/floors/${floorId}/cells`)
}

/** List floor rooms (including room-cell relations) */
export function listFloorRooms(floorId: number) {
  return api.get<FloorRoom[]>(`/api/v1/building/floors/${floorId}/rooms`)
}

/** Update a single cell's rotation (rotation_xyz) */
export function updateCellRotation(params: {
  floor_id: number
  row_no: number
  col_no: number
  rotation_xyz: string | null
}) {
  return api.patch<{ ok: boolean }>('/api/v1/building/cell-rotation', params)
}

/** Apply the same rotation to all cells of a building */
export function updateAllCellsRotation(params: {
  building_id: number
  rotation_xyz: string | null
}) {
  return api.patch<{ ok: boolean; updated: number }>('/api/v1/building/cell-rotation-all', params)
}

/** Apply the same rotation to all cells of a column */
export function updateColCellsRotation(params: {
  building_id: number
  col_no: number
  rotation_xyz: string | null
}) {
  return api.patch<{ ok: boolean; updated: number }>('/api/v1/building/cell-rotation-row', params)
}

/** Add or delete cells (single / row / column / append row / append column) */
export function cellEdit(params: {
  building_id: number
  row_no: number
  col_no: number
  action: 'add' | 'delete'
  scope: 'single' | 'row' | 'col' | 'append_row' | 'append_col'
  floor_id?: number
}) {
  return api.post<{ ok: boolean; affected: number }>('/api/v1/building/cell-edit', params)
}

/** Undo the previous cell edit operation */
export function undoEdit() {
  return api.patch<{ ok: boolean; affected: number }>('/api/v1/building/undo-edit')
}

/** Delete all appended cells beyond the 8x12 grid, restoring the original grid */
export function resetGridExtras(building_id: number) {
  return api.post<{ ok: boolean; affected: number }>('/api/v1/building/reset-grid-extras', { building_id })
}
