<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { SearchOutlined, ReloadOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  getPeopleCountOverview,
  listPeopleCountChannels,
  createPeopleCountExport,
  getPeopleCountExportStatus,
  downloadPeopleCountExport,
  type PeopleCountOverview as OverviewData,
  type PeopleCountExportParams,
  type PeopleCountExportLang,
} from '@/api/peopleCount'
import { typeLabel, weekdayLabel } from '@/utils/peopleCountType'

const { t, locale } = useI18n()

const loading = ref(false)
const overview = ref<OverviewData | null>(null)
const channels = ref<string[]>([])
const activeTab = ref<'daily' | 'channel'>('daily')

// 篩選條件：整合為「日期時間範圍」。
// 預設為空，由後端回傳最近 7 天數據；用戶自行填寫則依所選範圍查詢。
const dateTimeRange = ref<[Dayjs | null, Dayjs | null] | null>(null)
const channelName = ref<string | undefined>(undefined)
const excludeZero = ref(false)

// 匯出狀態
const exporting = ref(false)
const exportModalOpen = ref(false)
const exportPercent = ref(0)
const exportError = ref(false)

const weekdayName = (w: number) => weekdayLabel(t, w)

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

/** 未填寫範圍時預設最近 7 天（含今天），時段不限制（整天） */
function defaultWindow() {
  const now = dayjs()
  return { s: now.subtract(6, 'day'), e: now }
}

/** 由整合的日期時間範圍拆出日期/時段參數；未填範圍時回傳預設近 7 天 */
function buildDateParams() {
  const range = dateTimeRange.value
  if (range) {
    const s = range[0]
    const e = range[1]
    return {
      date_from: s?.format('YYYY-MM-DD') || undefined,
      date_to: e?.format('YYYY-MM-DD') || undefined,
      hour_from: s?.hour(),
      hour_to: e?.hour(),
    }
  }
  const { s, e } = defaultWindow()
  return {
    date_from: s.format('YYYY-MM-DD'),
    date_to: e.format('YYYY-MM-DD'),
    hour_from: undefined,
    hour_to: undefined,
  }
}

/** 由整合的日期時間範圍拆出查詢參數 */
function buildQuery() {
  return {
    ...buildDateParams(),
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
    console.error(t('peopleCount.loadFailed'), e)
  } finally {
    loading.value = false
  }
}

function onReset() {
  dateTimeRange.value = null
  channelName.value = undefined
  excludeZero.value = false
  load()
}

async function loadChannels() {
  try {
    const { data } = await listPeopleCountChannels()
    channels.value = data
  } catch (e: unknown) {
    channels.value = []
    console.error(t('peopleCount.loadFailed'), e)
  }
}

/** 由整合的日期時間範圍拆出匯出參數（含目前語言）；未填範圍時同樣預設近 7 天 */
function makeExportParams(): PeopleCountExportParams {
  const lang = (locale.value === 'zh-TW' ? 'zh-TW' : 'en') as PeopleCountExportLang
  return {
    ...buildDateParams(),
    channel_name: channelName.value,
    exclude_zero: excludeZero.value,
    lang,
  }
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function saveBlob(blob: Blob, filename?: string | null) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename || 'people_count.zip'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function pollExport(taskId: string) {
  let attempts = 0
  while (exporting.value) {
    const { data } = await getPeopleCountExportStatus(taskId)
    exportPercent.value = data.progress ?? 0
    if (data.status === 'failed') {
      exportError.value = true
      message.error(data.error || t('peopleCount.exportFailed'))
      return
    }
    if (data.status === 'done') {
      exportPercent.value = 100
      try {
        const { data: blob } = await downloadPeopleCountExport(taskId)
        saveBlob(blob, data.filename)
        message.success(t('peopleCount.exportDone'))
      } catch {
        exportError.value = true
        message.error(t('peopleCount.exportFailed'))
      }
      return
    }
    attempts += 1
    if (attempts >= 600) {
      // 上限約 15 分鐘，避免任務卡死時無限輪詢
      exportError.value = true
      message.error(t('peopleCount.exportFailed'))
      return
    }
    await sleep(1500)
  }
}

async function onExport() {
  if (exporting.value) return
  exporting.value = true
  exportModalOpen.value = true
  exportError.value = false
  exportPercent.value = 0
  try {
    const { data } = await createPeopleCountExport(makeExportParams())
    exportPercent.value = 5
    await pollExport(data.task_id)
  } catch {
    // 400（超過半年 / 無資料等）提示已由 http.ts 攔截器以 message 顯示
    exportError.value = true
  } finally {
    exporting.value = false
    exportModalOpen.value = false
  }
}

onMounted(() => {
  loadChannels()
  load()
})

onBeforeUnmount(() => {
  exporting.value = false
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
          <a-button :loading="exporting" :disabled="loading" class="export-btn" @click="onExport">
            <DownloadOutlined /> {{ t('peopleCount.exportBtn') }}
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
            <a-tag :color="typeColor(record.type)">{{ typeLabel(t, record.type) }}</a-tag>
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

    <!-- 匯出進度 -->
    <a-modal
      v-model:open="exportModalOpen"
      :title="t('peopleCount.exportTitle')"
      :footer="null"
      :closable="false"
      :mask-closable="false"
      :width="320"
      centered
    >
      <div class="export-body">
        <a-progress
          :percent="exportPercent"
          :status="exportPercent >= 100 ? 'success' : exportError ? 'exception' : 'active'"
          :stroke-width="6"
          class="export-progress"
        />
        <p class="export-hint">
          {{ exportError ? t('peopleCount.exportFailed') : t('peopleCount.exportHint') }}
        </p>
      </div>
    </a-modal>
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

.export-body {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 8px 4px 4px;
}

.export-progress {
  width: 220px;
}

.export-hint {
  margin: 0;
  color: #6b6b6b;
  font-size: 12px;
  text-align: center;
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