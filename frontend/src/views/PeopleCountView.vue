<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import {
  getPeopleCountOverview,
  listPeopleCountChannels,
  type PeopleCountOverview as OverviewData,
} from '@/api/peopleCount'
import ChartPanel from '@/components/ChartPanel.vue'
import {
  buildDailyTrendOption,
  buildHourDistOption,
  buildChannelTopOption,
  buildFloorDistOption,
  buildChannelTypeOption,
  buildDailyNetOption,
  buildWeekdayHourOption,
  buildCumulativeOption,
  WEEKDAYS_ZH,
} from '@/utils/peopleCountAggregateCharts'

const { t } = useI18n()

const loading = ref(false)
const overview = ref<OverviewData | null>(null)
const channels = ref<string[]>([])

// 篩選條件：整合為「日期時間範圍」（年月日時，分鐘固定 00）
const dateTimeRange = ref<[Dayjs | null, Dayjs | null] | null>(null)
const channelName = ref<string | undefined>(undefined)
const excludeZero = ref(true)

/** 截止到昨天的最近 7 天默認範圍（整點，分鐘為 0） */
function defaultRange(): [Dayjs, Dayjs] {
  const end = dayjs().subtract(1, 'day').hour(23).minute(0).second(0).millisecond(0)
  const start = end.subtract(6, 'day').hour(0).minute(0).second(0).millisecond(0)
  return [start, end]
}

const weekdayNames = computed(() =>
  Array.from({ length: 7 }, (_, i) => WEEKDAYS_ZH[i]),
)

const labels = computed(() => ({
  enter: t('peopleCount.enter'),
  exit: t('peopleCount.exit'),
}))

const netLabels = computed(() => ({
  net: t('peopleCount.netFlow'),
  enter: t('peopleCount.enter'),
  exit: t('peopleCount.exit'),
}))

const dailyTrendOption = computed(() =>
  overview.value ? buildDailyTrendOption(overview.value, labels.value) : {},
)
const hourDistOption = computed(() =>
  overview.value ? buildHourDistOption(overview.value, labels.value) : {},
)
const channelTopOption = computed(() =>
  overview.value ? buildChannelTopOption(overview.value, labels.value) : {},
)
const floorDistOption = computed(() =>
  overview.value ? buildFloorDistOption(overview.value, labels.value) : {},
)
const channelTypeOption = computed(() =>
  overview.value ? buildChannelTypeOption(overview.value) : {},
)
const dailyNetOption = computed(() =>
  overview.value ? buildDailyNetOption(overview.value, netLabels.value) : {},
)
const weekdayHourOption = computed(() =>
  overview.value ? buildWeekdayHourOption(overview.value, weekdayNames.value) : {},
)
const cumulativeOption = computed(() =>
  overview.value ? buildCumulativeOption(overview.value) : {},
)

const meta = computed(() => overview.value?.meta ?? null)

/** 由整合的日期時間範圍拆出查詢參數：日期取起止日、時段取起止小時 */
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
  load()
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
  <div class="people-count-view">
    <div class="page-intro">
      <div>
        <h1>{{ t('peopleCount.viewTitle') }}</h1>
        <p>{{ t('peopleCount.viewSubtitle') }}</p>
      </div>
    </div>

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

      <!-- KPI -->
      <div v-if="meta" class="kpis">
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiTotal') }}</div>
          <div class="kpi-value green">{{ meta.total_people.toLocaleString() }}</div>
          <div class="kpi-sub">{{ t('peopleCount.kpiTotalSub', { enter: meta.total_enter.toLocaleString(), exit: meta.total_exit.toLocaleString() }) }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiDailyAvg') }}</div>
          <div class="kpi-value blue">{{ Math.round(meta.daily_avg).toLocaleString() }}</div>
          <div class="kpi-sub">{{ meta.days }} 天</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiMaxDay') }}</div>
          <div class="kpi-value yellow">{{ meta.max_day ? meta.max_day.total.toLocaleString() : '—' }}</div>
          <div class="kpi-sub">{{ meta.max_day?.date ?? '—' }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiPeakHour') }}</div>
          <div class="kpi-value orange">{{ meta.peak_hour ? `${meta.peak_hour.hour}:00` : '—' }}</div>
          <div class="kpi-sub">{{ meta.peak_hour ? `${t('peopleCount.enter')} ${meta.peak_hour.total.toLocaleString()}` : '—' }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiBusiestChannel') }}</div>
          <div class="kpi-value blue">{{ meta.busiest_channel ? meta.busiest_channel.total.toLocaleString() : '—' }}</div>
          <div class="kpi-sub">{{ meta.busiest_channel?.name ?? '—' }}</div>
        </div>
        <div class="card kpi">
          <div class="kpi-label">{{ t('peopleCount.kpiBusiestFloor') }}</div>
          <div class="kpi-value green">{{ meta.busiest_floor ? meta.busiest_floor.total.toLocaleString() : '—' }}</div>
          <div class="kpi-sub">{{ meta.busiest_floor?.floor ?? '—' }}</div>
        </div>
      </div>

      <!-- 圖表 -->
      <div class="charts-grid">
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartDailyTrend') }}</div>
          <ChartPanel :option="dailyTrendOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartHourDist') }}</div>
          <ChartPanel :option="hourDistOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartChannelTop') }}</div>
          <ChartPanel :option="channelTopOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartFloorDist') }}</div>
          <ChartPanel :option="floorDistOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartChannelType') }}</div>
          <ChartPanel :option="channelTypeOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartDailyNet') }}</div>
          <ChartPanel :option="dailyNetOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartWeekdayHour') }}</div>
          <ChartPanel :option="weekdayHourOption" height="280px" />
        </div>
        <div class="card chart-card">
          <div class="chart-title">{{ t('peopleCount.chartCumulative') }}</div>
          <ChartPanel :option="cumulativeOption" height="280px" />
        </div>
      </div>
  </div>
</template>

<style scoped lang="less">
.people-count-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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

.kpis {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
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
  font-size: 30px;
  font-weight: 700;
  line-height: 1.1;
  color: #0d0d0d;
  overflow: hidden;
  text-overflow: ellipsis;

  &.small {
    font-size: 16px;
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

.charts-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.chart-card {
  min-width: 0;

  &.wide {
    grid-column: span 2;
  }
}

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: #0d0d0d;
  margin-bottom: 8px;
}

@media (max-width: 1400px) {
  .kpis {
    grid-template-columns: repeat(3, 1fr);
  }

  .charts-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }

  .charts-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 560px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>