<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { cleanOperLogs, deleteOperLogs, listOperLogs, type OperLogRow } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<OperLogRow[]>([])
const total = ref(0)
const query = reactive({
  title: '',
  oper_name: '',
  status: undefined as number | undefined,
  business_type: undefined as number | undefined,
  begin: undefined as unknown,
  end: undefined as unknown,
  offset: 0,
  limit: 10,
})

/** 日期选择器值（dayjs）或字符串 → 后端 yyyy-MM-dd HH:mm:ss 字符串 */
function toDateTime(v: unknown, fallback: string): string | undefined {
  if (v == null || v === '') return undefined
  if (typeof v === 'string') return v
  const d = v as { format?: (fmt: string) => string }
  if (typeof d.format === 'function') return d.format(fallback)
  return String(v)
}

function businessLabel(type: number): string {
  if (type === 1) return t('system.businessType.insert')
  if (type === 2) return t('system.businessType.update')
  if (type === 3) return t('system.businessType.delete')
  if (type === 4) return t('system.businessType.authorize')
  return t('system.businessType.other')
}

const businessOptions = [
  { value: 1, label: t('system.businessType.insert') },
  { value: 2, label: t('system.businessType.update') },
  { value: 3, label: t('system.businessType.delete') },
  { value: 4, label: t('system.businessType.authorize') },
  { value: 0, label: t('system.businessType.other') },
]

const columns: TableColumnsType<OperLogRow> = [
  { title: t('system.logId'), dataIndex: 'id', width: 80 },
  { title: t('system.logTitle'), dataIndex: 'title', width: 120 },
  {
    title: t('system.logBusinessType'),
    dataIndex: 'business_type',
    width: 100,
    customRender: ({ record }) => businessLabel(record.business_type),
  },
  { title: t('system.logRequestMethod'), dataIndex: 'request_method', width: 90 },
  { title: t('system.logOperName'), dataIndex: 'oper_name', width: 120 },
  { title: t('system.logIp'), dataIndex: 'oper_ip', width: 130 },
  {
    title: t('system.logStatus'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) =>
      record.status === 1
        ? h('span', { class: 'tag-ok' }, t('system.logSuccess'))
        : h('span', { class: 'tag-no' }, t('system.logFail')),
  },
  { title: t('system.logOperTime'), dataIndex: 'oper_time', width: 170 },
  { title: t('system.actions'), key: 'actions', width: 110, fixed: 'right' },
]

const pagination = computed(() => ({
  current: query.offset / query.limit + 1,
  pageSize: query.limit,
  total,
  showSizeChanger: true,
  onChange: onPageChange,
}))

function onPageChange(page: number, size: number) {
  query.offset = (page - 1) * size
  query.limit = size
  load()
}

async function load() {
  loading.value = true
  try {
    const res = await listOperLogs({
      ...query,
      begin: toDateTime(query.begin, 'YYYY-MM-DD 00:00:00'),
      end: toDateTime(query.end, 'YYYY-MM-DD 23:59:59'),
    })
    rows.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function onSearch() {
  query.offset = 0
  load()
}

function onReset() {
  query.title = ''
  query.oper_name = ''
  query.status = undefined
  query.business_type = undefined
  query.begin = undefined
  query.end = undefined
  onSearch()
}

// ---------- 详情 ----------
const detailOpen = ref(false)
const detailRow = ref<OperLogRow | null>(null)

function openDetail(row: OperLogRow) {
  detailRow.value = row
  detailOpen.value = true
}

// ---------- 删除 / 清空 ----------
function onDelete(row: OperLogRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteOperLogs([row.id])
        message.success(t('system.deleteSuccess'))
        load()
      } catch {
        // 已由拦截器提示
      }
    },
  })
}

function onClean() {
  Modal.confirm({
    title: t('system.logCleanConfirm'),
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await cleanOperLogs()
        message.success(t('system.deleteSuccess'))
        load()
      } catch {
        // 已由拦截器提示
      }
    },
  })
}

onMounted(load)
</script>

<template>
  <div class="app-container">
    <a-card :bordered="false">
      <div class="toolbar">
        <a-input
          v-model:value="query.title"
          :placeholder="t('system.logTitle')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-input
          v-model:value="query.oper_name"
          :placeholder="t('system.logOperName')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.business_type"
          :placeholder="t('system.logBusinessType')"
          allow-clear
          style="width: 130px"
          :options="businessOptions"
        />
        <a-select
          v-model:value="query.status"
          :placeholder="t('system.logStatus')"
          allow-clear
          style="width: 120px"
          :options="[
            { value: 1, label: t('system.logSuccess') },
            { value: 0, label: t('system.logFail') },
          ]"
        />
        <a-date-picker
          v-model:value="query.begin"
          :placeholder="t('system.logBegin')"
          style="width: 150px"
        />
        <span class="range-sep">~</span>
        <a-date-picker
          v-model:value="query.end"
          :placeholder="t('system.logEnd')"
          style="width: 150px"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
        <a-button v-permission="'system:log:clean'" danger ghost @click="onClean">
          {{ t('system.logClean') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-button type="link" size="small" @click="openDetail(record)">
              {{ t('system.detail') }}
            </a-button>
            <a-button
              v-permission="'system:log:remove'"
              type="link"
              size="small"
              danger
              @click="onDelete(record)"
            >
              {{ t('system.delete') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 详情 -->
    <a-modal
      v-model:open="detailOpen"
      :title="t('system.logParam')"
      :footer="null"
      width="720px"
    >
      <a-descriptions v-if="detailRow" bordered :column="1" size="small">
        <a-descriptions-item :label="t('system.logTitle')">
          {{ detailRow.title }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logBusinessType')">
          {{ businessLabel(detailRow.business_type) }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logMethod')">
          {{ detailRow.method }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logOperName')">
          {{ detailRow.oper_name }}（{{ detailRow.oper_ip }}）
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logOperTime')">
          {{ detailRow.oper_time }}
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logParam')">
          <pre class="detail-pre">{{ detailRow.oper_param || '-' }}</pre>
        </a-descriptions-item>
        <a-descriptions-item :label="t('system.logResult')">
          <pre class="detail-pre">{{ detailRow.json_result || '-' }}</pre>
        </a-descriptions-item>
        <a-descriptions-item v-if="detailRow.error_msg" :label="t('system.logError')">
          <pre class="detail-pre err">{{ detailRow.error_msg }}</pre>
        </a-descriptions-item>
      </a-descriptions>
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}
</style>
