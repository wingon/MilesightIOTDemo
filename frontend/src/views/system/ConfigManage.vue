<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  createConfig,
  deleteConfig,
  listConfigs,
  updateConfig,
  type SysConfigRow,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<SysConfigRow[]>([])
const total = ref(0)

const columns: TableColumnsType<SysConfigRow> = [
  { title: t('system.configId'), dataIndex: 'config_id', width: 80 },
  { title: t('system.configName'), dataIndex: 'config_name', width: 200 },
  { title: t('system.configKey'), dataIndex: 'config_key', width: 220 },
  { title: t('system.configValue'), dataIndex: 'config_value', ellipsis: true },
  {
    title: t('system.configType'),
    dataIndex: 'config_type',
    width: 100,
    customRender: ({ record }) =>
      record.config_type === 'Y'
        ? h('span', { class: 'tag-ok' }, t('system.configBuiltin'))
        : t('system.configCustom'),
  },
  { title: t('system.remark'), dataIndex: 'remark', width: 160, ellipsis: true },
  { title: t('system.actions'), key: 'actions', width: 130 },
]

const query = reactive({
  config_name: '',
  config_key: '',
  config_type: undefined as string | undefined,
  offset: 0,
  limit: 10,
})

async function load() {
  loading.value = true
  try {
    const res = await listConfigs(query)
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
  query.config_name = ''
  query.config_key = ''
  query.config_type = undefined
  onSearch()
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ config_name: '', config_key: '', config_value: '', config_type: 'N', remark: '' })

function openCreate() {
  editingId.value = null
  Object.assign(form, { config_name: '', config_key: '', config_value: '', config_type: 'N', remark: '' })
  modalOpen.value = true
}

function openEdit(row: SysConfigRow) {
  editingId.value = row.config_id
  Object.assign(form, {
    config_name: row.config_name,
    config_key: row.config_key,
    config_value: row.config_value,
    config_type: row.config_type,
    remark: row.remark || '',
  })
  modalOpen.value = true
}

async function submitModal() {
  if (!form.config_name || !form.config_key) {
    message.warning(t('system.configRequired'))
    return
  }
  modalLoading.value = true
  try {
    if (editingId.value === null) {
      await createConfig({ ...form })
    } else {
      await updateConfig(editingId.value, { ...form })
    }
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function onDelete(row: SysConfigRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.config_name}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteConfig(row.config_id)
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
          v-model:value="query.config_name"
          :placeholder="t('system.configName')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-input
          v-model:value="query.config_key"
          :placeholder="t('system.configKey')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.config_type"
          :placeholder="t('system.configType')"
          allow-clear
          style="width: 120px"
          :options="[
            { value: 'Y', label: t('system.configBuiltin') },
            { value: 'N', label: t('system.configCustom') },
          ]"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
        <a-button v-permission="'system:config:add'" type="primary" ghost @click="openCreate">
          + {{ t('system.add') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="config_id"
        :pagination="pagination"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-button
              v-permission="'system:config:edit'"
              type="link"
              size="small"
              @click="openEdit(record)"
            >
              {{ t('system.edit') }}
            </a-button>
            <a-button
              v-permission="'system:config:remove'"
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
        <a-form-item :label="t('system.configName')">
          <a-input v-model:value="form.config_name" />
        </a-form-item>
        <a-form-item :label="t('system.configKey')">
          <a-input v-model:value="form.config_key" />
        </a-form-item>
        <a-form-item :label="t('system.configValue')">
          <a-textarea v-model:value="form.config_value" :rows="3" />
        </a-form-item>
        <a-form-item :label="t('system.configType')">
          <a-radio-group v-model:value="form.config_type">
            <a-radio value="Y">{{ t('system.configBuiltin') }}</a-radio>
            <a-radio value="N">{{ t('system.configCustom') }}</a-radio>
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
