import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrentUser, logout, passwordLogin } from '@/services/api'

export interface UserInfo {
  id: number
  user_id: string
  nickname?: string
  avatar_url?: string
  phone?: string
  role: string
  is_password_set: boolean
}

export const useUserStore = defineStore('user', () => {
  // State
  const userInfo = ref<UserInfo | null>(null)
  const isLoading = ref(false)
  const isFirstLogin = ref(false)

  // Getters
  const isLoggedIn = computed(() => !!userInfo.value)
  const token = computed(() => localStorage.getItem('token'))
  const deviceId = computed(() => localStorage.getItem('device_id'))

  // Actions
  const setUserInfo = (info: UserInfo | null) => {
    userInfo.value = info
  }

  // 手机号密码登录(后端登录/注册一体:新手机号带 confirmPassword 自动注册)
  const loginWithPassword = async (
    phone: string,
    password: string,
    confirmPassword?: string
  ): Promise<void> => {
    const response = await passwordLogin(phone, password, confirmPassword)
    const { id, access_token, refresh_token, device_id, user_id, is_first_login } = response.data
    localStorage.setItem('token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('device_id', device_id)
    localStorage.setItem('user_id', user_id)
    localStorage.setItem('uid', String(id))
    localStorage.setItem('is_first_login', String(is_first_login))
    isFirstLogin.value = is_first_login
    await fetchUserInfo()
  }

  const fetchUserInfo = async (): Promise<boolean> => {
    if (!token.value) return false

    isLoading.value = true
    try {
      const response = await getCurrentUser()
      userInfo.value = response.data
      return true
    } catch (error) {
      console.error('获取用户信息失败:', error)
      // Token无效，清除登录状态
      clearAuth()
      return false
    } finally {
      isLoading.value = false
    }
  }

  const logoutUser = async (): Promise<void> => {
    const deviceIdVal = deviceId.value
    if (deviceIdVal) {
      try {
        await logout(deviceIdVal)
      } catch (error) {
        console.error('登出失败:', error)
      }
    }
    clearAuth()
  }

  const clearAuth = () => {
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('device_id')
    localStorage.removeItem('user_id')
    localStorage.removeItem('uid')
    localStorage.removeItem('is_first_login')
  }

  const initFromStorage = () => {
    const firstLogin = localStorage.getItem('is_first_login')
    if (firstLogin) {
      isFirstLogin.value = firstLogin === 'true'
    }
  }

  return {
    userInfo,
    isLoading,
    isFirstLogin,
    isLoggedIn,
    token,
    deviceId,
    setUserInfo,
    loginWithPassword,
    fetchUserInfo,
    logoutUser,
    clearAuth,
    initFromStorage
  }
})
