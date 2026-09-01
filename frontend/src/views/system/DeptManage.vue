<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  createDept,
  deleteDept,
  listDepts,
  updateDept,
  type SysDeptRow,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const treeData = ref<SysDeptRow[]>([])
const expandedKeys = ref<number[]>([])

const columns: TableColumnsType<SysDeptRow> = [
  { title: t('system.deptName'), dataIndex: 'dept_name' },
  { title: t('system.deptLeader'), dataIndex: 'leader', width: 120 },
  { title: t('system.deptPhone'), dataIndex: 'phone', width: 130 },
  { title: t('system.menuSort'), dataIndex: 'order_num', width: 90 },
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
  { title: t('system.actions'), key: 'actions', width: 150 },
]

function buildDeptTree(flat: SysDeptRow[]): SysDeptRow[] {
  const map = new Map<number, SysDeptRow>()
  const roots: SysDeptRow[] = []
  for (const item of flat) {
    map.set(item.dept_id, { ...item, children: [] })
  }
  for (const item of flat) {
    const node = map.get(item.dept_id)!
    if (item.parent_id && map.has(item.parent_id)) {
      map.get(item.parent_id)!.children!.push(node)
    } else {
      roots.push(node)
    }
  }
  return roots
}

function getAllKeys(data: SysDeptRow[]): number[] {
  const keys: number[] = []
  const walk = (list: SysDeptRow[]) => {
    for (const d of list) {
      if (d.children?.length) {
        keys.push(d.dept_id)
        walk(d.children)
      }
    }
  }
  walk(data)
  return keys
}

async function load() {
  loading.value = true
  try {
    const res = await listDepts()
    const tree = buildDeptTree(res.data)
    treeData.value = tree
    if (!expandedKeys.value.length) {
      expandedKeys.value = getAllKeys(tree)
    }
  } finally {
    loading.value = false
  }
}

function onExpandAll() {
  expandedKeys.value = getAllKeys(treeData.value)
}

function onCollapseAll() {
  expandedKeys.value = []
}

function onTableExpand(expanded: boolean, record: SysDeptRow) {
  if (expanded) {
    expandedKeys.value = [...expandedKeys.value, record.dept_id]
  } else {
    expandedKeys.value = expandedKeys.value.filter((k) => k !== record.dept_id)
  }
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  parent_id: 0,
  dept_name: '',
  order_num: 0,
  leader: '',
  phone: '',
  email: '',
  status: '0',
})

function openCreate(parent: SysDeptRow | null = null) {
  editingId.value = null
  Object.assign(form, {
    parent_id: parent ? parent.dept_id : 0,
    dept_name: '',
    order_num: parent ? parent.order_num + 1 : 0,
    leader: '',
    phone: '',
    email: '',
    status: '0',
  })
  modalOpen.value = true
}

function openEdit(row: SysDeptRow) {
  editingId.value = row.dept_id
  Object.assign(form, {
    parent_id: row.parent_id,
    dept_name: row.dept_name,
    order_num: row.order_num,
    leader: row.leader || '',
    phone: row.phone || '',
    email: row.email || '',
    status: row.status,
  })
  modalOpen.value = true
}

async function submitModal() {
  if (!form.dept_name) {
    message.warning(t('system.deptNameRequired'))
    return
  }
  modalLoading.value = true
  try {
    if (editingId.value === null) {
      await createDept({ ...form })
    } else {
      await updateDept(editingId.value, { ...form })
    }
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function onDelete(row: SysDeptRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.dept_name}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteDept(row.dept_id)
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
        <a-button @click="onExpandAll">{{ t('system.expandAll') }}</a-button>
        <a-button @click="onCollapseAll">{{ t('system.collapseAll') }}</a-button>
        <div class="toolbar-spacer"></div>
        <a-button v-permission="'system:dept:add'" type="primary" @click="openCreate(null)">
          + {{ t('system.add') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="treeData"
        :loading="loading"
        row-key="dept_id"
        :pagination="false"
        :expanded-row-keys="expandedKeys"
        children-column-name="children"
        @expand="onTableExpand"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-button type="link" size="small" @click="openCreate(record)">
              {{ t('system.add') }}
            </a-button>
            <a-button
              v-permission="'system:dept:edit'"
              type="link"
              size="small"
              @click="openEdit(record)"
            >
              {{ t('system.edit') }}
            </a-button>
            <a-button
              v-permission="'system:dept:remove'"
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
        <a-form-item :label="t('system.deptParent')">
          <a-tree-select
            v-model:value="form.parent_id"
            :tree-data="treeData"
            :field-names="{ label: 'dept_name', value: 'dept_id', children: 'children' }"
            :placeholder="t('system.menuRoot')"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item :label="t('system.deptName')">
          <a-input v-model:value="form.dept_name" />
        </a-form-item>
        <a-form-item :label="t('system.menuSort')">
          <a-input-number v-model:value="form.order_num" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('system.deptLeader')">
          <a-input v-model:value="form.leader" />
        </a-form-item>
        <a-form-item :label="t('system.deptPhone')">
          <a-input v-model:value="form.phone" />
        </a-form-item>
        <a-form-item :label="t('system.deptEmail')">
          <a-input v-model:value="form.email" />
        </a-form-item>
        <a-form-item :label="t('system.status')">
          <a-radio-group v-model:value="form.status">
            <a-radio value="0">{{ t('system.enabled') }}</a-radio>
            <a-radio value="1">{{ t('system.disabled') }}</a-radio>
          </a-radio-group>
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
  align-items: center;

  .toolbar-spacer {
    flex: 1;
  }
}
</style>
