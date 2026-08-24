<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBuildingStore } from '@/stores/building'
import { floorName, type FloorStats } from '@/utils/buildingDemo'

defineProps<{
  selectedFloor?: number | null
}>()

const emit = defineEmits<{
  selectFloor: [floor: number]
}>()

const { t } = useI18n()
const store = useBuildingStore()

const filter = ref<'all' | 'alert'>('all')

const summary = computed(() => store.buildingSummary)

const onlinePct = computed(() => {
  if (!summary.value.registered) return 0
  return Math.round((summary.value.connected / summary.value.registered) * 100)
})

/** Metric-high floors (CO₂ etc.) — independent of MQTT, capped to 3 */
const metricAlertFloors = computed(() =>
  summary.value.floors
    .filter((f) => f.metricAlert)
    .sort((a, b) => (b.co2 ?? 0) - (a.co2 ?? 0) || a.floor - b.floor)
    .slice(0, 3),
)

/** MQTT disconnect floors — independent of metrics, capped to 3 */
const mqttAlertFloors = computed(() =>
  summary.value.floors
    .filter((f) => f.mqttAlert)
    .sort((a, b) => b.failed - a.failed || a.floor - b.floor)
    .slice(0, 3),
)

const alertFloorCount = computed(
  () =>
    new Set([
      ...metricAlertFloors.value.map((f) => f.floor),
      ...mqttAlertFloors.value.map((f) => f.floor),
    ]).size,
)

const failRatePct = computed(() => {
  if (!summary.value.registered) return 0
  return Math.round((summary.value.failed / summary.value.registered) * 1000) / 10
})

const listFloors = computed(() => {
  if (filter.value === 'alert') {
    const ids = new Set([
      ...metricAlertFloors.value.map((f) => f.floor),
      ...mqttAlertFloors.value.map((f) => f.floor),
    ])
    return summary.value.floors
      .filter((f) => ids.has(f.floor))
      .sort((a, b) => b.floor - a.floor)
  }
  return [...summary.value.floors].sort((a, b) => b.floor - a.floor)
})

function alertReasons(f: FloorStats) {
  const parts: string[] = []
  if (f.metricAlert) parts.push(t('buildingDash.co2High', { n: f.co2 }))
  if (f.mqttAlert) parts.push(t('buildingDash.failCount', { n: f.failed }))
  return parts
}

function onPick(floor: number) {
  emit('selectFloor', floor)
}
</script>

<template>
  <aside class="dash">
    <div class="head">
      <div>
        <h2>{{ t('buildingDash.title') }}</h2>
        <p>{{ t('buildingDash.subtitle') }}</p>
      </div>
      <span class="demo live">LIVE · WINGONIOT</span>
    </div>
    <div class="scroll">
      <!-- Building health summary -->
      <section class="block health">
        <div class="health-top">
          <div>
            <span class="kicker">{{ t('buildingDash.connectedRatio') }}</span>
            <div class="health-num">
              <strong>{{ summary.connected }}</strong>
              <span>/ {{ summary.registered }}</span>
            </div>
          </div>
          <div class="health-pct">{{ onlinePct }}%</div>
        </div>
        <div class="bar">
          <span class="bar-fill" :style="{ width: onlinePct + '%' }" />
        </div>
        <div class="health-meta">
          <span>{{ t('buildingDash.registered') }} <b>{{ summary.registered }}</b></span>
          <span>{{ t('buildingDash.failed') }} <b :class="{ bad: summary.failed > 0 }">{{ summary.failed }}</b> <i>({{ failRatePct }}%)</i></span>
          <span>{{ t('buildingDash.needsMetric') }} <b :class="{ warn: summary.metricAlertFloors > 0 }">{{ summary.metricAlertFloors }}</b></span>
          <span>{{ t('buildingDash.mqttAlertFloors') }} <b :class="{ bad: summary.mqttAlertFloors > 0 }">{{ summary.mqttAlertFloors }}</b></span>
        </div>
      </section>

      <!-- Per-floor metrics list -->
      <section class="block floors">
        <div class="floors-head">
          <div class="section-label">{{ t('buildingDash.floorList') }}</div>
          <div class="filters">
            <button
              type="button"
              class="filter"
              :class="{ on: filter === 'all' }"
              @click="filter = 'all'"
            >
              {{ t('buildingDash.filterAll') }}
            </button>
            <button
              type="button"
              class="filter"
              :class="{ on: filter === 'alert' }"
              @click="filter = 'alert'"
            >
              {{ t('buildingDash.filterAlert') }}
              <em v-if="alertFloorCount">{{ alertFloorCount }}</em>
            </button>
          </div>
        </div>

        <div v-if="!listFloors.length" class="empty">{{ t('buildingDash.noAlertFloors') }}</div>

        <div v-else class="floor-scroll">
          <div class="floor-table">
            <!-- 後端已屏蔽多餘指標欄位，前端亦僅顯示 連通/溫度/濕度（其餘欄位暫註解保留） -->
            <!-- 舊欄位群組標頭（連通分組）：
            <div class="list-groups" aria-hidden="true">
              <span class="sticky g-floor" />
              <span class="g-conn">{{ t('buildingDash.groupConn') }}</span>
              <span class="g-ct">CT103</span>
              <span class="g-am">AM319</span>
              <span class="g-vs">VS135</span>
              <span class="g-cnt">{{ t('buildingDash.groupCount') }}</span>
            </div>
            -->
            <div class="list-legend" aria-hidden="true">
              <span class="sticky leg-floor">{{ t('buildingDash.colFloor') }}</span>
              <span class="leg-online">{{ t('buildingDash.metricOnline') }}</span>
              <span>{{ t('buildingDash.metricTemp') }}</span>
              <span>{{ t('buildingDash.metricHumidity') }}</span>
              <!-- 舊欄位標題（暫時註解保留）：
              <span>{{ t('buildingDash.metricFail') }}</span>
              <span>{{ t('buildingDash.metricCurrent') }}</span>
              <span>{{ t('buildingDash.metricCableTemp') }}</span>
              <span>{{ t('buildingDash.metricCo2') }}</span>
              <span>{{ t('buildingDash.metricPm25') }}</span>
              <span>{{ t('buildingDash.metricPeriodIn') }}</span>
              <span>{{ t('buildingDash.metricPeriodOut') }}</span>
              <span>{{ t('buildingDash.metricOccupancy') }}</span>
              <span>{{ t('buildingDash.metricCt') }}</span>
              <span>{{ t('buildingDash.metricAm') }}</span>
              <span>{{ t('buildingDash.metricVs') }}</span>
              -->
            </div>

            <button
              v-for="f in listFloors"
              :key="f.floor"
              type="button"
              class="floor-row"
              :class="{
                selected: selectedFloor === f.floor,
                'alert-metric': f.metricAlert,
                'alert-mqtt': f.mqttAlert && !f.metricAlert,
              }"
              :title="alertReasons(f).join(' · ') || undefined"
              @click="onPick(f.floor)"
            >
              <div class="sticky floor-id">{{ t('building.level', { n: floorName(f.floor) }) }}</div>
              <span class="m online">{{ f.connected }}/{{ f.registered }}</span>
              <span class="m muted">{{ f.temperature != null ? `${f.temperature}°` : '--' }}</span>
              <span class="m muted">{{ f.humidity != null ? `${f.humidity}%` : '--' }}</span>
              <!-- 舊欄位資料（暫時註解保留）：
              <span class="m fail" :class="{ bad: f.mqttAlert }">
                {{ f.failed > 0 ? f.failed : '—' }}
              </span>
              <span class="m">{{ f.current != null ? f.current : '--' }}</span>
              <span class="m muted">{{ f.cableTemp != null ? `${f.cableTemp}°` : '--' }}</span>
              <span
                class="m co2"
                :class="{ warn: f.metricAlert }"
                :title="t('buildingDash.co2WarnHint')"
              >
                {{ f.co2 != null ? f.co2 : '--' }}
              </span>
              <span class="m">{{ f.pm25 != null ? f.pm25 : '--' }}</span>
              <span class="m">{{ f.periodIn != null ? f.periodIn : '--' }}</span>
              <span class="m">{{ f.periodOut != null ? f.periodOut : '--' }}</span>
              <span class="m">{{ f.occupancy != null ? f.occupancy : '--' }}</span>
              <span class="m type ct">{{ f.byType.CT103 }}</span>
              <span class="m type am">{{ f.byType.AM319 }}</span>
              <span class="m type vs">{{ f.byType.VS135 }}</span>
              -->
            </button>
          </div>
        </div>
      </section>

      <!-- Metric alerts (independent of MQTT) -->
      <section v-if="metricAlertFloors.length" class="block alerts">
        <div class="section-label alert-label metric">{{ t('buildingDash.needsMetric') }}</div>
        <button
          v-for="f in metricAlertFloors"
          :key="`metric-${f.floor}`"
          type="button"
          class="alert-card metric"
          @click="onPick(f.floor)"
        >
          <div class="alert-left">
            <div class="alert-floor">{{ t('building.level', { n: floorName(f.floor) }) }}</div>
            <div class="alert-reason">{{ t('buildingDash.co2High', { n: f.co2 }) }}</div>
          </div>
          <div class="alert-right">
            <span class="pill metric">{{ t('buildingDash.statusMetric') }}</span>
            <span class="go">→</span>
          </div>
        </button>
      </section>

      <!-- MQTT alerts (independent of metrics) -->
      <section v-if="mqttAlertFloors.length" class="block alerts">
        <div class="section-label alert-label mqtt">{{ t('buildingDash.needsMqtt') }}</div>
        <button
          v-for="f in mqttAlertFloors"
          :key="`mqtt-${f.floor}`"
          type="button"
          class="alert-card mqtt"
          @click="onPick(f.floor)"
        >
          <div class="alert-left">
            <div class="alert-floor">{{ t('building.level', { n: floorName(f.floor) }) }}</div>
            <div class="alert-reason">{{ t('buildingDash.failCount', { n: f.failed }) }}</div>
          </div>
          <div class="alert-right">
            <span class="pill mqtt">{{ t('buildingDash.statusMqtt') }}</span>
            <span class="go">→</span>
          </div>
        </button>
      </section>
    </div>
  </aside>
</template>

<style scoped lang="less">
.dash {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: #fff;
  border: 1px solid #e6e2da;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid #e6e2da;
  flex-shrink: 0;

  h2 {
    margin: 0;
    font-size: 16px;
    font-weight: 650;
    color: #0d0d0d;
  }

  p {
    margin: 4px 0 0;
    font-size: 12px;
    color: #6b6b6b;
    line-height: 1.4;
  }
}

.demo {
  flex-shrink: 0;
  align-self: flex-start;
  font-size: 10px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #a88955;
  border: 1px solid rgba(196, 165, 116, 0.55);
  padding: 3px 7px;
}

.demo.live {
  color: #3d7a5a;
  border-color: rgba(61, 122, 90, 0.5);
}

.scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-label {
  font-size: 11px;
  font-weight: 650;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #6b6b6b;
}

.alert-label {
  &.metric {
    color: #a88955;
  }

  &.mqtt {
    color: #b42318;
  }
}

.kicker {
  font-size: 11px;
  color: #6b6b6b;
  margin-bottom: 4px;
}

.health {
  border: 1px solid #e6e2da;
  background: #fafaf8;
  padding: 12px 14px;
}

.health-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
}

.health-num {
  display: flex;
  align-items: baseline;
  gap: 6px;

  strong {
    font-size: 28px;
    font-weight: 700;
    color: #0d0d0d;
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  span {
    font-size: 14px;
    color: #6b6b6b;
  }
}

.health-pct {
  font-size: 22px;
  font-weight: 700;
  color: #3d7a5a;
  font-variant-numeric: tabular-nums;
}

.bar {
  height: 6px;
  background: #e6e2da;
  overflow: hidden;
}

.bar-fill {
  display: block;
  height: 100%;
  background: #c4a574;
}

.health-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  font-size: 12px;
  color: #6b6b6b;

  b {
    color: #0d0d0d;
    font-variant-numeric: tabular-nums;
    margin-left: 4px;
  }

  i {
    font-style: normal;
    margin-left: 2px;
    color: #6b6b6b;
  }

  .bad b,
  .bad i {
    color: #b42318;
  }

  .warn b {
    color: #a88955;
  }
}

.alert-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  cursor: pointer;

  &.metric {
    border: 1px solid rgba(168, 137, 85, 0.4);
    background: rgba(196, 165, 116, 0.08);

    &:hover {
      border-color: rgba(168, 137, 85, 0.65);
      background: rgba(196, 165, 116, 0.14);
    }

    .alert-reason {
      color: #8a6d3b;
    }
  }

  &.mqtt {
    border: 1px solid rgba(180, 35, 24, 0.28);
    background: rgba(180, 35, 24, 0.04);

    &:hover {
      border-color: rgba(180, 35, 24, 0.5);
      background: rgba(180, 35, 24, 0.07);
    }

    .alert-reason {
      color: #b42318;
    }
  }
}

.alert-floor {
  font-weight: 650;
  font-size: 13px;
  color: #0d0d0d;
}

.alert-reason {
  margin-top: 2px;
  font-size: 12px;
}

.alert-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.pill {
  font-size: 11px;
  font-weight: 650;
  padding: 2px 7px;

  &.metric {
    color: #8a6d3b;
    background: rgba(196, 165, 116, 0.2);
  }

  &.mqtt {
    color: #b42318;
    background: rgba(180, 35, 24, 0.1);
  }
}

.go {
  color: #6b6b6b;
}

.floors-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.filters {
  display: flex;
  gap: 4px;
}

.filter {
  border: 1px solid #e6e2da;
  background: #fff;
  font-size: 11px;
  padding: 2px 8px;
  cursor: pointer;
  color: #6b6b6b;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  &.on {
    border-color: #c4a574;
    color: #0d0d0d;
    font-weight: 650;
  }

  em {
    font-style: normal;
    background: rgba(180, 35, 24, 0.12);
    color: #b42318;
    padding: 0 5px;
    font-size: 10px;
    font-weight: 700;
  }
}

.empty {
  font-size: 12px;
  color: #6b6b6b;
  padding: 12px 0;
}

.floor-scroll {
  overflow-x: auto;
  overflow-y: visible;
  margin: 0 -4px;
  padding: 0 4px;
  -webkit-overflow-scrolling: touch;
}

.floor-table {
  /* 舊版 15 欄最小寬度（多餘欄位已屏蔽）：
  min-width: 920px;
  */
  min-width: 0;
}

/* 目前僅顯示 樓層/連通/溫度/濕度 四欄（其餘欄位註解保留）：
@floor-cols: 72px 64px 40px 52px 52px 52px 48px 48px 52px 48px 48px 48px 44px 44px 44px;
*/
@floor-cols: 72px 104px 92px 84px;

/* 舊欄位群組標頭樣式（多餘欄位已屏蔽，暫註解保留）：
.list-groups {
  display: grid;
  grid-template-columns: @floor-cols;
  gap: 6px;
  align-items: end;
  padding: 4px 4px 2px;
  font-size: 10px;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #6b6b6b;

  .g-floor {
    grid-column: 1;
  }
  .g-conn {
    grid-column: 2 / 4;
    color: #8a8070;
  }
  .g-ct {
    grid-column: 4 / 6;
    color: #a88955;
  }
  .g-am {
    grid-column: 6 / 10;
    color: #5b7c99;
  }
  .g-vs {
    grid-column: 10 / 13;
    color: #3d7a5a;
  }
  .g-cnt {
    grid-column: 13 / 16;
    color: #8a8070;
  }
}
*/

.list-legend,
.floor-row {
  display: grid;
  grid-template-columns: @floor-cols;
  gap: 6px;
  align-items: center;
  padding: 8px 4px;
}

.list-legend {
  font-size: 10px;
  color: #6b6b6b;
  border-bottom: 1px solid #eeeae3;
  background: #fff;

  span {
    text-align: right;
    white-space: nowrap;
  }

  .leg-floor {
    text-align: left;
  }

  /* 連通 欄位與資料（.m.online，靠左）對齊，避免標題與數據錯位 */
  .leg-online {
    text-align: left;
  }
}

.floor-row {
  width: 100%;
  border: 1px solid transparent;
  border-bottom-color: #eeeae3;
  background: #fff;
  cursor: pointer;
  text-align: left;

  &:hover {
    background: #fafaf8;
  }

  &.selected {
    border-color: #c4a574;
    background: rgba(196, 165, 116, 0.1);
  }

  &.alert-metric:not(.selected) {
    background: rgba(196, 165, 116, 0.06);
  }

  &.alert-mqtt:not(.selected) {
    background: rgba(180, 35, 24, 0.03);
  }
}

.sticky {
  position: sticky;
  left: 0;
  z-index: 1;
  background: inherit;
  box-shadow: 4px 0 8px -6px rgba(0, 0, 0, 0.18);
}

.floor-id {
  font-size: 12px;
  font-weight: 650;
  color: #0d0d0d;
  padding-right: 4px;
}

.list-groups .sticky,
.list-legend .sticky {
  background: #fff;
  z-index: 2;
}

.floor-row:hover .sticky {
  background: #fafaf8;
}

.floor-row.selected .sticky {
  background: #f5efe4;
}

.floor-row.alert-metric:not(.selected) .sticky {
  background: #f7f3eb;
}

.floor-row.alert-mqtt:not(.selected) .sticky {
  background: #faf3f2;
}

.m {
  text-align: right;
  color: #0d0d0d;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;

  &.online {
    text-align: left;
    font-weight: 600;
  }

  &.muted {
    color: #6b6b6b;
  }

  /* 舊欄位樣式（多餘欄位已屏蔽，暫註解保留）：
  &.co2.warn {
    color: #b42318;
    font-weight: 700;
  }

  &.fail.bad {
    color: #b42318;
    font-weight: 700;
  }

  &.type {
    font-weight: 650;

    &.ct {
      color: #a88955;
    }
    &.am {
      color: #5b7c99;
    }
    &.vs {
      color: #3d7a5a;
    }
  }
  */
}

.foot {
  flex-shrink: 0;
  border-top: 1px solid #e6e2da;
  padding: 8px 14px;
  font-size: 11px;
  color: #6b6b6b;
  background: #fafaf8;
}
</style>

<!-- Large-screen overrides (non-scoped, only active under html.ls-on) -->
<style lang="less">
html.ls-on .dash .section-label {
  font-size: 14px;
  margin-bottom: 2px;
}

html.ls-on .dash .filter {
  font-size: 14px;
  padding: 3px 10px;
}

html.ls-on .dash .filter em {
  font-size: 12px;
  padding: 0 5px;
}

html.ls-on .dash .list-legend {
  font-size: 13px;
  padding: 6px 4px;
}

html.ls-on .dash .floor-row {
  padding: 6px 4px;
}

html.ls-on .dash .floor-id {
  font-size: 16px;
}

html.ls-on .dash .m {
  font-size: 16px;
}

html.ls-on .dash .alert-floor {
  font-size: 16px;
}

html.ls-on .dash .alert-reason {
  font-size: 14px;
}

html.ls-on .dash .pill {
  font-size: 13px;
  padding: 3px 8px;
}

html.ls-on .dash .empty {
  font-size: 14px;
  padding: 10px 0;
}

html.ls-on .dash .floors-head {
  gap: 8px;
}

html.ls-on .dash .health-meta {
  font-size: 14px;
}

html.ls-on .dash .block {
  gap: 6px;
}
</style>
