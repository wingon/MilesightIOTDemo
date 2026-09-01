<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { listUg65, type Ug65Row } from '@/api/milesight'
import ChartPanel from '@/components/ChartPanel.vue'
import { brand } from '@/theme/colorConfig'
import { asRecord, formatNum, formatTableTimeUtcPlus8, latestGatewayModel, num, rowUplinkTime } from '@/utils/reportCommon'
import {
  AIR_EUI,
  AIR_METRIC_META,
  type AirMetric,
  airRangeLine,
  airRows,
  buildAirInsights,
  buildAirLightPirOption,
  buildAirMainOption,
  buildAirOverview,
  buildAirPressureOption,
  buildAirQualityOption,
  buildAirSignalOption,
  buildAirTempHumOption,
  buildAirVocOption,
} from '@/utils/airReport'

const { t, locale } = useI18n()
const loading = ref(false)
const rows = ref<Ug65Row[]>([])
const total = ref(0)
const mainMetric = ref<AirMetric>('temperature')
const page = ref(1)
const pageSize = ref(20)

const metricTabs = computed(() => {
  void locale.value
  return (Object.keys(AIR_METRIC_META) as AirMetric[]).map((key) => ({
    key,
    label: t(`air.metrics.${key}`),
  }))
})

async function load() {
  loading.value = true
  try {
    const { data } = await listUg65({
      dev_eui: AIR_EUI,
    })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const overview = computed(() => buildAirOverview(rows.value))

const gatewayBadge = computed(() => {
  void locale.value
  const model = latestGatewayModel(rows.value)
  return model
    ? t('air.viaGateway', { model })
    : t('air.viaGatewayUnknown')
})

const insights = computed(() => {
  void locale.value
  return buildAirInsights(overview.value, {
    co2: t('air.insights.co2'),
    temperature: t('air.insights.temperature'),
    pm25: t('air.insights.pm25'),
    pir: t('air.insights.pir'),
    signal: t('air.insights.signal'),
  })
})

const mainOption = computed(() => {
  void locale.value
  return buildAirMainOption(
    overview.value,
    mainMetric.value,
    t(`air.metrics.${mainMetric.value}`),
  )
})

const tempHumOption = computed(() => {
  void locale.value
  return buildAirTempHumOption(overview.value, {
    temperature: t('air.metrics.temperature'),
    humidity: t('air.metrics.humidity'),
  })
})

const aqOption = computed(() => {
  void locale.value
  return buildAirQualityOption(overview.value, {
    co2: t('air.metrics.co2'),
    pm25: t('air.metrics.pm2_5'),
    pm10: t('air.metrics.pm10'),
  })
})

const vocOption = computed(() => {
  void locale.value
  return buildAirVocOption(overview.value, {
    tvoc: t('air.metrics.tvoc'),
    hcho: t('air.metrics.hcho'),
  })
})

const pressureOption = computed(() => {
  void locale.value
  return buildAirPressureOption(overview.value, t('air.metrics.pressure'))
})

const lightPirOption = computed(() => {
  void locale.value
  return buildAirLightPirOption(overview.value, {
    light: t('air.metrics.light_level'),
    pir: t('air.metrics.pir'),
  })
})

const signalOption = computed(() => {
  void locale.value
  return buildAirSignalOption(overview.value, {
    rssi: t('air.charts.rssi'),
    snr: t('air.charts.snr'),
  })
})

const tableRows = computed(() => airRows(rows.value))

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tableRows.value.slice(start, start + pageSize.value)
})

const columns = computed(() => [
  { title: t('air.table.uplinkTime'), key: 'uplink_time', width: 170 },
  { title: t('air.metrics.temperature'), key: 'temperature', width: 90 },
  { title: t('air.metrics.humidity'), key: 'humidity', width: 90 },
  { title: t('air.metrics.co2'), key: 'co2', width: 90 },
  { title: t('air.metrics.pm2_5'), key: 'pm2_5', width: 90 },
  { title: t('air.metrics.pm10'), key: 'pm10', width: 90 },
  { title: t('air.metrics.tvoc'), key: 'tvoc', width: 90 },
  { title: t('air.metrics.hcho'), key: 'hcho', width: 90 },
  { title: t('air.metrics.pressure'), key: 'pressure', width: 100 },
  { title: t('air.metrics.light_level'), key: 'light_level', width: 90 },
  { title: t('air.metrics.pir'), key: 'pir', width: 70 },
  { title: t('air.charts.rssi'), dataIndex: 'rssi', width: 80 },
  { title: t('air.charts.snr'), dataIndex: 'lora_snr', width: 80 },
])

function payloadOf(row: Ug65Row) {
  return asRecord(row.payload_json) || {}
}

function cell(row: Ug65Row, key: AirMetric, digits = 1) {
  return formatNum(num(payloadOf(row)[key]), digits)
}

const aqBadgeClass = computed(() => {
  if (overview.value.aqLevel === 'warn') return 'badge-warn'
  if (overview.value.aqLevel === 'caution') return 'badge-caution'
  return 'badge-good'
})

const latestCards = computed(() => {
  void locale.value
  const keys: AirMetric[] = [
    'temperature',
    'humidity',
    'co2',
    'pm2_5',
    'pm10',
    'tvoc',
    'hcho',
    'pressure',
    'light_level',
    'pir',
  ]
  return keys.map((key) => {
    const stats = overview.value.metrics[key]
    const digits = key === 'co2' || key === 'pm2_5' || key === 'pm10' || key === 'tvoc' || key === 'pir' || key === 'light_level'
      ? 0
      : 1
    return {
      key,
      label: t(`air.metrics.${key}`),
      value: formatNum(stats.latest, digits),
      unit: AIR_METRIC_META[key].unit,
      range: airRangeLine(stats, digits),
      warn: key === 'co2' && (stats.latest ?? 0) >= 1000,
    }
  })
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
        <div class="hero-title">{{ t('air.title') }}</div>
        <div class="hero-sub">{{ t('air.subtitle') }}</div>
        <div class="badges">
          <span class="badge">Device EUI: {{ AIR_EUI }}</span>
          <span class="badge">{{ gatewayBadge }}</span>
        </div>
      </div>
      <a-button type="primary" @click="load">{{ t('common.refresh') }}</a-button>
    </div>

    <h3 class="section-title">{{ t('air.sections.overview') }}</h3>
    <a-row :gutter="[12, 12]">
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.packets') }}</div>
          <div class="ov-value">{{ overview.packetCount }} / {{ total }}</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.timeRange') }}</div>
          <div class="ov-value ov-small">
            <div>{{ overview.time.from || '—' }}</div>
            <div>to {{ overview.time.to || '—' }}</div>
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.duration') }}</div>
          <div class="ov-value">
            {{ overview.time.hours != null ? `${formatNum(overview.time.hours, 1)} h` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.interval') }}</div>
          <div class="ov-value">
            {{ overview.time.intervalSec != null ? `~${formatNum(overview.time.intervalSec, 0)} s` : '—' }}
          </div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.pirRatio') }}</div>
          <div class="ov-value">{{ formatNum(overview.pirRatio, 1) }}%</div>
        </div>
      </a-col>
      <a-col :xs="12" :md="8" :xl="4">
        <div class="ov-card">
          <div class="ov-label">{{ t('air.overview.fcnt') }}</div>
          <div class="ov-value ov-small">
            {{ overview.fcntMin ?? '—' }} – {{ overview.fcntMax ?? '—' }}
          </div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('air.overview.legendTitle') }}</div>
      <div class="legend-hint">{{ t('air.overview.legendHint') }}</div>
      <ul class="legend-list">
        <li>
          <strong>{{ t('air.overview.packets') }}</strong>
          — {{ t('air.overview.packetsDesc') }}
        </li>
        <li>
          <strong>{{ t('air.overview.timeRange') }}</strong>
          — {{ t('air.overview.timeRangeDesc') }}
        </li>
        <li>
          <strong>{{ t('air.overview.duration') }}</strong>
          — {{ t('air.overview.durationDesc') }}
        </li>
        <li>
          <strong>{{ t('air.overview.interval') }}</strong>
          — {{ t('air.overview.intervalDesc') }}
        </li>
        <li>
          <strong>{{ t('air.overview.pirRatio') }}</strong>
          — {{ t('air.overview.pirRatioDesc') }}
        </li>
        <li>
          <strong>{{ t('air.overview.fcnt') }}</strong>
          — {{ t('air.overview.fcntDesc') }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('air.sections.latest') }}</h3>
    <a-row :gutter="[12, 12]">
      <a-col v-for="card in latestCards" :key="card.key" :xs="12" :md="8" :xl="4">
        <div class="stat-card" :class="{ warn: card.warn }">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.warn ? brand.danger : brand.ink }">
            {{ card.value }}<span v-if="card.unit" class="unit">{{ card.unit }}</span>
          </div>
          <div class="stat-range">{{ card.range }}</div>
        </div>
      </a-col>
    </a-row>

    <div class="overview-legend">
      <div class="legend-title">{{ t('air.latestLegend.title') }}</div>
      <div class="legend-hint">{{ t('air.latestLegend.hint') }}</div>
      <ul class="legend-list">
        <li v-for="card in latestCards" :key="`legend-${card.key}`">
          <strong>{{ card.label }}</strong>
          — {{ t(`air.latestLegend.${card.key}`) }}
        </li>
      </ul>
    </div>

    <h3 class="section-title">{{ t('air.sections.insights') }}</h3>
    <a-card class="insight-card" :bordered="false">
      <div class="aq-badge" :class="aqBadgeClass">
        {{ t(`air.aq.${overview.aqLevel}`) }}
      </div>
      <ul class="insights">
        <li v-for="(item, idx) in insights" :key="idx">{{ item }}</li>
      </ul>
    </a-card>

    <h3 class="section-title">{{ t('air.sections.trends') }}</h3>
    <a-card :bordered="false">
      <a-radio-group v-model:value="mainMetric" button-style="solid" class="metric-tabs">
        <a-radio-button v-for="tab in metricTabs" :key="tab.key" :value="tab.key">
          {{ tab.label }}
        </a-radio-button>
      </a-radio-group>
      <div class="main-chart-title">
        {{ t(`air.metrics.${mainMetric}`) }} · {{ t('air.sections.trendSuffix') }}
      </div>
      <ChartPanel :option="mainOption" height="320px" />
    </a-card>

    <h3 class="section-title">{{ t('air.sections.multi') }}</h3>
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.charts.tempHum')" :bordered="false">
          <ChartPanel :option="tempHumOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.charts.airQuality')" :bordered="false">
          <ChartPanel :option="aqOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.charts.voc')" :bordered="false">
          <ChartPanel :option="vocOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.metrics.pressure')" :bordered="false">
          <ChartPanel :option="pressureOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.charts.lightPir')" :bordered="false">
          <ChartPanel :option="lightPirOption" height="260px" />
        </a-card>
      </a-col>
      <a-col :xs="24" :lg="12">
        <a-card :title="t('air.charts.signal')" :bordered="false">
          <div v-if="!overview.rssiStats.count" class="chart-note">{{ t('air.charts.signalEmpty') }}</div>
          <ChartPanel v-else :option="signalOption" height="260px" />
        </a-card>
      </a-col>
    </a-row>

    <h3 class="section-title">{{ t('air.sections.details') }}</h3>
    <a-card :bordered="false">
      <a-table
        row-key="id"
        size="small"
        :columns="columns"
        :data-source="pagedRows"
        :scroll="{ x: 1400 }"
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
          <template v-else-if="column.key === 'temperature'">{{ cell(record, 'temperature', 1) }}</template>
          <template v-else-if="column.key === 'humidity'">{{ cell(record, 'humidity', 1) }}</template>
          <template v-else-if="column.key === 'co2'">{{ cell(record, 'co2', 0) }}</template>
          <template v-else-if="column.key === 'pm2_5'">{{ cell(record, 'pm2_5', 0) }}</template>
          <template v-else-if="column.key === 'pm10'">{{ cell(record, 'pm10', 0) }}</template>
          <template v-else-if="column.key === 'tvoc'">{{ cell(record, 'tvoc', 0) }}</template>
          <template v-else-if="column.key === 'hcho'">{{ cell(record, 'hcho', 2) }}</template>
          <template v-else-if="column.key === 'pressure'">{{ cell(record, 'pressure', 1) }}</template>
          <template v-else-if="column.key === 'light_level'">{{ cell(record, 'light_level', 0) }}</template>
          <template v-else-if="column.key === 'pir'">{{ cell(record, 'pir', 0) }}</template>
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
}

.stat-card.warn {
  border-color: rgba(180, 35, 24, 0.35);
  background: rgba(180, 35, 24, 0.04);
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

.insight-card {
  background: var(--brand-surface, #fff);
  border: 1px solid #e6e2da;
}

.aq-badge {
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
