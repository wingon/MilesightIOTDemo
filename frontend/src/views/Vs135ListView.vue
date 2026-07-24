<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listTof, listTofDevices, type TofDevice, type TofRow } from '@/api/milesight'
import ChartPanel from '@/components/ChartPanel.vue'
import { brand } from '@/theme/colorConfig'
import { asRecord, formatNum, formatTableTime, num } from '@/utils/reportCommon'
import {
  type Vs135MainMetric,
  buildVs135CombinedOption,
  buildVs135CumulativeOption,
  buildVs135Insights,
  buildVs135MainOption,
  buildVs135NetOption,
  buildVs135Overview,
  buildVs135PeriodOption,
  vs135RangeLine,
} from '@/utils/vs135Report'

const { t, locale } = useI18n()
const loading = ref(false)
const rows = ref<TofRow[]>([])
const total = ref(0)
const devices = ref<TofDevice[]>([])
const deviceSn = ref<string | undefined>(undefined)
const mainMetric = ref<Vs135MainMetric>('periodIn')
const page = ref(1)
const pageSize = ref(20)

const metricTabs = computed(() => {
  void locale.value
  return (
    [
      'periodIn',
      'periodOut',
      'inCounted',
      'outCounted',
      'netFlow',
    ] as Vs135MainMetric[]
  ).map((key) => ({ key, label: t(`vs135.metrics.${key}`) }))
})

async function loadDevices() {
  const { data } = await listTofDevices()
  devices.value = data
  if (!deviceSn.value && data.length) {
    deviceSn.value = data[0].device_sn
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await listTof({
      device_sn: deviceSn.value,
    })
    rows.value = data.items
    total.value = data.total
    page.value = 1
  } finally {
    loading.value = false
  }
}

const overview = computed(() => buildVs135Overview(rows.value))

const insights = computed(() => {
  void locale.value
  return buildVs135Insights(overview.value, {
    traffic: t('vs135.insights.traffic'),
    peakIn: t('vs135.insights.peakIn'),
    peakOut: t('vs135.insights.peakOut'),
    cumulative: t('vs135.insights.cumulative'),
    activity: t('vs135.insights.activity'),
    interval: t('vs135.insights.interval'),
  })
})

const mainOption = computed(() => {
  void locale.value
  return buildVs135MainOption(
    overview.value,
    mainMetric.value,
    t(`vs135.metrics.${mainMetric.value}`),
  )
})

const periodOption = computed(() => {
  void locale.value
  return buildVs135PeriodOption(overview.value, {
    periodIn: t('vs135.metrics.periodIn'),
    periodOut: t('vs135.metrics.periodOut'),
  })
})

const cumulativeOption = computed(() => {
  void locale.value
  return buildVs135CumulativeOption(overview.value, {
    inCounted: t('vs135.metrics.inCounted'),
    outCounted: t('vs135.metrics.outCounted'),
  })
})

const combinedOption = computed(() => {
  void locale.value
  return buildVs135CombinedOption(overview.value, {
    periodIn: t('vs135.metrics.periodIn'),
    periodOut: t('vs135.metrics.periodOut'),
    inCounted: t('vs135.metrics.inCounted'),
    outCounted: t('vs135.metrics.outCounted'),
    cumulative: t('vs135.metrics.cumulative'),
  })
})

const netOption = computed(() => {
  void locale.value
  return buildVs135NetOption(overview.value, t('vs135.metrics.netFlow'))
})

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return rows.value.slice(start, start + pageSize.value)
})

const columns = computed(() => [
  { title: t('vs135.table.time'), dataIndex: 'received_at', width: 180 },
  { title: t('vs135.table.deviceSn'), dataIndex: 'device_sn', width: 180 },
  { title: t('vs135.table.deviceName'), dataIndex: 'device_name', width: 140 },
  { title: t('vs135.metrics.periodIn'), key: 'periodIn', width: 110 },
  { title: t('vs135.metrics.periodOut'), key: 'periodOut', width: 110 },
  { title: t('vs135.metrics.inCounted'), key: 'inCounted', width: 110 },
  { title: t('vs135.metrics.outCounted'), key: 'outCounted', width: 110 },
  { title: t('vs135.table.start'), dataIndex: 'start_time', width: 170 },
  { title: t('vs135.table.end'), dataIndex: 'end_time', width: 170 },
])

function periodicOf(row: TofRow) {
  return Array.isArray(row.line_periodic_data) ? asRecord(row.line_periodic_data[0]) : null
}

function totalOf(row: TofRow) {
  return Array.isArray(row.line_total_data) ? asRecord(row.line_total_data[0]) : null
}

function onPageChange(p: number, ps: number) {
  page.value = p
  pageSize.value = ps
}

async function onDeviceChange() {
  page.value = 1
  await load()
}

onMounted(async () => {
  await loadDevices()
  await load()
})
</script>

<template>
  <a-spin :spinning="loading">
    <div class="report-hero">
      <div>
        <div class="hero-title">{{ t('vs135.title') }}</div>
        <div class="hero-sub">{{ t('vs135.subtitle') }}</div>
        <div class="badges">
          <span v-if="overview.deviceSn" class="badge">SN: {{ overview.deviceSn }}</span>
          <span v-if="overview.deviceName" class="badge">{{ overview.deviceName }}</span>
          <span class="badge">{{ t('vs135.viaTof') }}</span>
        </div>
      </div>
      <a-space>
        <a-select
          v-model:value="deviceSn"
          allow-clear
          :placeholder="t('vs135.selectDevice')"
          style="width: 260px"
          :options="devices.map((d) => ({ label: `${d.device_sn} (${d.uplink_count})`, value: d.device_sn }))"
          @change="onDeviceChange"
        />
        <a-button type="primary" @click="load">{{ t('common.refresh') }}</a-button>
      </a-space>
    </div>

    <h3 class="section-title">{{ t('vs135.sections.overview') }}</h3>
    <a-row :gutter="[12, 12]">
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.packets') }}</div>
          <div class="ov-value">{{ overview.packetCount }} / {{ total }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.timeRange') }}</div>
          <div class="ov-value ov-small">
            <div>{{ overview.time.from || '—' }}</div>
            <div>to {{ overview.time.to || '—' }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.duration') }}</div>
          <div class="ov-value">
            {{ overview.time.hours != null ? `${formatNum(overview.time.hours, 1)} h` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.interval') }}</div>
          <div class="ov-value">
            {{ overview.time.intervalSec != null ? `~${formatNum(overview.time.intervalSec, 0)} s` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.activeRatio') }}</div>
          <div class="ov-value">{{ formatNum(overview.activeRatio, 1) }}%</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('vs135.overview.devices') }}</div>
          <div class="ov-value">{{ overview.deviceCount }}</div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('vs135.overview.legendTitle') }}</div>
      <div class="legend-hint">{{ t('vs135.overview.legendHint') }}</div>
      <ul class="legend-list">
        <li>
          <strong>{{ t('vs135.overview.packets') }}</strong>
          — {{ t('vs135.overview.packetsDesc') }}
        </li>
        <li>
          <strong>{{ t('vs135.overview.timeRange') }}</strong>
          — {{ t('vs135.overview.timeRangeDesc') }}
        </li>
        <li>
          <strong>{{ t('vs135.overview.duration') }}</strong>
          — {{ t('vs135.overview.durationDesc') }}
        </li>
        <li>
          <strong>{{ t('vs135.overview.interval') }}</strong>
          — {{ t('vs135.overview.intervalDesc') }}
        </li>
        <li>
          <strong>{{ t('vs135.overview.activeRatio') }}</strong>
          — {{ t('vs135.overview.activeRatioDesc') }}
        </li>
        <li>
          <strong>{{ t('vs135.overview.devices') }}</strong>
          — {{ t('vs135.overview.devicesDesc') }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('vs135.sections.latest') }}</h3>
    <a-row :gutter="[12, 12]" class="stat-cards">
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.periodIn') }}</div>
          <div class="stat-value" :style="{ color: brand.primary }">
            {{ formatNum(overview.latestPeriodIn, 0) }}
          </div>
          <div class="stat-range">{{ vs135RangeLine(overview.periodInStats) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.periodOut') }}</div>
          <div class="stat-value">{{ formatNum(overview.latestPeriodOut, 0) }}</div>
          <div class="stat-range">{{ vs135RangeLine(overview.periodOutStats) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.inCounted') }}</div>
          <div class="stat-value">{{ formatNum(overview.latestInCounted, 0) }}</div>
          <div class="stat-range">{{ vs135RangeLine(overview.inCountedStats) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.outCounted') }}</div>
          <div class="stat-value">{{ formatNum(overview.latestOutCounted, 0) }}</div>
          <div class="stat-range">{{ vs135RangeLine(overview.outCountedStats) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.sumIn') }}</div>
          <div class="stat-value">{{ overview.sumIn }}</div>
          <div class="stat-range">{{ t('vs135.metrics.sumInHint') }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('vs135.metrics.sumOut') }}</div>
          <div class="stat-value">{{ overview.sumOut }}</div>
          <div class="stat-range">{{ t('vs135.metrics.sumOutHint') }}</div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('vs135.latestLegend.title') }}</div>
      <div class="legend-hint">{{ t('vs135.latestLegend.hint') }}</div>
      <ul class="legend-list">
        <li>
          <strong>{{ t('vs135.metrics.periodIn') }}</strong>
          — {{ t('vs135.latestLegend.periodIn') }}
        </li>
        <li>
          <strong>{{ t('vs135.metrics.periodOut') }}</strong>
          — {{ t('vs135.latestLegend.periodOut') }}
        </li>
        <li>
          <strong>{{ t('vs135.metrics.inCounted') }}</strong>
          — {{ t('vs135.latestLegend.inCounted') }}
        </li>
        <li>
          <strong>{{ t('vs135.metrics.outCounted') }}</strong>
          — {{ t('vs135.latestLegend.outCounted') }}
        </li>
        <li>
          <strong>{{ t('vs135.metrics.sumIn') }} / {{ t('vs135.metrics.sumOut') }}</strong>
          — {{ t('vs135.latestLegend.sumFlow') }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('vs135.sections.insights') }}</h3>
    <a-card class="insight-card" :bordered="false">
      <ul class="insights">
        <li v-for="(item, idx) in insights" :key="idx">{{ item }}</li>
      </ul>
    </a-card>

    <h3 class="section-title">{{ t('vs135.sections.trends') }}</h3>
    <a-card :bordered="false">
      <a-radio-group v-model:value="mainMetric" button-style="solid" class="metric-tabs">
        <a-radio-button v-for="tab in metricTabs" :key="tab.key" :value="tab.key">
          {{ tab.label }}
        </a-radio-button>
      </a-radio-group>
      <div class="main-chart-title">
        {{ t(`vs135.metrics.${mainMetric}`) }} · {{ t('vs135.sections.trendSuffix') }}
      </div>
      <ChartPanel :option="mainOption" height="320px" />
    </a-card>

    <h3 class="section-title">{{ t('vs135.sections.multi') }}</h3>
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="12">
        <a-card :title="t('vs135.charts.period')" :bordered="false">
          <ChartPanel :option="periodOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('vs135.charts.cumulative')" :bordered="false">
          <ChartPanel :option="cumulativeOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('vs135.charts.combined')" :bordered="false">
          <ChartPanel :option="combinedOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('vs135.charts.netFlow')" :bordered="false">
          <ChartPanel :option="netOption" height="260px" />
        </a-card>
      </a-col>
    </a-row>

    <h3 class="section-title">{{ t('vs135.sections.details') }}</h3>
    <a-card :bordered="false">
      <a-table
        row-key="id"
        size="small"
        :columns="columns"
        :data-source="pagedRows"
        :scroll="{ x: 1300 }"
        :pagination="{
          current: page,
          pageSize,
          total: rows.length,
          showSizeChanger: true,
          onChange: onPageChange,
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'received_at'">{{ formatTableTime(record.received_at) }}</template>
          <template v-else-if="column.key === 'periodIn'">
            {{ formatNum(num(periodicOf(record)?.in), 0) }}
          </template>
          <template v-else-if="column.key === 'periodOut'">
            {{ formatNum(num(periodicOf(record)?.out), 0) }}
          </template>
          <template v-else-if="column.key === 'inCounted'">
            {{ formatNum(num(totalOf(record)?.in_counted), 0) }}
          </template>
          <template v-else-if="column.key === 'outCounted'">
            {{ formatNum(num(totalOf(record)?.out_counted), 0) }}
          </template>
        </template>
      </a-table>
    </a-card>
  </a-spin>
</template>

<style scoped lang="less">
.report-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 0 20px;
  margin-bottom: 8px;
  border-bottom: 1px solid #e6e2da;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.03em;
  color: #0d0d0d;
}

.hero-sub {
  margin-top: 4px;
  color: #6b6b6b;
  font-size: 13px;
}

.badges {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.badge {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  color: #a88955;
  background: rgba(196, 165, 116, 0.12);
  border: 1px solid rgba(196, 165, 116, 0.35);
}

.section-title {
  margin: 24px 0 12px;
  font-size: 15px;
  font-weight: 650;
  color: #0d0d0d;
  padding-bottom: 6px;
  border-bottom: 2px solid #c4a574;
  display: inline-block;
}

.ov-card,
.stat-card {
  background: #fff;
  border: 1px solid #e6e2da;
  padding: 14px 16px;
  min-height: 96px;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}

.stat-cards {
  align-items: stretch;
}

.stat-cards :deep(.ant-col) {
  display: flex;
}

.ov-label,
.stat-label {
  color: #6b6b6b;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.ov-value,
.stat-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 700;
  color: #0d0d0d;
}

.ov-small {
  font-size: 13px;
  line-height: 1.35;
}

.ov-muted,
.stat-range {
  margin-top: 4px;
  font-size: 12px;
  color: #6b6b6b;
}

.insight-card {
  background: #fff;
  border: 1px solid #e6e2da;
}

.insights {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.insights li {
  padding: 10px 12px;
  background: #f7f7f5;
  border-left: 3px solid #c4a574;
  font-size: 13px;
  color: #2a2a2a;
}

.metric-tabs {
  display: flex;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.main-chart-title {
  font-size: 13px;
  color: #6b6b6b;
  margin-bottom: 8px;
}

.overview-legend {
  margin-top: 14px;
  padding: 14px 16px;
  background: #f7f7f5;
  border: 1px solid #e6e2da;
  border-left: 3px solid #c4a574;
}

.legend-title {
  font-size: 13px;
  font-weight: 650;
  color: #0d0d0d;
}

.legend-hint {
  margin-top: 4px;
  font-size: 12px;
  color: #6b6b6b;
}

.legend-list {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #2a2a2a;
  font-size: 12px;
  line-height: 1.55;
}

.legend-list li + li {
  margin-top: 6px;
}

.legend-list strong {
  color: #0d0d0d;
  font-weight: 600;
}
</style>
