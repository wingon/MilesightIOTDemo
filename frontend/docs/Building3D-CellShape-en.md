# Building3D Cell Shape Configuration Component

> A reusable 3D building cell shape configuration system that lets you dynamically render any cell as a rectangle, triangle, or cylinder — or hide it from rendering entirely.

---

## Language / 語言

> [English](Building3D-CellShape-en.md) ・ [繁體中文](Building3D-CellShape.md)

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Code Locations](#code-locations)
- [Architecture Call Chain](#architecture-call-chain)
- [Type Definitions](#type-definitions)
- [Usage](#usage)
- [Configuration Parameters](#configuration-parameters)
- [Floor Numbering Reference](#floor-numbering-reference)
- [Call Examples](#call-examples)
- [Notes](#notes)
- [Related Files](#related-files)

---

## Architecture Overview

`floorGrid.ts` has been split by "shape" into several standalone utility files. `floorGrid.ts` keeps the shared public surface and **re-exports** everything, so the external `import` paths stay unchanged:

| File | Responsibility |
|------|---------------|
| `floorGrid.ts` | **Unified entry point**: `GridType` / `CellShapeConfig` types, `createGeometryByType` generic factory, `decorationGeometry` material, coordinate / rotation helpers, `disposeGeometryCache` unified disposal |
| `floorGridRect.ts` | Rect (box) factory + cache: `createRectGeometry()`, `disposeRectGeometryCache()`, `RECT_LENGTH` / `RECT_WIDTH` |
| `floorGridTriangle.ts` | Triangle factory + cache: `createTriangleGeometry()`, `disposeTriangleGeometryCache()` |
| `floorGridCylinder.ts` | Cylinder factory + cache: `createCylinderGeometry()`, `disposeCylinderGeometryCache()`, `CYLINDER_RADIUS` |
| `floorGridHidden.ts` | Hidden detection: `isHiddenType()` — creates no geometry |

---

## Code Locations

| File Path | Responsibility |
|-----------|---------------|
| `src/utils/floorGrid.ts` | Utility unified entry: types, config interface, generic factory, material, coordinate helpers |
| `src/utils/floorGridRect.ts` | Box geometry factory (split) |
| `src/utils/floorGridTriangle.ts` | Triangle geometry factory (split) |
| `src/utils/floorGridCylinder.ts` | Cylinder geometry factory (split) |
| `src/utils/floorGridHidden.ts` | Hidden type detection (split) |
| `src/components/building/Building3D.vue` | 3D building component: receives config, renders shapes |
| `src/views/BuildingViewerView.vue` | Page layer: defines config, passes it to the component |
| `src/utils/buildingDemo.ts` | Building data constants: `INTERIOR_CELLS`, `CELL_SIZE`, `shouldExcludeCell`, etc. |

### Key Code Index

```
src/
├── utils/
│   ├── floorGrid.ts                          # Unified entry (shared surface)
│   │   ├── Line 62:   export type GridType   # Shape type (incl. Hidden)
│   │   ├── Line 74-93: export interface CellShapeConfig  # Config interface
│   │   ├── Line 245-259: export function createGeometryByType()  # Generic factory
│   │   ├── Line 118-122: export function disposeGeometryCache()  # Unified disposal
│   │   └── Line 144-165: export function decorationGeometry()    # Material (temp/humidity or fixed color)
│   ├── floorGridRect.ts                      # Box (split)
│   │   └── Line 18-26: createRectGeometry(length, width, height) → BoxGeometry
│   ├── floorGridTriangle.ts                  # Triangle (split)
│   │   └── Line 35-58: createTriangleGeometry(size, height) → ExtrudeGeometry
│   ├── floorGridCylinder.ts                  # Cylinder (split)
│   │   └── Line 18-30: createCylinderGeometry(radius, height) → CylinderGeometry
│   └── floorGridHidden.ts                    # Hidden (split)
│       └── Line 12-14: isHiddenType(type) → boolean
│
├── components/
│   └── building/
│       └── Building3D.vue                    # 3D building component
│           ├── Line 20-25: import (createGeometryByType, isHiddenType)
│           ├── Line 72-75: DEFAULT_CELL_SHAPES
│           ├── Line 89-102: getCellShapeConfig() shape lookup
│           └── Line 152-161: shape selection logic in rebuildFloors()
│
└── views/
    └── BuildingViewerView.vue               # Page layer
        ├── Line 42-49: cellShape() helper
        └── Line 62-69: cellShapes config definition
```

---

## Architecture Call Chain

### Call Chain Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                        View Layer                                    │
│  BuildingViewerView.vue                                              │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ① Define config: cellShape() helper expands to CellShapeConfig[]│ │
│  │    const cellShapes = ref<CellShapeConfig[]>([                   │ │
│  │      ...cellShape(8, 11, [3,4,5,6,7], 'Triangle'),               │ │
│  │    ])                                                            │ │
│  │                                                                  │ │
│  │ ② Pass to component                                              │ │
│  │    <Building3D :cell-shapes="cellShapes" />                      │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ :cell-shapes prop (deep watch rebuild)
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     Component Layer (3D)                             │
│  Building3D.vue                                                      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ ① Receive props: props.cellShapes ?? DEFAULT_CELL_SHAPES         │ │
│  │ ② rebuildFloors() iterates INTERIOR_CELLS:                       │ │
│  │      shouldExcludeCell(level, row, col) hit → skip               │ │
│  │ ③ Lookup shape: getCellShapeConfig(level, row, col, shapes)      │ │
│  │ ④ Hidden check: isHiddenType(shapeType) → skip mesh creation     │ │
│  │ ⑤ Build geometry:                                                │ │
│  │      'Rect'     → reuse shared cellGeo (BoxGeometry)             │ │
│  │      otherwise → createGeometryByType(type, cellSize, FLOOR_H)   │ │
│  │ ⑥ new THREE.Mesh(geo, mat) → buildingGroup.add(mesh)            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────┬────────────────────────────────────────┘
                              │ import { createGeometryByType, isHiddenType }
                              ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        Utils Layer                                   │
│  floorGrid.ts (unified entry)                                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ createGeometryByType(type, size, height)                        │ │
│  │   ├── 'Rect'     → createRectGeometry(size, size, height)       │ │
│  │   ├── 'Triangle' → createTriangleGeometry(size, height)         │ │
│  │   └── 'Cylinder' → createCylinderGeometry(size / 2, height)     │ │
│  │                                                                 │ │
│  │ Factories are split into standalone files, each with a          │ │
│  │ module-level geometryCache (same size → created once, reused):  │ │
│  │   floorGridRect.ts      → BoxGeometry                            │ │
│  │   floorGridTriangle.ts  → ExtrudeGeometry                        │ │
│  │   floorGridCylinder.ts  → CylinderGeometry                       │ │
│  │   floorGridHidden.ts    → isHiddenType (no geometry created)     │ │
│  │                                                                 │ │
│  │ disposeGeometryCache() → calls the three dispose() to release    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Flow

1. **View layer defines config**: `BuildingViewerView.vue` uses the `cellShape(row, col, floors, shape)` helper to expand "the same cell × multiple floors" into an array of `CellShapeConfig[]`, then passes it to `Building3D` via the `:cell-shapes` prop.
2. **Component layer consumes config**: In `rebuildFloors()`, `Building3D.vue` processes every `INTERIOR_CELLS` cell:
   - First excludes non-rendered cells via `shouldExcludeCell()`;
   - Then looks up the shape config by `(row, col, floor)` via `getCellShapeConfig()`;
   - `Hidden` types are skipped; `Rect` reuses the shared `cellGeo`; everything else goes through `createGeometryByType()`.
3. **Utils layer produces geometry**: `createGeometryByType()` dispatches to the split factories (`floorGridRect` / `floorGridTriangle` / `floorGridCylinder`), each with its own module-level cache so identical sizes are only created once.
4. **Config changes react**: `watch(cellShapes, { deep: true })` triggers `rebuildFloors()` to rebuild all floors.

> Note: `Floor3D.vue` is another consumer of the utility layer. It directly uses the re-exported `createRectGeometry` / `createCylinderGeometry` / `decorationGeometry` / `DEFAULT_GRIDDATA` / `gridCellToWorld` / `parseRotation`, and calls `disposeGeometryCache()` on unmount.

---

## Type Definitions

### GridType (Shape Type)

```typescript
export type GridType = 'Rect' | 'Cylinder' | 'Triangle' | 'Hidden'
```

| Type | Description | Three.js Geometry | Source File |
|------|-------------|-------------------|-------------|
| `'Rect'` | Rectangle (default) | `BoxGeometry` | `floorGridRect.ts` |
| `'Triangle'` | Triangle (isosceles right) | `ExtrudeGeometry` | `floorGridTriangle.ts` |
| `'Cylinder'` | Cylinder | `CylinderGeometry` | `floorGridCylinder.ts` |
| `'Hidden'` | Hidden (not rendered) | — (no geometry) | `floorGridHidden.ts` |

### CellShapeConfig (Shape Config)

```typescript
export interface CellShapeConfig {
  row: number       // Row (1-based, 1~8, south to north)
  col: number       // Column (1-based, 1~12, west to east)
  floor: number     // Floor (0 = all floors, 1~11 = specific floor, see table below)
  shape: GridType   // Shape type
  color?: string    // Optional: custom color (e.g. '#4CAF50', 'red')
  rotation?: string // Optional: rotation 'x,y,z' (radians)
  height?: number   // Optional: custom height (world units)
}
```

### Other Utils Exports (re-exported from split files)

| Export | Source File | Description |
|--------|-------------|-------------|
| `createRectGeometry(length, width, height)` | `floorGridRect.ts` | Box `BoxGeometry` |
| `RECT_LENGTH` / `RECT_WIDTH` | `floorGridRect.ts` | Default cell size (`CELL_SIZE × 0.92`) |
| `createTriangleGeometry(size, height)` | `floorGridTriangle.ts` | Triangle `ExtrudeGeometry` |
| `createCylinderGeometry(radius, height)` | `floorGridCylinder.ts` | Cylinder `CylinderGeometry` |
| `CYLINDER_RADIUS` | `floorGridCylinder.ts` | Default radius (`CELL_SIZE / 2`) |
| `isHiddenType(type)` | `floorGridHidden.ts` | Whether the type is `'Hidden'` |
| `disposeGeometryCache()` | `floorGrid.ts` | Dispose all shared geometries |
| `decorationGeometry(opts)` | `floorGrid.ts` | Temp/humidity or fixed color → `MeshStandardMaterial` |
| `DEFAULT_GRIDDATA` / `ROOM_H` | `floorGrid.ts` | Default floor data / default room height |

---

## Usage

### Method 1: Use the Built-in Defaults (no prop)

```vue
<template>
  <!-- Automatically uses Building3D's built-in defaults: (8,11) and (7,12) as triangles -->
  <Building3D
    :selected-floor="selectedFloor"
    :floor-env="floorEnv"
  />
</template>
```

### Method 2: Pass a Custom Config

```vue
<script setup lang="ts">
import Building3D from '@/components/building/Building3D.vue'

// cellShape() is a helper defined in the page layer (see BuildingViewerView.vue)
function cellShape(row: number, col: number, floors: number[], shape: GridType): CellShapeConfig[] {
  return floors.map((floor) => ({ row, col, floor, shape }))
}

const cellShapes = [
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),  // (8,11) on G/F~4/F
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),  // (7,12) on G/F~4/F
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

### Method 3: Batch Generation with the Helper

```typescript
// Configure the same cell across multiple floors in one call
const cellShapes = [
  // Example 1: (8,11) on G/F~4/F as a triangle
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),

  // Example 2: (5,5) on 5F as a cylinder
  ...cellShape(5, 5, [8], 'Cylinder'),

  // Example 3: (3,3) on all 11 floors as a triangle
  ...cellShape(3, 3, Array.from({ length: 11 }, (_, i) => i + 1), 'Triangle'),

  // Example 4: (3,4) on 3~5F hidden (not rendered)
  ...cellShape(3, 4, [3, 4, 5], 'Hidden'),
]
```

---

## Configuration Parameters

### row (Row)

- Range: `1 ~ 8`
- Direction: south to north (positive z axis)
- Maps to a row on the building floor plan.

### col (Column)

- Range: `1 ~ 12`
- Direction: west to east (positive x axis)
- Maps to a column on the building floor plan.

### floor (Floor)

Uses the **3D level number** (not the floor name):

| 3D Level | Floor Name |
|----------|------------|
| 1 | B2/F (Basement 2) |
| 2 | B1/F (Basement 1) |
| 3 | G/F (Ground Floor) |
| 4 | 1/F (First Floor) |
| 5 | 2/F (Second Floor) |
| 6 | 3/F (Third Floor) |
| 7 | 4/F (Fourth Floor) |
| 8 | 5/F (Fifth Floor) |
| 9 | 6/F (Sixth Floor) |
| 10 | 7/F (Seventh Floor) |
| 11 | ROOF |
| **0** | **All floors** |

### shape (Shape Type)

| Value | Effect | Use Case |
|-------|--------|----------|
| `'Rect'` | Box | Regular room cells (default) |
| `'Triangle'` | Triangle | Building diagonal cuts |
| `'Cylinder'` | Cylinder | Special equipment areas |
| `'Hidden'` | Not rendered | When a cell should be hidden |

---

## Floor Numbering Reference

```
3D Level   Floor Name   Description
───────    ──────────   ───────────
   1         B2/F        Basement 2
   2         B1/F        Basement 1
   3         G/F         Ground Floor
   4         1/F         First Floor
   5         2/F         Second Floor
   6         3/F         Third Floor
   7         4/F         Fourth Floor
   8         5/F         Fifth Floor
   9         6/F         Sixth Floor
  10         7/F         Seventh Floor
  11         ROOF        Roof Level
```

---

## Call Examples

### Example 1: Diagonal Cut (G/F~4/F)

```typescript
import Building3D from '@/components/building/Building3D.vue'

const cellShapes = [
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),
]
```

Effect: the (8,11) and (7,12) cells in the building's lower-right corner render as triangles from G/F through 4/F.

### Example 2: Equipment Area Markers (5F)

```typescript
const cellShapes = [
  ...cellShape(4, 9, [8], 'Cylinder'),
  ...cellShape(5, 9, [8], 'Cylinder'),
  ...cellShape(5, 5, [8], 'Cylinder'),
  ...cellShape(5, 6, [8], 'Cylinder'),
  ...cellShape(7, 8, [8], 'Cylinder'),
]
```

Effect: the specified cells on 5F render as cylinders.

### Example 3: Mixed Shapes + Hidden

```typescript
const cellShapes = [
  // Triangle: G/F~4/F diagonal
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),

  // Cylinder: 5F equipment area
  ...cellShape(4, 9, [8], 'Cylinder'),
  ...cellShape(5, 9, [8], 'Cylinder'),

  // Hidden: (3,4) on 3~5F not rendered
  ...cellShape(3, 4, [3, 4, 5], 'Hidden'),
]
```

### Example 4: Using the Utility Functions Directly (outside Building3D)

When not going through the `Building3D` component, you can call the split factory functions directly:

```typescript
import {
  createGeometryByType,
  createRectGeometry,
  createTriangleGeometry,
  createCylinderGeometry,
  disposeGeometryCache,
} from '@/utils/floorGrid'

// Generic factory: build by type (cached internally)
const geo = createGeometryByType('Triangle', cellSize, FLOOR_H)

// Or call a single factory directly
const box = createRectGeometry(1, 1, 0.76)    // box
const tri = createTriangleGeometry(1, 0.76)   // triangle
const cyl = createCylinderGeometry(0.5, 0.76) // cylinder

// Dispose all shared geometries on unmount
disposeGeometryCache()
```

---

## Notes

### 1. Cell Exclusion Rules

Some cells are excluded (not rendered) on specific floors by `shouldExcludeCell()` (from `buildingDemo.ts`):

| Floor Range (3D Level) | Excluded Cells |
|------------------------|----------------|
| G/F~ROOF (3-11) | (8,12) |
| 5F~ROOF (8-11) | (7,11), (7,12), (8,11), (8,12) |

**Even if you configure a shape for these cells, they will not be displayed.**

### 2. Performance

- Geometry caches live at the module level in each split file (`geometryCache`); identical sizes are created once and reused.
- Mutating `cellShapes` triggers `rebuildFloors()` to rebuild all floors (deep watch).
- For many config entries, prefer the `cellShape()` helper for batch generation.

### 3. Default Config

When no `:cell-shapes` prop is passed, `Building3D` uses its built-in defaults:

```typescript
const DEFAULT_CELL_SHAPES: CellShapeConfig[] = [
  { row: 8, col: 11, floor: 0, shape: 'Triangle' },
  { row: 7, col: 12, floor: 0, shape: 'Triangle' },
]
```

Once a custom config is passed, the defaults are **completely replaced** (not merged).

### 4. Extending with New Shapes

To support more shapes (e.g. pentagon, hexagon):

1. Add a standalone file `floorGridXxx.ts` implementing a `createXxxGeometry()` factory (with its own cache).
2. Import and re-export it from `floorGrid.ts`.
3. Add the new type to the `GridType` union.
4. Add a new `case` in `createGeometryByType()`.
5. The new shape is now usable via config.

---

## Related Files

- [`floorGrid.ts`](../src/utils/floorGrid.ts) - Utility unified entry
- [`floorGridRect.ts`](../src/utils/floorGridRect.ts) - Box factory
- [`floorGridTriangle.ts`](../src/utils/floorGridTriangle.ts) - Triangle factory
- [`floorGridCylinder.ts`](../src/utils/floorGridCylinder.ts) - Cylinder factory
- [`floorGridHidden.ts`](../src/utils/floorGridHidden.ts) - Hidden detection
- [`Building3D.vue`](../src/components/building/Building3D.vue) - 3D component
- [`BuildingViewerView.vue`](../src/views/BuildingViewerView.vue) - Usage example
- [`buildingDemo.ts`](../src/utils/buildingDemo.ts) - Building data constants

---

*Doc version: v2.0 | Updated: 2026-08-12*
