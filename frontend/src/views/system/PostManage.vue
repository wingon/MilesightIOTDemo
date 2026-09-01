<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  createPost,
  deletePost,
  listPosts,
  updatePost,
  type SysPostRow,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<SysPostRow[]>([])
const total = ref(0)

const columns: TableColumnsType<SysPostRow> = [
  { title: t('system.postId'), dataIndex: 'post_id', width: 80 },
  { title: t('system.postCode'), dataIndex: 'post_code', width: 160 },
  { title: t('system.postName'), dataIndex: 'post_name', width: 180 },
  { title: t('system.postSort'), dataIndex: 'post_sort', width: 100 },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) =>
      record.status === '0'
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.createdAt'), dataIndex: 'create_time', width: 170 },
  { title: t('system.actions'), key: 'actions', width: 130 },
]

const query = reactive({ post_code: '', post_name: '', status: undefined as string | undefined, offset: 0, limit: 10 })

async function load() {
  loading.value = true
  try {
    const res = await listPosts(query)
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
  query.post_code = ''
  query.post_name = ''
  query.status = undefined
  onSearch()
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ post_code: '', post_name: '', post_sort: 0, status: '0', remark: '' })

function openCreate() {
  editingId.value = null
  Object.assign(form, { post_code: '', post_name: '', post_sort: 0, status: '0', remark: '' })
  modalOpen.value = true
}

function openEdit(row: SysPostRow) {
  editingId.value = row.post_id
  Object.assign(form, {
    post_code: row.post_code,
    post_name: row.post_name,
    post_sort: row.post_sort,
    status: row.status,
    remark: row.remark || '',
  })
  modalOpen.value = true
}

async function submitModal() {
  if (!form.post_code || !form.post_name) {
    message.warning(t('system.postRequired'))
    return
  }
  modalLoading.value = true
  try {
    if (editingId.value === null) {
      await createPost({ ...form })
    } else {
      await updatePost(editingId.value, { ...form })
    }
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function onDelete(row: SysPostRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.post_name}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deletePost(row.post_id)
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
          v-model:value="query.post_code"
          :placeholder="t('system.postCode')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-input
          v-model:value="query.post_name"
          :placeholder="t('system.postName')"
          allow-clear
          style="width: 160px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.status"
          :placeholder="t('system.status')"
          allow-clear
          style="width: 120px"
          :options="[
            { value: '0', label: t('system.enabled') },
            { value: '1', label: t('system.disabled') },
          ]"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
        <a-button v-permission="'system:post:add'" type="primary" ghost @click="openCreate">
          + {{ t('system.add') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="post_id"
        :pagination="pagination"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-button
              v-permission="'system:post:edit'"
              type="link"
              size="small"
              @click="openEdit(record)"
            >
              {{ t('system.edit') }}
            </a-button>
            <a-button
              v-permission="'system:post:remove'"
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
        <a-form-item :label="t('system.postCode')">
          <a-input v-model:value="form.post_code" />
        </a-form-item>
        <a-form-item :label="t('system.postName')">
          <a-input v-model:value="form.post_name" />
        </a-form-item>
        <a-form-item :label="t('system.postSort')">
          <a-input-number v-model:value="form.post_sort" :min="0" style="width: 100%" />
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
