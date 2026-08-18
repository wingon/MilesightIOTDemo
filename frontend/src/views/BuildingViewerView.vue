<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import Building3D from '@/components/building/Building3D.vue'
import BuildingDashboardPanel from '@/components/building/BuildingDashboardPanel.vue'
import DeviceDetailPanel from '@/components/building/DeviceDetailPanel.vue'
import { useBuildingStore } from '@/stores/building'
import { listBuildingCellShapes } from '@/api/building'
import { FLOOR_COUNT, floorName } from '@/utils/buildingDemo'
import type { EnvMetric } from '@/utils/envColor'
import type { CellShapeConfig } from '@/utils/floorGrid'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const store = useBuildingStore()

const selectedFloor = ref<number | null>(null)
/** 3D 樓棟當前著色指標（溫度/濕度） */
const metric = ref<EnvMetric>('temperature')

/**
 * Cell shape settings list
 *
 * Driven by the DB (Building_Cell table), fetched via GET /api/v1/building/cell-shapes,
 * replacing the old Building_Cell_Shape table and frontend hard-coded settings.
 * Passed to Building3D via the :cell-shapes prop (one entry per cell: row/col/floor/shape/rotation/color/height).
 */
const cellShapes = ref<CellShapeConfig[]>([])

/** Fetch cell shape settings from the DB; keep empty on failure (fall back to frontend hard-coded rectangles) */
async function fetchCellShapes() {
  try {
    const { data } = await listBuildingCellShapes()
    cellShapes.value = data ?? []
  } catch (err) {
    console.warn('[BuildingViewer] Failed to load cell shape settings (Building_Cell):', err)
    cellShapes.value = []
  }
}

onMounted(() => {
  // Warm inventory for dashboard metrics
  for (let i = 1; i <= FLOOR_COUNT; i++) store.ensureFloor(i)
  // 拉取 WingOnIOT 各樓層真實溫度/濕度 + 設備明細
  store.fetchFloorEnv()
  store.fetchEnvDevices()
  // Fetch the DB-driven building/floor structure (Building/Floor tables)
  store.fetchBuildingStructure()
  // Fetch the DB-driven cell shape settings (Building_Cell table, non-blocking for the rest of the init)
  fetchCellShapes()
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

/** Real WingOnIOT environment devices for the selected floor (empty when no data; panel falls back to demo) */
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
            :building-id="store.buildings[0]?.id"
            @select-floor="onSelectFloor"
            @refresh-shapes="fetchCellShapes"
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
