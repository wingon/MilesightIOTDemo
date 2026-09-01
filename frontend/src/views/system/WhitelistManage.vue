<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  createWhitelist,
  deleteWhitelist,
  listWhitelists,
  updateWhitelist,
  type WhitelistRow,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<WhitelistRow[]>([])
const total = ref(0)

const columns: TableColumnsType<WhitelistRow> = [
  { title: t('system.wlId'), dataIndex: 'id', width: 70 },
  {
    title: t('system.wlPathType'),
    dataIndex: 'path_type',
    width: 110,
    customRender: ({ record }) =>
      record.path_type === 'F'
        ? h('span', { class: 'tag-front' }, t('system.wlFront'))
        : h('span', { class: 'tag-api' }, t('system.wlApi')),
  },
  { title: t('system.wlPath'), dataIndex: 'path' },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) =>
      record.status === '0'
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.remark'), dataIndex: 'remark', width: 200, ellipsis: true },
  { title: t('system.updatedAt'), dataIndex: 'update_time', width: 170 },
  { title: t('system.actions'), key: 'actions', width: 130 },
]

const query = reactive({ keyword: '', path_type: undefined as string | undefined, offset: 0, limit: 10 })

async function load() {
  loading.value = true
  try {
    const res = await listWhitelists(query)
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
  query.keyword = ''
  query.path_type = undefined
  onSearch()
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ path: '', path_type: 'F', remark: '', status: '0' })

function openCreate() {
  editingId.value = null
  Object.assign(form, { path: '', path_type: 'F', remark: '', status: '0' })
  modalOpen.value = true
}

function openEdit(row: WhitelistRow) {
  editingId.value = row.id
  Object.assign(form, {
    path: row.path,
    path_type: row.path_type,
    remark: row.remark || '',
    status: row.status,
  })
  modalOpen.value = true
}

async function submitModal() {
  if (!form.path) {
    message.warning(t('system.wlPathRequired'))
    return
  }
  modalLoading.value = true
  try {
    if (editingId.value === null) {
      await createWhitelist({ ...form })
    } else {
      await updateWhitelist(editingId.value, { ...form })
    }
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function onDelete(row: WhitelistRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.path}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteWhitelist(row.id)
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
      <a-alert
        :message="t('system.wlHint')"
        type="info"
        show-icon
        style="margin-bottom: 16px"
      />
      <div class="toolbar">
        <a-input
          v-model:value="query.keyword"
          :placeholder="t('system.keyword')"
          allow-clear
          style="width: 220px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.path_type"
          :placeholder="t('system.wlPathType')"
          allow-clear
          style="width: 140px"
          :options="[
            { value: 'F', label: t('system.wlFront') },
            { value: 'A', label: t('system.wlApi') },
          ]"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
        <a-button v-permission="'system:whitelist:add'" type="primary" ghost @click="openCreate">
          + {{ t('system.add') }}
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
            <a-button
              v-permission="'system:whitelist:edit'"
              type="link"
              size="small"
              @click="openEdit(record)"
            >
              {{ t('system.edit') }}
            </a-button>
            <a-button
              v-permission="'system:whitelist:remove'"
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

    <a-modal
      v-model:open="modalOpen"
      :title="editingId === null ? t('system.add') : t('system.edit')"
      :confirm-loading="modalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      @ok="submitModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.wlPath')">
          <a-input v-model:value="form.path" :placeholder="t('system.wlPathPlaceholder')" />
        </a-form-item>
        <a-form-item :label="t('system.wlPathType')">
          <a-radio-group v-model:value="form.path_type">
            <a-radio value="F">{{ t('system.wlFront') }}</a-radio>
            <a-radio value="A">{{ t('system.wlApi') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.status')">
          <a-radio-group v-model:value="form.status">
            <a-radio value="0">{{ t('system.enabled') }}</a-radio>
            <a-radio value="1">{{ t('system.disabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.remark')">
          <a-input v-model:value="form.remark" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
</style>
