<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import {
  createDictData,
  createDictType,
  deleteDictData,
  deleteDictType,
  listDictData,
  listDictTypes,
  updateDictData,
  updateDictType,
  type SysDictDataRow,
  type SysDictTypeRow,
} from '@/api/system'

const { t } = useI18n()

// ---------- 字典类型 ----------
const typeLoading = ref(false)
const typeRows = ref<SysDictTypeRow[]>([])
const selectedType = ref<SysDictTypeRow | null>(null)
const typeQuery = reactive({ dict_name: '', dict_type: '', status: undefined as string | undefined })

const typeColumns: TableColumnsType<SysDictTypeRow> = [
  { title: t('system.dictName'), dataIndex: 'dict_name', width: 140 },
  { title: t('system.dictType'), dataIndex: 'dict_type', width: 170 },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 80,
    customRender: ({ record }) =>
      record.status === '0'
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.remark'), dataIndex: 'remark', ellipsis: true },
]

async function loadTypes() {
  typeLoading.value = true
  try {
    const res = await listDictTypes({ ...typeQuery, offset: 0, limit: 100 })
    typeRows.value = res.data.items
  } finally {
    typeLoading.value = false
  }
}

function onTypeSelect(record: SysDictTypeRow) {
  selectedType.value = record
  loadData()
}

// ---------- 字典数据 ----------
const dataLoading = ref(false)
const dataRows = ref<SysDictDataRow[]>([])

const dataColumns: TableColumnsType<SysDictDataRow> = [
  { title: t('system.dictLabel'), dataIndex: 'dict_label', width: 140 },
  { title: t('system.dictValue'), dataIndex: 'dict_value', width: 140 },
  { title: t('system.dictSort'), dataIndex: 'dict_sort', width: 90 },
  {
    title: t('system.status'),
    dataIndex: 'status',
    width: 80,
    customRender: ({ record }) =>
      record.status === '0'
        ? h('span', { class: 'tag-ok' }, t('system.enabled'))
        : h('span', { class: 'tag-no' }, t('system.disabled')),
  },
  { title: t('system.remark'), dataIndex: 'remark', ellipsis: true },
  { title: t('system.actions'), key: 'actions', width: 130 },
]

async function loadData() {
  if (!selectedType.value) return
  dataLoading.value = true
  try {
    const res = await listDictData({ dict_type: selectedType.value.dict_type, offset: 0, limit: 500 })
    dataRows.value = res.data.items
  } finally {
    dataLoading.value = false
  }
}

// ---------- 字典类型新增 / 编辑 ----------
const typeModalOpen = ref(false)
const typeModalLoading = ref(false)
const typeEditingId = ref<number | null>(null)
const typeForm = reactive({ dict_name: '', dict_type: '', status: '0', remark: '' })

function openTypeCreate() {
  typeEditingId.value = null
  Object.assign(typeForm, { dict_name: '', dict_type: '', status: '0', remark: '' })
  typeModalOpen.value = true
}

function openTypeEdit(row: SysDictTypeRow) {
  typeEditingId.value = row.dict_id
  Object.assign(typeForm, {
    dict_name: row.dict_name,
    dict_type: row.dict_type,
    status: row.status,
    remark: row.remark || '',
  })
  typeModalOpen.value = true
}

async function submitTypeModal() {
  if (!typeForm.dict_name || !typeForm.dict_type) {
    message.warning(t('system.dictRequired'))
    return
  }
  typeModalLoading.value = true
  try {
    if (typeEditingId.value === null) {
      await createDictType({ ...typeForm })
    } else {
      await updateDictType(typeEditingId.value, { ...typeForm })
    }
    message.success(t('system.saveSuccess'))
    typeModalOpen.value = false
    loadTypes()
  } finally {
    typeModalLoading.value = false
  }
}

function onDeleteType() {
  if (!selectedType.value) return
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${selectedType.value.dict_name}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteDictType(selectedType.value!.dict_id)
        message.success(t('system.deleteSuccess'))
        selectedType.value = null
        dataRows.value = []
        loadTypes()
      } catch {
        // 已由拦截器提示
      }
    },
  })
}

// ---------- 字典数据新增 / 编辑 ----------
const dataModalOpen = ref(false)
const dataModalLoading = ref(false)
const dataEditingCode = ref<number | null>(null)
const dataForm = reactive({
  dict_sort: 0,
  dict_label: '',
  dict_value: '',
  dict_type: '',
  is_default: 'N',
  status: '0',
  remark: '',
})

function openDataCreate() {
  if (!selectedType.value) return
  dataEditingCode.value = null
  Object.assign(dataForm, {
    dict_sort: 0,
    dict_label: '',
    dict_value: '',
    dict_type: selectedType.value.dict_type,
    is_default: 'N',
    status: '0',
    remark: '',
  })
  dataModalOpen.value = true
}

function openDataEdit(row: SysDictDataRow) {
  dataEditingCode.value = row.dict_code
  Object.assign(dataForm, {
    dict_sort: row.dict_sort,
    dict_label: row.dict_label,
    dict_value: row.dict_value,
    dict_type: row.dict_type,
    is_default: row.is_default,
    status: row.status,
    remark: row.remark || '',
  })
  dataModalOpen.value = true
}

async function submitDataModal() {
  if (!dataForm.dict_label || !dataForm.dict_value) {
    message.warning(t('system.dictDataRequired'))
    return
  }
  dataModalLoading.value = true
  try {
    if (dataEditingCode.value === null) {
      await createDictData({ ...dataForm })
    } else {
      await updateDictData(dataEditingCode.value, { ...dataForm })
    }
    message.success(t('system.saveSuccess'))
    dataModalOpen.value = false
    loadData()
  } finally {
    dataModalLoading.value = false
  }
}

function onDeleteData(row: SysDictDataRow) {
  Modal.confirm({
    title: t('system.deleteConfirm'),
    content: `${row.dict_label}`,
    okText: t('system.confirm'),
    cancelText: t('system.cancel'),
    onOk: async () => {
      try {
        await deleteDictData(row.dict_code)
        message.success(t('system.deleteSuccess'))
        loadData()
      } catch {
        // 已由拦截器提示
      }
    },
  })
}

onMounted(loadTypes)
</script>

<template>
  <div class="app-container">
    <div class="dict-layout">
      <!-- 左侧：字典类型 -->
      <a-card :bordered="false" class="type-card">
        <div class="card-toolbar">
          <a-input
            v-model:value="typeQuery.dict_name"
            :placeholder="t('system.dictName')"
            allow-clear
            size="small"
            @press-enter="loadTypes"
          />
          <a-input
            v-model:value="typeQuery.dict_type"
            :placeholder="t('system.dictType')"
            allow-clear
            size="small"
            @press-enter="loadTypes"
          />
          <a-button size="small" type="primary" @click="loadTypes">{{ t('system.search') }}</a-button>
          <a-button
            v-permission="'system:dict:add'"
            size="small"
            type="primary"
            ghost
            @click="openTypeCreate"
          >
            + {{ t('system.add') }}
          </a-button>
        </div>
        <a-table
          :columns="typeColumns"
          :data-source="typeRows"
          :loading="typeLoading"
          row-key="dict_id"
          :pagination="false"
          size="small"
          :row-class-name="(record: SysDictTypeRow) => selectedType?.dict_id === record.dict_id ? 'row-selected' : ''"
          @row-click="onTypeSelect"
        >
        </a-table>
      </a-card>

      <!-- 右侧：字典数据 -->
      <a-card :bordered="false" class="data-card">
        <div class="card-toolbar">
          <span class="data-title">
            {{ t('system.dictData') }}
            <template v-if="selectedType">· {{ selectedType.dict_name }}（{{ selectedType.dict_type }}）</template>
          </span>
          <div class="toolbar-spacer"></div>
          <a-button
            v-permission="'system:dict:addData'"
            type="primary"
            ghost
            :disabled="!selectedType"
            @click="openDataCreate"
          >
            + {{ t('system.add') }}
          </a-button>
          <a-button
            v-permission="'system:dict:remove'"
            danger
            ghost
            :disabled="!selectedType"
            @click="onDeleteType"
          >
            {{ t('system.delete') }} {{ t('system.dictType') }}
          </a-button>
        </div>
        <a-table
          :columns="dataColumns"
          :data-source="dataRows"
          :loading="dataLoading"
          row-key="dict_code"
          :pagination="false"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'actions'">
              <a-button
                v-permission="'system:dict:editData'"
                type="link"
                size="small"
                @click="openDataEdit(record)"
              >
                {{ t('system.edit') }}
              </a-button>
              <a-button
                v-permission="'system:dict:removeData'"
                type="link"
                size="small"
                danger
                @click="onDeleteData(record)"
              >
                {{ t('system.delete') }}
              </a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </div>

    <!-- 字典类型弹窗 -->
    <a-modal
      v-model:open="typeModalOpen"
      :title="typeEditingId === null ? t('system.add') : t('system.edit')"
      :confirm-loading="typeModalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      @ok="submitTypeModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.dictName')">
          <a-input v-model:value="typeForm.dict_name" />
        </a-form-item>
        <a-form-item :label="t('system.dictType')">
          <a-input v-model:value="typeForm.dict_type" />
        </a-form-item>
        <a-form-item :label="t('system.status')">
          <a-radio-group v-model:value="typeForm.status">
            <a-radio value="0">{{ t('system.enabled') }}</a-radio>
            <a-radio value="1">{{ t('system.disabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.remark')">
          <a-input v-model:value="typeForm.remark" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 字典数据弹窗 -->
    <a-modal
      v-model:open="dataModalOpen"
      :title="dataEditingCode === null ? t('system.add') : t('system.edit')"
      :confirm-loading="dataModalLoading"
      :ok-text="t('system.save')"
      :cancel-text="t('system.cancel')"
      @ok="submitDataModal"
    >
      <a-form layout="vertical">
        <a-form-item :label="t('system.dictLabel')">
          <a-input v-model:value="dataForm.dict_label" />
        </a-form-item>
        <a-form-item :label="t('system.dictValue')">
          <a-input v-model:value="dataForm.dict_value" />
        </a-form-item>
        <a-form-item :label="t('system.dictSort')">
          <a-input-number v-model:value="dataForm.dict_sort" :min="0" style="width: 100%" />
        </a-form-item>
        <a-form-item :label="t('system.dictDefault')">
          <a-radio-group v-model:value="dataForm.is_default">
            <a-radio value="Y">{{ t('system.yes') }}</a-radio>
            <a-radio value="N">{{ t('system.no') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.status')">
          <a-radio-group v-model:value="dataForm.status">
            <a-radio value="0">{{ t('system.enabled') }}</a-radio>
            <a-radio value="1">{{ t('system.disabled') }}</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item :label="t('system.remark')">
          <a-input v-model:value="dataForm.remark" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped lang="less">
.dict-layout {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 16px;

  .type-card {
    :deep(.ant-table-tbody > tr:hover) {
      cursor: pointer;
    }
  }
}

.card-toolbar {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;

  .toolbar-spacer {
    flex: 1;
  }
}

.data-title {
  font-weight: 600;
  color: var(--brand-ink, #333);
}
</style>
