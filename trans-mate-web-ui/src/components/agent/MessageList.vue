<template>
  <div class="message-list" ref="listContainer">
    <template v-for="(message, index) in messages" :key="index">
      <div :class="['message', 'role-' + (message.role || 'system')]">
        <!-- 任务计划面板（deep agent todos） -->
        <TodoPanel
          v-if="message.role === 'assistant' && message.todos && message.todos.length"
          :todos="message.todos"
        />

        <!-- 子智能体运行徽标 -->
        <div v-if="message.activeSubagent" class="subagent-badge">
          <span class="mini-spinner"></span>
          <span>{{ t('chat.subagentWorking', { agent: message.activeSubagent }) }}</span>
        </div>

        <!-- 工具调用块（ZCode 式折叠面板） -->
        <div v-if="message.toolCalls && message.toolCalls.length" class="tool-blocks">
          <ToolCallBlockView
            v-for="tool in message.toolCalls"
            :key="tool.id"
            :tool="tool"
          />
        </div>

        <div
          v-if="message.content"
          :class="['message-content', { collapsed: message.role === 'assistant' && collapsedSet.has(index) }]"
        >
          <template v-if="message.role === 'assistant'">
            <div class="markdown-body" v-html="renderMarkdown(message.content)"></div>
            <span v-if="message.streaming" class="streaming-cursor"></span>
          </template>
          <template v-else>{{ message.content }}</template>
        </div>

        <!-- AI 回复操作：朗读 / 收起 -->
        <div
          v-if="message.role === 'assistant' && !message.streaming && message.content"
          class="msg-actions"
        >
          <button
            :class="['msg-action-btn', { speaking: speakingIndex === index }]"
            :disabled="ttsMuted"
            :title="ttsMuted ? t('chat.speakMuted') : (speakingIndex === index ? t('chat.stopSpeak') : t('chat.speak'))"
            @click="emit('toggleSpeak', index)"
          >
            <i :class="speakingIndex === index ? 'fas fa-stop' : 'fas fa-volume-up'"></i>
          </button>
          <button
            v-if="isLongMessage(message)"
            class="msg-action-btn collapse-btn"
            @click="toggleCollapse(index)"
          >
            <span>{{ collapsedSet.has(index) ? t('chat.expand') : t('chat.collapse') }}</span>
            <i :class="collapsedSet.has(index) ? 'fas fa-chevron-down' : 'fas fa-chevron-up'"></i>
          </button>
        </div>

        <!-- 思考中状态（最后一条用户消息后） -->
        <div
          v-if="message.role === 'user' && isProcessing && index === messages.length - 1"
          class="processing-indicator"
        >
          <div class="processing-content">
            <div class="dots">
              <span></span><span></span><span></span>
            </div>
            <span class="processing-text">{{ processingStatus || t('chat.thinking') }}</span>
          </div>
        </div>

        <!-- 正在等待工具结果且暂无文本 -->
        <div
          v-else-if="message.role === 'assistant' && message.streaming && !message.content && hasRunningTools(message)"
          class="processing-indicator"
        >
          <div class="processing-content">
            <div class="dots">
              <span></span><span></span><span></span>
            </div>
            <span class="processing-text">{{ t('chat.runningTools') }}</span>
          </div>
        </div>

        <div v-if="message.timestamp && !message.streaming" class="timestamp">
          {{ formatTime(message.timestamp) }}
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import 'highlight.js/styles/github.css'
import ToolCallBlockView from './ToolCallBlockView.vue'
import TodoPanel from './TodoPanel.vue'
import { formatTime } from '@/utils/time-utils'
import { useI18n } from '@/i18n'
import type { Message } from '@/types'

const { t } = useI18n()

const props = defineProps<{
  messages: Message[]
  isProcessing: boolean
  processingStatus: string
  speakingIndex: number | null
  ttsMuted?: boolean
}>()

const emit = defineEmits<{
  (e: 'toggleSpeak', index: number): void
}>()

const listContainer = ref<HTMLDivElement | null>(null)

// 长回复折叠状态（按消息索引记录）
const collapsedSet = ref(new Set<number>())

const toggleCollapse = (index: number) => {
  const next = new Set(collapsedSet.value)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  collapsedSet.value = next
}

const isLongMessage = (message: Message) => {
  const content = message.content || ''
  return content.length > 280 || content.split('\n').length > 8
}

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch {
        /* 降级为普通代码块 */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`
  }
})

const renderMarkdown = (content: string): string => {
  try {
    return md.render(content || '')
  } catch {
    return md.utils.escapeHtml(content || '')
  }
}

const hasRunningTools = (message: Message): boolean => {
  return (message.toolCalls || []).some((tool) => tool.running)
}

const scrollToBottom = () => {
  nextTick(() => {
    // 滚动容器是父级 .main-body，本组件只占位居中列
    const el = listContainer.value
    if (!el) return
    const scroller = el.closest('.main-body') as HTMLElement | null
    if (scroller) scroller.scrollTop = scroller.scrollHeight
  })
}

watch(
  () => props.messages.map((message) => message.content || '').join(''),
  scrollToBottom
)
watch(() => props.messages.length, scrollToBottom)
watch(() => props.isProcessing, scrollToBottom)
onMounted(scrollToBottom)
</script>

<style scoped>
/* 滚动由父容器 .main-body 完成，这里只负责居中列布局 */
.message-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
  max-width: 860px;
  margin: 0 auto;
  padding: 16px 24px 8px;
  box-sizing: border-box;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 88%;
}

.role-user {
  align-self: flex-end;
  align-items: flex-end;
}

.role-assistant,
.role-system {
  align-self: flex-start;
  align-items: flex-start;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.65;
  word-break: break-word;
}

.role-user .message-content {
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #fff;
  border-bottom-right-radius: 4px;
}

.role-assistant .message-content {
  background: var(--color-fill);
  color: var(--color-text);
  border-bottom-left-radius: 4px;
}

.role-system .message-content {
  background: var(--color-danger-soft);
  color: var(--color-danger-deep);
  font-size: 13px;
}

.timestamp {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-text-faint);
}

/* AI 回复操作行：朗读 / 收起 */
.msg-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
}

.msg-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.msg-action-btn:hover {
  color: var(--color-text);
  background: var(--color-fill);
}

/* 全局静音时朗读按钮禁用置灰 */
.msg-action-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  background: transparent;
}

.msg-action-btn.speaking {
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

/* 折叠态：内容截断并底部渐隐 */
.message-content.collapsed .markdown-body {
  max-height: 108px;
  overflow: hidden;
  -webkit-mask-image: linear-gradient(180deg, #000 55%, transparent);
  mask-image: linear-gradient(180deg, #000 55%, transparent);
}

/* markdown 渲染样式 */
.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 2px 0;
}

.markdown-body :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--color-fill-strong);
  color: var(--color-text);
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow-x: auto;
  background: var(--color-soft-bg);
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
}

.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 13px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--color-border);
  padding: 5px 10px;
}

.markdown-body :deep(th) {
  background: var(--color-soft-bg);
}

.markdown-body :deep(a) {
  color: var(--color-primary);
}

.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid rgba(37, 99, 235, 0.45);
  color: var(--color-text-muted);
}

/* 流式光标 */
.streaming-cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  margin-left: 2px;
  vertical-align: -2px;
  background: #2563eb;
  border-radius: 1px;
  animation: cursor-blink 0.9s steps(2) infinite;
}

@keyframes cursor-blink {
  0% { opacity: 1; }
  50% { opacity: 0; }
  100% { opacity: 1; }
}

/* 思考中动画 */
.processing-indicator {
  margin-top: 6px;
}

.processing-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dots {
  display: flex;
  gap: 4px;
}

.dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #2563eb;
  animation: dot-bounce 1.2s infinite ease-in-out;
}

.dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes dot-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
  30% { transform: translateY(-5px); opacity: 1; }
}

.processing-text {
  font-size: 12px;
  color: var(--color-text-muted);
}

/* 子智能体运行徽标 */
.subagent-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 12px;
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
</style>
