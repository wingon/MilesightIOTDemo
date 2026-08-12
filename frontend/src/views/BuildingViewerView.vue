<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import Building3D from '@/components/building/Building3D.vue'
import BuildingDashboardPanel from '@/components/building/BuildingDashboardPanel.vue'
import DeviceDetailPanel from '@/components/building/DeviceDetailPanel.vue'
import { useBuildingStore } from '@/stores/building'
import { FLOOR_COUNT, floorName } from '@/utils/buildingDemo'
import type { EnvMetric } from '@/utils/envColor'
import type { CellShapeConfig, GridType } from '@/utils/floorGrid'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useBuildingStore()

const selectedFloor = ref<number | null>(null)
/** 3D 樓棟當前著色指標（溫度/濕度） */
const metric = ref<EnvMetric>('temperature')

/**
 * 格子形狀設定輔助函數
 *
 * 用途：為 Building3D 的指定格子設定自訂形狀（三角形、圓柱等）。
 * 支援一次設定多個樓層的同一個格子。
 *
 * @param row    - 格子行號（1-based，1~8，從南到北）
 * @param col    - 格子列號（1-based，1~12，從西到東）
 * @param floors - 要設定的樓層列表（3D 層號）
 *                 1=B2/F, 2=B1/F, 3=G/F, 4=1/F ... 10=7/F, 11=ROOF
 * @param shape  - 形狀類型：'Rect'(長方形) | 'Cylinder'(圓柱) | 'Triangle'(三角形) | 'Hidden'(隱藏不渲染)
 * @returns CellShapeConfig[] 設定陣列，可展開傳入 cellShapes
 *
 * 示例：
 *   cellShape(8, 11, [3, 4, 5], 'Triangle')
 *   → 3 樓(G/F)、4 樓(1/F)、5 樓(2/F) 的格子 (8,11) 顯示為三角形
 *
 *   cellShape(5, 5, Array.from({ length: 11 }, (_, i) => i + 1), 'Cylinder')
 *   → 所有 11 層的格子 (5,5) 顯示為圓柱
 */
function cellShape(
  row: number,
  col: number,
  floors: number[],
  shape: GridType,
): CellShapeConfig[] {
  return floors.map((floor) => ({ row, col, floor, shape }))
}

/**
 * 格子形狀設定列表
 *
 * 傳入 Building3D 的 :cell-shapes prop，覆蓋預設的三角形設定。
 * 使用展開運算符 ...cellShape(...) 批次產生設定。
 *
 * 注意事項：
 *  - floor 參數為 0 表示「所有樓層」（由 Building3D 內部處理）
 *  - 指定具體樓層號則只在該層生效
 *  - 被 shouldExcludeCell 排除的格子不會渲染，設定無效
 */
const cellShapes = ref<CellShapeConfig[]>([
     // G/F~4/F：格子 (8,11) 顯示為圓柱
  ...cellShape(8, 11, [3, 4, 5, 6, 7], 'Triangle'),
  ...cellShape(7, 11, [3, 4, 5, 6, 7], 'Rect'),
  ...cellShape(7, 12, [3, 4, 5, 6, 7], 'Triangle'),
  // ...cellShape(5, 5, [8], 'Cylinder'),              // 示例：5F 的 (5,5) 為圓柱
  // ...cellShape(3, 3, [3,4,5], 'Hidden'),            // 示例：3~5F 的 (3,3) 隱藏不渲染
])

onMounted(() => {
  // Warm inventory for dashboard metrics
  for (let i = 1; i <= FLOOR_COUNT; i++) store.ensureFloor(i)
  // 拉取 WingOnIOT 各樓層真實溫度/濕度 + 設備明細
  store.fetchFloorEnv()
  store.fetchEnvDevices()
  const q = Number(route.query.floor)
  if (Number.isInteger(q) && q >= 1 && q <= FLOOR_COUNT) {
    onSelectFloor(q)
  }
})

function onSelectFloor(floor: number) {
  // Toggle: click same floor again to return to overview dashboard
  if (selectedFloor.value === floor) {
    selectedFloor.value = null
    return
  }
  selectedFloor.value = floor
  store.ensureFloor(floor)
}

function clearFloor() {
  selectedFloor.value = null
}

function enterFloor() {
  if (selectedFloor.value == null) return
  store.ensureFloor(selectedFloor.value)
  router.push({ name: 'floor-viewer', params: { floor: String(selectedFloor.value) } })
}

function onFloorSelectChange(v: unknown) {
  if (typeof v === 'number') {
    onSelectFloor(v)
    return
  }
  selectedFloor.value = null
}

const panelDevices = computed(() => {
  if (selectedFloor.value == null) return []
  return store.listDeviceInstances(selectedFloor.value, null)
})

/** 選中樓層對應的 WingOnIOT 真實環境設備（無資料時為空陣列，面板回退 demo） */
const panelEnvDevices = computed(() => {
  if (selectedFloor.value == null) return []
  return store.devicesForFloor(selectedFloor.value)
})
</script>

<template>
  <div class="building-viewer">
    <div class="page-intro">
      <div>
        <h1>{{ t('building.title') }}</h1>
        <p>{{ t('building.subtitle') }}</p>
      </div>
      <div class="intro-actions">
        <a-button v-if="selectedFloor != null" @click="clearFloor">
          {{ t('buildingDash.backOverview') }}
        </a-button>
        <a-radio-group v-model:value="metric" size="small" button-style="solid">
          <a-radio-button value="temperature">{{ t('building.metricTemperature') }}</a-radio-button>
          <a-radio-button value="humidity">{{ t('building.metricHumidity') }}</a-radio-button>
        </a-radio-group>
        <a-select
          :value="selectedFloor ?? undefined"
          :placeholder="t('building.jumpFloor')"
          style="width: 140px"
          allow-clear
          @change="onFloorSelectChange"
        >
          <a-select-option v-for="n in FLOOR_COUNT" :key="n" :value="n">
            {{ t('building.level', { n: floorName(n) }) }}
          </a-select-option>
        </a-select>
      </div>
    </div>

    <div class="workspace">
      <div class="left">
        <div class="pane-3d">
          <div class="pane-label">{{ t('building.modelHint') }}</div>
          <Building3D
            :selected-floor="selectedFloor"
            :floor-env="store.floorEnv"
            :metric="metric"
            :cell-shapes="cellShapes"
            @select-floor="onSelectFloor"
          />
        </div>
      </div>

      <div class="right">
        <BuildingDashboardPanel
          v-if="selectedFloor == null"
          :selected-floor="selectedFloor"
          @select-floor="onSelectFloor"
        />
        <DeviceDetailPanel
          v-else
          :floor="selectedFloor"
          :room-key="null"
          :devices="panelDevices"
          :env-devices="panelEnvDevices"
          :can-enter="true"
          :can-back="true"
          @enter-floor="enterFloor"
          @back-overview="clearFloor"
        />
      </div>
    </div>
  </div>
</template>

<style scoped lang="less">
.building-viewer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 96px);
  min-height: 560px;
}

.page-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;

  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 650;
    color: #0d0d0d;
  }

  p {
    margin: 4px 0 0;
    color: #6b6b6b;
    font-size: 13px;
  }
}

.intro-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.workspace {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
  gap: 12px;
}

.left,
.right {
  min-height: 0;
  min-width: 0;
  height: 100%;
}

.pane-3d {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid #e6e2da;
  background: #fff;
}

.pane-label {
  position: absolute;
  z-index: 2;
  top: 10px;
  left: 10px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #e6e2da;
  padding: 4px 10px;
  font-size: 12px;
  color: #6b6b6b;
  pointer-events: none;
}

@media (max-width: 1100px) {
  .building-viewer {
    height: auto;
  }

  .workspace {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(420px, 55vh) minmax(360px, auto);
  }
}
</style>
