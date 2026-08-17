<template>
  <div class="chat-input">
    <div class="input-pill">
      <i class="fas fa-comment-dots input-icon"></i>
      <input
        type="text"
        class="text-input"
        :value="modelValue"
        placeholder="请输入您的问题..."
        @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        @keyup.enter="$emit('send')"
        autocomplete="off"
        :disabled="disabled"
      />
    </div>
    <button
      :class="['action-round', 'mic', { recording: isRecording, transcribing: isTranscribing }]"
      @click="$emit('toggleRecording')"
      :disabled="disabled"
      :title="isTranscribing ? '语音转写中...' : (isRecording ? '停止录音并转写' : '语音输入')"
    >
      <span v-if="isTranscribing" class="mic-spinner"></span>
      <i v-else :class="isRecording ? 'fas fa-stop' : 'fas fa-microphone'"></i>
    </button>
    <button v-if="!isProcessing" class="action-round send" @click="$emit('send')" :disabled="disabled" title="发送">
      <i class="fas fa-paper-plane"></i>
    </button>
    <button v-else class="action-round stop" @click="$emit('stop')" title="停止生成">
      <i class="fas fa-stop"></i>
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: string
  isProcessing: boolean
  isRecording: boolean
  isTranscribing?: boolean
  disabled: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'toggleRecording'): void
}>()
</script>

<style scoped>
.chat-input {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.input-pill {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  transition: border-color 0.2s;
}

.input-pill:focus-within {
  border-color: #3b82f6;
}

.input-icon {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.4);
}

.text-input {
  flex: 1;
  padding: 11px 0;
  font-size: 14px;
  color: #fff;
  background: transparent;
  border: none;
  outline: none;
}

.text-input::placeholder {
  color: rgba(255, 255, 255, 0.35);
}

.text-input:disabled {
  opacity: 0.6;
}

.action-round {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  font-size: 15px;
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  transition: transform 0.15s, opacity 0.2s;
}

.action-round:hover:not(:disabled) {
  transform: scale(1.06);
}

.action-round:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-round.send {
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border: none;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4);
}

.action-round.stop {
  background: linear-gradient(135deg, #dc2626, #ef4444);
  border: none;
  box-shadow: 0 4px 14px rgba(220, 38, 38, 0.4);
}

.action-round.mic.recording {
  color: #ef4444;
  border-color: #ef4444;
  animation: mic-pulse 1.2s infinite;
}

.action-round.mic.transcribing {
  color: #60a5fa;
  border-color: #60a5fa;
}

.mic-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(96, 165, 250, 0.3);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: mic-spin 0.8s linear infinite;
}

@keyframes mic-spin {
  to { transform: rotate(360deg); }
}

@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.35); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}
</style>
