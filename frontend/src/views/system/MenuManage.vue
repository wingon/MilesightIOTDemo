<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import * as Icons from '@ant-design/icons-vue'
import {
  VerticalAlignBottomOutlined,
  VerticalAlignTopOutlined,
} from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { createMenu, deleteMenu, listMenus, updateMenu } from '@/api/system'
import type { MenuNode } from '@/api/auth'

const { t } = useI18n()

const loading = ref(false)
const menuTree = ref<MenuNode[]>([])
const allTree = ref<MenuNode[]>([])
const expandedKeys = ref<number[]>([])

const query = reactive({
  menu_name: '',
  status: undefined as number | undefined,
})

function collectKey(list: MenuNode[]): number[] {
  const keys: number[] = []
  const walk = (nodes: MenuNode[]) => {
    for (const m of nodes) {
      if (m.children?.length) {
        keys.push(m.id)
        walk(m.children)
      }
    }
  }
  walk(list)
  return keys
}

/** 递归过滤菜单树：子节点命中则保留父级 */
function filterTree(nodes: MenuNode[], kw: string, status?: number): MenuNode[] {
  let out: (MenuNode | null)[] = []
  for (const n of nodes) {
    const children = n.children ? filterTree(n.children, kw, status) : []
    const selfMatch =
      (!kw || (n.menu_name || '').includes(kw)) &&
      (status === undefined || n.status === status)
    if (children.length) {
      out.push({ ...n, children })
    } else if (selfMatch) {
      out.push(n)
    }
  }
  return out.filter((n): n is MenuNode => !!n)
}

async function load() {
  loading.value = true
  try {
    const res = await listMenus()
    allTree.value = res.data
    if (!expandedKeys.value.length) expandedKeys.value = collectKey(allTree.value)
    applyFilter()
  } finally {
    loading.value = false
  }
}

function applyFilter() {
  if (!query.menu_name && query.status === undefined) {
    menuTree.value = allTree.value
  } else {
    menuTree.value = filterTree(allTree.value, query.menu_name.trim(), query.status)
  }
  expandedKeys.value = collectKey(menuTree.value)
}

function onSearch() {
  applyFilter()
}

function onReset() {
  query.menu_name = ''
  query.status = undefined
  allTreeMenuRefresh()
}

function allTreeMenuRefresh() {
  menuTree.value = allTree.value
  expandedKeys.value = collectKey(allTree.value)
}

function onExpandAll() {
  expandedKeys.value = collectKey(allTree.value)
}

function onCollapseAll() {
  expandedKeys.value = []
}

function typeText(type: string): string {
  if (type === 'M') return t('system.menuTypeDir')
  if (type === 'C') return t('system.menuTypeMenu')
  return t('system.menuTypeButton')
}

function typeTagClass(type: string): string {
  if (type === 'M') return 'tag-M'
  if (type === 'C') return 'tag-C'
  return 'tag-F'
}

function renderMenuIcon(record: MenuNode) {
  if (!record.icon) return null
  const iconComp = (Icons as unknown as Record<string, any>)[record.icon]
  return iconComp ? h(iconComp, { class: 'menu-row-icon' }) : null
}

// ---------- 图标选择 ----------
const iconOptions = [
  'DashboardOutlined', 'HomeOutlined', 'AppstoreOutlined', 'SettingOutlined',
  'UserOutlined', 'TeamOutlined', 'ApartmentOutlined', 'DeploymentUnitOutlined',
  'DatabaseOutlined', 'CloudOutlined', 'ApiOutlined', 'GatewayOutlined',
  'EnvironmentOutlined', 'BellOutlined', 'LockOutlined', 'SafetyOutlined',
  'FileTextOutlined', 'ToolOutlined', 'WifiOutlined', 'ControlOutlined',
  'LayoutOutlined', 'MenuOutlined', 'ProfileOutlined', 'SlidersOutlined',
  'BarChartOutlined', 'PieChartOutlined', 'LineChartOutlined', 'FundOutlined',
  'TableOutlined', 'FormOutlined', 'CheckCircleOutlined', 'InfoCircleOutlined',
  'GlobalOutlined', 'BuildOutlined', 'ClusterOutlined', 'PartitionOutlined',
  'MonitorOutlined', 'DesktopOutlined', 'MobileOutlined', 'BulbOutlined',
  'ThunderboltOutlined', 'AlertOutlined', 'WarningOutlined', 'NotificationOutlined',
]

const iconPickerOpen = ref(false)
const iconSearch = ref('')

const currentIconComp = computed(() => {
  if (!form.icon) return null
  return (Icons as unknown as Record<string, any>)[form.icon] || null
})

const filteredIcons = computed(() =>
  iconOptions.filter((n) => n.toLowerCase().includes(iconSearch.value.trim().toLowerCase())),
)

function openIconPicker() {
  iconSearch.value = ''
  iconPickerOpen.value = true
}

function pickIcon(name: string) {
  form.icon = name
  iconPickerOpen.value = false
}

const columns: TableColumnsType<MenuNode> = [
  {
    title: t('system.menuName'),
    dataIndex: 'menu_name',
    customRender: ({ record }) =>
      h('span', { class: 'menu-name-cell' }, [renderMenuIcon(record), record.menu_name]),
  },
  {
    title: t('system.menuType'),
    dataIndex: 'menu_type',
    width: 90,
    customRender: ({ record }) =>
      h('span', { class: typeTagClass(record.menu_type) }, typeText(record.menu_type)),
  },
  { title: t('system.menuSort'), dataIndex: 'sort', width: 80 },
  { title: t('system.menuPermission'), dataIndex: 'permission', width: 200, ellipsis: true },
  { title: t('system.menuComponent'), dataIndex: 'component', width: 180, ellipsis: true },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) =>
      record.status === 1
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.actions'), key: 'actions', width: 180, fixed: 'right' },
]

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  parent_id: 0,
  menu_name: '',
  i18n_key: undefined as string | undefined,
  path: '',
  component: '',
  menu_type: 'M' as 'M' | 'C' | 'F',
  permission: '',
  icon: '',
  sort: 0,
  visible: 1,
  status: 1,
  remark: '',
})

/** 父级选择树（剔除按钮 F，按钮不能作父级） */
const parentTreeData = computed(() => filterDirMenu(menuTree.value))

function filterDirMenu(menus: MenuNode[]): { value: number; title: string; children?: unknown[] }[] {
  return menus
    .filter((m) => m.menu_type !== 'F')
    .map((m) => ({
      value: m.id,
      title: m.menu_name,
      children: m.children?.length ? filterDirMenu(m.children) : undefined,
    }))
}

function openCreate(parent?: MenuNode) {
  editingId.value = null
  Object.assign(form, {
    parent_id: parent?.id ?? 0,
    menu_name: '',
    i18n_key: undefined,
    path: '',
    component: '',
    menu_type: 'M',
    permission: '',
    icon: '',
    sort: 0,
    visible: 1,
    status: 1,
    remark: '',
  })
  modalOpen.value = true
}

function openEdit(row: MenuNode) {
  editingId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id,
    menu_name: row.menu_name,
    i18n_key: row.i18n_key || undefined,
    path: row.path || '',
    component: row.component || '',
    menu_type: row.menu_type,
    permission: row.permission || '',
    icon: row.icon || '',
    sort: row.sort,
    visible: row.visible,
    status: row.status,
    remark: row.remark || '',
  })
  modalOpen.value = true
}

async function submitModal() {
  if (!form.menu_name) return
  modalLoading.value = true
  try {
    const payload = {
      parent_id: form.parent_id,
      menu_name: form.menu_name,
      i18n_key: form.i18n_key || null,
      path: form.path || null,
      component: form.component || null,
      menu_type: form.menu_type,
      permission: form.permission || null,
      icon: form.icon || null,
      sort: form.sort,
      visible: form.visible,
      status: form.status,
      remark: form.remark || null,
    }
    if (editingId.value === null) await createMenu(payload)
    else await updateMenu(editingId.value, payload)
    message.success(t('system.saveSuccess'))
    modalOpen.value = false
    load()
  } finally {
    modalLoading.value = false
  }
}

// ---------- 删除 ----------
function onDelete(row: MenuNode) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.menu_name}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteMenu(row.id)
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
      <!-- 查询区 -->
      <div class="query-bar">
        <a-input
          v-model:value="query.menu_name"
          :placeholder="t('system.menuName')"
          allow-clear
          style="width: 200px"
          @press-enter="onSearch"
        />
        <a-select
          v-model:value="query.status"
          :placeholder="t('system.status')"
          allow-clear
          style="width: 140px"
          :options="[
            { value: 1, label: t('system.enabled') },
            { value: 0, label: t('system.disabled') },
          ]"
        />
        <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
        <a-button @click="onReset">{{ t('system.reset') }}</a-button>
      </div>

      <!-- 树操作区 -->
      <div class="tree-toolbar">
        <a-button v-permission="'system:menu:add'" type="primary" ghost @click="openCreate()">
          + {{ t('system.add') }}
        </a-button>
        <a-space :size="6">
          <a-tooltip :title="t('system.expandAll')">
            <a-button size="small" @click="onExpandAll">
              <VerticalAlignBottomOutlined />
            </a-button>
          </a-tooltip>
          <a-tooltip :title="t('system.collapseAll')">
            <a-button size="small" @click="onCollapseAll">
              <VerticalAlignTopOutlined />
            </a-button>
          </a-tooltip>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="menuTree"
        :loading="loading"
        row-key="id"
        :pagination="false"
        :expanded-row-keys="expandedKeys"
        @update:expanded-row-keys="(keys: any[]) => (expandedKeys = keys)"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'actions'">
            <a-button
              v-permission="'system:menu:add'"
              type="link"
              size="small"
              @click="openCreate(record)"
            >
              {{ t('system.add') }}
            </a-button>
            <a-button
              v-permission="'system:menu:edit'"
              type="link"
              size="small"
              @click="openEdit(record)"
            >
              {{ t('system.edit') }}
            </a-button>
            <a-button
              v-permission="'system:menu:remove'"
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

    <!-- 新增 / 编辑 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId === null ? t('system.add') : t('system.edit')"
      :confirm-loading="modalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      width="680px"
      @ok="submitModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.menuParent')">
          <a-tree-select
            v-model:value="form.parent_id"
            :tree-data="parentTreeData"
            :field-names="{ value: 'value', label: 'title', children: 'children' }"
            :placeholder="t('system.menuParent')"
            tree-default-expand-all
            style="width: 100%"
          />
        </a-form-item>

        <div class="form-row">
          <a-form-item :label="t('system.menuType')" class="form-col">
            <a-radio-group v-model:value="form.menu_type">
              <a-radio value="M">{{ t('system.menuTypeDir') }}</a-radio>
              <a-radio value="C">{{ t('system.menuTypeMenu') }}</a-radio>
              <a-radio value="F">{{ t('system.menuTypeButton') }}</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item :label="t('system.menuIcon')" class="form-col">
            <div class="icon-field">
              <button type="button" class="icon-preview" @click="openIconPicker">
                <component :is="currentIconComp" v-if="currentIconComp" class="icon-picked" />
                <span v-else class="icon-empty">＋</span>
              </button>
              <a-input
                v-model:value="form.icon"
                :placeholder="t('system.iconPicker')"
                readonly
                class="icon-input"
                @click="openIconPicker"
              />
            </div>
          </a-form-item>
        </div>

        <div class="form-row">
          <a-form-item :label="t('system.menuName')" class="form-col">
            <a-input v-model:value="form.menu_name" />
          </a-form-item>
          <a-form-item :label="t('system.menuSort')" class="form-col">
            <a-input-number v-model:value="form.sort" :min="0" style="width: 100%" />
          </a-form-item>
        </div>

        <div class="form-row">
          <a-form-item v-if="form.menu_type !== 'F'" :label="t('system.menuPath')" class="form-col">
            <a-input v-model:value="form.path" placeholder="system/user" />
          </a-form-item>
          <a-form-item v-if="form.menu_type === 'C'" :label="t('system.menuComponent')" class="form-col">
            <a-input v-model:value="form.component" placeholder="system/UserManage" />
          </a-form-item>
          <a-form-item label="i18n key" class="form-col">
            <a-input v-model:value="form.i18n_key" placeholder="menu.dashboard" />
          </a-form-item>
        </div>

        <div v-if="form.menu_type === 'F'" class="form-row">
          <a-form-item :label="t('system.menuPermission')" class="form-col">
            <a-input v-model:value="form.permission" placeholder="system:user:add" />
          </a-form-item>
        </div>

        <div class="form-row">
          <a-form-item :label="t('system.menuVisible')" class="form-col">
            <a-radio-group v-model:value="form.visible">
              <a-radio :value="1">{{ t('system.show') }}</a-radio>
              <a-radio :value="0">{{ t('system.hide') }}</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item :label="t('system.status')" class="form-col">
            <a-radio-group v-model:value="form.status">
              <a-radio :value="1">{{ t('system.normal') }}</a-radio>
              <a-radio :value="0">{{ t('system.disabled') }}</a-radio>
            </a-radio-group>
          </a-form-item>
        </div>

        <a-form-item :label="t('system.remark')">
          <a-input v-model:value="form.remark" :placeholder="t('system.remarkPlaceholder', { name: t('system.menuName') })" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 图标选择 -->
    <a-modal
      v-model:open="iconPickerOpen"
      :title="t('system.iconPicker')"
      :footer="null"
      width="560px"
      class="icon-picker-modal"
    >
      <a-input
        v-model:value="iconSearch"
        :placeholder="t('system.iconSearch')"
        allow-clear
        style="margin-bottom: 16px"
      />
      <div class="icon-grid">
        <div
          v-for="name in filteredIcons"
          :key="name"
          class="icon-item"
          :class="{ active: form.icon === name }"
          @click="pickIcon(name)"
        >
          <component :is="(Icons as any)[name]" class="icon-item-glyph" />
        </div>
        <div v-if="!filteredIcons.length" class="icon-empty-state">
          {{ t('system.iconSearch') }}
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.query-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 16px;
}

.tree-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 16px;
}

.menu-name-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.menu-row-icon {
  color: var(--brand-primary, #c4a574);
  font-size: 14px;
}

.form-row {
  display: flex;
  gap: 16px;

  .form-col {
    flex: 1;
    min-width: 0;
  }
}

/* ── 图标选择器（弹窗表单内） ── */
.icon-field {
  display: flex;
  gap: 8px;
  align-items: center;
}

.icon-preview {
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border: 1px solid var(--brand-line, #d9d9d9);
  border-radius: 6px;
  background: var(--brand-canvas, #faf8f5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.18s ease, background 0.18s ease;

  &:hover {
    border-color: var(--brand-primary, #c4a574);
    background: rgba(196, 165, 116, 0.08);
  }
}

.icon-picked {
  color: var(--brand-primary, #c4a574);
  font-size: 18px;
}

.icon-empty {
  color: var(--brand-muted, #9b968e);
  font-size: 18px;
  line-height: 1;
}

.icon-input .ant-input {
  cursor: pointer;
}

/* ── 图标选择弹窗：网格 ── */
.icon-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.icon-item {
  aspect-ratio: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--brand-line, #e6e2da);
  border-radius: 6px;
  cursor: pointer;
  color: var(--brand-ink, #5a5a5a);
  transition: border-color 0.18s ease, background 0.18s ease, transform 0.18s ease;

  &:hover {
    border-color: var(--brand-primary, #c4a574);
    background: rgba(196, 165, 116, 0.1);
    transform: translateY(-1px);
  }

  &.active {
    border-color: var(--brand-primary, #c4a574);
    background: rgba(196, 165, 116, 0.18);
    box-shadow: 0 0 0 1px var(--brand-primary, #c4a574);
  }
}

.icon-item-glyph {
  font-size: 20px;
}

.icon-empty-state {
  grid-column: 1 / -1;
  padding: 24px;
  text-align: center;
  color: var(--brand-muted, #9b968e);
  font-size: 13px;
}
</style>