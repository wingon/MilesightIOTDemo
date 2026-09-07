<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  SearchOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  getPeopleCountOverview,
  listPeopleCountChannels,
  type PeopleCountOverview as OverviewData,
} from '@/api/peopleCount'
import ChartPanel from '@/components/ChartPanel.vue'
import {
  buildFloorCompareOption,
  buildFloorChannelShareOption,
  buildFloorChannelHourOption,
  buildFloorHourOption,
  buildFloorDailyOption,
  channelTypeColor,
} from '@/utils/peopleCountAggregateCharts'

const { t } = useI18n()

const loading = ref(false)
const overview = ref<OverviewData | null>(null)
const channels = ref<string[]>([])
const activeFloor = ref<string | null>(null)

// 篩選條件（與視圖頁一致的搜索框）：整合為「日期時間範圍」
const dateTimeRange = ref<[Dayjs | null, Dayjs | null] | null>(null)
const channelName = ref<string | undefined>(undefined)
const excludeZero = ref(true)

/** 截止到昨天的最近 7 天默認範圍（整點，分鐘為 0） */
function defaultRange(): [Dayjs, Dayjs] {
  const end = dayjs().subtract(1, 'day').hour(23).minute(0).second(0).millisecond(0)
  const start = end.subtract(6, 'day').hour(0).minute(0).second(0).millisecond(0)
  return [start, end]
}

const floorList = computed(() => {
  if (!overview.value) return []
  return overview.value.floors.map((f) => f.floor)
})

const labels = computed(() => ({
  enter: t('peopleCount.enter'),
  exit: t('peopleCount.exit'),
}))

const floorCompareOption = computed(() =>
  overview.value ? buildFloorCompareOption(overview.value) : {},
)

/** 當前選中樓層詳情 */
const currentFloor = computed(() => {
  if (!overview.value || !activeFloor.value) return null
  return overview.value.floors.find((f) => f.floor === activeFloor.value) ?? null
})

const floorHourOption = computed(() =>
  currentFloor.value ? buildFloorHourOption(currentFloor.value.hour) : {},
)
const floorDailyOption = computed(() =>
  currentFloor.value ? buildFloorDailyOption(currentFloor.value.daily) : {},
)
const floorShareOption = computed(() =>
  currentFloor.value ? buildFloorChannelShareOption(currentFloor.value.channels) : {},
)
const floorChannelHourOption = computed(() =>
  currentFloor.value ? buildFloorChannelHourOption(currentFloor.value, channelHourRows.value) : {},
)

/** 通道 × 小時（overview 提供全量通道級明細） */
const channelHourRows = computed(() => overview.value?.channelHour ?? [])

const currentFloorKpis = computed(() => {
  const f = currentFloor.value
  if (!f) return null
  return {
    total: f.total,
    dailyAvg: f.daily.length ? Math.round(f.total / (overview.value?.meta.days || 1)) : 0,
    channels: f.channels.length,
    busiest: f.channels[0]?.channel_name ?? '—',
  }
})

/** 由整合的日期時間範圍拆出查詢參數 */
function buildQuery() {
  const s = dateTimeRange.value?.[0]
  const e = dateTimeRange.value?.[1]
  return {
    date_from: s?.format('YYYY-MM-DD') || undefined,
    date_to: e?.format('YYYY-MM-DD') || undefined,
    hour_from: s?.hour(),
    hour_to: e?.hour(),
    channel_name: channelName.value,
    exclude_zero: excludeZero.value,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await getPeopleCountOverview(buildQuery())
    overview.value = data
    if (activeFloor.value && !data.floors.some((f) => f.floor === activeFloor.value)) {
      activeFloor.value = null
    }
  } catch (e: unknown) {
    const err = e instanceof Error ? e.message : String(e)
    message.error(`${t('peopleCount.loadFailed')} ${err}`)
  } finally {
    loading.value = false
  }
}

function onReset() {
  dateTimeRange.value = defaultRange()
  channelName.value = undefined
  excludeZero.value = true
  activeFloor.value = null
  load()
}

function selectFloor(floor: string | null) {
  activeFloor.value = floor
}

async function loadChannels() {
  try {
    const { data } = await listPeopleCountChannels()
    channels.value = data
  } catch {
    channels.value = []
  }
}

onMounted(() => {
  dateTimeRange.value = defaultRange()
  loadChannels()
  load()
})
</script>

<template>
  <div class="people-count-floor">
    <div class="page-intro">
      <h1>{{ t('peopleCount.floorTitle') }}</h1>
      <p>{{ t('peopleCount.floorSubtitle') }}</p>
    </div>

    <!-- 搜索框 -->
    <div class="card form-card">
      <div class="form-grid">
        <div class="field">
          <label>{{ t('peopleCount.dateTimeRange') }}</label>
          <a-range-picker
            v-model:value="dateTimeRange"
            format="YYYY-MM-DD HH:00"
            :show-time="{ format: 'HH:00', minuteStep: 60 }"
            :placeholder="[t('peopleCount.startTime'), t('peopleCount.endTime')]"
            style="width: 100%"
          />
        </div>
        <div class="field">
          <label>{{ t('peopleCount.channel') }}</label>
          <a-select
            v-model:value="channelName"
            :options="channels.map((c) => ({ value: c, label: c }))"
            :placeholder="t('peopleCount.channelPlaceholder')"
            show-search
            allow-clear
            option-filter-prop="label"
            style="width: 100%"
          />
        </div>
      </div>
      <div class="form-bottom">
        <a-checkbox v-model:checked="excludeZero">{{ t('peopleCount.filterExcludeZero') }}</a-checkbox>
        <div class="form-actions">
          <a-button type="primary" :loading="loading" @click="load">
            <SearchOutlined /> {{ t('peopleCount.query') }}
          </a-button>
          <a-button @click="onReset">
            <ReloadOutlined /> {{ t('peopleCount.reset') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- 樓層選擇 -->
    <div class="floor-bar">
      <button
        class="floor-btn"
        :class="{ active: activeFloor === null }"
        @click="selectFloor(null)"
      >
        {{ t('peopleCount.allFloors') }}
      </button>
      <button
        v-for="f in floorList"
        :key="f"
        class="floor-btn"
        :class="{ active: activeFloor === f }"
        @click="selectFloor(f)"
      >
        {{ f }}
      </button>
    </div>

    <!-- 全部樓層視圖 -->
    <template v-if="activeFloor === null">
      <div class="card chart-card">
        <div class="chart-title">{{ t('peopleCount.floorCompare') }}</div>
        <ChartPanel :option="floorCompareOption" height="300px" />
      </div>
    </template>

    <!-- 單層視圖 -->
    <template v-else-if="currentFloor">
      <div class="floor-kpis" v-if="currentFloorKpis">
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.floorTotal') }}</div>
          <div class="kpi-value green">{{ currentFloorKpis.total.toLocaleString() }}</div>
          <div class="kpi-sub">
            {{ t('peopleCount.kpiTotalSub', { enter: currentFloor.enter.toLocaleString(), exit: currentFloor.exit.toLocaleString() }) }}
          </div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.floorDailyAvg') }}</div>
          <div class="kpi-value blue">{{ currentFloorKpis.dailyAvg.toLocaleString() }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.floorChannelCount') }}</div>
          <div class="kpi-value yellow">{{ currentFloorKpis.channels }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.floorBusiest') }}</div>
          <div class="kpi-value orange small">{{ currentFloorKpis.busiest }}</div>
        </div>
      </div>

      <div class="ch-list">
        <div v-for="c in currentFloor.channels" :key="c.channel_name" class="card ch-card">
          <div class="ch-name">
            {{ c.channel_name }}
            <a-tag :color="channelTypeColor(c.type)">{{ c.type_label }}</a-tag>
          </div>
          <div class="ch-big">{{ c.total.toLocaleString() }} <span class="unit">人次</span></div>
          <div class="ch-nums">
            <span>{{ t('peopleCount.enter') }} <b class="in">{{ c.enter.toLocaleString() }}</b></span>
            <span>{{ t('peopleCount.exit') }} <b class="out">{{ c.exit.toLocaleString() }}</b></span>
            <span>{{ t('peopleCount.colNet') }} <b :class="c.enter - c.exit >= 0 ? 'pos' : 'neg'">{{ (c.enter - c.exit).toLocaleString() }}</b></span>
          </div>
        </div>
      </div>

      <div class="charts-grid">
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.floorHour24') }}</div>
          <ChartPanel :option="floorHourOption" height="260px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.floorDailyTrend') }}</div>
          <ChartPanel :option="floorDailyOption" height="260px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.floorChannelShare') }}</div>
          <ChartPanel :option="floorShareOption" height="260px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.floorChannelHour') }}</div>
          <ChartPanel :option="floorChannelHourOption" height="260px" />
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped lang="less">
.people-count-floor {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-intro {
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

.card {
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
  padding: 16px 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    font-weight: 600;
    color: #6b6b6b;
  }
}

.form-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.form-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.floor-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.floor-btn {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid #e6e2da;
  background: var(--brand-surface, #fff);
  font-size: 14px;
  font-weight: 600;
  color: #6b6b6b;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: var(--brand-color, #c4a574);
    color: var(--brand-color, #c4a574);
  }

  &.active {
    background: var(--brand-color, #c4a574);
    border-color: var(--brand-color, #c4a574);
    color: #fff;
  }
}

.floor-kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.kpi {
  padding: 16px 18px;
}

.kpi-label {
  font-size: 12px;
  color: #6b6b6b;
  margin-bottom: 6px;
  font-weight: 600;
}

.kpi-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.1;
  color: #0d0d0d;

  &.small {
    font-size: 15px;
  }

  &.green {
    color: #2f9e6e;
  }

  &.blue {
    color: #2f6fd6;
  }

  &.yellow {
    color: #c9a227;
  }

  &.orange {
    color: #e0782f;
  }
}

.kpi-sub {
  font-size: 12px;
  color: #6b6b6b;
  margin-top: 6px;
}

.ch-list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.ch-card {
  padding: 14px 16px;
}

.ch-name {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ch-big {
  font-size: 24px;
  font-weight: 700;
  color: #0d0d0d;

  .unit {
    font-size: 13px;
    color: #6b6b6b;
    font-weight: 400;
  }
}

.ch-nums {
  display: flex;
  gap: 16px;
  margin-top: 6px;
  font-size: 13px;
  color: #6b6b6b;

  b {
    font-weight: 600;
  }

  .in {
    color: #2f6fd6;
  }

  .out {
    color: #e0782f;
  }

  .pos {
    color: #2f9e6e;
  }

  .neg {
    color: #d6454f;
  }
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.chart-card {
  min-width: 0;
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #0d0d0d;
  margin-bottom: 8px;
}

@media (max-width: 1100px) {
  .ch-list {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }

  .floor-kpis {
    grid-template-columns: repeat(2, 1fr);
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .ch-list {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>