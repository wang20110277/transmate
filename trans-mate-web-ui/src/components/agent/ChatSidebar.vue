<template>
  <div class="chat-sidebar">
    <div class="sidebar-header">
      <span class="sidebar-title">会话</span>
      <button class="new-chat-btn" @click="$emit('newConversation')" title="新建会话">
        <i class="fas fa-plus"></i>
        <span>新会话</span>
      </button>
    </div>

    <div class="conversation-list">
      <div v-if="conversations.length === 0" class="empty-tip">暂无历史会话</div>
      <div
        v-for="conversation in conversations"
        :key="conversation.id"
        :class="['conversation-item', { active: conversation.id === currentConversationId }]"
        @click="$emit('selectConversation', conversation.id)"
      >
        <i class="fas fa-comment-dots conversation-icon"></i>
        <div class="conversation-info">
          <div class="conversation-title">{{ conversation.title || '新会话' }}</div>
          <div class="conversation-time">{{ formatTime(conversation.updated_at || conversation.created_at) }}</div>
        </div>
        <button
          class="delete-btn"
          title="删除会话"
          @click.stop="$emit('removeConversation', conversation.id)"
        >
          <i class="fas fa-trash-alt"></i>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Conversation } from '@/types'

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
  width: 220px;
  min-width: 220px;
  height: 100%;
  background: #1e293b;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 12px 10px;
}

.sidebar-title {
  font-size: 13px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.75);
  letter-spacing: 1px;
}

.new-chat-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  font-size: 12px;
  color: #fff;
  background: rgba(64, 158, 255, 0.85);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: #409eff;
}

.conversation-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px 12px;
}

.empty-tip {
  padding: 20px 8px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  text-align: center;
}

.conversation-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  margin-bottom: 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.conversation-item:hover {
  background: rgba(255, 255, 255, 0.08);
}

.conversation-item.active {
  background: rgba(64, 158, 255, 0.22);
}

.conversation-icon {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.5);
}

.conversation-info {
  flex: 1;
  min-width: 0;
}

.conversation-title {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-time {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  margin-top: 2px;
}

.delete-btn {
  padding: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.35);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  opacity: 0;
  transition: all 0.2s;
}

.conversation-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  color: #f56c6c;
}
</style>
