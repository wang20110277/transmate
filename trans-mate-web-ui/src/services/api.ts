import axios, { type AxiosInstance, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

// API基础配置（连接设置里保存的地址优先，其次环境变量，最后本地默认）
const API_BASE_URL = localStorage.getItem('tm_api_base') || import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// 创建axios实例
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 从localStorage获取token
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
apiClient.interceptors.response.use(
  (response: AxiosResponse) => {
    return response
  },
  async (error) => {
    const originalRequest = error.config

    // 处理401错误（token过期）
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        // 尝试刷新token（uid 是数字型用户 id，user_id 是 trans_xxx 展示串，refresh 接口要数字）
        const refreshToken = localStorage.getItem('refresh_token')
        const userId = localStorage.getItem('uid')
        const deviceId = localStorage.getItem('device_id')

        if (refreshToken && userId && deviceId) {
          const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
            user_id: parseInt(userId),
            device_id: deviceId,
            refresh_token: refreshToken
          })

          const { access_token, refresh_token } = response.data

          // 更新localStorage
          localStorage.setItem('token', access_token)
          localStorage.setItem('refresh_token', refresh_token)

          // 更新原始请求的Authorization header
          originalRequest.headers.Authorization = `Bearer ${access_token}`

          // 重试原始请求
          return apiClient(originalRequest)
        }
      } catch (refreshError) {
        // 刷新失败，清除token
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user_id')
        localStorage.removeItem('device_id')
        localStorage.removeItem('user_id')

        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// ==================== 认证相关接口 ====================

export interface LoginResponse {
  id: number
  user_id: string
  access_token: string
  refresh_token: string
  device_id: string
  is_first_login: boolean
}

export interface SMSCodeResponse {
  message: string
  expires_in: number
}

export interface UserInfo {
  id: number
  user_id: string
  nickname?: string
  avatar_url?: string
  phone?: string
  role: string
  is_password_set: boolean
}

// 微信登录
export const wechatLogin = (code: string, phone?: string): Promise<AxiosResponse<LoginResponse>> => {
  return apiClient.post('/api/auth/wechat/login', { code, phone })
}

// 发送短信验证码
export const sendSMSCode = (phone: string): Promise<AxiosResponse<SMSCodeResponse>> => {
  return apiClient.post('/api/auth/sms/send', { phone })
}

// 短信验证码登录
export const smsLogin = (phone: string, code: string): Promise<AxiosResponse<LoginResponse>> => {
  return apiClient.post('/api/auth/sms/login', { phone, code })
}

// 密码登录
export const passwordLogin = (
  phone: string,
  password: string,
  confirmPassword?: string
): Promise<AxiosResponse<LoginResponse>> => {
  const data: { phone: string; password: string; confirm_password?: string } = {
    phone,
    password
  }
  if (confirmPassword) {
    data.confirm_password = confirmPassword
  }
  return apiClient.post('/api/auth/password/login', data)
}

// 刷新token
export const refreshToken = (
  userId: number,
  deviceId: string,
  refreshToken: string
): Promise<AxiosResponse<{ access_token: string; refresh_token: string }>> => {
  return apiClient.post('/api/auth/refresh', {
    user_id: userId,
    device_id: deviceId,
    refresh_token: refreshToken
  })
}

// 登出
export const logout = (deviceId: string): Promise<AxiosResponse<{ message: string }>> => {
  return apiClient.post('/api/auth/logout', { device_id: deviceId })
}

// 获取当前用户信息
export const getCurrentUser = (): Promise<AxiosResponse<UserInfo>> => {
  return apiClient.get('/api/auth/me')
}

// 修改密码
export const changePassword = (
  newPassword: string,
  confirmPassword: string
): Promise<AxiosResponse<{ message: string }>> => {
  return apiClient.post('/api/auth/password/change', {
    new_password: newPassword,
    confirm_password: confirmPassword
  })
}



// 修改昵称
export const updateNickname = (
  nickname: string
): Promise<AxiosResponse<{ message: string }>> => {
  return apiClient.put('/api/auth/user/nickname', { nickname })
}


// ==================== 微信扫码登录接口 ====================

export interface QRCodeResponse {
  scene_id: string
  qr_code_url: string
  expire_seconds: number
  message: string
}

export interface LoginStatusResponse {
  status: 'pending' | 'scanned' | 'authorized' | 'rejected' | 'expired'
  message: string
  user_info?: {
    openid: string
    nickname: string
    avatar: string
    user_id: number
    is_new: boolean
  }
  auth_code?: string
}

// 生成微信登录二维码
export const createWechatQRCode = (): Promise<AxiosResponse<QRCodeResponse>> => {
  return apiClient.post('/api/auth/wechat/qr-code')
}

// 查询登录状态
export const getWechatLoginStatus = (sceneId: string): Promise<AxiosResponse<LoginStatusResponse>> => {
  return apiClient.get(`/api/auth/wechat/status/${sceneId}`)
}

// 微信扫码登录（用 auth_code 换取 token）
export const wechatQRLogin = (authCode: string): Promise<AxiosResponse<LoginResponse>> => {
  return apiClient.post('/api/auth/wechat/qr-login', { code: authCode })
}

// ==================== 会话（智能体）接口 ====================

export interface Conversation {
  id: number
  user_id: string
  title: string
  created_at?: string
  updated_at?: string
}

export interface ConversationMessage {
  id: number
  conversation_id: number
  role: string
  content: string
  tool_events?: string | null
  created_at?: string
}

// 获取用户会话列表
export const listConversations = (userId: string): Promise<AxiosResponse<Conversation[]>> => {
  return apiClient.get('/api/conversations', { params: { user_id: userId } })
}

// 创建新会话
export const createConversation = (userId: string, title?: string): Promise<AxiosResponse<Conversation>> => {
  return apiClient.post('/api/conversations', { user_id: userId, title: title || '新会话' })
}

// 重命名会话
export const renameConversation = (
  conversationId: number,
  title: string
): Promise<AxiosResponse<Conversation>> => {
  return apiClient.put(`/api/conversations/${conversationId}`, { title })
}

// 删除会话
export const deleteConversation = (conversationId: number): Promise<AxiosResponse<{ message: string }>> => {
  return apiClient.delete(`/api/conversations/${conversationId}`)
}

// 获取会话历史消息
export const listConversationMessages = (
  conversationId: number
): Promise<AxiosResponse<ConversationMessage[]>> => {
  return apiClient.get(`/api/conversations/${conversationId}/messages`)
}

// ==================== 语音转写（ASR）接口 ====================

// 上传录音 blob，返回识别文本
export const transcribeAudio = (audio: Blob): Promise<AxiosResponse<{ success: boolean; text: string }>> => {
  return apiClient.post('/api/asr/transcribe', audio, {
    headers: { 'Content-Type': 'audio/webm' },
    timeout: 60000
  })
}

// 文本合成语音，返回 WAV 音频 blob
export const synthesizeSpeech = (text: string): Promise<AxiosResponse<Blob>> => {
  return apiClient.post('/api/tts/synthesize', { text }, {
    responseType: 'blob',
    timeout: 180000
  })
}

export default apiClient
