import type { GridType } from './floorGrid'

/**
 * Hidden（隱藏）類型工具
 *
 * Hidden 不建立任何幾何體；此處僅提供類型判斷與說明，
 * 供 Building3D 等調用方在建立 Mesh 前跳過渲染。
 *
 * @param type - 形狀類型（'Rect' | 'Cylinder' | 'Triangle' | 'Hidden'）
 * @returns 若為 'Hidden' 回傳 true，否則回傳 false
 */
export function isHiddenType(type: GridType): boolean {
  return type === 'Hidden'
}
