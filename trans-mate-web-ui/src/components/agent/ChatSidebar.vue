<template>
  <div class="chat-sidebar">
    <div class="conversation-list">
      <div v-if="conversations.length === 0" class="empty-tip">{{ t('chat.emptyConversations') }}</div>
      <div
        v-for="conversation in conversations"
        :key="conversation.id"
        :class="['conversation-item', { active: conversation.id === currentConversationId }]"
        @click="$emit('selectConversation', conversation.id)"
      >
        <i class="fas fa-comment-dots conversation-icon"></i>
        <div class="conversation-info">
          <div class="conversation-title">{{ conversation.title || t('chat.untitled') }}</div>
          <div class="conversation-time">{{ formatTime(conversation.updated_at || conversation.created_at) }}</div>
        </div>
        <button
          class="delete-btn"
          :title="t('chat.deleteConversation')"
          @click.stop="$emit('removeConversation', conversation.id)"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'
import type { Conversation } from '@/types'

const { t } = useI18n()

defineProps<{
  conversations: Conversation[]
  currentConversationId: number | null
}>()

defineEmits<{
  (e: 'newConversation'): void
  (e: 'selectConversation', id: number): void
  (e: 'removeConversation', id: number): void
}>()

const formatTime = (value?: string): string => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const sameDay = date.toDateString() === now.toDateString()
  const time = `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  return sameDay ? time : `${date.getMonth() + 1}-${date.getDate()} ${time}`
}
</script>

<style scoped>
.chat-sidebar {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 2px 8px;
}

.empty-tip {
  padding: 20px 8px;
  font-size: 12px;
  color: var(--color-text-faint);
  text-align: center;
  line-height: 1.6;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  margin-bottom: 2px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.conversation-item:hover {
  background: var(--color-hover);
}

.conversation-item.active {
  background: var(--color-primary-soft);
}

.conversation-icon {
  font-size: 13px;
  color: var(--color-text-muted);
  flex-shrink: 0;
}

.conversation-item.active .conversation-icon {
  color: var(--color-primary);
}

.conversation-info {
  flex: 1;
  min-width: 0;
}

.conversation-title {
  font-size: 13px;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-item.active .conversation-title {
  color: var(--color-primary);
  font-weight: 500;
}

.conversation-time {
  font-size: 11px;
  color: var(--color-text-faint);
  margin-top: 2px;
}

.delete-btn {
  padding: 4px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
  flex-shrink: 0;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}
</style>
