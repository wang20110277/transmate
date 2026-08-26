<template>
  <div class="home-layout">
    <!-- 左侧：常驻浅色边栏（可通过顶栏按钮折叠） -->
    <aside :class="['sidebar', { collapsed: sidebarCollapsed }]">
      <!-- macOS 红绿灯让位区（兼作窗口拖动区，非 Mac 平台隐藏） -->
      <div class="sidebar-top"></div>

      <div class="brand">
        <span class="brand-logo">
          <img src="/icons/trans.svg" alt="logo" class="brand-logo-img">
        </span>
        <span class="brand-name">TransMate</span>
      </div>

      <button class="new-chat-btn" @click="newConversation">
        <i class="fas fa-plus"></i>
        <span>{{ t('home.newChat') }}</span>
      </button>

      <div class="recent-label">{{ t('home.recent') }}</div>

      <div class="sidebar-list">
        <ChatSidebar
          :conversations="conversations"
          :current-conversation-id="currentConversationId"
          @new-conversation="newConversation"
          @select-conversation="selectConversation"
          @remove-conversation="removeConversation"
        />
      </div>

      <div class="sidebar-footer">
        <div class="footer-row">
          <button class="user-btn" :title="t('home.prefButton')" :aria-label="t('home.prefButton')" @click.stop="toggleUserMenu">
            <span class="user-avatar"><i class="fas fa-user"></i></span>
          </button>
          <button class="settings-entry-btn" :title="t('home.settings')" :aria-label="t('home.openSettings')" @click="goSettings">
            <i class="fas fa-cog"></i>
          </button>
          <button class="settings-entry-btn" :title="t('home.skills')" :aria-label="t('home.skills')" @click="goSkills">
            <i class="fas fa-puzzle-piece"></i>
          </button>
        </div>

        <!-- 偏好浮层：语言 / 主题 / 连接 -->
        <div v-if="userMenuOpen" class="user-popover" @click.stop>
          <div class="pop-title">{{ t('home.prefTitle') }}</div>

          <div class="pop-row">
            <span class="pop-label">{{ t('home.langLabel') }}</span>
            <div class="pop-seg">
              <button :class="['seg-btn', { active: uiLang === 'zh' }]" @click="setUiLang('zh')">中文</button>
              <button :class="['seg-btn', { active: uiLang === 'en' }]" @click="setUiLang('en')">English</button>
            </div>
          </div>

          <div class="pop-row">
            <span class="pop-label">{{ t('home.themeLabel') }}</span>
            <div class="pop-seg">
              <button :class="['seg-btn', { active: uiTheme === 'light' }]" @click="setUiTheme('light')">{{ t('home.themeLight') }}</button>
              <button :class="['seg-btn', { active: uiTheme === 'dark' }]" @click="setUiTheme('dark')">{{ t('home.themeDark') }}</button>
            </div>
          </div>

          <div class="pop-divider"></div>

          <div class="pop-conn">
            <span class="pop-label">{{ t('home.connLabel') }}</span>
            <div class="conn-edit">
              <input
                v-model="apiBaseInput"
                class="conn-input"
                type="text"
                placeholder="http://localhost:8000"
                spellcheck="false"
              >
              <button class="conn-apply" @click="applyApiBase">{{ t('home.apply') }}</button>
            </div>
            <p class="conn-hint">{{ t('home.connHint') }}</p>
          </div>
        </div>
      </div>
    </aside>

    <!-- 右侧：主区 -->
    <main class="main-area">
      <header :class="['main-header', { 'sidebar-collapsed': sidebarCollapsed }]">
        <div class="header-left">
          <button
            class="sidebar-toggle-btn"
            :data-tip="sidebarCollapsed ? t('home.expandSidebar') : t('home.collapseSidebar')"
            :aria-label="sidebarCollapsed ? t('home.expandSidebar') : t('home.collapseSidebar')"
            @click="sidebarCollapsed = !sidebarCollapsed"
          >
            <i class="fas fa-columns"></i>
          </button>
          <div :class="['conn-status', isConnected ? 'on' : 'off']">
            <span class="conn-dot"></span>
            {{ isConnected ? t('home.connected') : t('home.connecting') }}
          </div>
        </div>
        <button
          :class="['tts-toggle', { active: ttsEnabled, speaking: isSpeaking }]"
          :title="ttsEnabled ? t('home.ttsDisable') : t('home.ttsEnable')"
          @click="toggleTts"
        >
          <i :class="ttsEnabled ? 'fas fa-volume-up' : 'fas fa-volume-mute'"></i>
          <span>{{ ttsEnabled ? (isSpeaking ? t('home.ttsSpeaking') : t('home.ttsLabel')) : t('home.ttsMuted') }}</span>
        </button>
      </header>

      <div class="main-body">
        <div v-if="showError" class="error-message" @click="hideError">
          <i class="fas fa-exclamation-circle"></i>
          {{ errorMessage }}
          <span class="close-btn">×</span>
        </div>

        <!-- 空状态：欢迎语 + 推荐卡片 -->
        <div v-if="dialogue.length === 0 && !isProcessing" class="welcome">
          <h1 class="greeting">{{ t('home.greeting') }}</h1>

          <div class="rec-section">
            <div class="rec-label">{{ t('home.recommend') }}</div>
            <div class="rec-grid">
              <button
                v-for="item in suggestions"
                :key="item.text"
                class="rec-card"
                @click="useSuggestion(item.text)"
              >
                <i :class="['fas', item.icon]"></i>
                <span>{{ item.text }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- 对话状态：消息列表 -->
        <MessageList
          v-else
          :messages="dialogue"
          :is-processing="isProcessing"
          :processing-status="processingStatus"
          :speaking-index="speakingIndex"
          :tts-muted="!ttsEnabled"
          @toggle-speak="onToggleSpeak"
        />
      </div>

      <div class="input-wrap">
        <ChatInput
          v-model="newMessage"
          :is-processing="isProcessing"
          :is-recording="isRecording"
          :is-transcribing="isTranscribing"
          :disabled="!isConnected"
          :placeholder="t('home.inputPlaceholder')"
          @send="sendMessage"
          @stop="stopGeneration"
          @toggle-recording="toggleRecording"
        />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import { useI18n } from '@/i18n';
import ChatSidebar from '../components/agent/ChatSidebar.vue';
import MessageList from '../components/agent/MessageList.vue';
import ChatInput from '../components/agent/ChatInput.vue';
import { useAgentChat } from '@/composables/useAgentChat';
import { transcribeAudio, synthesizeSpeech } from '@/services/api';

const userStore = useUserStore();
const router = useRouter();
const { t, tList, lang: uiLang, setLang } = useI18n();

const newMessage = ref<string>('');
const showError = ref<boolean>(false);
const errorMessage = ref<string>('');
const isRecording = ref<boolean>(false);
const isTranscribing = ref<boolean>(false);
// 左侧栏折叠状态
const sidebarCollapsed = ref<boolean>(false);
const ttsEnabled = ref<boolean>(true);
const isSpeaking = ref<boolean>(false);
// 当前正在朗读的消息索引（用于消息级喇叭按钮高亮）
const speakingIndex = ref<number | null>(null);
let currentAudio: HTMLAudioElement | null = null;
const userId = ref<string>('anonymous');

// 推荐卡片文案随界面语言切换
const suggestionIcons = ['fa-language', 'fa-cloud-sun', 'fa-search', 'fa-chart-line'];
const suggestions = computed(() => {
  return tList('home.suggestions').map((text, i) => ({ icon: suggestionIcons[i] || 'fa-lightbulb', text }));
});

const useSuggestion = (text: string) => {
  newMessage.value = text;
  sendMessage();
};

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
      newMessage.value = text;
      // 转写完成自动发送
      sendMessage();
    } else {
      showError.value = true;
      errorMessage.value = t('errors.noSpeech');
    }
  } catch (err: any) {
    showError.value = true;
    errorMessage.value = t('errors.transcribeFailed', { msg: err?.response?.data?.detail || err.message || t('errors.unknown') });
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
      errorMessage.value = t('errors.micDenied', { msg: error.message || t('errors.unknown') });
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
      // 定位刚完成的 assistant 消息索引，让对应喇叭按钮高亮
      const idx = dialogue.value.map((m) => m.role).lastIndexOf('assistant');
      playTts(content, idx >= 0 ? idx : null);
    }
  }
});

const playTts = async (text: string, messageIndex: number | null = null) => {
  const clean = text.trim();
  if (!clean) return;
  try {
    isSpeaking.value = true;
    speakingIndex.value = messageIndex;
    const response = await synthesizeSpeech(clean.slice(0, 500));
    const contentType = String(response.headers?.['content-type'] || 'audio/mpeg');
    const blob = new Blob([response.data], { type: contentType });
    const url = URL.createObjectURL(blob);
    stopAudio();
    // stopAudio 会重置朗读状态，这里恢复为当前这条消息
    isSpeaking.value = true;
    speakingIndex.value = messageIndex;
    currentAudio = new Audio(url);
    currentAudio.onended = () => {
      URL.revokeObjectURL(url);
      stopAudio();
    };
    currentAudio.onerror = () => {
      URL.revokeObjectURL(url);
      stopAudio();
    };
    await currentAudio.play();
  } catch (err) {
    isSpeaking.value = false;
    speakingIndex.value = null;
    console.error('语音合成播放失败:', err);
  }
};

const stopAudio = () => {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  isSpeaking.value = false;
  speakingIndex.value = null;
};

const toggleTts = () => {
  ttsEnabled.value = !ttsEnabled.value;
  if (!ttsEnabled.value) {
    stopAudio();
  }
};

// 消息级喇叭：点击朗读该条回复，再次点击停止（全局静音时禁用朗读）
const onToggleSpeak = (index: number) => {
  if (!ttsEnabled.value) return;
  if (speakingIndex.value === index) {
    stopAudio();
    return;
  }
  const message = dialogue.value[index];
  if (message?.content) {
    playTts(message.content, index);
  }
};

const hideError = () => { showError.value = false; };

// ===== 界面偏好（语言 / 主题 / 连接）=====
const userMenuOpen = ref<boolean>(false);
const uiTheme = ref<string>(localStorage.getItem('tm_ui_theme') || 'light');
const apiBaseInput = ref<string>(
  localStorage.getItem('tm_api_base') || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
);

const toggleUserMenu = () => { userMenuOpen.value = !userMenuOpen.value; };

// 切换界面语言：i18n 模块内持久化并即时生效
const setUiLang = (value: string) => {
  setLang(value === 'en' ? 'en' : 'zh');
};

// 主题即时切换：html.dark 触发全局 token 覆盖
const setUiTheme = (theme: string) => {
  uiTheme.value = theme;
  localStorage.setItem('tm_ui_theme', theme);
  document.documentElement.classList.toggle('dark', theme === 'dark');
};

const applyApiBase = () => {
  const value = apiBaseInput.value.trim().replace(/\/+$/, '');
  if (!/^https?:\/\//.test(value)) {
    showError.value = true;
    errorMessage.value = t('errors.invalidUrl');
    return;
  }
  localStorage.setItem('tm_api_base', value);
  location.reload();
};

// 点击浮层外部关闭
const onDocClick = () => { userMenuOpen.value = false; };
watch(userMenuOpen, (open) => {
  if (open) document.addEventListener('click', onDocClick);
  else document.removeEventListener('click', onDocClick);
});

const goSettings = () => { router.push('/settings'); };

const goSkills = () => { router.push('/skills'); };

const sendMessage = () => {
  const text = newMessage.value;
  if (!text.trim()) return;
  if (!sendChatMessage(text)) {
    showError.value = true;
    errorMessage.value = t('errors.wsNotConnected');
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
  document.removeEventListener('click', onDocClick);
});
</script>

<style>
/* 设计 tokens 统一在 src/styles/theme.css（:root 浅色 + html.dark 深色） */
.home-layout {
  height: 100vh;
  display: flex;
  font-family: "Noto Sans SC", "Helvetica Neue", Arial, sans-serif;
  background: var(--color-surface);
  color: var(--color-text);
  overflow: hidden;
}

/* ===== 左侧：常驻浅色边栏（可折叠） ===== */
.home-layout .sidebar {
  display: flex;
  flex-direction: column;
  width: 264px;
  min-width: 264px;
  padding: 16px 12px;
  box-sizing: border-box;
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-border);
  overflow: hidden;
  transition: width var(--transition), min-width var(--transition), padding var(--transition), border-right-color var(--transition);
}

.home-layout .sidebar.collapsed {
  width: 0;
  min-width: 0;
  padding: 16px 0;
  border-right-color: transparent;
}

.home-layout .brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 2px 8px 14px;
}

.home-layout .brand-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-radius: 10px;
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.3);
  overflow: hidden;
  flex-shrink: 0;
}

.home-layout .brand-logo-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.home-layout .brand-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.2px;
}

.home-layout .new-chat-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition);
  box-sizing: border-box;
}

.home-layout .new-chat-btn i {
  font-size: 12px;
  color: var(--color-primary);
}

.home-layout .new-chat-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-soft);
}

.home-layout .recent-label {
  padding: 18px 10px 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.home-layout .sidebar-list {
  flex: 1;
  min-height: 0;
}

.home-layout .sidebar-footer {
  position: relative;
  padding-top: 10px;
  border-top: 1px solid var(--color-border);
}

.home-layout .footer-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.home-layout .user-btn {
  display: flex;
  align-items: center;
  padding: 6px;
  background: transparent;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: background var(--transition);
}

.home-layout .user-btn:hover {
  background: var(--color-hover);
}

.home-layout .user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-size: 12px;
  color: #fff;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-radius: 50%;
  flex-shrink: 0;
}

/* 设置入口按钮（与头像分居底部左右两侧） */
.home-layout .settings-entry-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 14px;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 10px;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .settings-entry-btn:hover {
  color: var(--color-text);
  background: var(--color-hover);
}

/* ===== 偏好浮层（语言/主题/连接） ===== */
.home-layout .user-popover {
  position: absolute;
  left: 0;
  bottom: calc(100% + 10px);
  width: 100%;
  padding: 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  box-shadow: 0 8px 28px rgba(31, 35, 41, 0.14);
  box-sizing: border-box;
  z-index: 30;
}

.home-layout .pop-title {
  margin-bottom: 10px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.home-layout .pop-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.home-layout .pop-label {
  font-size: 13px;
  color: var(--color-text);
}

.home-layout .pop-seg {
  display: flex;
  background: var(--color-fill);
  border-radius: 8px;
  padding: 2px;
}

.home-layout .seg-btn {
  padding: 4px 10px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .seg-btn.active {
  color: var(--color-primary);
  background: var(--color-surface);
  font-weight: 500;
}

.home-layout .pop-divider {
  height: 1px;
  margin: 4px 0 12px;
  background: var(--color-border);
}

.home-layout .pop-conn {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.home-layout .conn-edit {
  display: flex;
  gap: 6px;
}

.home-layout .conn-input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  color: var(--color-text);
  background: var(--color-fill);
  border: 1px solid transparent;
  border-radius: 8px;
  outline: none;
  box-sizing: border-box;
  transition: border-color var(--transition);
}

.home-layout .conn-input:focus {
  border-color: var(--color-primary);
}

.home-layout .conn-apply {
  padding: 6px 12px;
  font-size: 12px;
  color: #fff;
  background: var(--color-primary);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition);
  flex-shrink: 0;
}

.home-layout .conn-apply:hover {
  background: var(--color-primary-deep);
}

.home-layout .conn-hint {
  margin: 0;
  font-size: 11px;
  color: var(--color-text-faint);
}

/* ===== 右侧：主区 ===== */
.home-layout .main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--color-surface);
}

.home-layout .main-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 56px;
  padding: 12px 24px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.home-layout .header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* 侧栏折叠/展开按钮：圆形描边 + 悬浮深色提示 */
.home-layout .sidebar-toggle-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  font-size: 13px;
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 50%;
  cursor: pointer;
  transition: color var(--transition), background var(--transition), border-color var(--transition);
  flex-shrink: 0;
  box-sizing: border-box;
  -webkit-app-region: no-drag;
}

.home-layout .sidebar-toggle-btn:hover {
  color: var(--color-text);
  background: var(--color-hover);
  border-color: var(--color-border-strong);
}

.home-layout .sidebar-toggle-btn::after {
  content: attr(data-tip);
  position: absolute;
  top: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  padding: 5px 9px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
  color: var(--color-tooltip-text);
  background: var(--color-tooltip);
  border-radius: 6px;
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--transition), visibility var(--transition);
  z-index: 20;
}

.home-layout .sidebar-toggle-btn::before {
  content: '';
  position: absolute;
  top: calc(100% + 3px);
  left: 50%;
  margin-left: -4px;
  border: 4px solid transparent;
  border-bottom-color: var(--color-tooltip);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity var(--transition), visibility var(--transition);
  z-index: 20;
}

.home-layout .sidebar-toggle-btn:hover::after,
.home-layout .sidebar-toggle-btn:hover::before {
  opacity: 1;
  visibility: visible;
}

.home-layout .conn-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-muted);
}

.home-layout .conn-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--color-text-faint);
}

.home-layout .conn-status.on .conn-dot {
  background: var(--color-success);
  box-shadow: 0 0 0 3px rgba(0, 180, 42, 0.12);
}

.home-layout .tts-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--color-text-muted);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all var(--transition);
  /* 头部是窗口拖动区，按钮需标记 no-drag 保持可点击 */
  -webkit-app-region: no-drag;
}

.home-layout .tts-toggle:hover {
  color: var(--color-text);
  background: var(--color-hover);
}

.home-layout .tts-toggle.active {
  color: var(--color-primary);
  background: var(--color-primary-soft);
  border-color: rgba(37, 99, 235, 0.35);
}

.home-layout .tts-toggle.speaking {
  animation: tts-pulse 1s infinite;
}

@keyframes tts-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.25); }
  50% { box-shadow: 0 0 0 6px rgba(37, 99, 235, 0); }
}

/* ===== 主内容（滚动区） ===== */
.home-layout .main-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  min-height: 0;
}

/* 空状态：欢迎语居中 */
.home-layout .welcome {
  max-width: 680px;
  width: 100%;
  margin: auto;
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  box-sizing: border-box;
}

.home-layout .greeting {
  margin: 0 0 24px;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.5px;
  text-align: center;
}

.home-layout .rec-section {
  width: 100%;
  margin-top: 28px;
}

.home-layout .rec-label {
  margin-bottom: 12px;
  font-size: 13px;
  color: var(--color-text-muted);
  text-align: left;
}

.home-layout .rec-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.home-layout .rec-card {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 16px;
  font-size: 13.5px;
  line-height: 1.5;
  text-align: left;
  color: var(--color-text);
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .rec-card i {
  margin-top: 2px;
  font-size: 14px;
  color: var(--color-primary);
  flex-shrink: 0;
}

.home-layout .rec-card:hover {
  border-color: rgba(37, 99, 235, 0.45);
  background: var(--color-primary-soft);
  transform: translateY(-1px);
}

/* 错误提示 */
.home-layout .error-message {
  margin: 10px 24px 0;
  padding: 10px 14px;
  background: var(--color-danger-soft);
  color: var(--color-danger);
  border: 1px solid rgba(245, 63, 63, 0.28);
  border-radius: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-size: 13px;
}

.home-layout .error-message > i {
  margin-right: 8px;
}

/* ===== 底部输入区 ===== */
.home-layout .input-wrap {
  padding: 8px 24px 20px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

/* ===== 响应式 ===== */
@media (max-width: 760px) {
  .home-layout .sidebar {
    display: none;
  }

  .home-layout .welcome {
    padding: 20px 16px;
  }

  .home-layout .greeting {
    font-size: 22px;
  }

  .home-layout .rec-grid {
    grid-template-columns: 1fr;
  }

  .home-layout .main-header,
  .home-layout .input-wrap {
    padding-left: 12px;
    padding-right: 12px;
  }

  .home-layout .sidebar-toggle-btn {
    display: none;
  }
}

/* ===== macOS 无标题栏适配 =====
   main.cjs 以 hiddenInset 隐藏标题栏后,红绿灯浮于左上角 (x:16, y:14):
   侧栏顶部预留 56px 让位区(红绿灯坐落其中),与主区头部 56px 对齐;
   两个区域均可拖动窗口,交互按钮需标记 no-drag 保持可点击 */
.home-layout .sidebar-top {
  display: none;
}

.platform-mac .home-layout .sidebar-top {
  display: block;
  height: 56px;
  flex-shrink: 0;
  -webkit-app-region: drag;
}

.platform-mac .home-layout .main-header {
  -webkit-app-region: drag;
}

/* 侧栏折叠后红绿灯让位区随之消失，主区头部左侧为红绿灯留出空间 */
.platform-mac .home-layout .main-header.sidebar-collapsed {
  padding-left: 84px;
}

@media (prefers-reduced-motion: reduce) {
  .home-layout .sidebar {
    transition: none;
  }

  .home-layout .tts-toggle.speaking {
    animation: none;
  }

  .home-layout .rec-card:hover {
    transform: none;
  }
}
</style>
