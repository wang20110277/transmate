<template>
  <div class="message-list" ref="listContainer">
    <div v-if="messages.length === 0" class="message role-assistant welcome-msg">
      <div class="message-content">你好，我是阿雅，您的专属智能助手。我可以调用工具为您查询天气、搜索网络、检索知识库和查询股票行情，有什么可以帮助您？</div>
    </div>

    <template v-for="(message, index) in messages" :key="index">
      <div :class="['message', 'role-' + (message.role || 'system')]">
        <!-- 工具调用块（ZCode 式折叠面板） -->
        <div v-if="message.toolCalls && message.toolCalls.length" class="tool-blocks">
          <ToolCallBlockView
            v-for="tool in message.toolCalls"
            :key="tool.id"
            :tool="tool"
          />
        </div>

        <div v-if="message.content" class="message-content">
          <template v-if="message.role === 'assistant'">
            <div class="markdown-body" v-html="renderMarkdown(message.content)"></div>
            <span v-if="message.streaming" class="streaming-cursor"></span>
          </template>
          <template v-else>{{ message.content }}</template>
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
            <span class="processing-text">{{ processingStatus || '正在思考中...' }}</span>
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
            <span class="processing-text">正在执行工具...</span>
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
import 'highlight.js/styles/github-dark.css'
import ToolCallBlockView from './ToolCallBlockView.vue'
import { formatTime } from '@/utils/time-utils'
import type { Message } from '@/types'

const props = defineProps<{
  messages: Message[]
  isProcessing: boolean
  processingStatus: string
}>()

const listContainer = ref<HTMLDivElement | null>(null)

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
    if (listContainer.value) listContainer.value.scrollTop = listContainer.value.scrollHeight
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
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.welcome-msg .message-content {
  background: rgba(255, 255, 255, 0.06);
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 92%;
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
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.92);
  border-bottom-left-radius: 4px;
}

.role-system .message-content {
  background: rgba(245, 108, 108, 0.15);
  color: #f89898;
  font-size: 13px;
}

.timestamp {
  margin-top: 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.3);
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
  background: rgba(0, 0, 0, 0.35);
  font-size: 13px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
}

.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  border-radius: 8px;
  overflow-x: auto;
  background: rgba(0, 0, 0, 0.4);
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
  border: 1px solid rgba(255, 255, 255, 0.15);
  padding: 5px 10px;
}

.markdown-body :deep(a) {
  color: #79bbff;
}

.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid rgba(64, 158, 255, 0.5);
  color: rgba(255, 255, 255, 0.65);
}

/* 流式光标 */
.streaming-cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  margin-left: 2px;
  vertical-align: -2px;
  background: #409eff;
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
  background: #409eff;
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
  color: rgba(255, 255, 255, 0.55);
}
</style>
