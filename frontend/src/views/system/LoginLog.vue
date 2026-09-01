<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { cleanLoginLogs, deleteLoginLogs, listLoginLogs, type LoginLogRow } from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<LoginLogRow[]>([])
const total = ref(0)
const selectedKeys = ref<number[]>([])

const columns: TableColumnsType<LoginLogRow> = [
  { title: t('system.logInfoId'), dataIndex: 'info_id', width: 90 },
  { title: t('system.logUserName'), dataIndex: 'user_name', width: 120 },
  { title: t('system.logIpaddr'), dataIndex: 'ipaddr', width: 140 },
  { title: t('system.logBrowser'), dataIndex: 'browser', width: 110 },
  { title: t('system.logOs'), dataIndex: 'os', width: 110 },
  {
    title: t('system.logLoginStatus'),
    dataIndex: 'status',
    width: 100,
    customRender: ({ record }) =>
      record.status === '0'
        ? h('span', { class: 'tag-ok' }, t('system.logSuccess'))
        : h('span', { class: 'tag-no' }, t('system.logFail')),
  },
  { title: t('system.logMsg'), dataIndex: 'msg', ellipsis: true },
  { title: t('system.logLoginTime'), dataIndex: 'login_time', width: 170 },
]

const query = reactive({
  user_name: '',
  status: undefined as string | undefined,
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

async function load() {
  loading.value = true
  try {
    const res = await listLoginLogs({
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

function onSearch() {
  query.offset = 0
  load()
}

function onReset() {
  query.user_name = ''
  query.status = undefined
  query.begin = undefined
  query.end = undefined
  onSearch()
}

function onDeleteSelected() {
  if (!selectedKeys.value.length) return
  Modal.confirm({
    title: t('system.deleteConfirm'),
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteLoginLogs(selectedKeys.value)
        message.success(t('system.deleteSuccess'))
        selectedKeys.value = []
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
        await cleanLoginLogs()
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
          v-model:value="query.user_name"
          :placeholder="t('system.logUserName')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.status"
          :placeholder="t('system.logLoginStatus')"
          allow-clear
          style="width: 140px"
          :options="[
            { value: '0', label: t('system.logSuccess') },
            { value: '1', label: t('system.logFail') },
          ]"
        />
        <a-date-picker
          v-model:value="query.begin"
          :placeholder="t('system.logBegin')"
          style="width: 160px"
        />
        <span class="range-sep">~</span>
        <a-date-picker
          v-model:value="query.end"
          :placeholder="t('system.logEnd')"
          style="width: 160px"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
        <div class="toolbar-spacer"></div>
        <a-button
          v-permission="'system:loginlog:remove'"
          danger
          :disabled="!selectedKeys.length"
          @click="onDeleteSelected"
        >
          {{ t('system.delete') }}
        </a-button>
        <a-button
          v-permission="'system:loginlog:clean'"
          danger
          ghost
          @click="onClean"
        >
          {{ t('system.logClean') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="info_id"
        :pagination="pagination"
        :row-selection="{ selectedRowKeys: selectedKeys, onChange: (keys: any[]) => (selectedKeys = keys) }"
      >
      </a-table>
    </a-card>
  </div>
</template>

<style scoped lang="less">
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;

  .toolbar-spacer {
    flex: 1;
  }
}
</style>
