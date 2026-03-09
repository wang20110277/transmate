<template>
  <div class="login-page">
    <div class="login-bg">
      <div class="login-bg-shape shape-1"></div>
      <div class="login-bg-shape shape-2"></div>
      <div class="login-bg-shape shape-3"></div>
    </div>

    <div class="login-card">
      <div class="login-header">
        <img src="/icons/trans.svg" alt="logo" class="login-logo" />
        <h1 class="login-title">AI智能助手</h1>
        <p class="login-subtitle">登录后使用专属理财助手</p>
      </div>

      <!-- 登录方式切换 -->
      <div class="login-tabs">
        <button
          type="button"
          :class="['login-tab', { active: loginMode === 'wechat' }]"
          @click="loginMode = 'wechat'"
        >
          <span class="login-tab-icon">
            <el-icon><ChatDotRound /></el-icon>
          </span>
          微信登录
        </button>
        <button
          type="button"
          :class="['login-tab', { active: loginMode === 'code' }]"
          @click="loginMode = 'code'"
        >
          <span class="login-tab-icon">
            <el-icon><Message /></el-icon>
          </span>
          验证码登录
        </button>
        <button
          type="button"
          :class="['login-tab', { active: loginMode === 'pwd' }]"
          @click="loginMode = 'pwd'"
        >
          <span class="login-tab-icon">
            <el-icon><Lock /></el-icon>
          </span>
          密码登录
        </button>
      </div>

      <!-- 微信登录 -->
      <div v-if="loginMode === 'wechat'" class="login-mode-content">
        <WeChatQRLogin ref="wechatQRRef" :on-success="saveAuthData" />
      </div>
      <!-- 手机号登录 -->
      <div v-else class="login-mode-content">
        <p v-if="loginMode === 'code'" class="mode-description">使用验证码快速登录/注册</p>
        <p v-else class="mode-description">使用密码登录您的账号</p>
        <div class="login-form">
          <div class="form-group">
            <label class="form-label">手机号</label>
            <div class="input-wrap">
              <span class="input-prefix">+86</span>
              <input
                v-model="phone"
                type="tel"
                class="form-input"
                placeholder="请输入手机号"
                maxlength="11"
                autocomplete="tel"
                :disabled="loading"
              />
            </div>
          </div>

          <div v-if="loginMode === 'code'" class="form-group">
            <label class="form-label">验证码</label>
            <div class="input-wrap input-wrap-suffix">
              <input
                v-model="code"
                type="text"
                class="form-input"
                placeholder="请输入验证码"
                maxlength="6"
                autocomplete="one-time-code"
                :disabled="loading"
              />
              <button
                type="button"
                class="btn-code"
                :disabled="countdown > 0 || loading"
                @click="sendCode"
              >
                {{ countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </button>
            </div>
          </div>

          <div v-else class="form-group">
            <label class="form-label">密码</label>
            <div class="input-wrap">
              <input
                v-model="password"
                :type="showPwd ? 'text' : 'password'"
                class="form-input"
                placeholder="请输入密码"
                autocomplete="current-password"
                :disabled="loading"
              />
              <button
                type="button"
                class="btn-toggle-pwd"
                :aria-label="showPwd ? '隐藏密码' : '显示密码'"
                @click="showPwd = !showPwd"
              >
                <i :class="showPwd ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
          </div>

          <!-- 密码登录时的确认密码（首次注册） -->
          <div v-if="loginMode === 'pwd' && showConfirmPassword" class="form-group">
            <label class="form-label">确认密码</label>
            <div class="input-wrap">
              <input
                v-model="confirmPassword"
                :type="showConfirmPwd ? 'text' : 'password'"
                class="form-input"
                placeholder="请确认密码"
                autocomplete="new-password"
                :disabled="loading"
              />
              <button
                type="button"
                class="btn-toggle-pwd"
                :aria-label="showConfirmPwd ? '隐藏密码' : '显示密码'"
                @click="showConfirmPwd = !showConfirmPwd"
              >
                <i :class="showConfirmPwd ? 'fas fa-eye-slash' : 'fas fa-eye'"></i>
              </button>
            </div>
            <p class="form-hint">首次登录请设置密码</p>
          </div>

          <button
            type="button"
            class="btn-submit"
            :disabled="!canSubmit || loading"
            @click="onPhoneSubmit"
          >
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>{{ loginMode === 'code' ? '登录 / 注册' : '登录' }}</span>
          </button>
        </div>
      </div>

      <p class="login-agree">
        登录即表示同意
        <a href="#" class="link">《用户协议》</a>
        与
        <a href="#" class="link">《隐私政策》</a>
      </p>
    </div>

    <!-- Footer with copyright, ICP, and links -->
    <footer class="main-footer">
      <div class="footer-content">
        <div class="footer-info">
          <p class="copyright">Copyright &copy; 2026 https://www.trans.com All rights reserved</p>
          <p class="rights">版权所有 &copy; 2026 北京传思科技有限公司 保留所有权利</p>
          <p class="icp">京ICP备XXXXXXXX号</p>
        </div>
        <div class="footer-links">
          <a href="#" class="footer-link">隐私政策</a>
          <a href="#" class="footer-link">服务条款</a>
          <a href="#" class="footer-link">联系我们</a>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { wechatLogin, sendSMSCode, smsLogin, passwordLogin } from '@/services/api'
import { ElMessageBox } from 'element-plus'
import { ChatDotRound, Message, Lock } from '@element-plus/icons-vue'
import WeChatQRLogin from '@/components/WeChatQRLogin.vue'
import type { LoginResponse } from '@/services/api'

const router = useRouter()

const loginMode = ref<'wechat' | 'code' | 'pwd'>('wechat')
const wechatQRRef = ref<InstanceType<typeof WeChatQRLogin> | null>(null)
const phone = ref('')
const code = ref('')
const password = ref('')
const confirmPassword = ref('')
const showPwd = ref(false)
const showConfirmPwd = ref(false)
const showConfirmPassword = ref(false)
const countdown = ref(0)
const loading = ref(false)
let countdownTimer: ReturnType<typeof setInterval> | null = null
const canSubmit = computed(() => {
  const validPhone = /^1\d{10}$/.test(phone.value)
  if (loginMode.value === 'code') {
    return validPhone && code.value.length >= 4
  }
  if (showConfirmPassword.value) {
    return validPhone && password.value.length >= 6 && confirmPassword.value.length >= 6
  }
  return validPhone && password.value.length >= 6
})

// 存储登录凭证
const saveAuthData = (data: {
  id: number
  username: string
  access_token: string
  refresh_token: string
  device_id: string
  is_first_login: boolean
}) => {
  // Token格式: user_id:device_id:access_token
  const token = `${data.id}:${data.device_id}:${data.access_token}`
  localStorage.setItem('token', token)
  localStorage.setItem('refresh_token', data.refresh_token)
  localStorage.setItem('user_id', String(data.id))
  localStorage.setItem('device_id', data.device_id)
  localStorage.setItem('username', data.username)
  localStorage.setItem('is_first_login', String(data.is_first_login))
}

// 发送验证码
async function sendCode() {
  if (!/^1\d{10}$/.test(phone.value)) {
    alert('请输入正确的手机号')
    return
  }
  if (countdown.value > 0 || loading.value) return

  loading.value = true
  try {
    const response = await sendSMSCode(phone.value)
    alert('验证码已发送，请查收')
    
    // 开始倒计时
    countdown.value = 60
    countdownTimer = setInterval(() => {
      countdown.value--
      if (countdown.value <= 0 && countdownTimer) {
        clearInterval(countdownTimer)
        countdownTimer = null
      }
    }, 1000)
  } catch (error: any) {
    const message = error.response?.data?.detail || '发送验证码失败，请重试'
    alert('发送失败: ' + message)
  } finally {
    loading.value = false
  }
}

function switchToWechat() {
  loginMode.value = 'wechat'
  // 组件会自动处理二维码生成
}

// 微信登录（旧版，已废弃，保留兼容性）
async function onWechatLogin() {
  // 新流程已迁移到 WeChatQRLogin 组件
  console.warn('请使用 WeChatQRLogin 组件')
}

// 手机号登录提交
async function onPhoneSubmit() {
  if (!canSubmit.value || loading.value) return

  loading.value = true
  try {
    if (loginMode.value === 'code') {
      // 短信验证码登录
      const response = await smsLogin(phone.value, code.value)
      saveAuthData(response.data)
      router.push('/')
    } else {
      // 密码登录
      try {
        const response = await passwordLogin(
          phone.value,
          password.value,
          showConfirmPassword.value ? confirmPassword.value : undefined
        )
        saveAuthData(response.data)
        router.push('/')
      } catch (error: any) {
        // 检查是否是首次登录（需要确认密码）
        const detail = error.response?.data?.detail
        if (detail === '首次登录需要确认密码' || detail === '请设置密码（输入确认密码）') {
          showConfirmPassword.value = true
          ElMessageBox.alert('首次登录，请确认密码', '提示', {
            confirmButtonText: '确定',
            type: 'info',
            center: true,
            customClass: 'custom-message-box',
            showClose: false,
            closeOnClickModal: false,
            closeOnPressEscape: false
          })
        } else {
          throw error
        }
      }
    }
  } catch (error: any) {
    const message = error.response?.data?.detail || '登录失败，请重试'
    ElMessageBox.alert(message, '登录失败', {
      confirmButtonText: '确定',
      type: 'error',
      center: true,
      customClass: 'custom-message-box error-box',
      showClose: false,
      closeOnClickModal: false,
      closeOnPressEscape: false
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px;
  font-family: "Noto Sans SC", "Helvetica Neue", sans-serif;
  position: relative;
  overflow-x: hidden;
}

.login-bg {
  position: absolute;
  inset: 0;
  background: linear-gradient(145deg, #0f172a 0%, #1e293b 40%, #334155 100%);
  z-index: 0;
}

.login-bg-shape {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}

.shape-1 {
  width: 400px;
  height: 400px;
  background: #3b82f6;
  top: -120px;
  right: -80px;
}

.shape-2 {
  width: 300px;
  height: 300px;
  background: #8b5cf6;
  bottom: 20%;
  left: -100px;
}

.shape-3 {
  width: 200px;
  height: 200px;
  background: #06b6d4;
  bottom: -50px;
  right: 20%;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 20px;
  padding: 40px 36px;
  margin-top: auto;
  margin-bottom: auto;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.35);
  backdrop-filter: blur(12px);
}

.login-header {
  text-align: center;
  margin-bottom: 28px;
}

.login-logo {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
}

.login-title {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.login-subtitle {
  margin: 8px 0 0;
  font-size: 0.875rem;
  color: #64748b;
}

.login-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  background: #f1f5f9;
  border-radius: 12px;
  padding: 4px;
}

.login-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 12px 8px;
  border: none;
  border-radius: 10px;
  background: transparent;
  font-size: 0.85rem;
  color: #64748b;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.login-tab.active {
  background: #fff;
  color: #0f172a;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.login-tab-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-mode-content {
  margin-bottom: 20px;
}

.mode-description {
  margin: 0 0 16px;
  font-size: 0.875rem;
  color: #64748b;
  text-align: center;
}

.btn-wechat {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  height: 48px;
  border: none;
  border-radius: 12px;
  background: #07c160;
  color: #fff;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, transform 0.15s;
}

.btn-wechat:hover:not(:disabled) {
  background: #06ad56;
  transform: translateY(-1px);
}

.btn-wechat:active {
  transform: translateY(0);
}

.btn-wechat:disabled {
  background: #9ca3af;
  cursor: not-allowed;
  transform: none;
}

.btn-wechat-icon {
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-form {
  margin-bottom: 0;
}

.form-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: #f1f5f9;
  border-radius: 10px;
  padding: 4px;
}

.form-tab {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-size: 0.875rem;
  color: #64748b;
  cursor: pointer;
  transition: background 0.2s, color 0.2s;
}

.form-tab.active {
  background: #fff;
  color: #0f172a;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

.form-group {
  margin-bottom: 18px;
}

.form-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.8125rem;
  font-weight: 500;
  color: #475569;
}

.input-wrap {
  display: flex;
  align-items: center;
  height: 48px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.input-wrap:focus-within {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
}

.input-prefix {
  padding: 0 14px;
  font-size: 0.9375rem;
  color: #64748b;
  border-right: 1px solid #e2e8f0;
}

.input-wrap-suffix {
  padding-right: 4px;
}

.form-input {
  flex: 1;
  min-width: 0;
  padding: 0 14px;
  border: none;
  background: transparent;
  font-size: 0.9375rem;
  color: #0f172a;
  outline: none;
}

.form-input::placeholder {
  color: #94a3b8;
}

.form-input:disabled {
  color: #64748b;
  cursor: not-allowed;
}

.form-hint {
  margin: 6px 0 0;
  font-size: 0.75rem;
  color: #64748b;
}

.btn-code {
  padding: 0 14px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: #f1f5f9;
  font-size: 0.8125rem;
  color: #3b82f6;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}

.btn-code:hover:not(:disabled) {
  background: #e2e8f0;
}

.btn-code:disabled {
  color: #94a3b8;
  cursor: not-allowed;
}

.btn-toggle-pwd {
  padding: 0 14px;
  height: 100%;
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
}

.btn-submit {
  width: 100%;
  height: 48px;
  margin-top: 8px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, #2563eb 0%, #3b82f6 100%);
  color: #fff;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s, transform 0.15s;
}

.btn-submit:hover:not(:disabled) {
  opacity: 0.95;
  transform: translateY(-1px);
}

.btn-submit:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  transform: none;
}

.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.login-agree {
  margin: 0;
  font-size: 0.75rem;
  color: #94a3b8;
  text-align: center;
  line-height: 1.5;
}

.login-agree .link {
  color: #3b82f6;
  text-decoration: none;
}

.login-agree .link:hover {
  text-decoration: underline;
}

/* Footer 样式 */
.main-footer {
  background: rgba(255, 255, 255, 0.08);
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  padding: 1rem 1.25rem;
  margin-top: auto;
  width: 100%;
  backdrop-filter: blur(10px);
}

.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
}

.copyright,
.rights,
.icp {
  margin: 0;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.8125rem;
}

.icp {
  margin-top: 4px;
}

.footer-links {
  display: flex;
  gap: 1.25rem;
}

.footer-link {
  color: rgba(255, 255, 255, 0.6);
  text-decoration: none;
  font-size: 0.8125rem;
  transition: color 0.2s ease;
}

.footer-link:hover {
  color: #fff;
}

@media (max-width: 768px) {
  .footer-content {
    flex-direction: column;
    text-align: center;
  }
}

@media (max-width: 480px) {
  .login-card {
    padding: 28px 24px;
  }

  .login-title {
    font-size: 1.4rem;
  }

  .login-tab {
    font-size: 0.8rem;
    padding: 10px 4px;
  }
}

/* Element Plus MessageBox 样式优化 */
:global(.custom-message-box) {
  border-radius: 16px !important;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25) !important;
  border: none !important;
}

:global(.custom-message-box .el-message-box__header) {
  padding: 24px 24px 16px !important;
}

:global(.custom-message-box .el-message-box__title) {
  font-size: 1.25rem !important;
  font-weight: 600 !important;
}

:global(.custom-message-box .el-message-box__content) {
  padding: 16px 24px 24px !important;
  font-size: 1rem !important;
  color: #334155 !important;
}

:global(.custom-message-box .el-message-box__btns) {
  padding: 16px 24px 24px !important;
}

:global(.custom-message-box .el-button--primary) {
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
  border: none !important;
  border-radius: 8px !important;
  padding: 10px 24px !important;
  font-size: 0.95rem !important;
  font-weight: 500 !important;
  transition: all 0.3s ease !important;
}

:global(.custom-message-box .el-button--primary:hover) {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 20px rgba(59, 130, 246, 0.4) !important;
}

:global(.error-box .el-button--primary) {
  background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%) !important;
}

:global(.error-box .el-button--primary:hover) {
  box-shadow: 0 8px 20px rgba(239, 68, 68, 0.4) !important;
}

:global(.custom-message-box .el-message-box__status) {
  font-size: 48px !important;
}

:global(.custom-message-box.el-message-box--center .el-message-box__status) {
  margin-bottom: 16px !important;
}

/* 响应式优化 */
@media (max-width: 480px) {
  :global(.custom-message-box) {
    width: 90% !important;
    max-width: 320px !important;
  }
}
</style>
