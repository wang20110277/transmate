<template>
  <div class="home-layout">
    <AppHeader :user-name="userStore.userInfo?.nickname || userStore.userInfo?.user_id || userId" @logout="handleLogout" />

    <div :class="`connection-status ${connectionStatus}`" hidden>
      {{ connectionStatusText }}
    </div>

    <div class="main-container">
      <!-- 左侧面板：知识 + 记忆 -->
      <AppLeft :collapsed="leftPanelCollapsed" @update:collapsed="leftPanelCollapsed = $event" />

      <!-- 中间主内容区 -->
      <div class="center-content">
        <div class="avatar-panel">
          <div id="video-container">
            <div id="remoteVideo" style="width:100%;height:100%;"></div>
            <canvas id="canvas" style="max-width: 1920px; height: 1080px; background-color: transparent;" hidden="hidden"></canvas>
            <canvas id="tmpCanvas" style="max-width: 1920px; height: 1080px;" hidden="hidden"></canvas>
          </div>
          <div class="subtitle-wrapper-home">
            <ScrollSubtitle :text="spokenText" v-if="spokenText" @complete="spokenText = ''" />
          </div>
        </div>

        <div class="chat-container">
          <div class="tabs">
            <button :class="['tab-button', { active: activeTab === 'chat' }]" @click="activeTab = 'chat'">对话</button>
          </div>
          <div class="tab-content">
            <div v-show="activeTab === 'chat'" class="tab-pane">
              <div class="dialogue-container" ref="dialogueContainer">
                <div v-if="showError" class="error-message" @click="hideError">
                  <i class="fas fa-exclamation-triangle"></i>
                  {{ errorMessage }}
                  <span class="close-btn">×</span>
                </div>
                <div v-if="dialogue.length === 0" class="message role-assistant welcome-msg">
                  <div class="message-content">你好，我是阿雅，您的专属理财助手，有什么可以帮助您？</div>
                </div>
                <div v-for="(message, index) in dialogue"
                     :key="index"
                     :class="['message', 'role-' + (message.role || 'system')]">
                  <div class="message-content">{{ message.content || '无内容' }}</div>
                  <div class="timestamp">{{ formatTime(message.timestamp || Date.now()) }}</div>
                  <div v-if="message.role === 'user' && isProcessing && index === dialogue.length - 1"
                       class="processing-indicator">
                    <div class="processing-content">
                      <div class="dots">
                        <span></span><span></span><span></span>
                      </div>
                      <span class="processing-text">{{ processingStatus || '正在思考中...' }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="input-area">
                <input type="text"
                       class="text-input"
                       v-model="newMessage"
                       placeholder="请输入您的问题..."
                       @keyup.enter="sendMessage"
                       autocomplete="off">
                <button class="send-btn" @click="sendMessage" :disabled="isProcessing">发送</button>
                <button :class="['record-btn', {recording: isRecording}]" @click="toggleRecording" :disabled="isProcessing">
                  <i :class="isRecording ? 'fas fa-stop' : 'fas fa-microphone'"></i>
                </button>
                <button class="video-call-btn" @click="startVideoCall" :disabled="!isConnected || isCallActive">
                  <i class="fas fa-video"></i>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧面板：SKILLS + MCPs -->
      <AppRight :collapsed="rightPanelCollapsed" @update:collapsed="rightPanelCollapsed = $event" />
    </div>

    <!-- AppFooter removed -->
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { useUserStore } from '@/stores/user';
import AppHeader from '../components/AppHeader.vue';
import AppLeft from '../components/AppLeft.vue';
import AppRight from '../components/AppRight.vue';
import ScrollSubtitle from '../components/ScrollSubtitle.vue';
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
import { formatTime } from '../utils/time-utils';
import { Message, WebSocketMessage, ParsedWebSocketMessage } from '../types';

const router = useRouter();
const userStore = useUserStore();

const activeTab = ref<string>('chat');
const dialogue = ref<Message[]>([]);
const newMessage = ref<string>('');
const showError = ref<boolean>(false);
const errorMessage = ref<string>('');
const isConnected = ref<boolean>(false);
const isProcessing = ref<boolean>(false);
const processingStatus = ref<string>('');
const isRecording = ref<boolean>(false);
const isCallActive = ref<boolean>(false);
const dialogueContainer = ref<HTMLDivElement | null>(null);
const userId = ref<string>('用户');

// 侧边面板折叠状态
const leftPanelCollapsed = ref(false);
const rightPanelCollapsed = ref(false);

const handleLogout = async () => {
  await userStore.logoutUser();
  router.push('/login');
};

const currentVoiceIndex = ref<number>(0);
const currentVoice = appConfig.availableVoices[currentVoiceIndex.value];
const region = appConfig.azureRegion;
const subscriptionKey = appConfig.azureSubscriptionKey;
let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
const spokenText = ref<string>('');
const avatarSessionActive = ref<boolean>(false);
const avatarCharacter = ref<string>('lisa');
const avatarStyle = ref<string>('casual-sitting');
const socket = ref<WebSocket | null>(null);
const socketConnected = ref<boolean>(false);
const websocketMessages = ref<WebSocketMessage[]>([]);
const connectionStatus = ref<'connected' | 'disconnected' | 'connecting'>('disconnected');
const connectionStatusText = ref('未连接');

const connectWebSocket = () => {
  if (socket.value && socket.value.readyState === WebSocket.OPEN) return;
  const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
  const wsUrl = `${protocol}${window.location.host}/ws?user_id=${userId.value}`;
  try {
    socket.value = new WebSocket(wsUrl);
    socket.value.onopen = () => {
      socketConnected.value = true;
      connectionStatus.value = 'connected';
      connectionStatusText.value = '已连接到 WebSocket 服务器';
      websocketMessages.value.push({ type: 'info', data: 'WebSocket 连接已建立', timestamp: new Date().getTime() });
    };
    socket.value.onmessage = (event) => {
      let parsedData: ParsedWebSocketMessage;
      try {
        parsedData = JSON.parse(event.data as string);
        if (!Object.prototype.hasOwnProperty.call(parsedData, 'timestamp')) parsedData.timestamp = Date.now();
      } catch {
        parsedData = { text: event.data as string, timestamp: Date.now() };
      }
      const assistantMessage = {
        role: 'assistant',
        content: parsedData.text || event.data,
        timestamp: parsedData.timestamp || Date.now()
      };
      dialogue.value.push(assistantMessage);
      if (assistantMessage.content) {
        spokenText.value = assistantMessage.content;
        speakWithAvatar();
      }
      isProcessing.value = false;
      processingStatus.value = '';
      setTimeout(() => {
        if (dialogueContainer.value) dialogueContainer.value.scrollTop = dialogueContainer.value.scrollHeight;
      }, 100);
      websocketMessages.value.push({
        type: 'received',
        data: typeof event.data === 'string' ? event.data : JSON.stringify(event.data),
        timestamp: new Date().getTime()
      });
    };
    socket.value.onclose = () => {
      socketConnected.value = false;
      connectionStatus.value = 'disconnected';
      connectionStatusText.value = 'WebSocket 已断开';
      websocketMessages.value.push({ type: 'info', data: 'WebSocket 连接已断开', timestamp: new Date().getTime() });
    };
    socket.value.onerror = () => {
      connectionStatus.value = 'disconnected';
      connectionStatusText.value = 'WebSocket 连接错误';
      websocketMessages.value.push({ type: 'error', data: 'WebSocket 连接发生错误', timestamp: new Date().getTime() });
    };
  } catch (err) {
    console.error('创建 WebSocket 连接失败:', err);
    connectionStatus.value = 'disconnected';
    connectionStatusText.value = 'WebSocket 连接失败';
  }
};

const hideError = () => { showError.value = false; };

const sendMessage = () => {
  if (!newMessage.value.trim()) return;
  if (!socket.value || socket.value.readyState !== WebSocket.OPEN) {
    showError.value = true;
    errorMessage.value = 'WebSocket未连接，请先连接服务器';
    return;
  }
  const userMessage = { role: 'user', content: newMessage.value, timestamp: Date.now() };
  dialogue.value.push(userMessage);
  isProcessing.value = true;
  processingStatus.value = 'AI正在思考中...';
  const wsMessage = JSON.stringify({ type: 'chat_message', message: newMessage.value, timestamp: Date.now() });
  socket.value.send(wsMessage);
  websocketMessages.value.push({ type: 'sent', data: wsMessage, timestamp: Date.now() });
  newMessage.value = '';
  setTimeout(() => {
    if (dialogueContainer.value) dialogueContainer.value.scrollTop = dialogueContainer.value.scrollHeight;
  }, 100);
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
    }
  };
  newPeerConnection.oniceconnectionstatechange = function () {
    if (newPeerConnection.iceConnectionState === 'connected') {
      avatarSessionActive.value = true;
      connectionStatus.value = 'connected';
      connectionStatusText.value = '数字人连接已建立';
    } else if (newPeerConnection.iceConnectionState === 'failed') {
      avatarSessionActive.value = false;
      connectionStatus.value = 'disconnected';
      connectionStatusText.value = '数字人连接失败';
      showError.value = true;
      errorMessage.value = '数字人连接失败，请检查网络连接和配置';
    } else if (newPeerConnection.iceConnectionState === 'disconnected' || newPeerConnection.iceConnectionState === 'closed') {
      avatarSessionActive.value = false;
      connectionStatus.value = 'disconnected';
      connectionStatusText.value = '数字人连接已断开';
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

const startAvatarSession = async () => {
  if (isAvatarSessionInitialized() && avatarSessionActive.value) return;
  try {
    if (!subscriptionKey) {
      showError.value = true;
      errorMessage.value = '缺少Azure订阅密钥，请配置VITE_AZURE_SUBSCRIPTION_KEY环境变量。';
      return;
    }
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

const toggleRecording = async () => {
  if (isRecording.value) {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();
      isRecording.value = false;
    }
  } else {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      mediaRecorder = new MediaRecorder(stream);
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstop = () => stream.getTracks().forEach(track => track.stop());
      mediaRecorder.start();
      isRecording.value = true;
    } catch (error: any) {
      showError.value = true;
      errorMessage.value = `无法访问麦克风: ${error.message || '未知错误'}`;
    }
  }
};

const startVideoCall = () => { isCallActive.value = !isCallActive.value; };

onMounted(async () => {
  // 初始化用户状态
  userStore.initFromStorage();
  if (userStore.userInfo) {
    userId.value = localStorage.getItem('user_code') || userStore.userInfo.user_id;
  }

  connectWebSocket();
  setTimeout(async () => { await startAvatarSession(); }, 1000);
  document.addEventListener('visibilitychange', async () => {
    if (!document.hidden && !avatarSessionActive.value) await startAvatarSession();
  });
});

onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state === 'recording') mediaRecorder.stop();
  if (socket.value) socket.value.close();
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
  --color-primary-hover: #1d4ed8;
  --color-surface: #ffffff;
  --color-bg: #f8fafc;
  --color-bg-chat: #f1f5f9;
  --color-border: #e2e8f0;
  --color-text: #1e293b;
  --color-text-muted: #64748b;
  --color-danger: #dc2626;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-full: 9999px;
  --shadow-md: 0 4px 12px rgba(0,0,0,0.08);
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

.home-layout .connection-status {
  padding: 0.5rem 1rem;
  text-align: center;
  font-size: 0.875rem;
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
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

/* 中间内容区 - 左右结构 */
.home-layout .center-content {
  flex: 1;
  display: flex;
  flex-direction: row;
  gap: 1rem;
  min-width: 0;
  overflow: hidden;
}

.home-layout .avatar-panel {
  flex: 1;
  background: #0f172a;
  border-radius: var(--radius-lg);
  overflow: hidden;
  min-width: 400px;
  display: flex;
  flex-direction: column;
  position: relative;
  box-shadow: var(--shadow-lg);
}

.home-layout #video-container {
  flex: 1;
  width: 100%;
  height: calc(100% - 80px);
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
  background: #0f172a;
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

@keyframes char-appear {
  0% {
    opacity: 0;
    transform: translateX(15px);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

.home-layout .chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  min-width: 350px;
  border: 1px solid var(--color-border);
}

.home-layout .tabs {
  display: flex;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-bg);
}

.home-layout .tab-button {
  padding: 12px 20px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 0.9375rem;
  font-weight: 500;
  color: var(--color-text-muted);
  border-bottom: 3px solid transparent;
  transition: color var(--transition), border-color var(--transition), background var(--transition);
}

.home-layout .tab-button.active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
  background: var(--color-surface);
}

.home-layout .tab-content,
.home-layout .tab-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.home-layout .dialogue-container {
  flex: 1;
  padding: 1rem 1.25rem;
  overflow-y: auto;
  background: var(--color-bg-chat);
}

.home-layout .dialogue-container::-webkit-scrollbar {
  width: 6px;
}

.home-layout .dialogue-container::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: var(--radius-full);
}

.home-layout .message {
  margin-bottom: 1rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  max-width: 82%;
  animation: fadeIn 0.25s ease;
  line-height: 1.5;
}

.home-layout .message.welcome-msg {
  border-left: 4px solid var(--color-primary);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.home-layout .message.role-user {
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  color: white;
  margin-left: auto;
  text-align: right;
}

.home-layout .message.role-assistant {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  color: var(--color-text);
}

.home-layout .message.role-system {
  background: var(--color-bg);
  color: var(--color-text-muted);
  font-style: italic;
  border: 1px dashed var(--color-border);
}

.home-layout .message-content {
  margin-bottom: 0.25rem;
  font-size: 0.9375rem;
}

.home-layout .timestamp {
  font-size: 0.6875rem;
  color: var(--color-text-muted);
  text-align: right;
  opacity: 0.85;
}

.home-layout .processing-content {
  display: flex;
  align-items: center;
  color: var(--color-text-muted);
  font-size: 0.875rem;
}

.home-layout .dots {
  display: flex;
  margin-right: 0.5rem;
  gap: 4px;
}

.home-layout .dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: bounce 1.5s infinite;
}

.home-layout .dots span:nth-child(2) { animation-delay: 0.2s; }
.home-layout .dots span:nth-child(3) { animation-delay: 0.4s; }

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-5px); }
}

.home-layout .input-area {
  padding: 1rem 1.25rem;
  background: var(--color-surface);
  border-top: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.home-layout .text-input {
  flex: 1;
  padding: 0.75rem 1.125rem;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-full);
  font-size: 0.9375rem;
  font-family: inherit;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
}

.home-layout .text-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.home-layout .send-btn,
.home-layout .record-btn,
.home-layout .video-call-btn {
  padding: 0.75rem 1rem;
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: 0.9375rem;
  transition: transform var(--transition), background var(--transition), opacity var(--transition);
  min-width: 44px;
}

.home-layout .send-btn {
  background: var(--color-primary);
  color: white;
  font-weight: 500;
}

.home-layout .send-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  opacity: 0.8;
}

.home-layout .record-btn {
  background: var(--color-text-muted);
  color: white;
}

.home-layout .record-btn.recording {
  background: var(--color-danger);
  animation: pulse 1.5s infinite;
}

.home-layout .video-call-btn {
  background: #059669;
  color: white;
}

.home-layout .video-call-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  opacity: 0.8;
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.7; }
  100% { opacity: 1; }
}

.home-layout .error-message {
  background: #fef2f2;
  color: #991b1b;
  padding: 0.875rem 1rem;
  border-radius: var(--radius-md);
  margin-bottom: 1rem;
  border: 1px solid #fecaca;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-size: 0.9375rem;
}

@media (max-width: 900px) {
  .home-layout .main-container {
    flex-direction: column;
    padding: 0.75rem;
  }
  .home-layout .center-content {
    flex-direction: column;
  }
  .home-layout .avatar-panel {
    min-height: 280px;
    min-width: 100%;
  }
  .home-layout .chat-container {
    min-height: 360px;
    min-width: 100%;
  }
}

@media (max-width: 768px) {
  .home-layout .message {
    max-width: 92%;
  }
}
</style>
