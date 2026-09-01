<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { ApiOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons-vue'
import { testMqttConnectivity } from '@/api/milesight'
import { useBuildingStore } from '@/stores/building'
import { DEVICE_TYPES, FLOOR_COUNT, floorName, type DeviceType } from '@/utils/buildingDemo'

const { t } = useI18n()
const store = useBuildingStore()

const floor = ref<number>(5)
const sn = ref('')
const deviceType = ref<DeviceType>('AM319')
const testing = ref(false)
const lastTestOk = ref<boolean | null>(null)
const lastTestMsg = ref('')

const inventory = computed(() => store.getInventory(floor.value))

const floorOptions = computed(() =>
  Array.from({ length: FLOOR_COUNT }, (_, i) => ({
    value: i + 1,
    label: t('building.level', { n: floorName(i + 1) }),
  })),
)

const typeOptions = DEVICE_TYPES.map((d) => ({ value: d, label: d }))

const columns = computed(() => [
  { title: t('devicesPage.sn'), dataIndex: 'sn', key: 'sn' },
  { title: t('devicesPage.type'), dataIndex: 'type', key: 'type', width: 120 },
  { title: t('devicesPage.mqtt'), key: 'mqtt', width: 140 },
  { title: t('devicesPage.actions'), key: 'actions', width: 100 },
])

async function onTestMqtt() {
  const deviceSn = sn.value.trim()
  if (!deviceSn) {
    message.warning(t('devicesPage.needSn'))
    return
  }
  testing.value = true
  lastTestOk.value = null
  lastTestMsg.value = ''
  try {
    const { data } = await testMqttConnectivity(deviceSn)
    lastTestOk.value = !!data.ok
    lastTestMsg.value = data.ok
      ? t('devicesPage.mqttOk', { broker: data.broker || '' })
      : t('devicesPage.mqttFail', { error: data.error || `rc=${data.reason_code ?? '?'}` })
    if (data.ok) message.success(lastTestMsg.value)
    else message.error(lastTestMsg.value)
  } catch (e: unknown) {
    lastTestOk.value = false
    const err = e instanceof Error ? e.message : String(e)
    lastTestMsg.value = t('devicesPage.mqttFail', { error: err })
    message.error(lastTestMsg.value)
  } finally {
    testing.value = false
  }
}

function onAddToFloor() {
  const deviceSn = sn.value.trim()
  if (!deviceSn) {
    message.warning(t('devicesPage.needSn'))
    return
  }
  const added = store.addInventoryDevice(floor.value, {
    sn: deviceSn,
    type: deviceType.value,
    mqttOk: lastTestOk.value,
  })
  if (!added) {
    message.error(t('devicesPage.duplicateSn'))
    return
  }
  message.success(t('devicesPage.added', { sn: deviceSn, floor: floorName(floor.value) }))
  sn.value = ''
  lastTestOk.value = null
  lastTestMsg.value = ''
}

function onRemove(id: string) {
  store.removeInventoryDevice(floor.value, id)
  message.success(t('devicesPage.removed'))
}

function mqttTag(ok: boolean | null) {
  if (ok === true) return { color: 'success', text: t('devicesPage.testedOk') }
  if (ok === false) return { color: 'error', text: t('devicesPage.testedFail') }
  return { color: 'default', text: t('devicesPage.notTested') }
}
</script>

<template>
  <div class="devices-page">
    <div class="page-intro">
      <h1>{{ t('devicesPage.title') }}</h1>
      <p>{{ t('devicesPage.subtitle') }}</p>
    </div>

    <div class="card form-card">
      <div class="form-grid">
        <div class="field">
          <label>{{ t('devicesPage.floor') }}</label>
          <a-select v-model:value="floor" :options="floorOptions" style="width: 100%" />
        </div>
        <div class="field">
          <label>{{ t('devicesPage.type') }}</label>
          <a-select v-model:value="deviceType" :options="typeOptions" style="width: 100%" />
        </div>
        <div class="field sn-field">
          <label>{{ t('devicesPage.sn') }}</label>
          <a-input
            v-model:value="sn"
            :placeholder="t('devicesPage.snPlaceholder')"
            allow-clear
            @pressEnter="onAddToFloor"
          />
        </div>
      </div>

      <div class="form-actions">
        <a-button :loading="testing" @click="onTestMqtt">
          <ApiOutlined /> {{ t('devicesPage.testMqtt') }}
        </a-button>
        <a-button type="primary" @click="onAddToFloor">
          <PlusOutlined /> {{ t('devicesPage.addToFloor') }}
        </a-button>
      </div>

      <p v-if="lastTestMsg" class="test-msg" :class="{ ok: lastTestOk, bad: lastTestOk === false }">
        {{ lastTestMsg }}
      </p>
    </div>

    <div class="card table-card">
      <div class="table-title">
        {{ t('devicesPage.inventoryTitle', { n: floor }) }}
        <a-tag>{{ inventory.length }}</a-tag>
      </div>
      <a-table
        :columns="columns"
        :data-source="inventory"
        :pagination="{ pageSize: 10 }"
        row-key="id"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'mqtt'">
            <a-tag :color="mqttTag(record.mqttOk).color">{{ mqttTag(record.mqttOk).text }}</a-tag>
          </template>
          <template v-else-if="column.key === 'actions'">
            <a-button type="text" danger size="small" @click="onRemove(record.id)">
              <DeleteOutlined />
            </a-button>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<style scoped lang="less">
.devices-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-intro {
  h1 {
    margin: 0;
    font-size: 20px;
    font-weight: 650;
    color: #0d0d0d;
  }

  p {
    margin: 4px 0 0;
    color: #6b6b6b;
    font-size: 13px;
  }
}

.card {
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
  padding: 16px 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: 160px 140px minmax(0, 1fr);
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;

  label {
    font-size: 12px;
    font-weight: 600;
    color: #6b6b6b;
  }
}

.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}

.test-msg {
  margin: 10px 0 0;
  font-size: 13px;

  &.ok {
    color: #3d7a5a;
  }

  &.bad {
    color: #b42318;
  }
}

.table-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 650;
  margin-bottom: 12px;
}

@media (max-width: 720px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
