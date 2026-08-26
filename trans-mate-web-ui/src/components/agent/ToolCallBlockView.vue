<template>
  <div :class="['tool-block', { running: tool.running }]">
    <div class="tool-header" @click="expanded = !expanded">
      <i :class="expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-right'" class="chevron"></i>
      <i class="fas fa-toolbox tool-icon"></i>
      <span class="tool-name">{{ displayName }}</span>
      <span v-if="tool.running" class="tool-status running-status">
        <span class="mini-spinner"></span>
        {{ t('chat.toolRunning') }}
      </span>
      <span v-else class="tool-status done-status">
        <i class="fas fa-check"></i>
        {{ t('chat.toolDone') }}
      </span>
    </div>
    <div v-if="expanded" class="tool-body">
      <div v-if="argsText" class="tool-section">
        <div class="section-label">{{ t('chat.toolArgs') }}</div>
        <pre class="section-content">{{ argsText }}</pre>
      </div>
      <div v-if="tool.result" class="tool-section">
        <div class="section-label">{{ t('chat.toolResult') }}</div>
        <pre class="section-content">{{ tool.result }}</pre>
      </div>
      <div v-if="!argsText && !tool.result && tool.running" class="tool-section">
        <div class="section-label">{{ t('chat.toolWaiting') }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from '@/i18n'
import type { ToolCallBlock } from '@/types'

const { t } = useI18n()

const props = defineProps<{ tool: ToolCallBlock }>()

const expanded = ref(false)

// 内置工具显示友好名（write_todos/task 已有专用 UI，避免暴露内部工具名）
const displayName = computed(() => {
  const map: Record<string, string> = {
    write_todos: t('chat.toolNameTodos'),
    task: t('chat.toolNameTask')
  }
  return map[props.tool.name] || props.tool.name
})

const argsText = computed(() => {
  const args = props.tool.args
  if (args === undefined || args === null) return ''
  if (typeof args === 'string') return args
  try {
    return JSON.stringify(args, null, 2)
  } catch {
    return String(args)
  }
})
</script>

<style scoped>
.tool-block {
  width: 100%;
  margin-bottom: 8px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-soft-bg);
  overflow: hidden;
}

.tool-block.running {
  border-color: rgba(37, 99, 235, 0.45);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.2s;
}

.tool-header:hover {
  background: var(--color-hover);
}

.chevron {
  font-size: 10px;
  color: var(--color-text-muted);
}

.tool-icon {
  font-size: 12px;
  color: #e6a23c;
}

.tool-name {
  flex: 1;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  color: var(--color-text);
}

.tool-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

.done-status {
  color: var(--color-success);
}

.running-status {
  color: var(--color-primary);
}

.mini-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(37, 99, 235, 0.25);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tool-body {
  padding: 8px 12px 10px;
  border-top: 1px solid var(--color-border);
}

.tool-section {
  margin-bottom: 8px;
}

.tool-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-bottom: 4px;
}

.section-content {
  margin: 0;
  padding: 8px 10px;
  max-height: 220px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: 12px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
