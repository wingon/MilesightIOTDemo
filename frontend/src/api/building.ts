import api from './http'
import type { CellShapeConfig } from '@/utils/floorGrid'

/** 拉取 3D 樓棟格子形狀設定（DB 驅動，取代前端硬編碼） */
export function listBuildingCellShapes() {
  return api.get<CellShapeConfig[]>('/api/v1/building/cell-shapes')
}
