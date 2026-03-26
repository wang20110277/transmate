<template>
  <div class="wechat-qr-login">
    <p class="qr-description">{{ descriptionText }}</p>
    
    <!-- 二维码区域 -->
    <div class="qr-container">
      <div v-if="loading" class="qr-loading">
        <div class="loading-spinner"></div>
        <span>正在生成二维码...</span>
      </div>
      
      <div v-else-if="error" class="qr-error">
        <div class="error-icon">⚠️</div>
        <p>{{ error }}</p>
        <button class="btn-retry" @click="generateQRCode">重新获取</button>
      </div>
      
      <div v-else-if="qrCodeUrl" class="qr-image-wrapper">
        <img :src="qrCodeUrl" alt="微信登录二维码" class="qr-image" />
        
        <!-- 过期遮罩 -->
        <div v-if="isExpired" class="qr-expired-overlay">
          <div class="expired-content">
            <div class="expired-icon">⏰</div>
            <p>二维码已过期</p>
            <button class="btn-refresh" @click="generateQRCode">
              <svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
              </svg>
              点击刷新
            </button>
          </div>
        </div>
      </div>
      
      <div v-else class="qr-placeholder">
        <div class="placeholder-icon">
          <svg viewBox="0 0 24 24" fill="currentColor" width="48" height="48">
            <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578-.857-4.972 0-7.55C9.234 2.903 9.01 2.188 8.691 2.188z"/>
          </svg>
        </div>
        <p>点击生成二维码</p>
        <button class="btn-generate" @click="generateQRCode">获取微信登录二维码</button>
      </div>
    </div>
    
    <!-- 状态提示 -->
    <div v-if="statusMessage" :class="['status-message', statusType]">
      <span class="status-icon">{{ statusIcon }}</span>
      <span>{{ statusMessage }}</span>
    </div>
    
    <!-- 倒计时 -->
    <div v-if="countdown > 0 && !isExpired" class="countdown">
      二维码有效期：{{ countdown }} 秒
    </div>
    
    <!-- 刷新按钮（未过期时） -->
    <button 
      v-if="qrCodeUrl && !isExpired && !loading" 
      class="btn-refresh-inline"
      @click="generateQRCode"
    >
      <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14">
        <path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/>
      </svg>
      刷新二维码
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { createWechatQRCode, getWechatLoginStatus, wechatQRLogin } from '@/services/api'
import type { LoginResponse } from '@/services/api'

const router = useRouter()

// Props
const props = defineProps<{
  onSuccess?: (data: LoginResponse) => void
}>()

// 状态
const loading = ref(false)
const error = ref('')
const qrCodeUrl = ref('')
const sceneId = ref('')
const countdown = ref(0)
const loginStatus = ref<'pending' | 'scanned' | 'authorized' | 'rejected' | 'expired' | ''>('')
const statusMessage = ref('')

// 定时器
let countdownTimer: ReturnType<typeof setInterval> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

// 计算属性
const isExpired = computed(() => countdown.value <= 0 && qrCodeUrl.value !== '')

const descriptionText = computed(() => {
  switch (loginStatus.value) {
    case 'pending':
      return '请使用微信扫一扫登录'
    case 'scanned':
      return '已扫码，请在手机上确认'
    case 'authorized':
      return '授权成功，正在登录...'
    case 'rejected':
      return '用户拒绝授权，请重新扫码'
    case 'expired':
      return '二维码已过期，请刷新重试'
    default:
      return '请使用微信扫一扫登录'
  }
})

const statusType = computed(() => {
  switch (loginStatus.value) {
    case 'authorized':
      return 'success'
    case 'rejected':
    case 'expired':
      return 'error'
    case 'scanned':
      return 'info'
    default:
      return ''
  }
})

const statusIcon = computed(() => {
  switch (loginStatus.value) {
    case 'authorized':
      return '✓'
    case 'rejected':
    case 'expired':
      return '✗'
    case 'scanned':
      return '⏳'
    default:
      return ''
  }
})

// 清理定时器
function clearTimers() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 开始倒计时
function startCountdown(seconds: number) {
  countdown.value = seconds
  countdownTimer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) {
      if (countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
      loginStatus.value = 'expired'
      statusMessage.value = '二维码已过期，请刷新'
      if (pollTimer) {
        clearInterval(pollTimer)
        pollTimer = null
      }
    }
  }, 1000)
}

// 轮询登录状态
function startPolling() {
  pollTimer = setInterval(async () => {
    if (!sceneId.value || loginStatus.value === 'authorized' || loginStatus.value === 'rejected') {
      return
    }
    
    try {
      const response = await getWechatLoginStatus(sceneId.value)
      const data = response.data
      
      // 更新状态
      if (data.status !== loginStatus.value) {
        loginStatus.value = data.status
        statusMessage.value = data.message
        
        // 根据状态处理
        switch (data.status) {
          case 'authorized':
            // 授权成功，停止轮询，换取 token
            if (pollTimer) {
              clearInterval(pollTimer)
              pollTimer = null
            }
            if (countdownTimer) {
              clearInterval(countdownTimer)
              countdownTimer = null
            }
            // 登录
            await handleLogin(data.auth_code!)
            break
            
          case 'rejected':
            // 用户拒绝
            if (pollTimer) {
              clearInterval(pollTimer)
              pollTimer = null
            }
            break
            
          case 'expired':
            // 二维码过期
            if (pollTimer) {
              clearInterval(pollTimer)
              pollTimer = null
            }
            if (countdownTimer) {
              clearInterval(countdownTimer)
              countdownTimer = null
            }
            countdown.value = 0
            break
        }
      }
    } catch (err) {
      console.error('轮询登录状态失败:', err)
    }
  }, 2000) // 每2秒轮询一次
}

// 处理登录
async function handleLogin(authCode: string) {
  try {
    const response = await wechatQRLogin(authCode)
    const data = response.data
    
    // 保存登录数据
    saveAuthData(data)
    
    // 调用成功回调
    if (props.onSuccess) {
      props.onSuccess(data)
    }
    
    // 跳转到首页
    router.push('/')
  } catch (err: any) {
    const message = err.response?.data?.detail || '登录失败，请重试'
    statusMessage.value = message
    loginStatus.value = ''
    console.error('登录失败:', err)
  }
}

// 保存登录数据
function saveAuthData(data: LoginResponse) {
  const token = `${data.id}:${data.device_id}:${data.access_token}`
  localStorage.setItem('token', token)
  localStorage.setItem('refresh_token', data.refresh_token)
  localStorage.setItem('user_id', String(data.id))
  localStorage.setItem('device_id', data.device_id)
  localStorage.setItem('user_code', data.user_id)
  localStorage.setItem('is_first_login', String(data.is_first_login))
}

// 生成二维码
async function generateQRCode() {
  clearTimers()
  
  loading.value = true
  error.value = ''
  qrCodeUrl.value = ''
  sceneId.value = ''
  countdown.value = 0
  loginStatus.value = ''
  statusMessage.value = ''
  
  try {
    const response = await createWechatQRCode()
    const data = response.data
    
    qrCodeUrl.value = data.qr_code_url
    sceneId.value = data.scene_id
    loginStatus.value = 'pending'
    
    // 开始倒计时
    startCountdown(data.expire_seconds)
    
    // 开始轮询
    startPolling()
  } catch (err: any) {
    const message = err.response?.data?.detail || '生成二维码失败，请重试'
    error.value = message
    console.error('生成二维码失败:', err)
  } finally {
    loading.value = false
  }
}

// 组件挂载时自动生成二维码
onMounted(() => {
  generateQRCode()
})

// 组件卸载时清理定时器
onUnmounted(() => {
  clearTimers()
})

// 暴露方法给父组件
defineExpose({
  generateQRCode
})
</script>

<style scoped>
.wechat-qr-login {
  text-align: center;
}

.qr-description {
  margin: 0 0 16px;
  font-size: 0.875rem;
  color: #64748b;
}

.qr-container {
  width: 200px;
  height: 200px;
  margin: 0 auto 16px;
  border-radius: 8px;
  overflow: hidden;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.qr-loading {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: #64748b;
  font-size: 0.875rem;
}

.qr-error {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  color: #64748b;
}

.error-icon {
  font-size: 32px;
}

.qr-error p {
  margin: 0;
  font-size: 0.8rem;
}

.btn-retry {
  padding: 6px 12px;
  border: none;
  border-radius: 6px;
  background: #3b82f6;
  color: #fff;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-retry:hover {
  background: #2563eb;
}

.qr-image-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
}

.qr-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.qr-expired-overlay {
  position: absolute;
  inset: 0;
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  align-items: center;
  justify-content: center;
}

.expired-content {
  text-align: center;
}

.expired-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.expired-content p {
  margin: 0 0 12px;
  color: #64748b;
  font-size: 0.875rem;
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: #07c160;
  color: #fff;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-refresh:hover {
  background: #06ad56;
}

.qr-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 16px;
  color: #64748b;
}

.placeholder-icon {
  color: #cbd5e1;
}

.qr-placeholder p {
  margin: 0;
  font-size: 0.8rem;
}

.btn-generate {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  background: #07c160;
  color: #fff;
  font-size: 0.875rem;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-generate:hover {
  background: #06ad56;
}

.status-message {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 0.875rem;
  margin-bottom: 12px;
}

.status-message.success {
  background: #dcfce7;
  color: #166534;
}

.status-message.error {
  background: #fee2e2;
  color: #991b1b;
}

.status-message.info {
  background: #dbeafe;
  color: #1e40af;
}

.status-icon {
  font-weight: bold;
}

.countdown {
  font-size: 0.75rem;
  color: #94a3b8;
  margin-bottom: 12px;
}

.btn-refresh-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #64748b;
  font-size: 0.75rem;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-refresh-inline:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
