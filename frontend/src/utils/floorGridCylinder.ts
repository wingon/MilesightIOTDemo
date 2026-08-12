import * as THREE from 'three'
import { CELL_SIZE } from '@/utils/buildingDemo'

/**
 * Cylinder（圓柱）幾何工具
 *
 * 只負責「形狀」：同尺寸只 new 一次並復用（共享模板），
 * 此處的快取僅供 Cylinder 類型使用。
 */

const geometryCache = new Map<string, THREE.CylinderGeometry>()

function geometryKey(dims: number[]): string {
  return `${dims.map((d) => d.toFixed(3)).join('x')}`
}

/** 圓柱（Cylinder）：只負責形狀，回傳共享實例。 */
export function createCylinderGeometry(
  radius: number,
  height: number,
  radialSegments = 24,
): THREE.CylinderGeometry {
  const key = geometryKey([radius, height, radialSegments])
  let geometry = geometryCache.get(key)
  if (!geometry) {
    geometry = new THREE.CylinderGeometry(radius, radius, height, radialSegments)
    geometryCache.set(key, geometry)
  }
  return geometry
}

/** 釋放 Cylinder 共享幾何（由 floorGrid.disposeGeometryCache 統一調用）。 */
export function disposeCylinderGeometryCache(): void {
  for (const geometry of geometryCache.values()) geometry.dispose()
  geometryCache.clear()
}

/** 圓柱預設半徑（與 buildingDemo 的 CELL_SIZE 對齊） */
export const CYLINDER_RADIUS = CELL_SIZE / 2
