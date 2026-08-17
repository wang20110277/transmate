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
          <button
            :class="['rail-btn', { active: !avatarCollapsed }]"
            title="数字人面板"
            @click="avatarCollapsed = !avatarCollapsed"
          >
            <i class="fas fa-video"></i>
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
            <i :class="isSpeaking ? 'fas fa-volume-high' : (ttsEnabled ? 'fas fa-volume-high' : 'fas fa-volume-xmark')"></i>
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

      <!-- 最右：数字人面板（可折叠） -->
      <div v-show="!avatarCollapsed" class="avatar-panel">
        <div class="avatar-topbar">
          <span class="avatar-user-avatar">
            <i class="fas fa-user"></i>
          </span>
          <div class="avatar-user-info">
            <div class="avatar-user-name">{{ displayName }}</div>
            <div class="avatar-user-status">
              <span :class="['status-dot', avatarSessionActive ? 'on' : 'off']"></span>
              {{ avatarSessionActive ? '数字人已就绪' : '数字人未连接' }}
            </div>
          </div>
          <span class="conn-dot" :class="isConnected ? 'online' : 'offline'"></span>
          <button class="avatar-panel-btn" title="重新连接数字人" @click="restartAvatar">
            <i class="fas fa-rotate-right"></i>
          </button>
          <button class="avatar-panel-btn" title="收起面板" @click="avatarCollapsed = true">
            <i class="fas fa-chevron-right"></i>
          </button>
        </div>

        <div id="video-container">
          <div id="remoteVideo" style="width:100%;height:100%;"></div>
          <canvas id="canvas" style="max-width: 1920px; height: 1080px; background-color: transparent;" hidden="hidden"></canvas>
          <canvas id="tmpCanvas" style="max-width: 1920px; height: 1080px;" hidden="hidden"></canvas>
        </div>
        <div class="subtitle-wrapper-home">
          <ScrollSubtitle :text="spokenText" v-if="spokenText" @complete="spokenText = ''" />
        </div>
      </div>

      <!-- 数字人面板折叠后的展开把手 -->
      <button
        v-show="avatarCollapsed"
        class="avatar-expand-handle"
        title="展开数字人面板"
        @click="avatarCollapsed = false"
      >
        <i class="fas fa-chevron-left"></i>
        <span class="handle-text">数字人</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import ScrollSubtitle from '../components/ScrollSubtitle.vue';
import ChatSidebar from '../components/agent/ChatSidebar.vue';
import MessageList from '../components/agent/MessageList.vue';
import ChatInput from '../components/agent/ChatInput.vue';
import { useAgentChat } from '@/composables/useAgentChat';
import { transcribeAudio, synthesizeSpeech } from '@/services/api';
import {
  getOrCreateSpeechConfig,
  getAvatarSynthesizer,
  setAvatarSynthesizer,
  setPeerConnection,
  getPeerConnection,
  setAvatarSessionInitialized,
  isAvatarSessionInitialized,
  resetAzureInstances,
  SpeechSDK
} from '../services/azure-sdk';
import { appConfig } from '../config/app-config';

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
const spokenText = ref<string>('');
const avatarSessionActive = ref<boolean>(false);
const avatarCharacter = ref<string>('lisa');
const avatarStyle = ref<string>('casual-sitting');
const showConversations = ref<boolean>(false);
const avatarCollapsed = ref<boolean>(false);

const displayName = computed(() => userStore.userInfo?.nickname || '访客用户');

const currentVoiceIndex = ref<number>(0);
const currentVoice = appConfig.availableVoices[currentVoiceIndex.value];
const region = appConfig.azureRegion;
const subscriptionKey = appConfig.azureSubscriptionKey;
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
    spokenText.value = content;
    if (avatarEnabled && avatarSessionActive.value) {
      speakWithAvatar();
    } else if (ttsEnabled.value) {
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
    const contentType = response.headers?.['content-type'] || 'audio/mpeg';
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

const restartAvatar = () => {
  avatarSessionActive.value = false;
  setAvatarSessionInitialized(false);
  startAvatarSession();
};

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

const fetchIceServerInfo = async (key: string, reg: string) => {
  try {
    const axios = (await import('axios')).default;
    const response = await axios.get(
      `https://${reg}.tts.speech.microsoft.com/cognitiveservices/avatar/relay/token/v1`,
      { headers: { 'Ocp-Apim-Subscription-Key': key }, timeout: 60000 }
    );
    if (response.status !== 200) throw new Error('Token acquisition failed: ' + response.status + ' ' + response.statusText);
    return response.data;
  } catch (error: any) {
    console.error('WebRTC连接失败', error);
  }
};

const setupWebRTC = (iceServerUrl: string, iceServerUsername: string, iceServerCredential: string) => {
  const newPeerConnection = new RTCPeerConnection({
    iceServers: [{ urls: [iceServerUrl], username: iceServerUsername, credential: iceServerCredential }]
  });
  setPeerConnection(newPeerConnection);
  newPeerConnection.ontrack = function (event: RTCTrackEvent) {
    if (event.track.kind === 'video') {
      const videoContainer = document.getElementById('remoteVideo');
      if (!videoContainer) return;
      videoContainer.innerHTML = '';
      const videoElement = document.createElement('video');
      videoElement.id = 'videoPlayer';
      videoElement.srcObject = event.streams[0];
      videoElement.autoplay = true;
      videoElement.muted = false;
      videoElement.playsInline = true;
      videoElement.style.width = '100%';
      videoElement.style.height = '100%';
      videoElement.style.objectFit = 'contain';
      videoContainer.appendChild(videoElement);
    }
    if (event.track.kind === 'audio') {
      const existingAudio = document.getElementById('audioPlayer');
      if (existingAudio) existingAudio.remove();
      const audioElement = document.createElement('audio');
      audioElement.id = 'audioPlayer';
      audioElement.srcObject = event.streams[0];
      audioElement.autoplay = true;
      audioElement.muted = true;
      document.body.appendChild(audioElement);
    }
  };
  newPeerConnection.oniceconnectionstatechange = function () {
    if (newPeerConnection.iceConnectionState === 'connected') {
      avatarSessionActive.value = true;
    } else if (newPeerConnection.iceConnectionState === 'failed') {
      avatarSessionActive.value = false;
      showError.value = true;
      errorMessage.value = '数字人连接失败，请检查网络连接和配置';
    } else if (newPeerConnection.iceConnectionState === 'disconnected' || newPeerConnection.iceConnectionState === 'closed') {
      avatarSessionActive.value = false;
    }
  };
  try {
    newPeerConnection.addTransceiver('video', { direction: 'sendrecv' });
    newPeerConnection.addTransceiver('audio', { direction: 'sendrecv' });
  } catch (error: any) {
    showError.value = true;
    errorMessage.value = `添加音视频收发器失败: ${error.message || '未知错误'}`;
  }
};

// 未配置 Azure 订阅密钥时静默禁用数字人功能，聊天不受影响
const avatarEnabled = Boolean(subscriptionKey);

const startAvatarSession = async () => {
  if (!avatarEnabled) return;
  if (isAvatarSessionInitialized() && avatarSessionActive.value) return;
  try {
    const speechConfig = getOrCreateSpeechConfig(subscriptionKey, region, currentVoice);
    const videoFormat = new SpeechSDK.AvatarVideoFormat();
    const avatarConfiguration: any = new SpeechSDK.AvatarConfig(avatarCharacter.value, avatarStyle.value, videoFormat);
    avatarConfiguration.backgroundColor = 'white';
    const iceServerInfo = await fetchIceServerInfo(subscriptionKey, region);
    if (!iceServerInfo) {
      showError.value = true;
      errorMessage.value = '获取ICE服务器信息失败。请检查您的Azure订阅。';
      return;
    }
    setupWebRTC(iceServerInfo.Urls[0], iceServerInfo.Username, iceServerInfo.Password);
    const newAvatarSynthesizer = new SpeechSDK.AvatarSynthesizer(speechConfig, avatarConfiguration);
    setAvatarSynthesizer(newAvatarSynthesizer);
    newAvatarSynthesizer.startAvatarAsync(getPeerConnection()!).then(
      () => {
        avatarSessionActive.value = true;
        setAvatarSessionInitialized(true);
      }
    ).catch((error: any) => {
      showError.value = true;
      errorMessage.value = `Avatar failed to start: ${error.message || 'Unknown error'}`;
    });
    avatarSessionActive.value = true;
  } catch (error: any) {
    avatarSessionActive.value = false;
    showError.value = true;
    errorMessage.value = `启动数字人会话失败: ${error.message || '未知错误'}`;
  }
};

const speakWithAvatar = async () => {
  if (!avatarEnabled) return;
  if (!avatarSessionActive.value) await startAvatarSession();
  const currentAvatarSynthesizer = getAvatarSynthesizer();
  if (!currentAvatarSynthesizer) {
    showError.value = true;
    errorMessage.value = '虚拟形象合成器未初始化。请尝试重新启动。';
    return;
  }

  try {
    const text = spokenText.value;

    currentAvatarSynthesizer.speakTextAsync(text).then(
      (result: any) => {
        if (result.reason === SpeechSDK.ResultReason.Canceled) {
          const cancellationDetails = SpeechSDK.CancellationDetails.fromResult(result);
          if (cancellationDetails.reason === SpeechSDK.CancellationReason.Error) {
            showError.value = true;
            errorMessage.value = `数字人合成错误: ${cancellationDetails.errorDetails || '未知错误'}`;
          }
        }
      }
    ).catch((error: any) => {
      showError.value = true;
      errorMessage.value = `合成语音和数字人失败: ${error.message || '未知错误'}`;
    });
  } catch (error: any) {
    showError.value = true;
    errorMessage.value = `合成语音和数字人失败: ${error.message || '未知错误'}`;
  }
};

onMounted(async () => {
  // 初始化用户状态
  userStore.initFromStorage();
  if (userStore.userInfo) {
    userId.value = localStorage.getItem('user_code') || userStore.userInfo.user_id;
  }

  connect();
  refreshConversations();
  setTimeout(async () => { await startAvatarSession(); }, 1000);
  document.addEventListener('visibilitychange', async () => {
    if (!document.hidden && !avatarSessionActive.value) await startAvatarSession();
  });
});

onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
  stopAudio();
  const currentAvatarSynthesizer = getAvatarSynthesizer();
  if (currentAvatarSynthesizer) {
    currentAvatarSynthesizer.close();
    resetAzureInstances();
  }
  const currentPeerConnection = getPeerConnection();
  if (currentPeerConnection) currentPeerConnection.close();
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

/* ===== 最右：数字人面板（可折叠） ===== */
.home-layout .avatar-panel {
  flex: 1.1;
  display: flex;
  flex-direction: column;
  min-width: 300px;
  max-width: 460px;
  background: linear-gradient(160deg, #1e3a8a 0%, #1e40af 55%, #1d4ed8 100%);
  border-radius: 16px;
  overflow: hidden;
  position: relative;
  box-shadow: var(--shadow-lg);
}

.home-layout .avatar-panel-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.16);
  border-radius: 8px;
  cursor: pointer;
  flex-shrink: 0;
  transition: all var(--transition);
}

.home-layout .avatar-panel-btn:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.22);
}

/* 折叠后的展开把手（贴右缘竖条） */
.home-layout .avatar-expand-handle {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 44px;
  padding: 16px 0;
  color: rgba(255, 255, 255, 0.85);
  background: linear-gradient(180deg, #172554 0%, #1e3a8a 100%);
  border: none;
  border-radius: 16px;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: background var(--transition);
}

.home-layout .avatar-expand-handle:hover {
  background: linear-gradient(180deg, #1e3a8a 0%, #1d4ed8 100%);
}

.home-layout .handle-text {
  writing-mode: vertical-rl;
  letter-spacing: 4px;
  font-size: 12px;
  font-weight: 500;
}

.home-layout .avatar-topbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 18px;
  background: rgba(0, 0, 0, 0.18);
}

.home-layout .avatar-user-avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  font-size: 16px;
  color: #1e3a8a;
  background: #e0e7ff;
  border: 2px solid rgba(255, 255, 255, 0.65);
  border-radius: 50%;
}

.home-layout .avatar-user-info {
  flex: 1;
  min-width: 0;
}

.home-layout .avatar-user-name {
  font-size: 0.9375rem;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.home-layout .avatar-user-status {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 2px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.65);
}

.home-layout .status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
}

.home-layout .status-dot.on {
  background: #4ade80;
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.9);
}

.home-layout .status-dot.off {
  background: rgba(255, 255, 255, 0.4);
}

.home-layout .conn-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
}

.home-layout .conn-dot.online {
  background: #4ade80;
  box-shadow: 0 0 8px rgba(74, 222, 128, 0.9);
}

.home-layout .conn-dot.offline {
  background: #f87171;
}

.home-layout #video-container {
  flex: 1;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  min-height: 280px;
}

.home-layout #remoteVideo {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

/* 字幕容器定位 */
.subtitle-wrapper-home {
  position: absolute;
  bottom: 20px;
  left: 0;
  right: 0;
  z-index: 100;
  width: 100%;
  display: flex;
  justify-content: center;
  pointer-events: none;
}

.subtitle-wrapper-home > * {
  pointer-events: auto;
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
  width: 32px;
  height: 32px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 50%;
  cursor: pointer;
  transition: all var(--transition);
}

.home-layout .tts-toggle.active {
  color: #4ade80;
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

@media (max-width: 1100px) {
  .home-layout .avatar-panel,
  .home-layout .avatar-expand-handle {
    display: none;
  }
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
