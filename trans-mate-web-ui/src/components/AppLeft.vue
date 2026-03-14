<template>
  <div class="side-panel left-panel" :class="{ collapsed: collapsed }">
    <button class="panel-toggle" @click="toggleCollapse">
      <span class="toggle-icon">{{ collapsed ? '›' : '‹' }}</span>
    </button>
    <div class="panel-content" v-show="!collapsed">
      <div class="panel-section knowledge-section">
        <div class="section-header">
          <span class="section-icon">📚</span>
          <span class="section-title">知识</span>
        </div>
        <div class="section-content">
          <div class="empty-placeholder">知识库内容</div>
        </div>
      </div>
      <div class="panel-section memory-section">
        <div class="section-header">
          <span class="section-icon">🧠</span>
          <span class="section-title">记忆</span>
        </div>
        <div class="section-content">
          <div class="empty-placeholder">记忆内容</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:collapsed', value: boolean): void;
}>();

const toggleCollapse = () => {
  emit('update:collapsed', !props.collapsed);
};
</script>

<style scoped>
.side-panel {
  display: flex;
  flex-direction: column;
  background: var(--color-surface, #ffffff);
  border-radius: 16px;
  border: 1px solid var(--color-border, #e2e8f0);
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transition: width 0.3s ease, min-width 0.3s ease;
  overflow: hidden;
  position: relative;
}

.side-panel.left-panel {
  width: 280px;
  min-width: 280px;
}

.side-panel.collapsed {
  width: 48px;
  min-width: 48px;
}

.panel-toggle {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: var(--color-bg, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10;
  transition: background 0.2s ease;
}

.panel-toggle:hover {
  background: var(--color-bg-chat, #f1f5f9);
}

.left-panel .panel-toggle {
  right: -12px;
}

.toggle-icon {
  font-size: 14px;
  color: var(--color-text-muted, #64748b);
}

.panel-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding: 0.75rem;
  gap: 0.75rem;
}

.panel-section {
  display: flex;
  flex-direction: column;
  background: var(--color-bg, #f8fafc);
  border-radius: 12px;
  overflow: hidden;
  flex: 1;
  min-height: 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: var(--color-surface, #ffffff);
  border-bottom: 1px solid var(--color-border, #e2e8f0);
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--color-text, #1e293b);
}

.section-icon {
  font-size: 1rem;
}

.section-title {
  letter-spacing: 0.025em;
}

.section-content {
  flex: 1;
  padding: 0.75rem;
  overflow-y: auto;
}

.empty-placeholder {
  color: var(--color-text-muted, #64748b);
  font-size: 0.8125rem;
  text-align: center;
  padding: 1rem;
}

@media (max-width: 1200px) {
  .side-panel.left-panel {
    width: 240px !important;
    min-width: 240px !important;
  }
  .side-panel.collapsed {
    width: 48px !important;
    min-width: 48px !important;
  }
}

@media (max-width: 900px) {
  .side-panel.left-panel {
    width: 100% !important;
    min-width: 100% !important;
    max-height: 200px;
  }
  .side-panel.collapsed {
    width: 48px !important;
    min-width: 48px !important;
    max-height: 48px;
  }
  .left-panel .panel-toggle {
    top: auto;
    bottom: -12px;
    transform: none;
    width: 48px;
    height: 24px;
  }
}
</style>
