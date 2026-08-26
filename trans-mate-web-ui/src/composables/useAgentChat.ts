import { ref, onUnmounted, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { AgentEvent, Conversation, Message, ToolCallBlock } from '@/types'
import { t } from '@/i18n'
import {
  listConversations,
  createConversation,
  deleteConversation as apiDeleteConversation,
  listConversationMessages
} from '@/services/api'

interface UseAgentChatOptions {
  userId: MaybeRefOrGetter<string>
  /** 一条回复完成（含停止/出错前已生成内容）后的回调，用于语音播报等 */
  onReplyComplete?: (content: string) => void
}

/**
 * ZCode 式智能体聊天 composable：
 * 管理 WebSocket 事件流（流式 token / 工具调用块）、多会话切换与发送/停止。
 */
export function useAgentChat(options: UseAgentChatOptions) {
  const { userId } = options

  const dialogue = ref<Message[]>([])
  const conversations = ref<Conversation[]>([])
  const currentConversationId = ref<number | null>(null)
  const isConnected = ref(false)
  const isProcessing = ref(false)
  const processingStatus = ref('')
  const connectionStatus = ref<'connected' | 'disconnected' | 'connecting'>('disconnected')

  const socket = ref<WebSocket | null>(null)
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false

  /** 确保存在一条流式输出中的 assistant 消息，返回其下标 */
  const ensureAssistantMessage = (): number => {
    const last = dialogue.value[dialogue.value.length - 1]
    if (last && last.role === 'assistant' && last.streaming) {
      return dialogue.value.length - 1
    }
    dialogue.value.push({
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      streaming: true,
      toolCalls: []
    })
    return dialogue.value.length - 1
  }

  const finalizeAssistant = () => {
    const last = dialogue.value[dialogue.value.length - 1]
    if (last && last.role === 'assistant' && last.streaming) {
      last.streaming = false
    }
    isProcessing.value = false
    processingStatus.value = ''
    const content = last?.content || ''
    if (content) options.onReplyComplete?.(content)
  }

  const handleAgentEvent = (event: AgentEvent) => {
    switch (event.type) {
      case 'status':
        processingStatus.value = event.message
        break
      case 'agent_start': {
        const index = ensureAssistantMessage()
        dialogue.value[index].agent = event.agent
        processingStatus.value = t('chat.agentWorking', { agent: event.agent })
        break
      }
      case 'token': {
        const index = ensureAssistantMessage()
        dialogue.value[index].content = (dialogue.value[index].content || '') + event.content
        processingStatus.value = ''
        break
      }
      case 'tool_call': {
        const index = ensureAssistantMessage()
        const calls = dialogue.value[index].toolCalls || (dialogue.value[index].toolCalls = [])
        calls.push({
          id: event.id,
          name: event.name,
          args: event.args,
          running: true
        })
        break
      }
      case 'tool_result': {
        const last = dialogue.value[dialogue.value.length - 1]
        const block = last?.toolCalls?.find((tool) => tool.id === event.id)
        if (block) {
          block.running = false
          block.result = event.result
        }
        break
      }
      case 'plan_update': {
        const index = ensureAssistantMessage()
        dialogue.value[index].todos = event.todos
        break
      }
      case 'subagent_start': {
        const index = ensureAssistantMessage()
        dialogue.value[index].activeSubagent = event.name
        processingStatus.value = t('chat.subagentWorking', { agent: event.name })
        break
      }
      case 'subagent_end': {
        const last = dialogue.value[dialogue.value.length - 1]
        if (last?.role === 'assistant') last.activeSubagent = undefined
        break
      }
      case 'conversation_created':
        currentConversationId.value = event.conversation_id
        break
      case 'done': {
        const index = ensureAssistantMessage()
        dialogue.value[index].content = event.content
        if (event.tool_events) {
          dialogue.value[index].toolCalls = event.tool_events.map((tool) => ({
            ...tool,
            running: false
          }))
        }
        finalizeAssistant()
        refreshConversations()
        break
      }
      case 'stopped':
        finalizeAssistant()
        break
      case 'error':
        dialogue.value.push({
          role: 'system',
          content: event.message,
          timestamp: Date.now()
        })
        finalizeAssistant()
        break
    }
  }

  const connect = () => {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) return
    intentionalClose = false
    connectionStatus.value = 'connecting'
    const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://'
    // 浏览器环境用当前域名（走 vite 代理）；Electron file:// 环境 host 为空，回退到直连后端
    const host = window.location.host
      || `${import.meta.env.VITE_WS_HOST || 'localhost'}:${import.meta.env.VITE_WS_PORT || '8000'}`
    const wsUrl = `${protocol}${host}/ws?user_id=${encodeURIComponent(toValue(userId))}`
    socket.value = new WebSocket(wsUrl)
    socket.value.onopen = () => {
      isConnected.value = true
      connectionStatus.value = 'connected'
    }
    socket.value.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string)
        handleAgentEvent(parsed as AgentEvent)
      } catch {
        // 兼容纯文本回复
        handleAgentEvent({ type: 'token', content: String(event.data) })
        handleAgentEvent({ type: 'done', content: String(event.data) })
      }
    }
    socket.value.onclose = () => {
      isConnected.value = false
      connectionStatus.value = 'disconnected'
      if (!intentionalClose) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }
    socket.value.onerror = () => {
      connectionStatus.value = 'disconnected'
    }
  }

  const disconnect = () => {
    intentionalClose = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    socket.value?.close()
    socket.value = null
    isConnected.value = false
  }

  const sendMessage = (text: string): boolean => {
    const message = text.trim()
    if (!message) return false
    if (!socket.value || socket.value.readyState !== WebSocket.OPEN) return false
    dialogue.value.push({ role: 'user', content: message, timestamp: Date.now() })
    isProcessing.value = true
    processingStatus.value = t('chat.thinking')
    socket.value.send(
      JSON.stringify({
        type: 'chat_message',
        message,
        conversation_id: currentConversationId.value,
        user_id: toValue(userId),
        timestamp: Date.now()
      })
    )
    return true
  }

  const stopGeneration = () => {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify({ type: 'stop' }))
    }
  }

  const refreshConversations = async () => {
    try {
      const response = await listConversations(toValue(userId))
      conversations.value = response.data
    } catch (err) {
      console.error('获取会话列表失败:', err)
    }
  }

  const parseToolEvents = (raw?: string | null): ToolCallBlock[] => {
    if (!raw) return []
    try {
      const parsed = JSON.parse(raw)
      return Array.isArray(parsed)
        ? parsed.map((tool) => ({ ...tool, running: false }))
        : []
    } catch {
      return []
    }
  }

  const selectConversation = async (conversationId: number) => {
    if (isProcessing.value) stopGeneration()
    currentConversationId.value = conversationId
    try {
      const response = await listConversationMessages(conversationId)
      dialogue.value = response.data.map((message) => ({
        role: message.role,
        content: message.content,
        timestamp: message.created_at ? new Date(message.created_at).getTime() : Date.now(),
        toolCalls: parseToolEvents(message.tool_events)
      }))
    } catch (err) {
      console.error('加载会话消息失败:', err)
      dialogue.value = []
    }
  }

  const newConversation = () => {
    if (isProcessing.value) stopGeneration()
    currentConversationId.value = null
    dialogue.value = []
  }

  const removeConversation = async (conversationId: number) => {
    try {
      await apiDeleteConversation(conversationId)
      if (currentConversationId.value === conversationId) {
        newConversation()
      }
      await refreshConversations()
    } catch (err) {
      console.error('删除会话失败:', err)
    }
  }

  const createNewConversation = async (): Promise<Conversation | null> => {
    try {
      const response = await createConversation(toValue(userId))
      await refreshConversations()
      return response.data
    } catch (err) {
      console.error('创建会话失败:', err)
      return null
    }
  }

  onUnmounted(disconnect)

  return {
    dialogue,
    conversations,
    currentConversationId,
    isConnected,
    isProcessing,
    processingStatus,
    connectionStatus,
    connect,
    disconnect,
    sendMessage,
    stopGeneration,
    refreshConversations,
    selectConversation,
    newConversation,
    removeConversation,
    createNewConversation
  }
}
