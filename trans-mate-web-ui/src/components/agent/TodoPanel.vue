<template>
  <div class="todo-panel">
    <div class="todo-title">
      <i class="fas fa-list-check"></i>
      <span>{{ t('chat.planTitle') }}</span>
    </div>
    <div
      v-for="(todo, index) in todos"
      :key="index"
      :class="['todo-item', `status-${todo.status}`]"
    >
      <span class="todo-icon">
        <i v-if="todo.status === 'completed'" class="fas fa-check-circle"></i>
        <i v-else-if="todo.status === 'in_progress'" class="fas fa-circle-half-stroke"></i>
        <i v-else class="fas fa-circle-dot"></i>
      </span>
      <span class="todo-content">{{ todo.content }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from '@/i18n'
import type { TodoItem } from '@/types'

const { t } = useI18n()

defineProps<{ todos: TodoItem[] }>()
</script>

<style scoped>
.todo-panel {
  width: 100%;
  margin-bottom: 8px;
  padding: 8px 12px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-soft-bg);
  box-sizing: border-box;
}

.todo-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 0;
  font-size: 13px;
  color: var(--color-text);
}

.todo-item.status-completed {
  color: var(--color-text-faint);
  text-decoration: line-through;
}

.todo-item.status-pending .todo-icon {
  color: var(--color-text-faint);
}

.todo-item.status-in_progress .todo-icon {
  color: var(--color-primary);
}

.todo-item.status-completed .todo-icon {
  color: var(--color-success);
}

.todo-content {
  flex: 1;
  line-height: 1.5;
}
</style>
