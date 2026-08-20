<template>
  <div :class="['chat-input-card', { recording: isRecording }]">
    <div v-if="isRecording || isTranscribing" class="voice-state">
      <template v-if="isRecording">
        <span class="waveform" aria-hidden="true">
          <i></i><i></i><i></i><i></i><i></i>
        </span>
        <span class="voice-text">{{ t('chat.listening') }}</span>
      </template>
      <template v-else>
        <span class="mini-spinner"></span>
        <span class="voice-text">{{ t('chat.transcribing') }}</span>
      </template>
    </div>

    <textarea
      v-show="!isRecording && !isTranscribing"
      ref="textareaRef"
      class="text-input"
      rows="1"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      autocomplete="off"
      @input="onInput"
      @keydown.enter.exact.prevent="$emit('send')"
    ></textarea>

    <div class="action-row">
      <button
        :class="['action-btn', 'mic', { recording: isRecording, transcribing: isTranscribing }]"
        :disabled="disabled"
        :title="micTitle"
        @click="$emit('toggleRecording')"
      >
        <span v-if="isTranscribing" class="mini-spinner"></span>
        <i v-else :class="isRecording ? 'fas fa-stop' : 'fas fa-microphone'"></i>
      </button>

      <button
        v-if="!isProcessing"
        class="action-btn send"
        :disabled="disabled || !modelValue.trim()"
        :title="t('chat.send')"
        @click="$emit('send')"
      >
        <i class="fas fa-arrow-up"></i>
      </button>
      <button v-else class="action-btn stop" :title="t('chat.stopGenerate')" @click="$emit('stop')">
        <i class="fas fa-stop"></i>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed } from 'vue'
import { useI18n } from '@/i18n'

const { t } = useI18n()

const props = defineProps<{
  modelValue: string
  isProcessing: boolean
  isRecording: boolean
  isTranscribing?: boolean
  disabled: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'send'): void
  (e: 'stop'): void
  (e: 'toggleRecording'): void
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const micTitle = computed(() => {
  if (props.isTranscribing) return t('chat.micTranscribing')
  return props.isRecording ? t('chat.micStop') : t('chat.micTitle')
})

// 自动增高，最高 160px 后内部滚动
const adjustHeight = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

const onInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  nextTick(adjustHeight)
}

watch(() => props.modelValue, () => nextTick(adjustHeight))
onMounted(adjustHeight)
</script>

<style scoped>
.chat-input-card {
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
  padding: 12px 14px 10px;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.chat-input-card:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.1);
}

.chat-input-card.recording {
  border-color: var(--color-danger);
  box-shadow: 0 4px 16px rgba(245, 63, 63, 0.1);
}

/* 录音/转写状态条 */
.voice-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 44px;
}

.voice-text {
  font-size: 13px;
  color: var(--color-text-muted);
}

.waveform {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 18px;
}

.waveform i {
  width: 3px;
  height: 100%;
  border-radius: 2px;
  background: var(--color-danger);
  animation: wave 1s ease-in-out infinite;
}

.waveform i:nth-child(1) { animation-delay: 0s; }
.waveform i:nth-child(2) { animation-delay: 0.15s; }
.waveform i:nth-child(3) { animation-delay: 0.3s; }
.waveform i:nth-child(4) { animation-delay: 0.15s; }
.waveform i:nth-child(5) { animation-delay: 0s; }

@keyframes wave {
  0%, 100% { transform: scaleY(0.3); }
  50% { transform: scaleY(1); }
}

.text-input {
  width: 100%;
  padding: 0 2px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.6;
  color: var(--color-text);
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  max-height: 160px;
  box-sizing: border-box;
}

.text-input::placeholder {
  color: var(--color-text-faint);
}

.text-input:disabled {
  opacity: 0.6;
}

/* 底部操作行 */
.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  font-size: 14px;
  color: var(--color-text-secondary);
  background: var(--color-fill);
  border: none;
  border-radius: 10px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: var(--color-border);
}

.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.action-btn:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.action-btn.send {
  color: #ffffff;
  background: var(--color-primary);
}

.action-btn.send:hover:not(:disabled) {
  background: var(--color-primary-deep);
}

.action-btn.stop {
  color: #ffffff;
  background: var(--color-danger);
}

.action-btn.stop:hover {
  background: var(--color-danger-deep);
}

.action-btn.mic {
  font-size: 15px;
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.action-btn.mic:hover:not(:disabled) {
  background: var(--color-primary-soft-strong);
}

.action-btn.mic.recording {
  color: var(--color-danger);
  background: var(--color-danger-soft);
  animation: mic-pulse 1.2s infinite;
}

.action-btn.mic.transcribing {
  color: var(--color-primary);
}

.mini-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(37, 99, 235, 0.25);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: mic-spin 0.8s linear infinite;
}

@keyframes mic-spin {
  to { transform: rotate(360deg); }
}

@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 63, 63, 0.3); }
  50% { box-shadow: 0 0 0 7px rgba(245, 63, 63, 0); }
}

@media (prefers-reduced-motion: reduce) {
  .waveform i,
  .action-btn.mic.recording,
  .mini-spinner {
    animation: none;
  }
}
</style>
