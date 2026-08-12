import * as THREE from 'three'

/**
 * Triangle（三角形）幾何工具
 *
 * 只負責「形狀」：同尺寸只 new 一次並復用（共享模板），
 * 此處的快取僅供 Triangle 類型使用。
 */

const geometryCache = new Map<string, THREE.ExtrudeGeometry>()

function geometryKey(dims: number[]): string {
  return `${dims.map((d) => d.toFixed(3)).join('x')}`
}

/**
 * 建立一個等腰直角三角形的拉伸幾何體，用於建築對角線切割效果。
 *
 * 幾何形狀（俯視圖）：
 *   ┌─────────┐
 *   │╲        │
 *   │  ╲      │  ← 三角形佔據格子的左上半部分
 *   │    ╲    │
 *   │      ╲  │
 *   │─────────│
 *   └─────────┘
 *
 * @param size   - 三角形的底邊長度（世界單位），通常傳入 cellSize
 * @param height - 拉伸高度（世界單位），通常傳入 FLOOR_H
 * @returns 共享的 ExtrudeGeometry 實例（同尺寸復用）
 *
 * 注意：幾何體已預置居中對齊（rotateX + translate），
 *       建立 mesh 後只需設定 position 即可。
 */
export function createTriangleGeometry(
  size: number,
  height: number,
): THREE.ExtrudeGeometry {
  const key = geometryKey([size, height])
  let geometry = geometryCache.get(key)
  if (!geometry) {
    const half = size / 2
    const triShape = new THREE.Shape()
    triShape.moveTo(-half, -half)
    triShape.lineTo(-half, half)
    triShape.lineTo(half, half)
    triShape.closePath()

    geometry = new THREE.ExtrudeGeometry(triShape, {
      depth: height,
      bevelEnabled: false,
    })
    geometry.rotateX(-Math.PI / 2)
    geometry.translate(0, -height / 2, 0)
    geometryCache.set(key, geometry)
  }
  return geometry
}

/** 釋放 Triangle 共享幾何（由 floorGrid.disposeGeometryCache 統一調用）。 */
export function disposeTriangleGeometryCache(): void {
  for (const geometry of geometryCache.values()) geometry.dispose()
  geometryCache.clear()
}
