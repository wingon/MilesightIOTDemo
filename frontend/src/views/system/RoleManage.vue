<script setup lang="ts">
import { computed, h, nextTick, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType, TreeProps } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  assignRoleDataScope,
  assignRoleMenus,
  changeRoleStatus,
  createRole,
  deleteRolesBatch,
  getRole,
  getRoleDeptIds,
  getRoleDeptTree,
  getRoleMenuIds,
  getRoleMenuTree,
  listRoles,
  updateRole,
  type SysDeptRow,
  type SysRoleRow,
} from '@/api/system'
import type { MenuNode } from '@/api/auth'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<SysRoleRow[]>([])
const total = ref(0)
const selectedRowKeys = ref<number[]>([])

const columns: TableColumnsType<SysRoleRow> = [
  { title: t('system.roleId'), dataIndex: 'id', width: 100 },
  { title: t('system.roleName'), dataIndex: 'role_name', width: 150, ellipsis: true },
  { title: t('system.roleKey'), dataIndex: 'role_key', width: 150, ellipsis: true },
  { title: t('system.roleSort'), dataIndex: 'sort', width: 90 },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) => h('span', {
      class: record.status === 1 ? 'tag-ok' : 'tag-no',
    }, record.status === 1 ? t('system.enabled') : t('system.disabled')),
  },
  { title: t('system.createdAt'), dataIndex: 'created_at', width: 170 },
  {
    title: t('system.actions'),
    key: 'actions',
    width: 220,
    fixed: 'right',
    customRender: ({ record }) => {
      const isAdmin = record.role_key === 'admin'
      if (isAdmin) return h('span', '-')
      return h('div', { class: 'row-actions' }, [
        h('a', { onClick: () => openEdit(record) }, t('system.edit')),
        ' ',
        h('a', { onClick: () => openDataScope(record) }, t('system.dataScope')),
        ' ',
        h('a', { class: 'danger', onClick: () => handleDelete(record) }, t('system.delete')),
      ])
    },
  },
]

const query = reactive({
  role_name: '',
  role_key: '',
  status: undefined as number | undefined,
  dateRange: [] as string[],
  offset: 0,
  limit: 10,
})

async function load() {
  loading.value = true
  try {
    const res = await listRoles({
      role_name: query.role_name,
      role_key: query.role_key,
      status: query.status,
      begin: query.dateRange?.[0],
      end: query.dateRange?.[1],
      offset: query.offset,
      limit: query.limit,
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
  showTotal: (sum: number) => t('system.totalCount', { n: sum }),
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
  query.role_name = ''
  query.role_key = ''
  query.status = undefined
  query.dateRange = []
  onSearch()
}

function onRowSelectionChange(keys: (string | number)[]) {
  selectedRowKeys.value = keys.map(Number)
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ role_name: '', role_key: '', sort: 0, status: 1, data_scope: '1', remark: '' })

// 菜单树
const menuTree = ref<MenuNode[]>([])
const menuExpand = ref(false)
const menuNodeAll = ref(false)
const menuCheckStrictly = ref(true)
const checkedMenuIds = ref<number[]>([])
const halfCheckedMenuIds = ref<number[]>([])
const menuTreeRef = ref<{ getCheckedKeys: () => (string | number)[]; getHalfCheckedKeys: () => (string | number)[] }>()

async function initMenuTree() {
  if (!menuTree.value.length) {
    const res = await getRoleMenuTree()
    menuTree.value = res.data.menus || []
  }
}

function toggleMenuExpand(value: boolean) {
  menuExpand.value = value
  if (menuTreeRef.value?.getHalfCheckedKeys) return
  nextTick(() => {
    const treeEl = document.querySelector('.menu-perm-tree')
    treeEl?.querySelectorAll('.ant-tree-treenode').forEach((el) => {
      const indent = (el as HTMLElement).style.paddingLeft
      // 简化：展开/折叠由 tree 组件 state 控制，这里仅切换勾选
    })
  })
}

function handleMenuCheckChange(
  key: number | string,
  info: { checked: boolean; node: { checkedKeys?: (string | number)[]; halfCheckedKeys?: (string | number)[] } },
) {
  checkedMenuIds.value = (info.node.checkedKeys || []) as number[]
  halfCheckedMenuIds.value = (info.node.halfCheckedKeys || []) as number[]
}

function getMenuAllCheckedKeys(): number[] {
  const checked = menuTreeRef.value?.getCheckedKeys?.() || []
  const half = menuTreeRef.value?.getHalfCheckedKeys?.() || []
  return [...checked, ...half].map(Number)
}

function setMenuChecked(ids: number[]) {
  nextTick(() => {
    const el = menuTreeRef.value
    if (!el) return
    // antdv 树通过 checkedKeys 单向控制；采用默认联动，逐个 setChecked 影响父子
    checkedMenuIds.value = ids
  })
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { role_name: '', role_key: '', sort: 0, status: 1, data_scope: '1', remark: '' })
  checkedMenuIds.value = []
  halfCheckedMenuIds.value = []
  menuExpand.value = false
  initMenuTree()
  modalOpen.value = true
}

async function openEdit(row: SysRoleRow) {
  editingId.value = row.id
  await initMenuTree()
  const detail = await getRole(row.id)
  Object.assign(form, {
    role_name: detail.data.role_name,
    role_key: detail.data.role_key,
    sort: detail.data.sort,
    status: detail.data.status,
    data_scope: detail.data.data_scope || '1',
    remark: detail.data.remark || '',
  })
  const menuIds = (await getRoleMenuIds(row.id)).data
  checkedMenuIds.value = menuIds
  halfCheckedMenuIds.value = []
  modalOpen.value = true
  nextTick(() => {
    if (menuTreeRef.value && !menuCheckStrictly.value) {
      // 联动模式下需先展开根节点再反射已选
    }
  })
}

async function submitModal() {
  if (!form.role_name || !form.role_key) return
  modalLoading.value = true
  try {
    const body = { ...form }
    if (editingId.value === null) {
      const res = await createRole(body)
      await assignRoleMenus(res.data.id, getMenuAllCheckedKeys())
    } else {
      await updateRole(editingId.value, body)
      await assignRoleMenus(editingId.value, getMenuAllCheckedKeys())
    }
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function handleDelete(row: SysRoleRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.role_name}（${row.role_key}）`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      await deleteRolesBatch([row.id])
      message.success(t('system.deleteSuccess'))
      load()
    },
  })
}

function onBatchDelete() {
  if (!selectedRowKeys.value.length) return
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: t('system.batchDeleteConfirm', { n: selectedRowKeys.value.length }),
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      await deleteRolesBatch(selectedRowKeys.value)
      message.success(t('system.deleteSuccess'))
      selectedRowKeys.value = []
      load()
    },
  })
}

// ---------- 状态切换 ----------
async function onStatusChange(row: SysRoleRow, checked: boolean) {
  if (row.role_key === 'admin') return
  const newStatus = checked ? 1 : 0
  const text = checked ? t('system.enabled') : t('system.disabled')
  try {
    await changeRoleStatus(row.id, newStatus)
    message.success(`${text}${t('system.saveSuccess')}`)
    row.status = newStatus
  } catch {
    row.status = checked ? 0 : 1
  }
}

// ---------- 数据权限 ----------
const dataScopeOpen = ref(false)
const dataScopeLoading = ref(false)
const dataScopeRoleId = ref<number | null>(null)
const dataScopeForm = reactive({ data_scope: '1' })
const deptTree = ref<SysDeptRow[]>([])
const checkedDeptIds = ref<number[]>([])
const halfCheckedDeptIds = ref<number[]>([])
const deptTreeRef = ref<{ getCheckedKeys: () => (string | number)[]; getHalfCheckedKeys: () => (string | number)[] }>()
const deptExpand = ref(true)
const deptNodeAll = ref(false)
const deptCheckStrictly = ref(true)

const dataScopeOptions = [
  { value: '1', label: t('system.dataScopeAll') },
  { value: '2', label: t('system.dataScopeCustom') },
  { value: '3', label: t('system.dataScopeDept') },
  { value: '4', label: t('system.dataScopeDeptAndChild') },
  { value: '5', label: t('system.dataScopeSelf') },
]

async function openDataScope(row: SysRoleRow) {
  dataScopeRoleId.value = row.id
  Object.assign(dataScopeForm, { data_scope: row.data_scope || '1' })
  if (!deptTree.value.length) {
    const res = await getRoleDeptTree()
    deptTree.value = res.data.depts || []
  }
  const deptIds = (await getRoleDeptIds(row.id)).data
  checkedDeptIds.value = deptIds
  halfCheckedDeptIds.value = []
  dataScopeOpen.value = true
}

function handleDeptCheckChange(
  key: number | string,
  info: { checked: boolean; node: { checkedKeys?: (string | number)[]; halfCheckedKeys?: (string | number)[] } },
) {
  checkedDeptIds.value = (info.node.checkedKeys || []) as number[]
  halfCheckedDeptIds.value = (info.node.halfCheckedKeys || []) as number[]
}

function getDeptAllCheckedKeys(): number[] {
  const checked = deptTreeRef.value?.getCheckedKeys?.() || []
  const half = deptTreeRef.value?.getHalfCheckedKeys?.() || []
  return [...checked, ...half].map(Number)
}

async function submitDataScope() {
  if (dataScopeRoleId.value === null) return
  dataScopeLoading.value = true
  try {
    await assignRoleDataScope(dataScopeRoleId.value, {
      data_scope: dataScopeForm.data_scope,
      dept_ids: dataScopeForm.data_scope === '2' ? getDeptAllCheckedKeys() : [],
    })
    message.success(t('system.saveSuccess'))
    dataScopeOpen.value = false
    load()
  } finally {
    dataScopeLoading.value = false
  }
}

// 供 a-tree 使用的字段映射与事件
const menuFieldNames = { key: 'id', title: 'menu_name', children: 'children' }
const deptFieldNames = { key: 'dept_id', title: 'dept_name', children: 'children' }

function onMenuExpandToggle(value: boolean) {
  menuExpand.value = value
}

function onMenuNodeAll(value: boolean) {
  menuNodeAll.value = value
  // antdv 树：通过 checkStrictly 实现全选/全不选
  checkAllMenu(value)
}

function onDeptExpandToggle(value: boolean) {
  deptExpand.value = value
}

function onDeptNodeAll(value: boolean) {
  checkAllDept(value)
}

function checkAllMenu(checked: boolean) {
  const els = document.querySelectorAll('.menu-perm-tree')
  // antdv: 用 group 方式全选需要访问 tree 实例；这里用递归收集叶子
  const collect = (nodes: MenuNode[]): number[] => {
    const out: number[] = []
    for (const n of nodes) {
      if (n.children?.length) out.push(...collect(n.children))
      else out.push(n.id)
    }
    return out
  }
  if (checked) {
    checkedMenuIds.value = collect(menuTree.value)
  } else {
    checkedMenuIds.value = []
  }
}

function checkAllDept(checked: boolean) {
  const collect = (nodes: SysDeptRow[]): number[] => {
    const out: number[] = []
    for (const n of nodes) {
      if (n.children?.length) out.push(...collect(n.children))
      else out.push(n.dept_id)
    }
    return out
  }
  if (checked) {
    checkedDeptIds.value = collect(deptTree.value)
  } else {
    checkedDeptIds.value = []
  }
}

onMounted(load)
</script>

<template>
  <div class="app-container">
    <a-card :bordered="false">
      <!-- 查询区 -->
      <div class="toolbar">
        <a-input v-model:value="query.role_name" :placeholder="t('system.roleName')" allow-clear style="width: 180px" @press-enter="onSearch" />
        <a-input v-model:value="query.role_key" :placeholder="t('system.roleKey')" allow-clear style="width: 180px" @press-enter="onSearch" />
        <a-select v-model:value="query.status" :placeholder="t('system.status')" allow-clear style="width: 120px" :options="[
          { value: 1, label: t('system.enabled') },
          { value: 0, label: t('system.disabled') },
        ]" />
        <a-range-picker v-model:value="query.dateRange" value-format="YYYY-MM-DD" style="width: 240px" />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
      </div>

      <!-- 操作区 -->
      <div class="toolbar" style="margin-top: 8px">
        <a-button v-permission="'system:role:add'" type="primary" ghost @click="openCreate">
          + {{ t('system.add') }}
        </a-button>
        <a-button
          v-permission="'system:role:remove'"
          type="danger"
          ghost
          :disabled="!selectedRowKeys.length"
          @click="onBatchDelete"
        >
          - {{ t('system.delete') }}
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="rows"
        :loading="loading"
        row-key="id"
        :pagination="pagination"
        :row-selection="{ selectedRowKeys, onChange: onRowSelectionChange }"
      />
    </a-card>

    <!-- 新增 / 编辑 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId === null ? t('system.addRole') : t('system.editRole')"
      :confirm-loading="modalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      width="640px"
      @ok="submitModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.roleName')" required>
          <a-input v-model:value="form.role_name" :placeholder="t('system.roleName')" />
        </a-form-item>
        <a-form-item :label="t('system.roleKey')" required>
          <a-input v-model:value="form.role_key" :placeholder="t('system.roleKey')" :disabled="editingId !== null" />
        </a-form-item>
        <a-form-item :label="t('system.roleSort')">
          <a-input-number v-model:value="form.sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('system.status')">
          <a-radio-group v-model:value="form.status">
            <a-radio :value="1">{{ t('system.enabled') }}</a-radio>
            <a-radio :value="0">{{ t('system.disabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.roleMenuPermissions')">
          <div class="tree-controls">
            <a-checkbox v-model:checked="menuExpand" @change="(e: any) => onMenuExpandToggle(e.target.checked)">{{ t('system.expandCollapse') }}</a-checkbox>
            <a-checkbox v-model:checked="menuNodeAll" @change="(e: any) => onMenuNodeAll(e.target.checked)">{{ t('system.selectAllNone') }}</a-checkbox>
            <a-checkbox v-model:checked="menuCheckStrictly">{{ t('system.parentChildLink') }}</a-checkbox>
          </div>
          <div class="tree-border menu-perm-tree">
            <a-tree
              ref="menuTreeRef"
              checkable
              :check-strictly="!menuCheckStrictly"
              :tree-data="menuTree"
              :field-names="menuFieldNames"
              :checked-keys="checkedMenuIds"
              default-expand-all
              @check="handleMenuCheckChange"
            />
          </div>
        </a-form-item>
        <a-form-item :label="t('system.remark')">
          <a-textarea v-model:value="form.remark" :rows="3" :placeholder="t('system.remark')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 分配数据权限 -->
    <a-modal
      v-model:open="dataScopeOpen"
      :title="t('system.assignDataScope')"
      :confirm-loading="dataScopeLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      width="560px"
      @ok="submitDataScope"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.roleName')">
          <a-input :value="rows.find((r) => r.id === dataScopeRoleId)?.role_name" disabled />
        </a-form-item>
        <a-form-item :label="t('system.roleKey')">
          <a-input :value="rows.find((r) => r.id === dataScopeRoleId)?.role_key" disabled />
        </a-form-item>
        <a-form-item :label="t('system.dataScope')">
          <a-select v-model:value="dataScopeForm.data_scope" style="width: 100%">
            <a-select-option v-for="opt in dataScopeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('system.dataPermission')" v-show="dataScopeForm.data_scope === '2'">
          <div class="tree-controls">
            <a-checkbox v-model:checked="deptExpand" @change="(e: any) => onDeptExpandToggle(e.target.checked)">{{ t('system.expandCollapse') }}</a-checkbox>
            <a-checkbox v-model:checked="deptNodeAll" @change="(e: any) => onDeptNodeAll(e.target.checked)">{{ t('system.selectAllNone') }}</a-checkbox>
            <a-checkbox v-model:checked="deptCheckStrictly">{{ t('system.parentChildLink') }}</a-checkbox>
          </div>
          <div class="tree-border dept-perm-tree">
            <a-tree
              ref="deptTreeRef"
              checkable
              :check-strictly="!deptCheckStrictly"
              :tree-data="deptTree"
              :field-names="deptFieldNames"
              :checked-keys="checkedDeptIds"
              default-expand-all
              @check="handleDeptCheckChange"
            />
          </div>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.toolbar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tree-controls {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.tree-border {
  max-height: 300px;
  overflow: auto;
  border: 1px solid var(--brand-line, #e6e2da);
  border-radius: 4px;
  padding: 8px;
}

.row-actions a {
  margin-right: 10px;
  color: var(--brand-primary, #c4a574);

  &:hover {
    color: var(--brand-primary, #a88955);
    opacity: 0.82;
  }

  &.danger {
    color: var(--brand-error, #d93026);

    &:hover {
      color: #c0261c;
      opacity: 1;
    }
  }
}
</style>
