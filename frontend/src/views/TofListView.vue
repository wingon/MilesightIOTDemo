<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listUg65, type Ug65Row } from '@/api/milesight'
import ChartPanel from '@/components/ChartPanel.vue'
import { brand } from '@/theme/colorConfig'
import { formatNum, num, asRecord, latestGatewayModel, formatTableTimeUtcPlus8, rowUplinkTime } from '@/utils/reportCommon'
import {
  CT103_EUI,
  TEMP_STATUS_LABEL,
  buildCt103CompareOption,
  buildCt103HistOption,
  buildCt103Insights,
  buildCt103LoadOption,
  buildCt103MainOption,
  buildCt103Overview,
  buildCt103SignalOption,
  buildCt103TempOption,
  buildCt103TempStatusOption,
  ct103RangeLine,
  ct103Rows,
} from '@/utils/ct103Report'

const { t, locale } = useI18n()
const loading = ref(false)
const rows = ref<Ug65Row[]>([])
const total = ref(0)
const mainTab = ref<'current' | 'total_current'>('current')
const page = ref(1)
const pageSize = ref(20)

async function load() {
  loading.value = true
  try {
    const { data } = await listUg65({
      dev_eui: CT103_EUI,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const overview = computed(() => buildCt103Overview(rows.value))

const gatewayBadge = computed(() => {
  void locale.value
  const model = latestGatewayModel(rows.value)
  return model
    ? t('ct103.viaGateway', { model })
    : t('ct103.viaGatewayUnknown')
})

const insights = computed(() => {
  void locale.value
  return buildCt103Insights(overview.value, {
    idlePackets: t('ct103.insights.idlePackets'),
    currentRange: t('ct103.insights.currentRange'),
    totalRise: t('ct103.insights.totalRise'),
    tempNote: t('ct103.insights.tempNote'),
    under6a: t('ct103.insights.under6a'),
    signal: t('ct103.insights.signal'),
    interval: t('ct103.insights.interval'),
  })
})

const mainOption = computed(() => {
  void locale.value
  const key = mainTab.value
  const label =
    key === 'current' ? t('ct103.charts.instantCurrent') : t('ct103.charts.totalCurrent')
  return buildCt103MainOption(overview.value, key, label)
})

const compareOption = computed(() => {
  void locale.value
  return buildCt103CompareOption(overview.value, {
    current: t('ct103.charts.instantCurrent'),
    total: t('ct103.charts.totalCurrent'),
  })
})

const tempOption = computed(() => {
  void locale.value
  return buildCt103TempOption(overview.value, t('ct103.charts.cableTemp'))
})

const tempStatusOption = computed(() => {
  void locale.value
  return buildCt103TempStatusOption(overview.value, t('ct103.charts.tempStatus'))
})

const histOption = computed(() => {
  void locale.value
  return buildCt103HistOption(overview.value, t('ct103.charts.distribution'))
})

const loadOption = computed(() => {
  void locale.value
  return buildCt103LoadOption(overview.value, t('ct103.charts.loadState'))
})

const signalOption = computed(() => {
  void locale.value
  return buildCt103SignalOption(overview.value, {
    rssi: t('ct103.charts.rssi'),
    snr: t('ct103.charts.snr'),
  })
})

const tableRows = computed(() => ct103Rows(rows.value))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tableRows.value.slice(start, start + pageSize.value)
})

const columns = computed(() => [
  { title: t('ct103.table.uplinkTime'), key: 'uplink_time', width: 150 },
  { title: t('ct103.table.receivedAt'), key: 'received_at', width: 150 },
  { title: t('ct103.table.current'), key: 'current', width: 100 },
  { title: t('ct103.table.total'), key: 'total', width: 110 },
  { title: t('ct103.table.cableTemp'), key: 'temp', width: 110 },
  { title: t('ct103.table.tempStatus'), key: 'tempStatus', width: 220 },
  { title: t('ct103.charts.rssi'), dataIndex: 'rssi', width: 90 },
  { title: t('ct103.charts.snr'), dataIndex: 'lora_snr', width: 90 },
  { title: 'FCnt', dataIndex: 'f_cnt', width: 80 },
])

function payloadOf(row: Ug65Row) {
  return asRecord(row.payload_json) || {}
}

function tempStatusText(status: number | null) {
  if (status == null) return '—'
  return TEMP_STATUS_LABEL[status] || String(status)
}

const loadBadgeClass = computed(() => {
  const level = overview.value.loadLevel
  if (level === 'high') return 'badge-warn'
  if (level === 'medium') return 'badge-caution'
  return 'badge-good'
})

function onPageChange(p: number, ps: number) {
  page.value = p
  pageSize.value = ps
}

onMounted(load)
</script>

<template>
  <a-spin :spinning="loading">
    <div class="report-hero">
      <div>
        <div class="hero-title">{{ t('ct103.title') }}</div>
        <div class="hero-sub">{{ t('ct103.subtitle') }}</div>
        <div class="badges">
          <span class="badge">Device EUI: {{ CT103_EUI }}</span>
          <span class="badge">{{ t('ct103.band') }}</span>
          <span class="badge">{{ gatewayBadge }}</span>
        </div>
      </div>
      <a-button type="primary" @click="load">{{ t('common.refresh') }}</a-button>
    </div>

    <h3 class="section-title">{{ t('ct103.sections.overview') }}</h3>
    <a-row :gutter="[12, 12]" class="ov-cards">
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.packets') }}</div>
          <div class="ov-value">{{ overview.packetCount }} / {{ total }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.timeRange') }}</div>
          <div class="ov-value ov-small">
            <div>{{ overview.time.from || '—' }}</div>
            <div>to {{ overview.time.to || '—' }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.duration') }}</div>
          <div class="ov-value">
            {{ overview.time.hours != null ? `${formatNum(overview.time.hours, 1)} h` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.interval') }}</div>
          <div class="ov-value">
            {{ overview.time.intervalSec != null ? `~${formatNum(overview.time.intervalSec, 0)} s` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.loadRatio') }}</div>
          <div class="ov-value">{{ formatNum(overview.loadRatio, 1) }}%</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('ct103.overview.tempStatus2') }}</div>
          <div class="ov-value">{{ overview.status2 }}/{{ overview.packetCount }}</div>
          <div class="ov-muted">{{ t('ct103.overview.tempStatus2Hint') }}</div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('ct103.overview.legendTitle') }}</div>
      <div class="legend-hint">{{ t('ct103.overview.legendHint') }}</div>
      <ul class="legend-list">
        <li>
          <strong>{{ t('ct103.overview.packets') }}</strong>
          — {{ t('ct103.overview.packetsDesc') }}
        </li>
        <li>
          <strong>{{ t('ct103.overview.timeRange') }}</strong>
          — {{ t('ct103.overview.timeRangeDesc') }}
        </li>
        <li>
          <strong>{{ t('ct103.overview.duration') }}</strong>
          — {{ t('ct103.overview.durationDesc') }}
        </li>
        <li>
          <strong>{{ t('ct103.overview.interval') }}</strong>
          — {{ t('ct103.overview.intervalDesc') }}
        </li>
        <li>
          <strong>{{ t('ct103.overview.loadRatio') }}</strong>
          — {{ t('ct103.overview.loadRatioDesc') }}
        </li>
        <li>
          <strong>{{ t('ct103.overview.tempStatus2') }}</strong>
          — {{ t('ct103.overview.tempStatus2Desc') }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('ct103.sections.latest') }}</h3>
    <a-row :gutter="[12, 12]">
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('ct103.charts.instantCurrent') }}</div>
          <div class="stat-value" :style="{ color: brand.primary }">
            {{ formatNum(overview.latestCurrent, 2) }}<span class="unit">A</span>
          </div>
          <div class="stat-range">{{ ct103RangeLine(overview.currentStats, 2) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('ct103.charts.totalCurrent') }}</div>
          <div class="stat-value">
            {{ formatNum(overview.latestTotal, 2) }}<span class="unit">A·h</span>
          </div>
          <div class="stat-range">{{ ct103RangeLine(overview.totalStats, 2) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('ct103.charts.cableTemp') }}</div>
          <div class="stat-value">
            {{ formatNum(overview.latestTemp, 1) }}<span class="unit">°C</span>
          </div>
          <div class="stat-range">{{ ct103RangeLine(overview.tempStats, 1) }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">{{ t('ct103.charts.tempStatus') }}</div>
          <div class="stat-value stat-text">
            {{ tempStatusText(overview.latestTempStatus) }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="stat-card">
          <div class="stat-label">RSSI / SNR</div>
          <div class="stat-value">
            {{ formatNum(overview.latestRssi, 1) }}<span class="unit">dBm</span>
          </div>
          <div class="stat-range">SNR {{ formatNum(overview.latestSnr, 1) }} dB</div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('ct103.latestLegend.title') }}</div>
      <div class="legend-hint">{{ t('ct103.latestLegend.hint') }}</div>
      <ul class="legend-list">
        <li>
          <strong>{{ t('ct103.charts.instantCurrent') }}</strong>
          — {{ t('ct103.latestLegend.instantCurrent') }}
        </li>
        <li>
          <strong>{{ t('ct103.charts.totalCurrent') }}</strong>
          — {{ t('ct103.latestLegend.totalCurrent') }}
        </li>
        <li>
          <strong>{{ t('ct103.charts.cableTemp') }}</strong>
          — {{ t('ct103.latestLegend.cableTemp') }}
        </li>
        <li>
          <strong>{{ t('ct103.charts.tempStatus') }}</strong>
          — {{ t('ct103.latestLegend.tempStatus') }}
        </li>
        <li>
          <strong>RSSI / SNR</strong>
          — {{ t('ct103.latestLegend.rssiSnr') }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('ct103.sections.insights') }}</h3>
    <a-card class="insight-card" :bordered="false">
      <div class="load-badge" :class="loadBadgeClass">
        {{ t(`ct103.load.${overview.loadLevel}`) }}
        <template v-if="overview.latestCurrent != null">
          ({{ formatNum(overview.latestCurrent, 2) }} A)
        </template>
      </div>
      <ul class="insights">
        <li v-for="(item, idx) in insights" :key="idx">{{ item }}</li>
      </ul>
    </a-card>

    <h3 class="section-title">{{ t('ct103.sections.trends') }}</h3>
    <a-card :bordered="false">
      <a-radio-group v-model:value="mainTab" button-style="solid" style="margin-bottom: 12px">
        <a-radio-button value="current">{{ t('ct103.charts.instantCurrent') }}</a-radio-button>
        <a-radio-button value="total_current">{{ t('ct103.charts.totalCurrent') }}</a-radio-button>
      </a-radio-group>
      <ChartPanel :option="mainOption" height="320px" />
    </a-card>

    <h3 class="section-title">{{ t('ct103.sections.multi') }}</h3>
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.compare')" :bordered="false">
          <ChartPanel :option="compareOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.cableTemp')" :bordered="false">
          <div class="chart-note">{{ t('ct103.charts.tempNote') }}</div>
          <ChartPanel :option="tempOption" height="240px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.tempStatus')" :bordered="false">
          <div class="chart-note">{{ t('ct103.charts.tempStatusNote') }}</div>
          <ChartPanel :option="tempStatusOption" height="240px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.distribution')" :bordered="false">
          <ChartPanel :option="histOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.loadState')" :bordered="false">
          <ChartPanel :option="loadOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('ct103.charts.signal')" :bordered="false">
          <div v-if="!overview.rssiStats.count" class="chart-note">{{ t('ct103.charts.signalEmpty') }}</div>
          <ChartPanel v-else :option="signalOption" height="260px" />
        </a-card>
      </a-col>
    </a-row>

    <h3 class="section-title">{{ t('ct103.sections.notes') }}</h3>
    <a-card :bordered="false">
      <ul class="insights">
        <li>{{ t('ct103.notes.n1') }}</li>
        <li>{{ t('ct103.notes.n2') }}</li>
        <li>{{ t('ct103.notes.n3') }}</li>
        <li>{{ t('ct103.notes.n4') }}</li>
      </ul>
    </a-card>

    <h3 class="section-title">{{ t('ct103.sections.details') }}</h3>
    <a-card :bordered="false">
      <a-table
        row-key="id"
        size="small"
        :columns="columns"
        :data-source="pagedRows"
        :scroll="{ x: 1100 }"
        :pagination="{
          current: page,
          pageSize,
          total: tableRows.length,
          showSizeChanger: true,
          onChange: onPageChange,
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'uplink_time'">{{ formatTableTimeUtcPlus8(rowUplinkTime(record)) }}</template>
          <template v-else-if="column.key === 'received_at'">{{ formatTableTimeUtcPlus8(record.received_at) }}</template>
          <template v-else-if="column.key === 'current'">
            {{ formatNum(num(payloadOf(record).current), 2) }}
          </template>
          <template v-else-if="column.key === 'total'">
            {{ formatNum(num(payloadOf(record).total_current), 2) }}
          </template>
          <template v-else-if="column.key === 'temp'">
            {{ formatNum(num(payloadOf(record).temperature), 1) }}
          </template>
          <template v-else-if="column.key === 'tempStatus'">
            {{ tempStatusText(num(payloadOf(record).temperature_sensor_status)) }}
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
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
  padding: 14px 16px;
  min-height: 96px;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
}

.ov-cards {
  align-items: stretch;
}

.ov-cards :deep(.ant-col) {
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

.unit {
  margin-left: 3px;
  font-size: 12px;
  color: #6b6b6b;
  font-weight: 500;
}

.stat-text {
  font-size: 14px;
  line-height: 1.35;
}

.insight-card {
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
}

.load-badge {
  display: inline-flex;
  padding: 6px 12px;
  font-weight: 600;
  margin-bottom: 12px;
}

.badge-good {
  background: rgba(61, 122, 90, 0.12);
  color: #3d7a5a;
}

.badge-caution {
  background: rgba(196, 165, 116, 0.18);
  color: #a88955;
}

.badge-warn {
  background: rgba(180, 35, 24, 0.1);
  color: #b42318;
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
  background: var(--brand-canvas, #f7f7f5);
  border-left: 3px solid #c4a574;
  font-size: 13px;
  color: #2a2a2a;
}

.chart-note {
  font-size: 12px;
  color: #6b6b6b;
  margin-bottom: 8px;
}

.overview-legend {
  margin-top: 14px;
  padding: 14px 16px;
  background: var(--brand-canvas, #f7f7f5);
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
