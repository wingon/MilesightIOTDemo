<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import dayjs, { type Dayjs } from 'dayjs'
import {
  listPeopleCountHourly,
  listPeopleCountChannels,
  type PeopleCountHourlyRow,
} from '@/api/peopleCount'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<PeopleCountHourlyRow[]>([])
const total = ref(0)

// Filter state (date_from / date_to are sent only when the range picker has a value)
const dateRange = ref<[Dayjs | null, Dayjs | null] | null>(null)
const hour = ref<number | undefined>(undefined)
const channelName = ref<string | undefined>(undefined)
const ipAddress = ref('')
const channels = ref<string[]>([])

// Pagination state (server-side pagination)
const page = ref(1)
const pageSize = ref(20)

const hourOptions = computed(() =>
  Array.from({ length: 24 }, (_, h) => ({ value: h, label: `${h}:00` })),
)

const columns = computed(() => [
  { title: t('peopleCount.colDate'), dataIndex: 'date', key: 'date', width: 120 },
  { title: t('peopleCount.colHour'), dataIndex: 'hour', key: 'hour', width: 90 },
  { title: t('peopleCount.colChannel'), dataIndex: 'channel_name', key: 'channel_name', width: 200 },
  { title: t('peopleCount.colIp'), dataIndex: 'ip_address', key: 'ip_address', width: 130 },
  { title: t('peopleCount.colEnter'), dataIndex: 'enter_count', key: 'enter_count', width: 110, align: 'right' as const },
  { title: t('peopleCount.colExit'), dataIndex: 'exit_count', key: 'exit_count', width: 110, align: 'right' as const },
  { title: t('peopleCount.colUpdated'), dataIndex: 'updated_at', key: 'updated_at', width: 180 },
])

// Build the API query from the current filter state
function buildQuery() {
  return {
    date_from: dateRange.value?.[0]?.format('YYYY-MM-DD') || undefined,
    date_to: dateRange.value?.[1]?.format('YYYY-MM-DD') || undefined,
    hour: hour.value,
    ip_address: ipAddress.value.trim() || undefined,
    channel_name: channelName.value,
    limit: pageSize.value,
    offset: (page.value - 1) * pageSize.value,
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await listPeopleCountHourly(buildQuery())
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    const err = e instanceof Error ? e.message : String(e)
    message.error(`${t('peopleCount.loadFailed')} ${err}`)
  } finally {
    loading.value = false
  }
}

// Reset filters to their defaults and reload the first page
function onReset() {
  dateRange.value = null
  hour.value = undefined
  channelName.value = undefined
  ipAddress.value = ''
  page.value = 1
  load()
}

// Server-side pagination change handler
function onPageChange(p: number, ps: number) {
  page.value = p
  pageSize.value = ps
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
  loadChannels()
  load()
})
</script>

<template>
  <div class="people-count-page">
    <div class="page-intro">
      <h1>{{ t('peopleCount.title') }}</h1>
      <p>{{ t('peopleCount.subtitle') }}</p>
    </div>

    <div class="card form-card">
      <div class="form-grid">
        <div class="field">
          <label>{{ t('peopleCount.dateRange') }}</label>
          <a-range-picker v-model:value="dateRange" style="width: 100%" />
        </div>
        <div class="field">
          <label>{{ t('peopleCount.hour') }}</label>
          <a-select
            v-model:value="hour"
            :options="hourOptions"
            :placeholder="t('peopleCount.hourPlaceholder')"
            allow-clear
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
        <div class="field">
          <label>{{ t('peopleCount.ip') }}</label>
          <a-input
            v-model:value="ipAddress"
            :placeholder="t('peopleCount.ipPlaceholder')"
            allow-clear
            @pressEnter="onPageChange(1, pageSize)"
          />
        </div>
      </div>

      <div class="form-actions">
        <a-button type="primary" :loading="loading" @click="onPageChange(1, pageSize)">
          {{ t('common.query') }}
        </a-button>
        <a-button @click="onReset">{{ t('common.refresh') }}</a-button>
      </div>
    </div>

    <div class="card table-card">
      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="id"
        size="middle"
        :scroll="{ x: 960 }"
        :pagination="{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (tCount: number) => t('peopleCount.totalRows', { n: tCount }),
          onChange: onPageChange,
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'updated_at'">
            {{ record.updated_at ? dayjs(record.updated_at).format('YYYY-MM-DD HH:mm:ss') : '—' }}
          </template>
          <template v-else-if="column.key === 'enter_count' || column.key === 'exit_count'">
            {{ record[column.key as 'enter_count' | 'exit_count'].toLocaleString() }}
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<style scoped lang="less">
.people-count-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 1100px;
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
  background: #fff;
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

.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
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