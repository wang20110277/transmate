<template>
  <div class="home-layout">
    <div class="main-container">
      <!-- 最左：图标功能栏（含原头部内容） -->
      <div class="icon-rail">
        <div class="rail-top">
          <span class="rail-logo">
            <img src="/icons/logo.svg" alt="logo" class="rail-logo-img">
          </span>
        </div>
        <div class="rail-actions">
          <button class="rail-btn" title="新会话" @click="newConversation">
            <i class="fas fa-plus"></i>
          </button>
          <button
            :class="['rail-btn', { active: showConversations }]"
            title="历史会话"
            @click="showConversations = !showConversations"
          >
            <i class="fas fa-history"></i>
          </button>
        </div>
        <div class="rail-bottom">
          <button class="rail-btn" title="主页" @click="goHome">
            <i class="fas fa-home"></i>
          </button>
          <button class="rail-btn rail-avatar" title="个人中心" @click="goSettings">
            <i class="fas fa-user"></i>
          </button>
        </div>
      </div>

      <!-- 历史会话面板（点击图标展开） -->
      <div v-show="showConversations" class="conv-panel">
        <ChatSidebar
          :conversations="conversations"
          :current-conversation-id="currentConversationId"
          @new-conversation="newConversation"
          @select-conversation="selectConversation"
          @remove-conversation="removeConversation"
        />
      </div>

      <!-- 中间：智能体对话（主区） -->
      <div class="chat-container">
        <div class="chat-title-bar">
          <span class="chat-title">
            <i class="fas fa-robot"></i>
            欢迎使用 TransMate 智能助手
          </span>
          <button
            :class="['tts-toggle', { active: ttsEnabled, speaking: isSpeaking }]"
            :title="ttsEnabled ? '关闭语音播报' : '开启语音播报'"
            @click="toggleTts"
          >
            <i :class="ttsEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute'"></i>
          </button>
        </div>
        <div v-if="showError" class="error-message" @click="hideError">
          <i class="fas fa-exclamation-triangle"></i>
          {{ errorMessage }}
          <span class="close-btn">×</span>
        </div>
        <MessageList
          :messages="dialogue"
          :is-processing="isProcessing"
          :processing-status="processingStatus"
        />
        <ChatInput
          v-model="newMessage"
          :is-processing="isProcessing"
          :is-recording="isRecording"
          :is-transcribing="isTranscribing"
          :disabled="!isConnected"
          @send="sendMessage"
          @stop="stopGeneration"
          @toggle-recording="toggleRecording"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import ChatSidebar from '../components/agent/ChatSidebar.vue';
import MessageList from '../components/agent/MessageList.vue';
import ChatInput from '../components/agent/ChatInput.vue';
import { useAgentChat } from '@/composables/useAgentChat';
import { transcribeAudio, synthesizeSpeech } from '@/services/api';

const userStore = useUserStore();
const router = useRouter();

const newMessage = ref<string>('');
const showError = ref<boolean>(false);
const errorMessage = ref<string>('');
const isRecording = ref<boolean>(false);
const isTranscribing = ref<boolean>(false);
const ttsEnabled = ref<boolean>(true);
const isSpeaking = ref<boolean>(false);
let currentAudio: HTMLAudioElement | null = null;
const userId = ref<string>('anonymous');
const showConversations = ref<boolean>(false);

let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];

const pickMimeType = (): string => {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
  for (const type of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return '';
};

const transcribeRecording = async (blob: Blob) => {
  if (blob.size === 0) return;
  isTranscribing.value = true;
  try {
    const response = await transcribeAudio(blob);
    const text = response.data?.text?.trim();
    if (text) {
      // 转写完成自动发送，无需人工点击
      newMessage.value = text;
      sendMessage();
    } else {
      showError.value = true;
      errorMessage.value = '未识别到语音内容，请重试';
    }
  } catch (err: any) {
    showError.value = true;
    errorMessage.value = `语音转写失败: ${err?.response?.data?.detail || err.message || '未知错误'}`;
  } finally {
    isTranscribing.value = false;
  }
};

const toggleRecording = async () => {
  if (isTranscribing.value) return;
  if (isRecording.value) {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
    }
  } else {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      const mimeType = pickMimeType();
      mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };
      mediaRecorder.onstop = () => {
        stream.getTracks().forEach(track => track.stop());
        isRecording.value = false;
        const blob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || 'audio/webm' });
        audioChunks = [];
        transcribeRecording(blob);
      };
      mediaRecorder.start();
      isRecording.value = true;
    } catch (error: any) {
      showError.value = true;
      errorMessage.value = `无法访问麦克风: ${error.message || '未知错误'}`;
    }
  }
};

const {
  dialogue,
  conversations,
  currentConversationId,
  isConnected,
  isProcessing,
  processingStatus,
  connect,
  sendMessage: sendChatMessage,
  stopGeneration,
  refreshConversations,
  selectConversation,
  newConversation,
  removeConversation
} = useAgentChat({
  userId,
  onReplyComplete: (content) => {
    if (ttsEnabled.value) {
      playTts(content);
    }
  }
});

const playTts = async (text: string) => {
  const clean = text.trim();
  if (!clean) return;
  try {
    isSpeaking.value = true;
    const response = await synthesizeSpeech(clean.slice(0, 500));
    const contentType = String(response.headers?.['content-type'] || 'audio/mpeg');
    const blob = new Blob([response.data], { type: contentType });
    const url = URL.createObjectURL(blob);
    stopAudio();
    currentAudio = new Audio(url);
    currentAudio.onended = () => {
      isSpeaking.value = false;
      URL.revokeObjectURL(url);
    };
    currentAudio.onerror = () => {
      isSpeaking.value = false;
      URL.revokeObjectURL(url);
    };
    await currentAudio.play();
  } catch (err) {
    isSpeaking.value = false;
    console.error('语音合成播放失败:', err);
  }
};

const stopAudio = () => {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
};

const toggleTts = () => {
  ttsEnabled.value = !ttsEnabled.value;
  if (!ttsEnabled.value) {
    stopAudio();
    isSpeaking.value = false;
  }
};

const hideError = () => { showError.value = false; };

const goSettings = () => { router.push('/personal-center'); };

const goHome = () => { router.push('/'); };

const sendMessage = () => {
  const text = newMessage.value;
  if (!text.trim()) return;
  if (!sendChatMessage(text)) {
    showError.value = true;
    errorMessage.value = 'WebSocket未连接，请先连接服务器';
    return;
  }
  newMessage.value = '';
};

onMounted(async () => {
  // 初始化用户状态
  userStore.initFromStorage();
  if (userStore.userInfo) {
    userId.value = localStorage.getItem('user_code') || userStore.userInfo.user_id;
  }

  connect();
  refreshConversations();
});

onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
  stopAudio();
});
</script>

<style>
/* 设计变量：仅本页使用，避免与全局冲突 */
.home-layout {
  --color-primary: #2563eb;
  --color-primary-deep: #1e3a8a;
  --color-surface: #ffffff;
  --color-bg: #f1f5f9;
  --color-border: #e2e8f0;
  --color-text: #1e293b;
  --color-text-muted: #64748b;
  --color-danger: #dc2626;
  --radius-full: 9999px;
  --shadow-lg: 0 10px 40px rgba(0,0,0,0.1);
  --transition: 0.2s ease;
}

.home-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: "Noto Sans SC", "Helvetica Neue", Arial, sans-serif;
  background: var(--color-bg);
  color: var(--color-text);
}

.home-layout .main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  max-width: 1600px;
  margin: 0 auto;
  width: 100%;
  padding: 1rem;
  box-sizing: border-box;
  gap: 1rem;
}

/* ===== 最左图标功能栏 ===== */
.home-layout .icon-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  width: 64px;
  min-width: 64px;
  padding: 14px 0;
  background: linear-gradient(180deg, #172554 0%, #1e3a8a 100%);
  border-radius: 16px;
  box-shadow: var(--shadow-lg);
}

.home-layout .rail-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-radius: 50%;
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.5);
  overflow: hidden;
}

.home-layout .rail-logo-img {
  width: 26px;
  height: 26px;
  object-fit: contain;
}

.home-layout .rail-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.home-layout .rail-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  font-size: 15px;
  color: rgba(255, 255, 255, 0.65);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .rail-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.16);
}

.home-layout .rail-btn.active {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-color: transparent;
  box-shadow: 0 4px 14px rgba(59, 130, 246, 0.45);
}

.home-layout .rail-bottom {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.home-layout .rail-avatar {
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-color: transparent;
}

/* ===== 历史会话面板 ===== */
.home-layout .conv-panel {
  height: 100%;
}

/* ===== 中间：智能体对话（主区，内容居中） ===== */
.home-layout .chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #1e293b;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  min-width: 420px;
  max-width: 900px;
  margin: 0 auto;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.home-layout .chat-title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.home-layout .tts-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  font-size: 15px;
  color: rgba(255, 255, 255, 0.55);
  background: rgba(255, 255, 255, 0.1);
  border: 1.5px solid rgba(255, 255, 255, 0.22);
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .tts-toggle:hover {
  background: rgba(255, 255, 255, 0.18);
}

.home-layout .tts-toggle.active {
  color: #4ade80;
  background: rgba(74, 222, 128, 0.15);
  border-color: rgba(74, 222, 128, 0.55);
}

.home-layout .tts-toggle.speaking {
  animation: tts-pulse 1s infinite;
}

@keyframes tts-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.4); }
  50% { box-shadow: 0 0 0 7px rgba(74, 222, 128, 0); }
}

.home-layout .chat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9375rem;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.85);
}

.home-layout .error-message {
  margin: 10px 14px 0;
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
  padding: 0.625rem 0.875rem;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.35);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-size: 0.875rem;
}

@media (max-width: 760px) {
  .home-layout .conv-panel {
    display: none;
  }
  .home-layout .icon-rail {
    width: 52px;
    min-width: 52px;
  }
  .home-layout .chat-container {
    min-width: 0;
  }
}
</style>
