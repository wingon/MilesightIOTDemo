<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  getHealth,
  getStats,
  listTof,
  listUg65,
  type StatsResponse,
  type TofRow,
  type Ug65Row,
} from '@/api/milesight'
import ChartPanel from '@/components/ChartPanel.vue'
import { brand } from '@/theme/colorConfig'
import {
  AIR_EUI,
  CT103_EUI,
  buildAirMetricOption,
  buildCurrentOption,
  buildPeopleOption,
  latestAirSnapshot,
  latestCurrentSnapshot,
  latestPeopleSnapshot,
} from '@/utils/dashboardCharts'

const { t, locale } = useI18n()
const loading = ref(false)
const health = ref<{ status: string; database: string } | null>(null)
const stats = ref<StatsResponse | null>(null)
const tofRows = ref<TofRow[]>([])
const ug65Rows = ref<Ug65Row[]>([])
const error = ref('')

const peopleLatest = computed(() => latestPeopleSnapshot(tofRows.value))
const airLatest = computed(() => latestAirSnapshot(ug65Rows.value))
const currentLatest = computed(() => latestCurrentSnapshot(ug65Rows.value))

const peopleOption = computed(() => {
  void locale.value
  return buildPeopleOption(tofRows.value, {
    periodIn: t('dashboard.charts.periodIn'),
    periodOut: t('dashboard.charts.periodOut'),
    cumulative: t('dashboard.charts.cumulative'),
    inCounted: t('dashboard.charts.inCounted'),
    outCounted: t('dashboard.charts.outCounted'),
  })
})

const airCo2Option = computed(() => {
  void locale.value
  return buildAirMetricOption(
    ug65Rows.value,
    'co2',
    t('dashboard.charts.co2'),
    'ppm',
    brand.primary,
  )
})

const airTempOption = computed(() => {
  void locale.value
  return buildAirMetricOption(
    ug65Rows.value,
    'temperature',
    t('dashboard.charts.temperature'),
    '°C',
    '#8B5A2B',
  )
})

const airHumidityOption = computed(() => {
  void locale.value
  return buildAirMetricOption(
    ug65Rows.value,
    'humidity',
    t('dashboard.charts.humidity'),
    '%',
    '#5B7C99',
  )
})

const airPm25Option = computed(() => {
  void locale.value
  return buildAirMetricOption(
    ug65Rows.value,
    'pm2_5',
    t('dashboard.charts.pm25'),
    'µg/m³',
    '#6B6B6B',
  )
})

const currentOption = computed(() => {
  void locale.value
  return buildCurrentOption(ug65Rows.value, {
    current: t('dashboard.charts.current'),
    totalCurrent: t('dashboard.charts.totalCurrent'),
  })
})

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [h, s, tof, ug65] = await Promise.all([
      getHealth(),
      getStats(),
      listTof({ limit: 60 }),
      listUg65({ limit: 80 }),
    ])
    health.value = h.data
    stats.value = s.data
    tofRows.value = tof.data.items
    ug65Rows.value = ug65.data.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : t('dashboard.loadFailed')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <a-spin :spinning="loading">
    <div class="page-hero">
      <div class="hero-left">
        <div class="hero-title">{{ t('common.brand') }}</div>
        <div class="hero-sub">{{ t('dashboard.subtitle') }}</div>
      </div>
      <a-button type="primary" @click="load">{{ t('common.refresh') }}</a-button>
    </div>

    <a-alert
      v-if="error"
      type="error"
      show-icon
      :message="error"
      style="margin-bottom: 16px"
    />

    <a-row :gutter="16" class="stat-cards">
      <a-col :xs="24" :md="8">
        <a-card class="stat-card" :title="t('dashboard.serviceStatus')">
          <a-statistic
            :title="t('dashboard.api')"
            :value="health?.status || '-'"
            :value-style="{
              color: health?.status === 'ok' ? brand.success : brand.danger,
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
            }"
          />
          <div class="meta">{{ t('dashboard.mariadb') }}：{{ health?.database || '-' }}</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card class="stat-card" :title="t('dashboard.tofCard')">
          <a-statistic :title="t('dashboard.uplinkCount')" :value="stats?.tof.total_rows ?? 0" />
          <div class="meta">{{ t('dashboard.deviceCount') }}：{{ stats?.tof.device_count ?? 0 }}</div>
          <div class="meta">{{ t('dashboard.lastReceived') }}：{{ stats?.tof.last_received_at || '-' }}</div>
        </a-card>
      </a-col>
      <a-col :xs="24" :md="8">
        <a-card class="stat-card" :title="t('dashboard.ug65Card')">
          <a-statistic :title="t('dashboard.uplinkCount')" :value="stats?.ug65.total_rows ?? 0" />
          <div class="meta">{{ t('dashboard.deviceCount') }}：{{ stats?.ug65.device_count ?? 0 }}</div>
          <div class="meta">{{ t('dashboard.lastReceived') }}：{{ stats?.ug65.last_received_at || '-' }}</div>
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :xs="24" :lg="14">
        <a-card :title="t('dashboard.reports.peopleTitle')">
          <template #extra>
            <span class="card-extra">{{ t('dashboard.reports.peopleDesc') }}</span>
          </template>
          <a-row :gutter="12" class="kpi-row">
            <a-col :span="6">
              <a-statistic
                :title="t('dashboard.charts.periodIn')"
                :value="Number(peopleLatest?.periodic?.in ?? 0)"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                :title="t('dashboard.charts.periodOut')"
                :value="Number(peopleLatest?.periodic?.out ?? 0)"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                :title="t('dashboard.charts.inCounted')"
                :value="Number(peopleLatest?.total?.in_counted ?? 0)"
              />
            </a-col>
            <a-col :span="6">
              <a-statistic
                :title="t('dashboard.charts.outCounted')"
                :value="Number(peopleLatest?.total?.out_counted ?? 0)"
              />
            </a-col>
          </a-row>
          <ChartPanel :option="peopleOption" height="320px" />
        </a-card>
      </a-col>

      <a-col :xs="24" :lg="10">
        <a-card :title="t('dashboard.reports.currentTitle')">
          <template #extra>
            <span class="card-extra">{{ CT103_EUI }}</span>
          </template>
          <a-row :gutter="12" class="kpi-row">
            <a-col :span="12">
              <a-statistic
                :title="t('dashboard.charts.current')"
                :value="Number(currentLatest?.current ?? 0)"
                :precision="2"
                suffix="A"
              />
            </a-col>
            <a-col :span="12">
              <a-statistic
                :title="t('dashboard.charts.totalCurrent')"
                :value="Number(currentLatest?.total_current ?? 0)"
                :precision="2"
                suffix="A"
              />
            </a-col>
          </a-row>
          <ChartPanel :option="currentOption" height="320px" />
        </a-card>
      </a-col>
    </a-row>

    <a-row :gutter="16" style="margin-top: 16px">
      <a-col :span="24">
        <a-card :title="t('dashboard.reports.airTitle')">
          <template #extra>
            <span class="card-extra">{{ AIR_EUI }} · {{ t('dashboard.reports.airDesc') }}</span>
          </template>
          <a-row :gutter="12" class="kpi-row">
            <a-col :xs="12" :md="6">
              <a-statistic
                :title="t('dashboard.charts.co2')"
                :value="Number(airLatest?.co2 ?? 0)"
                suffix="ppm"
              />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic
                :title="t('dashboard.charts.temperature')"
                :value="Number(airLatest?.temperature ?? 0)"
                :precision="1"
                suffix="°C"
              />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic
                :title="t('dashboard.charts.humidity')"
                :value="Number(airLatest?.humidity ?? 0)"
                :precision="1"
                suffix="%"
              />
            </a-col>
            <a-col :xs="12" :md="6">
              <a-statistic
                :title="t('dashboard.charts.pm25')"
                :value="Number(airLatest?.pm2_5 ?? 0)"
                suffix="µg/m³"
              />
            </a-col>
          </a-row>
          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :md="12">
              <div class="chart-subtitle">{{ t('dashboard.charts.co2') }}</div>
              <ChartPanel :option="airCo2Option" height="240px" />
            </a-col>
            <a-col :xs="24" :md="12">
              <div class="chart-subtitle">{{ t('dashboard.charts.temperature') }}</div>
              <ChartPanel :option="airTempOption" height="240px" />
            </a-col>
            <a-col :xs="24" :md="12">
              <div class="chart-subtitle">{{ t('dashboard.charts.humidity') }}</div>
              <ChartPanel :option="airHumidityOption" height="240px" />
            </a-col>
            <a-col :xs="24" :md="12">
              <div class="chart-subtitle">{{ t('dashboard.charts.pm25') }}</div>
              <ChartPanel :option="airPm25Option" height="240px" />
            </a-col>
          </a-row>
        </a-card>
      </a-col>
    </a-row>
  </a-spin>
</template>

<style scoped lang="less">
.page-hero {
  padding: 8px 0 20px;
  margin-bottom: 16px;
  border-bottom: 1px solid #e6e2da;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.hero-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #0d0d0d;
}

.hero-sub {
  margin-top: 4px;
  color: #6b6b6b;
  font-size: 13px;
}

.chart-subtitle {
  margin-bottom: 4px;
  font-size: 13px;
  font-weight: 600;
  color: #0d0d0d;
}

.meta {
  margin-top: 8px;
  color: #6b6b6b;
  font-size: 13px;
}

.card-extra {
  color: #6b6b6b;
  font-size: 12px;
}

.kpi-row {
  margin-bottom: 8px;
}

.stat-cards {
  align-items: stretch;
}

.stat-cards :deep(.ant-col) {
  display: flex;
}

.stat-card {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.stat-card :deep(.ant-card-body) {
  flex: 1;
}
</style>
