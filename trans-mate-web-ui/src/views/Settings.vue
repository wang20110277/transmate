<template>
  <div class="settings-layout">
    <!-- 左侧：分组菜单栏 -->
    <aside class="settings-side">
      <!-- macOS 红绿灯让位区（兼作窗口拖动区，非 Mac 平台隐藏） -->
      <div class="side-top"></div>

      <div class="side-brand">
        <button
          class="back-btn"
          :data-tip="t('settings.backHome')"
          :aria-label="t('settings.backHome')"
          @click="goHome"
        >
          <i class="fas fa-arrow-left"></i>
        </button>
        <span class="brand-name">TransMate</span>
      </div>

      <div v-for="group in menuGroups" :key="group.key" class="menu-group">
        <div class="group-label">{{ group.label }}</div>
        <button
          v-for="item in group.items"
          :key="item.key"
          :class="['menu-item', { active: activeKey === item.key }]"
          @click="activeKey = item.key"
        >
          <i :class="['fas', item.icon]"></i>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </aside>

    <!-- 右侧：分区内容 -->
    <main class="settings-main">
      <header class="settings-header">
        <h1 class="settings-title">{{ currentItem.label }}</h1>
      </header>

      <div :class="['settings-body', { panel: activeKey === 'skills' }]">
        <!-- 技能分区：嵌入技能管理面板（仓库浏览/搜索/装卸） -->
        <SkillsPanel v-if="activeKey === 'skills'" />
        <div v-else class="placeholder-card">
          <span class="placeholder-icon">
            <i :class="['fas', currentItem.icon]"></i>
          </span>
          <h2 class="placeholder-title">{{ currentItem.label }}</h2>
          <p class="placeholder-desc">{{ currentItem.desc }}</p>
          <span class="placeholder-pill">{{ t('settings.notOpen') }}</span>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/i18n'
import SkillsPanel from './Skills.vue'

interface MenuItem {
  key: string
  label: string
  icon: string
  desc: string
}

const router = useRouter()
const { t } = useI18n()

// 菜单项配置：图标固定，文案随界面语言切换
const itemMetas: { key: string; icon: string }[] = [
  { key: 'general', icon: 'fa-cog' },
  { key: 'appearance', icon: 'fa-palette' },
  { key: 'memory', icon: 'fa-brain' },
  { key: 'skills', icon: 'fa-bolt' },
  { key: 'rag', icon: 'fa-database' },
  { key: 'mcp', icon: 'fa-plug' }
]

// 左栏菜单：基础设置 / 能力设置 两组
const menuGroups = computed<{ key: string; label: string; items: MenuItem[] }[]>(() => [
  {
    key: 'basic',
    label: t('settings.groupBasic'),
    items: itemMetas.slice(0, 2).map(({ key, icon }) => ({
      key,
      icon,
      label: t(`settings.items.${key}.label`),
      desc: t(`settings.items.${key}.desc`)
    }))
  },
  {
    key: 'capability',
    label: t('settings.groupCapability'),
    items: itemMetas.slice(2).map(({ key, icon }) => ({
      key,
      icon,
      label: t(`settings.items.${key}.label`),
      desc: t(`settings.items.${key}.desc`)
    }))
  }
])

const activeKey = ref('general')

const currentItem = computed<MenuItem>(() => {
  for (const group of menuGroups.value) {
    const found = group.items.find((item) => item.key === activeKey.value)
    if (found) return found
  }
  return menuGroups.value[0].items[0]
})

const goHome = () => {
  router.push('/')
}
</script>

<style>
.settings-layout {
  height: 100vh;
  display: flex;
  font-family: "Noto Sans SC", "Helvetica Neue", Arial, sans-serif;
  background: var(--color-surface);
  color: var(--color-text);
  overflow: hidden;
}

/* ===== 左侧：分组菜单 ===== */
.settings-layout .settings-side {
  display: flex;
  flex-direction: column;
  width: 240px;
  min-width: 240px;
  padding: 16px 12px;
  box-sizing: border-box;
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-border);
  overflow-y: auto;
}

.settings-layout .side-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 4px 16px;
}

.settings-layout .back-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: 13px;
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  cursor: pointer;
  transition: color var(--transition), background var(--transition), border-color var(--transition);
  flex-shrink: 0;
  box-sizing: border-box;
  -webkit-app-region: no-drag;
}

.settings-layout .back-btn:hover {
  color: var(--color-text);
  background: var(--color-hover);
  border-color: var(--color-border-strong);
}

.settings-layout .back-btn::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  padding: 5px 9px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  color: var(--color-tooltip-text);
  background: var(--color-tooltip);
  border-radius: 6px;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--transition), visibility var(--transition);
  z-index: 20;
}

.settings-layout .back-btn:hover::after {
  opacity: 1;
  visibility: visible;
}

.settings-layout .brand-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.settings-layout .menu-group {
  margin-bottom: 18px;
}

.settings-layout .group-label {
  padding: 0 10px 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.settings-layout .menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  font-size: 13.5px;
  text-align: left;
  color: var(--color-text-secondary);
  background: transparent;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition);
  box-sizing: border-box;
}

.settings-layout .menu-item i {
  width: 16px;
  font-size: 13px;
  text-align: center;
  flex-shrink: 0;
}

.settings-layout .menu-item:hover {
  color: var(--color-text);
  background: var(--color-hover);
}

.settings-layout .menu-item.active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  font-weight: 500;
}

/* ===== 右侧：分区内容 ===== */
.settings-layout .settings-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.settings-layout .settings-header {
  display: flex;
  align-items: center;
  min-height: 56px;
  padding: 12px 32px;
  border-bottom: 1px solid var(--color-border);
}

.settings-layout .settings-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.settings-layout .settings-body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 32px;
  box-sizing: border-box;
}

/* 嵌入面板类分区（如技能管理）：块级铺满，去掉居中空态布局 */
.settings-layout .settings-body.panel {
  display: block;
  padding: 24px 32px;
}

/* 占位空状态卡片 */
.settings-layout .placeholder-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  width: 100%;
  max-width: 420px;
  padding: 48px 32px;
  text-align: center;
  background: var(--color-surface);
  border: 1px dashed var(--color-border-strong);
  border-radius: var(--radius-card);
  box-sizing: border-box;
}

.settings-layout .placeholder-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  margin-bottom: 10px;
  font-size: 20px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-radius: 14px;
}

.settings-layout .placeholder-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.settings-layout .placeholder-desc {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-text-muted);
}

.settings-layout .placeholder-pill {
  margin-top: 14px;
  padding: 3px 12px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-fill);
  border-radius: 999px;
}

/* ===== 响应式 ===== */
@media (max-width: 760px) {
  .settings-layout .settings-side {
    display: none;
  }

  .settings-layout .settings-header {
    padding: 0 16px;
  }

  .settings-layout .settings-body {
    padding: 24px 16px;
  }
}

/* ===== macOS 无标题栏适配 =====
   左栏顶部预留 40px 红绿灯让位区，内容区头部可拖动窗口 */
.settings-layout .side-top {
  display: none;
}

.platform-mac .settings-layout .side-top {
  display: block;
  height: 56px;
  flex-shrink: 0;
  margin: -16px -12px 0;
  -webkit-app-region: drag;
}

.platform-mac .settings-layout .settings-header {
  -webkit-app-region: drag;
}
</style>
