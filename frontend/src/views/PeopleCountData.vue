<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  getPeopleCountOverview,
  listPeopleCountChannels,
  type PeopleCountOverview as OverviewData,
} from '@/api/peopleCount'
import { WEEKDAYS_ZH } from '@/utils/peopleCountAggregateCharts'

const { t } = useI18n()

const loading = ref(false)
const overview = ref<OverviewData | null>(null)
const channels = ref<string[]>([])
const activeTab = ref<'daily' | 'channel'>('daily')

// 篩選條件：整合為「日期時間範圍」
const dateTimeRange = ref<[Dayjs | null, Dayjs | null] | null>(null)
const channelName = ref<string | undefined>(undefined)
const excludeZero = ref(true)

/** 截止到昨天的最近 7 天默認範圍（整點，分鐘為 0） */
function defaultRange(): [Dayjs, Dayjs] {
  const end = dayjs().subtract(1, 'day').hour(23).minute(0).second(0).millisecond(0)
  const start = end.subtract(6, 'day').hour(0).minute(0).second(0).millisecond(0)
  return [start, end]
}

const weekdayName = (w: number) => WEEKDAYS_ZH[w] ?? ''

const dailyColumns = computed(() => [
  { title: t('peopleCount.colDate'), dataIndex: 'date', key: 'date', width: 120 },
  { title: t('peopleCount.colWeekday'), dataIndex: 'weekday', key: 'weekday', width: 90 },
  { title: t('peopleCount.colEnter'), dataIndex: 'enter', key: 'enter', width: 120, align: 'right' as const },
  { title: t('peopleCount.colExit'), dataIndex: 'exit', key: 'exit', width: 120, align: 'right' as const },
  { title: t('peopleCount.colTotal'), dataIndex: 'total', key: 'total', width: 120, align: 'right' as const },
])

const channelColumns = computed(() => [
  { title: t('peopleCount.colChannel'), dataIndex: 'channel_name', key: 'channel_name', width: 220 },
  { title: t('peopleCount.colFloor'), dataIndex: 'floors', key: 'floors', width: 140 },
  { title: t('peopleCount.colType'), dataIndex: 'type_label', key: 'type_label', width: 100 },
  { title: t('peopleCount.colEnter'), dataIndex: 'enter', key: 'enter', width: 110, align: 'right' as const },
  { title: t('peopleCount.colExit'), dataIndex: 'exit', key: 'exit', width: 110, align: 'right' as const },
  { title: t('peopleCount.colTotal'), dataIndex: 'total', key: 'total', width: 110, align: 'right' as const },
  { title: t('peopleCount.colNet'), key: 'net', width: 110, align: 'right' as const },
])

const dailyRows = computed(() => overview.value?.daily ?? [])
const channelRows = computed(() => overview.value?.channel ?? [])

const typeColor = (type: string) => {
  if (type === 'lift') return 'blue'
  if (type === 'stairs') return 'orange'
  return 'green'
}

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
  <div class="people-count-data">
    <div class="page-intro">
      <h1>{{ t('peopleCount.dataTitle') }}</h1>
      <p>{{ t('peopleCount.dataSubtitle') }}</p>
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

    <!-- 資料表格 -->
    <div class="card table-card">
      <div class="tabs-bar">
        <button class="tab-btn" :class="{ active: activeTab === 'daily' }" @click="activeTab = 'daily'">
          {{ t('peopleCount.tabDaily') }}
        </button>
        <button class="tab-btn" :class="{ active: activeTab === 'channel' }" @click="activeTab = 'channel'">
          {{ t('peopleCount.tabChannel') }}
        </button>
      </div>

      <a-table
        v-if="activeTab === 'daily'"
        :columns="dailyColumns"
        :data-source="dailyRows"
        :loading="loading"
        row-key="date"
        size="middle"
        :scroll="{ x: 600 }"
        :pagination="{ pageSize: 15, showTotal: (tCount: number) => t('peopleCount.totalRows', { n: tCount }) }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'weekday'">
            {{ weekdayName(record.weekday) }}
          </template>
          <template v-else-if="column.key === 'enter' || column.key === 'exit' || column.key === 'total'">
            {{ Number(record[column.key as 'enter' | 'exit' | 'total']).toLocaleString() }}
          </template>
        </template>
      </a-table>

      <a-table
        v-else
        :columns="channelColumns"
        :data-source="channelRows"
        :loading="loading"
        row-key="channel_name"
        size="middle"
        :scroll="{ x: 900 }"
        :pagination="{ pageSize: 15, showTotal: (tCount: number) => t('peopleCount.totalRows', { n: tCount }) }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'floors'">
            {{ record.floors.join('、') || '—' }}
          </template>
          <template v-else-if="column.key === 'type_label'">
            <a-tag :color="typeColor(record.type)">{{ record.type_label }}</a-tag>
          </template>
          <template v-else-if="column.key === 'enter' || column.key === 'exit' || column.key === 'total'">
            {{ Number(record[column.key as 'enter' | 'exit' | 'total']).toLocaleString() }}
          </template>
          <template v-else-if="column.key === 'net'">
            <span :class="record.enter - record.exit >= 0 ? 'net-pos' : 'net-neg'">
              {{ (record.enter - record.exit).toLocaleString() }}
            </span>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<style scoped lang="less">
.people-count-data {
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

.tabs-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.tab-btn {
  padding: 8px 20px;
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

.net-pos {
  color: #2f9e6e;
  font-weight: 600;
}

.net-neg {
  color: #d6454f;
  font-weight: 600;
}

@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>