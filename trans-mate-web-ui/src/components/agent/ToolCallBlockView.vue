<template>
  <div :class="['tool-block', { running: tool.running }]">
    <div class="tool-header" @click="expanded = !expanded">
      <i :class="expanded ? 'fas fa-chevron-down' : 'fas fa-chevron-right'" class="chevron"></i>
      <i class="fas fa-toolbox tool-icon"></i>
      <span class="tool-name">{{ tool.name }}</span>
      <span v-if="tool.running" class="tool-status running-status">
        <span class="mini-spinner"></span>
        运行中
      </span>
      <span v-else class="tool-status done-status">
        <i class="fas fa-check"></i>
        完成
      </span>
    </div>
    <div v-if="expanded" class="tool-body">
      <div v-if="argsText" class="tool-section">
        <div class="section-label">参数</div>
        <pre class="section-content">{{ argsText }}</pre>
      </div>
      <div v-if="tool.result" class="tool-section">
        <div class="section-label">结果</div>
        <pre class="section-content">{{ tool.result }}</pre>
      </div>
      <div v-if="!argsText && !tool.result && tool.running" class="tool-section">
        <div class="section-label">正在等待工具执行...</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCallBlock } from '@/types'

const props = defineProps<{ tool: ToolCallBlock }>()

const expanded = ref(false)

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
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.18);
  overflow: hidden;
}

.tool-block.running {
  border-color: rgba(64, 158, 255, 0.5);
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
  background: rgba(255, 255, 255, 0.05);
}

.chevron {
  font-size: 10px;
  color: rgba(255, 255, 255, 0.45);
}

.tool-icon {
  font-size: 12px;
  color: #e6a23c;
}

.tool-name {
  flex: 1;
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  color: rgba(255, 255, 255, 0.85);
}

.tool-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
}

.done-status {
  color: #67c23a;
}

.running-status {
  color: #409eff;
}

.mini-spinner {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid rgba(64, 158, 255, 0.3);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.tool-body {
  padding: 8px 12px 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.tool-section {
  margin-bottom: 8px;
}

.tool-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.4);
  margin-bottom: 4px;
}

.section-content {
  margin: 0;
  padding: 8px 10px;
  max-height: 220px;
  overflow: auto;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.35);
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
