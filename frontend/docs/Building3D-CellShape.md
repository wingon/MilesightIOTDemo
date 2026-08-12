# Building3D 格子形狀設定元件

> 可複用的 3D 建築格子形狀設定系統，支援動態指定任意格子顯示為長方形、三角形、圓柱形，或隱藏不渲染。

---

## 語言切換 / Language

> [繁體中文](Building3D-CellShape.md) ・ [English](Building3D-CellShape-en.md)

---

## 目錄

- [架構總覽](#架構總覽)
- [程式碼位置](#程式碼位置)
- [架構呼叫鏈路](#架構呼叫鏈路)
- [類型定義](#類型定義)
- [使用說明](#使用說明)
- [設定參數詳解](#設定參數詳解)
- [樓層編號對照表](#樓層編號對照表)
- [呼叫範例](#呼叫範例)
- [注意事項](#注意事項)
- [相關檔案](#相關檔案)

---

## 架構總覽

`floorGrid.ts` 已依「形狀」拆分為多個獨立工具檔，`floorGrid.ts` 保留公共部分並統一 **re-export**，對外 `import` 路徑不變：

| 檔案 | 職責 |
|------|------|
| `floorGrid.ts` | **統一入口**：`GridType`/`CellShapeConfig` 類型、`createGeometryByType` 通用工廠、`decorationGeometry` 材質、座標/旋轉工具、`disposeGeometryCache` 統一釋放 |
| `floorGridRect.ts` | Rect（長方體）工廠 + 快取：`createRectGeometry()`、`disposeRectGeometryCache()`、`RECT_LENGTH`/`RECT_WIDTH` |
| `floorGridTriangle.ts` | Triangle（三角形）工廠 + 快取：`createTriangleGeometry()`、`disposeTriangleGeometryCache()` |
| `floorGridCylinder.ts` | Cylinder（圓柱）工廠 + 快取：`createCylinderGeometry()`、`disposeCylinderGeometryCache()`、`CYLINDER_RADIUS` |
| `floorGridHidden.ts` | Hidden（隱藏）判斷：`isHiddenType()`，不建立幾何體 |

---

## 程式碼位置

| 檔案路徑 | 職責 |
|---------|------|
| `src/utils/floorGrid.ts` | 工具庫統一入口：類型、設定介面、通用工廠、材質、座標工具 |
| `src/utils/floorGridRect.ts` | 長方體幾何工廠（拆分） |
| `src/utils/floorGridTriangle.ts` | 三角形幾何工廠（拆分） |
| `src/utils/floorGridCylinder.ts` | 圓柱幾何工廠（拆分） |
| `src/utils/floorGridHidden.ts` | 隱藏類型判斷（拆分） |
| `src/components/building/Building3D.vue` | 3D 樓棟元件：接收設定、依形狀渲染 |
| `src/views/BuildingViewerView.vue` | 頁面層：定義設定、傳入元件 |
| `src/utils/buildingDemo.ts` | 建築資料常數：`INTERIOR_CELLS`、`CELL_SIZE`、`shouldExcludeCell` 等 |

### 關鍵程式碼位置索引

```
src/
├── utils/
│   ├── floorGrid.ts                          # 統一入口（公共部分）
│   │   ├── Line 62:   export type GridType   # 形狀類型（含 Hidden）
│   │   ├── Line 74-93: export interface CellShapeConfig  # 設定介面
│   │   ├── Line 245-259: export function createGeometryByType()  # 通用工廠
│   │   ├── Line 118-122: export function disposeGeometryCache()  # 統一釋放
│   │   └── Line 144-165: export function decorationGeometry()    # 材質（溫濕度/固定色）
│   ├── floorGridRect.ts                      # 長方體（拆分）
│   │   └── Line 18-26: createRectGeometry(length, width, height) → BoxGeometry
│   ├── floorGridTriangle.ts                  # 三角形（拆分）
│   │   └── Line 35-58: createTriangleGeometry(size, height) → ExtrudeGeometry
│   ├── floorGridCylinder.ts                  # 圓柱（拆分）
│   │   └── Line 18-30: createCylinderGeometry(radius, height) → CylinderGeometry
│   └── floorGridHidden.ts                    # 隱藏（拆分）
│       └── Line 12-14: isHiddenType(type) → boolean
│
├── components/
│   └── building/
│       └── Building3D.vue                    # 3D 樓棟元件
│           ├── Line 20-25: import（createGeometryByType、isHiddenType）
│           ├── Line 72-75: DEFAULT_CELL_SHAPES 預設設定
│           ├── Line 89-102: getCellShapeConfig() 查詢設定
│           └── Line 152-161: rebuildFloors() 中的形狀選擇邏輯
│
└── views/
    └── BuildingViewerView.vue               # 頁面層
        ├── Line 42-49: cellShape() 輔助函數
        └── Line 62-69: cellShapes 設定定義
```

---

## 架構呼叫鏈路

### 呼叫鏈路圖

```
┌──────────────────────────────────────────────────────────────────────┐
│                        頁面層（View）                                 │
│  BuildingViewerView.vue                                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ① 定義設定：用 cellShape() 輔助函數產生 CellShapeConfig[]       │ │
│  │    const cellShapes = ref<CellShapeConfig[]>([                   │ │
│  │      ...cellShape(8, 11, [3,4,5,6,7], 'Triangle'),               │ │
│  │    ])                                                            │ │
│  │                                                                  │ │
│  │ ② 傳入元件                                                       │ │
│  │    <Building3D :cell-shapes="cellShapes" />                      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ :cell-shapes prop（deep watch 觸發重建）
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     3D 元件層（Component）                            │
│  Building3D.vue                                                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ① 接收 props：props.cellShapes ?? DEFAULT_CELL_SHAPES            │ │
│  │ ② rebuildFloors() 遍歷 INTERIOR_CELLS：                          │ │
│  │      shouldExcludeCell(level, row, col) 命中 → 跳過              │ │
│  │ ③ 查詢形狀：getCellShapeConfig(level, row, col, shapes)          │ │
│  │ ④ Hidden 判斷：isHiddenType(shapeType) → 不建立 Mesh             │ │
│  │ ⑤ 建立幾何體：                                                   │ │
│  │      'Rect'     → 共用 cellGeo（BoxGeometry）                    │ │
│  │      其他       → createGeometryByType(type, cellSize, FLOOR_H)  │ │
│  │ ⑥ new THREE.Mesh(geo, mat) → buildingGroup.add(mesh)            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ import { createGeometryByType, isHiddenType }
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      工具庫層（Utils）                                │
│  floorGrid.ts（統一入口）                                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ createGeometryByType(type, size, height)                        │ │
│  │   ├── 'Rect'     → createRectGeometry(size, size, height)       │ │
│  │   ├── 'Triangle' → createTriangleGeometry(size, height)         │ │
│  │   └── 'Cylinder' → createCylinderGeometry(size / 2, height)     │ │
│  │                                                                 │ │
│  │ 各類型工廠已拆分至獨立檔，各自的模組層級 geometryCache，         │ │
│  │ 同尺寸只 new 一次並復用：                                        │ │
│  │   floorGridRect.ts      → BoxGeometry                            │ │
│  │   floorGridTriangle.ts  → ExtrudeGeometry                        │ │
│  │   floorGridCylinder.ts  → CylinderGeometry                       │ │
│  │   floorGridHidden.ts    → isHiddenType（不建立幾何體）            │ │
│  │                                                                 │ │
│  │ disposeGeometryCache() → 統一呼叫三種 dispose 釋放共享幾何        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### 關鍵流程說明

1. **頁面層定義**：`BuildingViewerView.vue` 用 `cellShape(row, col, floors, shape)` 輔助函數把「同一個格子 × 多個樓層」展開成一組 `CellShapeConfig[]`，透過 `:cell-shapes` prop 傳給 `Building3D`。
2. **元件層消費**：`Building3D.vue` 在 `rebuildFloors()` 中對每個 `INTERIOR_CELLS` 格子：
   - 先以 `shouldExcludeCell()` 排除不渲染的格子；
   - 再用 `getCellShapeConfig()` 依 `(row, col, floor)` 找出形狀設定；
   - `Hidden` 型別直接跳過；`Rect` 復用共享 `cellGeo`；其餘走 `createGeometryByType()`。
3. **工具庫產出幾何**：`createGeometryByType()` 依 `GridType` 轉發到拆分後的工廠（`floorGridRect` / `floorGridTriangle` / `floorGridCylinder`），各自模組層級快取，同尺寸不重複建立。
4. **設定變更反應**：`watch(cellShapes, { deep: true })` 觸發 `rebuildFloors()` 重建所有樓層。

> 補充：`Floor3D.vue` 是工具庫的另一個消費者，直接使用 re-export 的 `createRectGeometry` / `createCylinderGeometry` / `decorationGeometry` / `DEFAULT_GRIDDATA` / `gridCellToWorld` / `parseRotation`，並在卸載時呼叫 `disposeGeometryCache()`。

---

## 類型定義

### GridType（形狀類型）

```typescript
export type GridType = 'Rect' | 'Cylinder' | 'Triangle' | 'Hidden'
```

| 類型 | 說明 | Three.js 幾何體 | 對應檔案 |
|------|------|----------------|---------|
| `'Rect'` | 長方形（預設） | `BoxGeometry` | `floorGridRect.ts` |
| `'Triangle'` | 三角形（等腰直角） | `ExtrudeGeometry` | `floorGridTriangle.ts` |
| `'Cylinder'` | 圓柱形 | `CylinderGeometry` | `floorGridCylinder.ts` |
| `'Hidden'` | 隱藏不渲染 | —（不建立幾何體） | `floorGridHidden.ts` |

### CellShapeConfig（形狀設定）

```typescript
export interface CellShapeConfig {
  row: number       // 行號（1-based，1~8，從南到北）
  col: number       // 列號（1-based，1~12，從西到東）
  floor: number     // 樓層（0=所有樓層，1~11=指定樓層，見下方對照表）
  shape: GridType   // 形狀類型
  color?: string    // 可選：自訂顏色（如 '#4CAF50'、'red'）
  rotation?: string // 可選：旋轉角度 'x,y,z'（弧度）
  height?: number   // 可選：自訂高度（世界單位）
}
```

### 工具庫其他匯出（由拆分檔 re-export）

| 匯出名稱 | 來源檔 | 說明 |
|---------|--------|------|
| `createRectGeometry(length, width, height)` | `floorGridRect.ts` | 長方體 `BoxGeometry` |
| `RECT_LENGTH` / `RECT_WIDTH` | `floorGridRect.ts` | 預設格子尺寸（`CELL_SIZE × 0.92`） |
| `createTriangleGeometry(size, height)` | `floorGridTriangle.ts` | 三角形 `ExtrudeGeometry` |
| `createCylinderGeometry(radius, height)` | `floorGridCylinder.ts` | 圓柱 `CylinderGeometry` |
| `CYLINDER_RADIUS` | `floorGridCylinder.ts` | 預設半徑（`CELL_SIZE / 2`） |
| `isHiddenType(type)` | `floorGridHidden.ts` | 是否為 `'Hidden'` |
| `disposeGeometryCache()` | `floorGrid.ts` | 統一釋放四種共享幾何 |
| `decorationGeometry(opts)` | `floorGrid.ts` | 溫濕度/固定色 → `MeshStandardMaterial` |
| `DEFAULT_GRIDDATA` / `ROOM_H` | `floorGrid.ts` | 預設樓層資料 / 預設房間高度 |

---

## 使用說明

### 方式一：使用預設設定（不傳 prop）

```vue
<template>
  <!-- 自動使用 Building3D 內建預設設定：(8,11)、(7,12) 顯示為三角形 -->
  <Building3D
    :selected-floor="selectedFloor"
    :floor-env="floorEnv"
  />
</template>
```

### 方式二：傳入自訂設定

```vue
<script setup lang="ts">
import Building3D from '@/components/building/Building3D.vue'

// cellShape() 為頁面層定義的輔助函數（見 BuildingViewerView.vue）
function cellShape(row: number, col: number, floors: number[], shape: GridType): CellShapeConfig[] {
  return floors.map((floor) => ({ row, col, floor, shape }))
}

const cellShapes = [
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),  // G/F~4/F 的 (8,11)
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),  // G/F~4/F 的 (7,12)
]
</script>

<template>
  <Building3D
    :selected-floor="selectedFloor"
    :floor-env="floorEnv"
    :cell-shapes="cellShapes"
  />
</template>
```

### 方式三：使用輔助函數批量生成

```typescript
// 一次設定多個樓層的同一個格子
const cellShapes = [
  // 範例1：G/F~4/F 的 (8,11) 為三角形
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),

  // 範例2：5F 的 (5,5) 為圓柱
  ...cellShape(5, 5, [8], 'Cylinder'),

  // 範例3：所有 11 層的 (3,3) 為三角形
  ...cellShape(3, 3, Array.from({ length: 11 }, (_, i) => i + 1), 'Triangle'),

  // 範例4：3~5F 的 (3,4) 隱藏不渲染
  ...cellShape(3, 4, [3, 4, 5], 'Hidden'),
]
```

---

## 設定參數詳解

### row（行號）

- 範圍：`1 ~ 8`
- 方向：從南到北（z 軸正方向）
- 說明：對應建築平面圖的行

### col（列號）

- 範圍：`1 ~ 12`
- 方向：從西到東（x 軸正方向）
- 說明：對應建築平面圖的列

### floor（樓層）

使用 **3D 層號**（不是樓層名稱）：

| 3D 層號 | 樓層名稱 |
|---------|---------|
| 1 | B2/F（地下二層） |
| 2 | B1/F（地下一層） |
| 3 | G/F（地面層） |
| 4 | 1/F（一層） |
| 5 | 2/F（二層） |
| 6 | 3/F（三層） |
| 7 | 4/F（四層） |
| 8 | 5/F（五層） |
| 9 | 6/F（六層） |
| 10 | 7/F（七層） |
| 11 | ROOF（屋頂） |
| **0** | **所有樓層** |

### shape（形狀類型）

| 值 | 效果 | 適用場景 |
|----|------|---------|
| `'Rect'` | 長方體 | 一般房間格子（預設） |
| `'Triangle'` | 三角形 | 建築對角線切割 |
| `'Cylinder'` | 圓柱體 | 特殊設備區域 |
| `'Hidden'` | 不渲染 | 需要隱藏格子的場景 |

---

## 樓層編號對照表

```
3D層號    樓層名稱    說明
─────    ────────    ────
  1       B2/F       地下二層
  2       B1/F       地下一層
  3       G/F        地面層（Ground Floor）
  4       1/F        一層
  5       2/F        二層
  6       3/F        三層
  7       4/F        四層
  8       5/F        五層
  9       6/F        六層
 10       7/F        七層
 11       ROOF       屋頂層
```

---

## 呼叫範例

### 範例1：對角線切割（G/F~4/F）

```typescript
import Building3D from '@/components/building/Building3D.vue'

const cellShapes = [
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),
]
```

效果：建築右下角 G/F 到 4/F 的 (8,11) 和 (7,12) 顯示為三角形。

### 範例2：設備區域標記（5F）

```typescript
const cellShapes = [
  ...cellShape(4, 9, [8], 'Cylinder'),
  ...cellShape(5, 9, [8], 'Cylinder'),
  ...cellShape(5, 5, [8], 'Cylinder'),
  ...cellShape(5, 6, [8], 'Cylinder'),
  ...cellShape(7, 8, [8], 'Cylinder'),
]
```

效果：5F 的指定格子顯示為圓柱形。

### 範例3：混合形狀 + 隱藏

```typescript
const cellShapes = [
  // 三角形：G/F~4/F 對角線
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),

  // 圓柱：5F 設備區域
  ...cellShape(4, 9, [8], 'Cylinder'),
  ...cellShape(5, 9, [8], 'Cylinder'),

  // 隱藏：3~5F 的 (3,4) 不渲染
  ...cellShape(3, 4, [3, 4, 5], 'Hidden'),
]
```

### 範例4：直接使用工具庫函數（Building3D 以外情境）

不透過 `Building3D` 元件時，也可直接呼叫拆分後的工廠函數：

```typescript
import {
  createGeometryByType,
  createRectGeometry,
  createTriangleGeometry,
  createCylinderGeometry,
  disposeGeometryCache,
} from '@/utils/floorGrid'

// 通用工廠：依類型建立（內部有快取）
const geo = createGeometryByType('Triangle', cellSize, FLOOR_H)

// 或直接呼叫單一工廠
const box = createRectGeometry(1, 1, 0.76)   // 長方體
const tri = createTriangleGeometry(1, 0.76)  // 三角形
const cyl = createCylinderGeometry(0.5, 0.76) // 圓柱

// 頁面卸載時統一釋放
disposeGeometryCache()
```

---

## 注意事項

### 1. 格子排除規則

某些格子在特定樓層會被 `shouldExcludeCell()`（`buildingDemo.ts`）排除，不渲染：

| 樓層範圍（3D 層號） | 排除的格子 |
|---------|-----------|
| G/F~ROOF (3-11) | (8,12) |
| 5F~ROOF (8-11) | (7,11)、(7,12)、(8,11)、(8,12) |

**即使設定了這些格子的形狀，也不會顯示。**

### 2. 效能考量

- 幾何體快取位於各拆分檔的模組層級（`geometryCache`），同尺寸只 new 一次並復用
- 修改 `cellShapes` 會觸發 `rebuildFloors()` 重建所有樓層（deep watch）
- 設定項較多時建議使用 `cellShape()` 輔助函數批量產生

### 3. 預設設定

當不傳入 `:cell-shapes` prop 時，`Building3D` 使用內建預設設定：

```typescript
const DEFAULT_CELL_SHAPES: CellShapeConfig[] = [
  { row: 8, col: 11, floor: 0, shape: 'Triangle' },
  { row: 7, col: 12, floor: 0, shape: 'Triangle' },
]
```

傳入自訂設定後，預設設定會被**完全替換**（不是合併）。

### 4. 擴充新形狀

如需支援更多形狀（如五邊形、六邊形）：

1. 新增獨立檔案 `floorGridXxx.ts`，實作 `createXxxGeometry()` 工廠函數（含快取）
2. 在 `floorGrid.ts` 匯入並 re-export
3. 在 `GridType` 聯合型別中新增類型
4. 在 `createGeometryByType()` 中新增 case
5. 即可透過設定使用新形狀

---

## 相關檔案

- [`floorGrid.ts`](../src/utils/floorGrid.ts) - 工具庫統一入口
- [`floorGridRect.ts`](../src/utils/floorGridRect.ts) - 長方體工廠
- [`floorGridTriangle.ts`](../src/utils/floorGridTriangle.ts) - 三角形工廠
- [`floorGridCylinder.ts`](../src/utils/floorGridCylinder.ts) - 圓柱工廠
- [`floorGridHidden.ts`](../src/utils/floorGridHidden.ts) - 隱藏判斷
- [`Building3D.vue`](../src/components/building/Building3D.vue) - 3D 元件
- [`BuildingViewerView.vue`](../src/views/BuildingViewerView.vue) - 使用範例
- [`buildingDemo.ts`](../src/utils/buildingDemo.ts) - 建築資料常數

---

*文件版本：v2.0 | 更新日期：2026-08-12*
