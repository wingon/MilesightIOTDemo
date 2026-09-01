<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  BgColorsOutlined,
  CheckOutlined,
  LayoutOutlined,
  MenuOutlined,
  SettingOutlined,
} from '@ant-design/icons-vue'
import { useAppStore } from '@/stores/app'

const { t } = useI18n()
const appStore = useAppStore()

const config = computed(() => appStore.layoutConfig)

const themeModes = [
  { key: 'dark', label: t('layoutSettings.themeModeDark') },
  { key: 'light', label: t('layoutSettings.themeModeLight') },
]

const navModes = [
  { key: 'dark', label: t('layoutSettings.navModeDark') },
  { key: 'light', label: t('layoutSettings.navModeLight') },
]

const themeColors = [
  '#C4A574',
  '#1890ff',
  '#3D7A5A',
  '#722ed1',
  '#B42318',
  '#fa8c16',
  '#13c2c2',
  '#2f54eb',
]

function handleToggle(key: string, value: boolean) {
  appStore.updateLayoutConfig({ [key]: value })
}

function handleRadioChange(key: string, e: any) {
  appStore.updateLayoutConfig({ [key]: e.target.value })
}

function handleSideThemeChange(theme: 'dark' | 'light') {
  appStore.updateLayoutConfig({ sideTheme: theme })
}

function handleThemeModeChange(mode: 'dark' | 'light') {
  appStore.updateLayoutConfig({ themeMode: mode })
}

function handleThemeColorChange(color: string) {
  appStore.updateLayoutConfig({ themeColor: color })
}

function handleSave() {
  appStore.closeLayoutSettings()
}

function handleReset() {
  appStore.resetLayoutConfig()
}
</script>

<template>
  <a-drawer
    :open="appStore.layoutSettingsVisible"
    :title="t('layoutSettings.title')"
    placement="right"
    :width="360"
    root-class-name="layout-settings-drawer"
    @close="appStore.closeLayoutSettings"
  >
    <div class="settings-content">
      <!-- 菜單導航設置 -->
      <div class="settings-section">
        <h4 class="section-title">
          <MenuOutlined class="section-icon" />
          <span>{{ t('layoutSettings.navSettings') }}</span>
        </h4>
        <div class="mode-grid">
          <div
            v-for="mode in navModes"
            :key="mode.key"
            class="mode-card"
            :class="{ active: config.sideTheme === mode.key }"
            @click="handleSideThemeChange(mode.key as 'dark' | 'light')"
          >
            <div class="mode-preview" :class="`preview-nav-${mode.key}`">
              <div class="pv-side">
                <div class="pv-logo"></div>
                <div class="pv-menu"><i></i><i></i><i></i></div>
              </div>
              <div class="pv-main">
                <div class="pv-header"><i class="pv-brandline"></i></div>
                <div class="pv-body">
                  <div class="pv-card"><i></i><i></i><i></i></div>
                  <div class="pv-card"><i></i><i></i></div>
                </div>
              </div>
            </div>
            <span class="mode-check"><CheckOutlined /></span>
            <span class="mode-label">{{ mode.label }}</span>
          </div>
        </div>
      </div>

      <!-- 主題風格設置 -->
      <div class="settings-section">
        <h4 class="section-title">
          <BgColorsOutlined class="section-icon" />
          <span>{{ t('layoutSettings.themeSettings') }}</span>
        </h4>
        <div class="mode-grid">
          <div
            v-for="mode in themeModes"
            :key="mode.key"
            class="mode-card"
            :class="{ active: config.themeMode === mode.key }"
            @click="handleThemeModeChange(mode.key as 'dark' | 'light')"
          >
            <div class="mode-preview" :class="`preview-theme-${mode.key}`">
              <div class="pv-side">
                <div class="pv-logo"></div>
                <div class="pv-menu"><i></i><i></i><i></i></div>
              </div>
              <div class="pv-main">
                <div class="pv-header"><i class="pv-brandline"></i></div>
                <div class="pv-body">
                  <div class="pv-card"><i></i><i></i><i></i></div>
                  <div class="pv-card"><i></i><i></i></div>
                </div>
              </div>
            </div>
            <span class="mode-check"><CheckOutlined /></span>
            <span class="mode-label">{{ mode.label }}</span>
          </div>
        </div>
      </div>

      <!-- 主題顏色 -->
      <div class="settings-section">
        <h4 class="section-title">
          <LayoutOutlined class="section-icon" />
          <span>{{ t('layoutSettings.themeColor') }}</span>
        </h4>
        <div class="theme-colors">
          <div
            v-for="(color, index) in themeColors"
            :key="index"
            class="color-dot"
            :class="{ active: config.themeColor === color }"
            :style="{ background: color }"
            @click="handleThemeColorChange(color)"
          >
            <span v-if="config.themeColor === color" class="color-check">
              <CheckOutlined />
            </span>
          </div>
        </div>
      </div>

      <!-- 系統佈局配置 -->
      <div class="settings-section">
        <h4 class="section-title">
          <SettingOutlined class="section-icon" />
          <span>{{ t('layoutSettings.systemConfig') }}</span>
        </h4>
        <div class="config-list">
          <div class="config-item">
            <span>{{ t('layoutSettings.showTabs') }}</span>
            <a-switch :checked="config.showTabs" @change="(v: boolean) => handleToggle('showTabs', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.persistTabs') }}</span>
            <a-switch :checked="config.persistTabs" @change="(v: boolean) => handleToggle('persistTabs', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.showTabIcons') }}</span>
            <a-switch :checked="config.showTabIcons" @change="(v: boolean) => handleToggle('showTabIcons', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.tabStyle') }}</span>
            <a-radio-group
              :value="config.tabStyle"
              size="small"
              @change="(e: any) => handleRadioChange('tabStyle', e)"
            >
              <a-radio-button value="card">{{ t('layoutSettings.tabStyleCard') }}</a-radio-button>
              <a-radio-button value="button">{{ t('layoutSettings.tabStyleButton') }}</a-radio-button>
            </a-radio-group>
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.fixedHeader') }}</span>
            <a-switch :checked="config.fixedHeader" @change="(v: boolean) => handleToggle('fixedHeader', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.showLogo') }}</span>
            <a-switch :checked="config.showLogo" @change="(v: boolean) => handleToggle('showLogo', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.dynamicTitle') }}</span>
            <a-switch :checked="config.dynamicTitle" @change="(v: boolean) => handleToggle('dynamicTitle', v)" />
          </div>
          <div class="config-item">
            <span>{{ t('layoutSettings.showFooter') }}</span>
            <a-switch :checked="config.showFooter" @change="(v: boolean) => handleToggle('showFooter', v)" />
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="drawer-footer">
        <a-button @click="handleReset">{{ t('layoutSettings.resetConfig') }}</a-button>
        <a-button type="primary" class="save-btn" @click="handleSave">{{ t('layoutSettings.saveConfig') }}</a-button>
      </div>
    </template>
  </a-drawer>
</template>

<style scoped lang="less">
.settings-content {
  padding: 4px 4px 16px;
}

.settings-section {
  margin-bottom: 28px;
}

/* ── 区块标题：金色竖线 + 图标 ── */
.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--brand-ink, #0d0d0d);
  margin: 0 0 16px;
  padding: 0 0 10px 12px;
  border-bottom: 1px solid var(--brand-line, #f0ece5);
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 1px;
    bottom: 10px;
    width: 3px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--brand-primary, #c4a574), rgba(196, 165, 116, 0.35));
  }

  .section-icon {
    color: var(--brand-primary, #c4a574);
    font-size: 14px;
  }
}

/* ── 模式选择卡（导航 / 主题共用） ── */
.mode-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.mode-card {
  position: relative;
  cursor: pointer;
  border-radius: 8px;
  padding: 4px 4px 8px;
  border: 1.5px solid transparent;
  background: transparent;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;

  &:hover {
    border-color: rgba(196, 165, 116, 0.55);
    background: var(--brand-line, #faf8f5);
  }

  &.active {
    border-color: var(--brand-primary, #c4a574);
    background: rgba(196, 165, 116, 0.06);
    box-shadow: 0 0 0 1px rgba(196, 165, 116, 0.18);
  }
}

.mode-label {
  font-size: 12px;
  color: var(--brand-muted, #666);
  transition: color 0.2s;
}

.mode-card.active .mode-label {
  color: var(--brand-primary, #a88955);
  font-weight: 600;
}

/* ── 布局缩略预览（结构化骨架） ── */
.mode-preview {
  position: relative;
  width: 148px;
  height: 90px;
  border-radius: 6px;
  overflow: hidden;
  display: flex;
  border: 1px solid var(--brand-line, #e0e0e0);
  transition: box-shadow 0.2s ease;

  .mode-card.active & {
    box-shadow: 0 2px 8px rgba(196, 165, 116, 0.28);
  }
}

/* 侧栏 */
.pv-side {
  width: 34px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: 5px 4px;
  gap: 5px;
}

.pv-logo {
  height: 7px;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--brand-primary, #c4a574), rgba(196, 165, 116, 0.55));
}

.pv-menu {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 2px;

  i {
    height: 4px;
    border-radius: 2px;
    background: currentColor;
    opacity: 0.45;

    &:nth-child(1) {
      opacity: 1;
    }
  }
}

/* 主区 */
.pv-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.pv-header {
  height: 14px;
  display: flex;
  align-items: flex-end;
  padding: 0 5px 3px;
  border-bottom: 1px solid rgba(196, 165, 116, 0.5);

  .pv-brandline {
    height: 3px;
    width: 40%;
    border-radius: 2px;
    background: var(--brand-primary, #c4a574);
    opacity: 0.75;
  }
}

.pv-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 5px;
}

.pv-card {
  flex: 1;
  border-radius: 3px;
  display: flex;
  gap: 3px;
  padding: 3px;

  i {
    flex: 1;
    border-radius: 2px;
  }

  &:first-child i:nth-child(1) {
    opacity: 1;
  }
}

/* ── 主题模式配色：深色 ── */
.preview-theme-dark {
  background: #171717;
  border-color: #333;

  .pv-side {
    background: #232323;

    .pv-menu {
      color: #d9d2c2;

      i {
        background: rgba(255, 255, 255, 0.22);

        &:nth-child(1) {
          background: #c4a574;
        }
      }
    }
  }

  .pv-main {
    background: #171717;
  }

  .pv-header {
    background: #1e1e1e;

    .pv-brandline {
      background: var(--brand-primary, #c4a574);
      opacity: 1;
    }
  }

  .pv-body {
    .pv-card {
      background: #262626;
      border: 1px solid #323232;

      i {
        background: #3c3c3c;

        &:first-child {
          background: rgba(196, 165, 116, 0.5);
        }
      }
    }
  }
}

/* ── 主题模式配色：浅色 ── */
.preview-theme-light {
  background: #f2f0ec;
  border-color: #e0dbd1;

  .pv-side {
    background: #ffffff;
    border-right: 1px solid #e6e2da;

    .pv-menu {
      color: #a88955;

      i {
        background: #d9d2c2;

        &:nth-child(1) {
          background: #c4a574;
        }
      }
    }
  }

  .pv-main {
    background: #f2f0ec;
  }

  .pv-header {
    background: #ffffff;

    .pv-brandline {
      background: var(--brand-primary, #c4a574);
      opacity: 1;
    }
  }

  .pv-body {
    .pv-card {
      background: #ffffff;
      border: 1px solid #e6e2da;

      i {
        background: #ece8df;

        &:first-child {
          background: rgba(196, 165, 116, 0.5);
        }
      }
    }
  }
}

/* ── 导航模式配色（侧栏主题） ── */
.preview-nav-dark {
  background: #f2f0ec;
  border-color: #e0dbd1;

  .pv-side {
    background: #1a1a1a;
    border-right: 1px solid rgba(196, 165, 116, 0.35);

    .pv-menu {
      color: #f5ead7;

      i {
        background: rgba(255, 255, 255, 0.3);

        &:nth-child(1) {
          background: #c4a574;
        }
      }
    }
  }

  .pv-main {
    background: #f2f0ec;
  }

  .pv-header {
    background: #ffffff;

    .pv-brandline {
      background: var(--brand-primary, #c4a574);
      opacity: 1;
    }
  }

  .pv-body {
    .pv-card {
      background: #ffffff;
      border: 1px solid #e6e2da;

      i {
        background: #ece8df;

        &:first-child {
          background: rgba(196, 165, 116, 0.5);
        }
      }
    }
  }
}

.preview-nav-light {
  background: #f2f0ec;
  border-color: #e0dbd1;

  .pv-side {
    background: #ffffff;
    border-right: 1px solid #e6e2da;

    .pv-menu {
      color: #a88955;

      i {
        background: #d9d2c2;

        &:nth-child(1) {
          background: #c4a574;
        }
      }
    }
  }

  .pv-main {
    background: #f2f0ec;
  }

  .pv-header {
    background: #ffffff;

    .pv-brandline {
      background: var(--brand-primary, #c4a574);
      opacity: 1;
    }
  }

  .pv-body {
    .pv-card {
      background: #ffffff;
      border: 1px solid #e6e2da;

      i {
        background: #ece8df;

        &:first-child {
          background: rgba(196, 165, 116, 0.5);
        }
      }
    }
  }
}

/* ── 选中角标 ── */
.mode-check {
  position: absolute;
  top: -9px;
  right: 4px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--brand-primary, #c4a574);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.35);
  opacity: 0;
  transform: scale(0.5);
  transition: opacity 0.2s ease, transform 0.2s ease;
  pointer-events: none;
  z-index: 2;

  .mode-card.active & {
    opacity: 1;
    transform: scale(1);
  }
}

/* ── 主题颜色：圆形色板 ── */
.theme-colors {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 10px;
  padding: 2px;
}

.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative;

  &:hover {
    transform: scale(1.12);
  }

  &.active {
    box-shadow: 0 0 0 2px var(--brand-surface, #fff), 0 0 0 4px var(--brand-primary, #c4a574);
    transform: scale(1.08);
  }
}

.color-check {
  color: #fff;
  font-size: 13px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
}

/* ── 配置列表 ── */
.config-list {
  display: flex;
  flex-direction: column;
}

.config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 2px;
  border-bottom: 1px dashed var(--brand-line, #f0ece5);

  &:last-child {
    border-bottom: none;
  }

  span {
    font-size: 13px;
    color: var(--brand-ink, #333);
  }
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--brand-line, #f0ece5);

  .save-btn {
    flex: 1;
  }
}
</style>

<style lang="less">
/* 抽屉根级样式（非 scoped，作用于 .layout-settings-drawer 及其内部） */
.layout-settings-drawer {
  .ant-drawer-header {
    padding: 16px 20px;
    border-bottom: 1px solid var(--brand-line, #f0ece5);

    .ant-drawer-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 600;
      color: var(--brand-ink, #0d0d0d);
      letter-spacing: 0.03em;

      &::before {
        content: '';
        width: 4px;
        height: 16px;
        border-radius: 2px;
        background: linear-gradient(180deg, var(--brand-primary, #c4a574), rgba(196, 165, 116, 0.4));
      }
    }
  }

  .ant-drawer-body {
    padding: 20px;
  }

  .ant-drawer-footer {
    padding: 12px 20px;
  }
}
</style>