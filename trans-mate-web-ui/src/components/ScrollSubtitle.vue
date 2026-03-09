<template>
  <div class="subtitle-wrapper" v-if="visible">
    <div class="subtitle-track" :style="trackStyle" @animationend="onAnimationEnd">
      <span class="subtitle-text">{{ displayText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'

interface Props {
  text?: string
}

const props = withDefaults(defineProps<Props>(), {
  text: ''
})

const emit = defineEmits<{
  (e: 'complete'): void
}>()

const visible = ref(false)

const displayText = computed(() => props.text)

// 根据文本长度计算动画时长，保持恒定速度（每秒约30px）
const trackStyle = computed(() => {
  const textLength = props.text?.length || 0
  // 基础距离600px + 每字符约16px，除以速度30px/s
  const duration = Math.max(30, (600 + textLength * 16) / 30)
  return {
    animationDuration: `${duration}s`
  }
})

function onAnimationEnd() {
  visible.value = false
  emit('complete')
}

// 监听 text 变化，当有新文本时显示字幕
watch(() => props.text, (newText) => {
  if (newText && newText.trim()) {
    visible.value = true
  }
}, { immediate: true })
</script>

<style scoped>
.subtitle-wrapper {
  width: 100%;
  max-width: 600px;
  height: 36px;
  overflow: hidden;
  position: relative;
  background: rgba(0, 0, 0, 0.75);
  border-radius: 18px;
  backdrop-filter: blur(10px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.subtitle-track {
  position: absolute;
  right: 0;
  top: 0;
  height: 100%;
  display: flex;
  align-items: center;
  white-space: nowrap;
  padding: 0 20px;
  animation-name: scroll-left;
  animation-timing-function: linear;
  animation-fill-mode: forwards;
}

.subtitle-text {
  color: #ffffff;
  font-size: 16px;
  font-weight: 500;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}

@keyframes scroll-left {
  0% {
    transform: translateX(100%);
  }
  100% {
    transform: translateX(calc(-100% - 600px));
  }
}

@media (max-width: 768px) {
  .subtitle-wrapper {
    height: 32px;
    border-radius: 16px;
  }
  
  .subtitle-text {
    font-size: 14px;
  }
  
  .subtitle-track {
    padding: 0 16px;
  }
}
</style>
