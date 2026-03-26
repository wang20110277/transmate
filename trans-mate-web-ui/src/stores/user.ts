import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrentUser, logout } from '@/services/api'

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
    fetchUserInfo,
    logoutUser,
    clearAuth,
    initFromStorage
  }
})
