<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import BuildingFacade3D from '@/components/building/BuildingFacade3D.vue'
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
/** 3D 着色指标（温度/湿度），与 BuildingFacade3D 控制面板双向同步 */
const metric = ref<EnvMetric>('temperature')
/** Loading state - wait for all data before rendering 3D */
const loading3D = ref(true)
/** 格子设置（building_cell，DB 驱动；供 3D 编辑模式使用） */
const cellShapes = ref<CellShapeConfig[]>([])
/** 3D 组件实例（用于左上角提示文字连点 3 次弹出控制面板） */
const buildingFacadeRef = ref<InstanceType<typeof BuildingFacade3D>>()

/**
 * 左上角提示文字「连点 3 次」（3 秒内累计，超时重置）。
 * 触发后弹出/收起 3D 图形控制面板。
 */
const EDIT_HINT_REQUIRED = 3
const EDIT_HINT_WINDOW_MS = 3000
const editHintCount = ref(0)
let lastEditHintAt = 0
let editHintTimer: ReturnType<typeof setTimeout> | undefined
/** 轻量反馈：连点达标时提示文字短促高亮 */
const editHintFlash = ref(false)
let flashTimer: ReturnType<typeof setTimeout> | undefined

function onEditHintClick() {
  const now = Date.now()
  if (now - lastEditHintAt > EDIT_HINT_WINDOW_MS) {
    editHintCount.value = 0
  }
  lastEditHintAt = now
  editHintCount.value += 1
  if (editHintTimer) clearTimeout(editHintTimer)
  editHintTimer = setTimeout(() => {
    if (Date.now() - lastEditHintAt >= EDIT_HINT_WINDOW_MS) {
      editHintCount.value = 0
    }
  }, EDIT_HINT_WINDOW_MS)

  if (editHintCount.value >= EDIT_HINT_REQUIRED) {
    editHintCount.value = 0
    void buildingFacadeRef.value?.togglePanel()
    editHintFlash.value = true
    if (flashTimer) clearTimeout(flashTimer)
    flashTimer = setTimeout(() => { editHintFlash.value = false }, 500)
  }
}

onBeforeUnmount(() => {
  if (editHintTimer) clearTimeout(editHintTimer)
  if (flashTimer) clearTimeout(flashTimer)
})

async function fetchCellShapes(): Promise<void> {
  try {
    const { data } = await listBuildingCellShapes()
    cellShapes.value = data ?? []
  } catch (err) {
    console.warn('[BuildingViewer] Failed to load cell shapes (building_cell):', err)
    cellShapes.value = []
  }
}

onMounted(async () => {
  // Warm inventory for dashboard metrics
  for (let i = 1; i <= FLOOR_COUNT; i++) store.ensureFloor(i)
  // Fetch all critical data in parallel before rendering 3D（列表数据来自 WingOnIOT 数据库）
  await Promise.all([
    store.fetchFloorEnv(),
    store.fetchEnvDevices(),
    store.fetchBuildingStructure(),
    fetchCellShapes(),
  ])
  loading3D.value = false
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

/** 各楼层指标列表点击楼层行：直接跳转到对应楼层 */
function onDashboardEnterFloor(floor: number) {
  store.ensureFloor(floor)
  router.push({ name: 'floor-viewer', params: { floor: String(floor) } })
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
      <div class="intro-title">
        <img class="intro-logo" src="/wingon-logo.png" alt="Wing On" />
        <div>
          <h1>{{ t('building.title') }}</h1>
          <p>{{ t('building.subtitle') }}</p>
        </div>
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
          <div
            class="pane-label"
            :class="{ flash: editHintFlash }"
            @click="onEditHintClick"
          >{{ t('building.modelHint') }}</div>
          <BuildingFacade3D
            ref="buildingFacadeRef"
            :selected-floor="selectedFloor"
            v-model:metric="metric"
            :loading="loading3D"
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
          @enter-floor="onDashboardEnterFloor"
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
  height: calc((100vh / var(--ls-scale, 1)) - var(--ls-content-offset, 96px));
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

/* Wing On logo — hidden by default, shown only in large-screen mode (html.ls-on) */
.intro-title {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.intro-logo {
  display: none;
  width: 44px;
  height: auto;
  object-fit: contain;
  flex-shrink: 0;
}

.intro-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
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
  background: var(--brand-surface, #fff);
}

.pane-label {
  position: absolute;
  z-index: 2;
  top: 10px;
  left: 10px;
  background: var(--brand-surface, rgba(255, 255, 255, 0.88));
  border: 1px solid #e6e2da;
  padding: 4px 10px;
  font-size: 12px;
  color: #6b6b6b;
  transition: border-color 0.15s;
  user-select: none;
}

.pane-label.flash {
  border-color: #c4a574;
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