import * as THREE from 'three'
import { CELL_SIZE } from '@/utils/buildingDemo'

/**
 * Rect（長方體）幾何工具
 *
 * 只負責「形狀」：同尺寸只 new 一次並復用（共享模板），
 * 此處的快取僅供 Rect 類型使用。
 */

const geometryCache = new Map<string, THREE.BoxGeometry>()

function geometryKey(dims: number[]): string {
  return `${dims.map((d) => d.toFixed(3)).join('x')}`
}

/** 長方體（Rect）：只負責形狀，回傳共享實例。 */
export function createRectGeometry(length: number, width: number, height: number): THREE.BoxGeometry {
  const key = geometryKey([length, width, height])
  let geometry = geometryCache.get(key)
  if (!geometry) {
    geometry = new THREE.BoxGeometry(length, width, height)
    geometryCache.set(key, geometry)
  }
  return geometry
}

/** 釋放 Rect 共享幾何（由 floorGrid.disposeGeometryCache 統一調用）。 */
export function disposeRectGeometryCache(): void {
  for (const geometry of geometryCache.values()) geometry.dispose()
  geometryCache.clear()
}

/** 預設格子尺寸（與 buildingDemo 的 CELL_SIZE 對齊） */
export const RECT_LENGTH = CELL_SIZE * 0.92
export const RECT_WIDTH = CELL_SIZE * 0.92
