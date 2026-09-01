<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { DownOutlined } from '@ant-design/icons-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  assignUserPosts,
  assignUserRoles,
  createUser,
  deleteUser,
  getUserPostIds,
  getUserRoleIds,
  listDepts,
  listPostOptions,
  listRoleOptions,
  listUsers,
  resetUserPassword,
  updateUser,
  type SysDeptRow,
  type SysPostRow,
  type SysRoleRow,
  type SysUserRow,
} from '@/api/system'

const { t } = useI18n()

const loading = ref(false)
const rows = ref<SysUserRow[]>([])
const total = ref(0)
const deptTree = ref<SysDeptRow[]>([])
const selectedDept = ref<number | undefined>(undefined)
const deptSearchValue = ref('')

const columns: TableColumnsType<SysUserRow> = [
  { title: t('system.userId'), dataIndex: 'id', width: 80 },
  { title: t('system.userUsername'), dataIndex: 'username', width: 120 },
  { title: t('system.userNickname'), dataIndex: 'nickname', width: 120 },
  { title: t('system.dept'), dataIndex: 'dept_name', width: 120 },
  { title: t('system.userPhone'), dataIndex: 'phone', width: 130 },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 90,
    customRender: ({ record }) =>
      record.status === 1
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.createdAt'), dataIndex: 'created_at', width: 170 },
  { title: t('system.actions'), key: 'actions', width: 180, fixed: 'right' },
]

const query = reactive({ username: '', phone: '', status: undefined as number | undefined, offset: 0, limit: 10 })

async function load() {
  loading.value = true
  try {
    const res = await listUsers({
      keyword: query.username || query.phone,
      status: query.status,
      dept_id: selectedDept.value,
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
  query.username = ''
  query.phone = ''
  query.status = undefined
  onSearch()
}

function onSelectDept(deptId?: number) {
  selectedDept.value = deptId
  onSearch()
}

function isSuperAdmin(row: SysUserRow): boolean {
  return (row.role_keys || '').split(',').includes('admin')
}

// ---------- 新增 / 编辑 ----------
const modalOpen = ref(false)
const modalLoading = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  username: '',
  password: '',
  dept_id: undefined as number | undefined,
  nickname: '',
  email: '',
  phone: '',
  status: 1,
  remark: '',
  post_ids: [] as number[],
  role_ids: [] as number[],
})

const roleOptions = ref<SysRoleRow[]>([])
const postOptions = ref<SysPostRow[]>([])

async function loadOptions() {
  if (!roleOptions.value.length) {
    const res = await listRoleOptions()
    roleOptions.value = res.data
  }
  if (!postOptions.value.length) {
    const res = await listPostOptions()
    postOptions.value = res.data
  }
}

async function openCreate() {
  editingId.value = null
  Object.assign(form, {
    username: '',
    password: '',
    dept_id: selectedDept.value,
    nickname: '',
    email: '',
    phone: '',
    status: 1,
    remark: '',
    post_ids: [],
    role_ids: [],
  })
  await loadOptions()
  modalOpen.value = true
}

async function openEdit(row: SysUserRow) {
  editingId.value = row.id
  Object.assign(form, {
    username: row.username,
    password: '',
    dept_id: row.dept_id ?? undefined,
    nickname: row.nickname || '',
    email: row.email || '',
    phone: row.phone || '',
    status: row.status,
    remark: row.remark || '',
    post_ids: [],
    role_ids: [],
  })
  await loadOptions()
  const [roleRes, postRes] = await Promise.all([
    getUserRoleIds(row.id),
    getUserPostIds(row.id),
  ])
  form.role_ids = roleRes.data
  form.post_ids = postRes.data
  modalOpen.value = true
}

async function submitModal() {
  if (editingId.value === null) {
    if (!form.username || !form.password) {
      message.warning(t('login.required'))
      return
    }
    modalLoading.value = true
    try {
      const res = await createUser({ ...form })
      await Promise.all([
        assignUserRoles(res.data.id, form.role_ids),
        assignUserPosts(res.data.id, form.post_ids),
      ])
      message.success(t('system.saveSuccess'))
      modalOpen.value = false
      load()
    } finally {
      modalLoading.value = false
    }
  } else {
    modalLoading.value = true
    try {
      await updateUser(editingId.value, {
        dept_id: form.dept_id,
        nickname: form.nickname,
        email: form.email,
        phone: form.phone,
        status: form.status,
        remark: form.remark,
      })
      await Promise.all([
        assignUserRoles(editingId.value, form.role_ids),
        assignUserPosts(editingId.value, form.post_ids),
      ])
      message.success(t('system.saveSuccess'))
      modalOpen.value = false
      load()
    } finally {
      modalLoading.value = false
    }
  }
}

// ---------- 删除 ----------
function onDelete(row: SysUserRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.username}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteUser(row.id)
        message.success(t('system.deleteSuccess'))
        load()
      } catch {
        // 已由拦截器提示
      }
    },
  })
}

// ---------- 重置密码 ----------
const pwdOpen = ref(false)
const pwdLoading = ref(false)
const pwdUserId = ref<number | null>(null)
const newPassword = ref('')

function openResetPwd(row: SysUserRow) {
  pwdUserId.value = row.id
  newPassword.value = ''
  pwdOpen.value = true
}

async function submitResetPwd() {
  if (pwdUserId.value === null || newPassword.value.length < 6) return
  pwdLoading.value = true
  try {
    await resetUserPassword(pwdUserId.value, newPassword.value)
    message.success(t('system.saveSuccess'))
    pwdOpen.value = false
  } finally {
    pwdLoading.value = false
  }
}

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

function filterDeptTree(nodes: SysDeptRow[], keyword: string): SysDeptRow[] {
  return nodes.reduce<SysDeptRow[]>((acc, node) => {
    const children = filterDeptTree(node.children || [], keyword)
    if (node.dept_name.toLowerCase().includes(keyword) || children.length > 0) {
      acc.push({ ...node, children })
    }
    return acc
  }, [])
}

function collectAllKeys(nodes: SysDeptRow[]): number[] {
  const keys: number[] = []
  for (const node of nodes) {
    keys.push(node.dept_id)
    if (node.children?.length) keys.push(...collectAllKeys(node.children))
  }
  return keys
}

const filteredDeptTree = computed(() => {
  if (!deptSearchValue.value) return deptTree.value
  return filterDeptTree(deptTree.value, deptSearchValue.value.toLowerCase())
})

const expandedDeptKeys = computed(() => {
  if (deptSearchValue.value) return collectAllKeys(filteredDeptTree.value)
  return undefined
})

onMounted(async () => {
  const res = await listDepts()
  deptTree.value = buildDeptTree(res.data)
  load()
})
</script>

<template>
  <div class="app-container">
    <a-card :bordered="false">
      <div class="user-layout">
        <!-- 左侧部门树 -->
        <div class="dept-tree">
          <a-input-search
            v-model:value="deptSearchValue"
            :placeholder="t('system.deptSearch')"
            allow-clear
            style="margin-bottom: 8px"
          />
          <a-tree
            :tree-data="filteredDeptTree"
            :field-names="{ key: 'dept_id', title: 'dept_name', children: 'children' }"
            :default-expand-all="!deptSearchValue"
            :expanded-keys="expandedDeptKeys"
            :selected-keys="selectedDept ? [selectedDept] : []"
            @select="(keys: any[]) => onSelectDept(keys[0] as number | undefined)"
          />
        </div>

        <!-- 右侧用户列表 -->
        <div class="user-main">
          <div class="toolbar">
            <a-input
              v-model:value="query.username"
              :placeholder="t('system.userUsername')"
              allow-clear
              style="width: 160px"
              @press-enter="onSearch"
            />
            <a-input
              v-model:value="query.phone"
              :placeholder="t('system.userPhone')"
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
                { value: 1, label: t('system.enabled') },
                { value: 0, label: t('system.disabled') },
              ]"
            />
            <a-button type="primary" @click="onSearch">{{ t('system.search') }}</a-button>
            <a-button @click="onReset">{{ t('system.reset') }}</a-button>
            <a-button v-permission="'system:user:add'" type="primary" ghost @click="openCreate">
              + {{ t('system.add') }}
            </a-button>
          </div>

          <a-table
            :columns="columns"
            :data-source="rows"
            :loading="loading"
            row-key="id"
            :pagination="pagination"
            :scroll="{ x: 1200 }"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'actions'">
                <template v-if="!isSuperAdmin(record)">
                  <a-button
                    v-permission="'system:user:edit'"
                    type="link"
                    size="small"
                    @click="openEdit(record)"
                  >
                    {{ t('system.edit') }}
                  </a-button>
                  <a-dropdown>
                    <a-button type="link" size="small">
                      {{ t('system.more') }} <DownOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item v-permission="'system:user:resetPwd'" @click="openResetPwd(record)">
                          {{ t('system.userResetPwd') }}
                        </a-menu-item>
                        <a-menu-item v-permission="'system:user:assignRole'" @click="openEdit(record)">
                          {{ t('system.userAssignRole') }}
                        </a-menu-item>
                        <a-menu-item v-permission="'system:user:remove'" @click="onDelete(record)">
                          <span style="color: #ff4d4f">{{ t('system.delete') }}</span>
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </template>
              </template>
            </template>
          </a-table>
        </div>
      </div>
    </a-card>

    <!-- 新增 / 编辑 -->
    <a-modal
      v-model:open="modalOpen"
      :title="editingId === null ? t('system.add') : t('system.edit')"
      :confirm-loading="modalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      @ok="submitModal"
      width="620px"
    >
      <a-form layout="vertical">
        <div class="form-row">
          <a-form-item :label="t('system.userNickname')" class="form-col">
            <a-input v-model:value="form.nickname" />
          </a-form-item>
          <a-form-item :label="t('system.dept')" class="form-col">
            <a-tree-select
              v-model:value="form.dept_id"
              :tree-data="deptTree"
              :field-names="{ label: 'dept_name', value: 'dept_id', children: 'children' }"
              :placeholder="t('system.dept')"
              allow-clear
              tree-default-expand-all
              style="width: 100%"
            />
          </a-form-item>
        </div>
        <div class="form-row">
          <a-form-item :label="t('system.userPhone')" class="form-col">
            <a-input v-model:value="form.phone" />
          </a-form-item>
          <a-form-item :label="t('system.userEmail')" class="form-col">
            <a-input v-model:value="form.email" />
          </a-form-item>
        </div>
        <div class="form-row">
          <a-form-item :label="t('system.userUsername')" class="form-col">
            <a-input v-model:value="form.username" :disabled="editingId !== null" />
          </a-form-item>
          <a-form-item v-if="editingId === null" :label="t('system.userPassword')" class="form-col">
            <a-input-password v-model:value="form.password" :placeholder="t('system.userPasswordHint')" />
          </a-form-item>
        </div>
        <div class="form-row">
          <a-form-item :label="t('system.status')" class="form-col">
            <a-radio-group v-model:value="form.status">
              <a-radio :value="1">{{ t('system.enabled') }}</a-radio>
              <a-radio :value="0">{{ t('system.disabled') }}</a-radio>
            </a-radio-group>
          </a-form-item>
        </div>
        <div class="form-row">
          <a-form-item :label="t('system.post')" class="form-col">
            <a-select
              v-model:value="form.post_ids"
              mode="multiple"
              :placeholder="t('system.post')"
              :options="postOptions.map(p => ({ value: p.post_id, label: p.post_name }))"
            />
          </a-form-item>
          <a-form-item :label="t('system.role')" class="form-col">
            <a-select
              v-model:value="form.role_ids"
              mode="multiple"
              :placeholder="t('system.role')"
              :options="roleOptions.map(r => ({ value: r.id, label: r.role_name }))"
            />
          </a-form-item>
        </div>
        <a-form-item :label="t('system.remark')">
          <a-input v-model:value="form.remark" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 重置密码 -->
    <a-modal
      v-model:open="pwdOpen"
      :title="t('system.userResetPwd')"
      :confirm-loading="pwdLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      @ok="submitResetPwd"
    >
      <a-input-password
        v-model:value="newPassword"
        :placeholder="t('system.userPasswordHint')"
        style="width: 100%"
      />
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.user-layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;

  .dept-tree {
    border-right: 1px solid var(--brand-line, #f0f0f0);
    padding-right: 12px;
    overflow: auto;
    max-height: calc(100vh - 240px);
  }

  .user-main {
    min-width: 0;
  }
}

.toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.form-row {
  display: flex;
  gap: 16px;
}

.form-col {
  flex: 1;
  min-width: 0;
}
</style>
