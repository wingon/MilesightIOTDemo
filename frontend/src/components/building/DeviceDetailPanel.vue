<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import ChartPanel from '@/components/ChartPanel.vue'
import type { EnvironmentDevice } from '@/api/environment'
import {
  buildAm319Option,
  buildCt103Option,
  buildVs135Option,
  FLOOR_ROOMS,
  floorName,
  latestSnapshot,
  type DeviceType,
} from '@/utils/buildingDemo'

export interface DeviceInstance {
  type: DeviceType
  roomKey: string
  seed: number
  deviceId: string
  sn: string
}

export interface AssignableOption {
  value: string
  label: string
  type: DeviceType
}

const props = defineProps<{
  floor: number | null
  roomKey: string | null
  devices: DeviceInstance[]
  canEnter?: boolean
  /** Show back-to-overview control next to Enter floor */
  canBack?: boolean
  manageable?: boolean
  roomLabel?: string | null
  /** Unassigned floor inventory for dropdown */
  assignableOptions?: AssignableOption[]
  /** WingOnIOT 真实环境设备（传入且非空时优先展示，替代 demo 设备与图表） */
  envDevices?: EnvironmentDevice[]
}>()

const emit = defineEmits<{
  enterFloor: []
  backOverview: []
  assignToRoom: [deviceId: string]
  removeFromRoom: [payload: { roomId: string; deviceId: string }]
}>()

const { t, locale } = useI18n()

const activeId = ref<string | null>(null)
const chartPane = ref<HTMLElement | null>(null)
const pickDeviceId = ref<string | undefined>(undefined)

const title = computed(() => {
  if (props.floor == null) return t('building.selectFloorHint')
  if (props.roomKey) {
    const label =
      props.roomLabel ||
      t('building.roomN', {
        n: FLOOR_ROOMS.find((r) => r.id === props.roomKey)?.index ?? props.roomKey,
      })
    return t('building.selectionRoom', { floor: floorName(props.floor), room: label })
  }
  return t('building.selectionFloor', { floor: floorName(props.floor) })
})

const deviceBlocks = computed(() => {
  void locale.value
  if (props.floor == null || !props.devices.length) return []
  return props.devices.map((inst) => {
    const id = inst.deviceId
    let option
    if (inst.type === 'CT103') {
      option = buildCt103Option(inst.seed, {
        current: t('dashboard.charts.current'),
        total: t('dashboard.charts.totalCurrent'),
      })
    } else if (inst.type === 'AM319') {
      option = buildAm319Option(inst.seed, {
        co2: t('dashboard.charts.co2'),
        temp: t('dashboard.charts.temperature'),
        humidity: t('dashboard.charts.humidity'),
        pm25: t('dashboard.charts.pm25'),
      })
    } else {
      option = buildVs135Option(inst.seed, {
        periodIn: t('dashboard.charts.periodIn'),
        periodOut: t('dashboard.charts.periodOut'),
        cumulative: t('dashboard.charts.cumulative'),
      })
    }
    const room = FLOOR_ROOMS.find((r) => r.id === inst.roomKey)
    return {
      type: inst.type,
      roomKey: inst.roomKey,
      roomLabel: room ? t('building.roomN', { n: room.index }) : inst.roomKey,
      id,
      sn: inst.sn,
      deviceId: inst.deviceId,
      option,
      snapshot: latestSnapshot(inst.type, inst.seed),
    }
  })
})

const dropdownOptions = computed(() =>
  (props.assignableOptions || []).map((o) => ({
    value: o.value,
    label: `${o.type} · ${o.label}`,
  })),
)

/** WingOnIOT 真实设备（envDevices 传入时优先） */
const envBlocks = computed(() => props.envDevices || [])

/** 真实设备模式：envDevices 已传入即强制启用；无设备时显示空状态，不回退 demo */
const envMode = computed(() => props.envDevices !== undefined)

watch(
  () => props.assignableOptions,
  (opts) => {
    if (!opts?.some((o) => o.value === pickDeviceId.value)) {
      pickDeviceId.value = opts?.[0]?.value
    }
  },
  { immediate: true, deep: true },
)

watch(
  deviceBlocks,
  (blocks) => {
    if (!blocks.length) {
      activeId.value = null
      return
    }
    if (!activeId.value || !blocks.some((b) => b.id === activeId.value)) {
      activeId.value = blocks[0].id
    }
  },
  { immediate: true },
)

watch(
  envBlocks,
  (blocks) => {
    if (!blocks.length) return
    if (!activeId.value || !blocks.some((b) => b.sn === activeId.value)) {
      activeId.value = blocks[0].sn
    }
  },
  { immediate: true },
)

async function scrollToDevice(id: string) {
  activeId.value = id
  await nextTick()
  const el = chartPane.value?.querySelector(
    `[data-device-id="${CSS.escape(id)}"]`,
  ) as HTMLElement | null
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function onAssign() {
  if (!props.roomKey || !pickDeviceId.value) return
  emit('assignToRoom', pickDeviceId.value)
}

function onRemove(block: { roomKey: string; deviceId: string }, ev: Event) {
  ev.stopPropagation()
  emit('removeFromRoom', { roomId: block.roomKey, deviceId: block.deviceId })
}
</script>

<template>
  <aside class="device-panel">
    <div class="panel-head">
      <h2>{{ t('building.devicePanel') }}</h2>
      <p>{{ title }}</p>
      <div class="head-meta">
        <a-tag v-if="(envMode ? envBlocks.length : devices.length) > 0" color="gold">
          {{ envBlocks.length || devices.length }} {{ t('building.devices') }}
        </a-tag>
        <a-tag v-else>{{ t('building.noDevices') }}</a-tag>
        <a-button
          v-if="canBack"
          class="back-btn"
          @click="emit('backOverview')"
        >
          {{ t('buildingDash.backOverview') }}
        </a-button>
        <a-button
          v-if="canEnter"
          type="primary"
          class="enter-btn"
          @click="emit('enterFloor')"
        >
          {{ t('building.enterFloor') }}
        </a-button>
      </div>
      <div v-if="envMode" class="live-badge">{{ t('building.liveData') }}</div>
      <div v-else class="demo-badge">{{ t('building.demoData') }}</div>
    </div>

    <div
      v-if="manageable"
      class="assign-bar"
    >
      <a-select
        v-model:value="pickDeviceId"
        :options="dropdownOptions"
        :placeholder="t('building.pickFloorDevice')"
        :disabled="!roomKey || !dropdownOptions.length"
        style="flex: 1; min-width: 0"
        show-search
        option-filter-prop="label"
      />
      <a-button
        type="primary"
        :disabled="!roomKey || !pickDeviceId"
        @click="onAssign"
      >
        <PlusOutlined /> {{ t('building.addToRoom') }}
      </a-button>
      <p v-if="!roomKey" class="assign-hint">{{ t('building.selectRoomToAssign') }}</p>
      <p v-else-if="!dropdownOptions.length" class="assign-hint">{{ t('building.noAssignable') }}</p>
    </div>

    <div v-if="!floor" class="empty">
      <p>{{ t('building.clickFloor') }}</p>
    </div>

    <div v-else class="split">
      <div class="nav">
        <div class="nav-title">{{ t('building.deviceList') }}</div>

        <template v-if="envMode">
          <div v-if="!envBlocks.length" class="nav-empty">
            {{ t('building.envNoDevices') }}
          </div>
          <div
            v-for="dev in envBlocks"
            :key="dev.sn"
            class="nav-item"
            :class="{ active: activeId === dev.sn }"
            role="button"
            tabindex="0"
            @click="scrollToDevice(dev.sn)"
            @keydown.enter="scrollToDevice(dev.sn)"
          >
            <div class="nav-main">
              <div class="nav-type">{{ dev.deviceName || dev.name || dev.sn }}</div>
              <div class="nav-sub">{{ dev.sn }}</div>
              <div class="nav-sub dim">{{ t('building.envLocation') }}: {{ dev.location || '-' }}</div>
            </div>
          </div>
        </template>

        <template v-else>
          <div v-if="!deviceBlocks.length" class="nav-empty">
            {{ roomKey ? t('building.roomNoDevices') : t('building.assignHint') }}
          </div>

          <div
            v-for="block in deviceBlocks"
            :key="block.id"
            class="nav-item"
            :class="{ active: activeId === block.id }"
            role="button"
            tabindex="0"
            @click="scrollToDevice(block.id)"
            @keydown.enter="scrollToDevice(block.id)"
          >
            <div class="nav-main">
              <div class="nav-type">{{ block.type }}</div>
              <div class="nav-sub">{{ block.sn }}</div>
              <div class="nav-sub dim">{{ block.roomLabel }}</div>
            </div>
            <button
              v-if="manageable"
              type="button"
              class="nav-remove"
              :title="t('building.removeDevice')"
              @click="onRemove(block, $event)"
            >
              <DeleteOutlined />
            </button>
          </div>

          <a-button
            v-if="canEnter && !devices.length"
            type="primary"
            size="small"
            block
            style="margin-top: 12px"
            @click="emit('enterFloor')"
          >
            {{ t('building.enterFloor') }}
          </a-button>
        </template>
      </div>

      <div ref="chartPane" class="charts">
        <template v-if="envMode">
          <div v-if="!envBlocks.length" class="empty charts-empty">
            <p>{{ t('building.envNoDevices') }}</p>
          </div>
          <section
            v-for="dev in envBlocks"
            :key="dev.sn"
            class="device-card env-card"
            :class="{ active: activeId === dev.sn }"
            :data-device-id="dev.sn"
          >
            <div class="device-head">
              <div>
                <div class="device-type">{{ dev.deviceName || dev.name || dev.sn }}</div>
                <div class="device-id">{{ dev.sn }}</div>
                <div class="device-room">
                  {{ t('building.envLocation') }}: {{ dev.location || '-' }} ·
                  {{ t('building.envModel') }}: {{ dev.model || '-' }}
                </div>
              </div>
              <a-tag>{{ dev.floor || '-' }}</a-tag>
            </div>
            <div class="metrics">
              <div class="metric">
                <span class="m-label">{{ t('dashboard.charts.temperature') }}</span>
                <span class="m-value">
                  {{ dev.temperatureMedian != null ? `${dev.temperatureMedian}°C` : '--' }}
                </span>
              </div>
              <div class="metric">
                <span class="m-label">{{ t('dashboard.charts.humidity') }}</span>
                <span class="m-value">
                  {{ dev.humidityMedian != null ? `${dev.humidityMedian}%RH` : '--' }}
                </span>
              </div>
            </div>
            <div class="env-updated">
              {{ dev.toDateTime ? t('building.envUpdatedAt', { t: dev.toDateTime }) : t('building.envNoReading') }}
            </div>
          </section>
        </template>

        <template v-else>
          <div v-if="!deviceBlocks.length" class="empty charts-empty">
            <p>{{ roomKey ? t('building.roomNoDevices') : t('building.assignHint') }}</p>
          </div>
          <section
            v-for="block in deviceBlocks"
            :key="block.id"
            class="device-card"
            :class="{ active: activeId === block.id }"
            :data-device-id="block.id"
          >
            <div class="device-head">
              <div>
                <div class="device-type">{{ block.type }}</div>
                <div class="device-id">{{ block.sn }}</div>
                <div class="device-room">{{ block.roomLabel }}</div>
              </div>
              <a-tag>{{ t('building.online') }}</a-tag>
            </div>
            <div class="metrics">
              <div v-for="m in block.snapshot" :key="m.label" class="metric">
                <span class="m-label">{{ m.label }}</span>
                <span class="m-value">{{ m.value }}</span>
              </div>
            </div>
            <ChartPanel :option="block.option" height="220px" />
          </section>
        </template>
      </div>
    </div>
  </aside>
</template>

<style scoped lang="less">
.device-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #fff;
  border: 1px solid #e6e2da;
}

.panel-head {
  padding: 14px 16px 12px;
  border-bottom: 1px solid #e6e2da;
  position: relative;
  padding-right: 88px;
  flex-shrink: 0;

  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 650;
    color: #0d0d0d;
  }

  p {
    margin: 4px 0 8px;
    font-size: 13px;
    color: #6b6b6b;
  }
}

.head-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.enter-btn {
  font-weight: 600;
}

.back-btn {
  font-weight: 400;
  color: #6b6b6b;
  border-color: #e6e2da;
  background: #fff;

  &:hover {
    color: #0d0d0d !important;
    border-color: #cfc9be !important;
    background: #fafaf8 !important;
  }
}

.demo-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #a88955;
  border: 1px solid rgba(196, 165, 116, 0.55);
  padding: 2px 8px;
}

.live-badge {
  position: absolute;
  top: 14px;
  right: 14px;
  font-size: 11px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #3d7a5a;
  border: 1px solid rgba(61, 122, 90, 0.5);
  padding: 2px 8px;
}

.assign-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid #e6e2da;
  background: #fafaf8;
  flex-shrink: 0;
}

.assign-hint {
  flex-basis: 100%;
  margin: 0;
  font-size: 11px;
  color: #a88955;
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  color: #6b6b6b;
  text-align: center;
}

.split {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(140px, 200px) minmax(0, 1fr);
}

.nav {
  border-right: 1px solid #e6e2da;
  overflow: auto;
  padding: 10px 8px;
  background: #fafaf8;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-title {
  font-size: 11px;
  font-weight: 650;
  color: #6b6b6b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 0 6px 8px;
}

.nav-empty {
  font-size: 12px;
  color: #6b6b6b;
  padding: 8px 6px;
  line-height: 1.4;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
  padding: 8px 8px;
  cursor: pointer;
  color: #0d0d0d;

  &:hover {
    background: #fff;
  }

  &.active {
    background: #fff;
    border-color: #c4a574;
    box-shadow: inset 3px 0 0 #c4a574;
  }
}

.nav-main {
  min-width: 0;
  flex: 1;
}

.nav-type {
  font-size: 13px;
  font-weight: 650;
}

.nav-sub {
  font-size: 11px;
  color: #6b6b6b;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;

  &.dim {
    color: #a88955;
  }
}

.nav-remove {
  border: none;
  background: transparent;
  color: #6b6b6b;
  cursor: pointer;
  padding: 4px;
  flex-shrink: 0;

  &:hover {
    color: #b42318;
  }
}

.charts {
  overflow: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.charts-empty {
  min-height: 200px;
}

.device-card {
  border: 1px solid #e6e2da;
  padding: 12px;
  background: #fafaf8;
  scroll-margin-top: 8px;

  &.active {
    border-color: #c4a574;
  }
}

.device-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}

.device-type {
  font-weight: 700;
  font-size: 15px;
  color: #0d0d0d;
}

.device-id {
  font-size: 11px;
  color: #6b6b6b;
  font-family: ui-monospace, Consolas, monospace;
  margin-top: 2px;
}

.device-room {
  font-size: 12px;
  color: #a88955;
  margin-top: 2px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.metric {
  background: #fff;
  border: 1px solid #e6e2da;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.m-label {
  font-size: 11px;
  color: #6b6b6b;
}

.m-value {
  font-size: 15px;
  font-weight: 650;
  color: #0d0d0d;
}

.env-updated {
  font-size: 11px;
  color: #9a9a9a;
  padding-top: 2px;
}

.env-card .device-room {
  color: #6b6b6b;
}

@media (max-width: 700px) {
  .split {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(280px, 1fr);
  }

  .nav {
    border-right: none;
    border-bottom: 1px solid #e6e2da;
    max-height: 220px;
  }
}
</style>
