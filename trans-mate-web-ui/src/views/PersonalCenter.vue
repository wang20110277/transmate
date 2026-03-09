<template>
  <div class="personal-center">
    <AppHeader :user-name="userStore.userInfo?.nickname || userStore.userInfo?.username || '用户'" @logout="handleLogout" />

    <div class="page-content">
      <div class="page-header">
        <h1 class="page-title">个人中心</h1>
        <p class="page-subtitle">管理您的个人信息和账户安全</p>
      </div>

      <div class="content-card">
        <el-tabs v-model="activeTab" class="center-tabs">
          <!-- 基本信息 -->
          <el-tab-pane label="基本信息" name="basic">
            <div class="info-section">
              <h3 class="section-title">个人信息</h3>

              <div class="info-list">
                <div class="info-item">
                  <span class="info-label">手机号</span>
                  <span class="info-value">{{ maskedPhone }}</span>
                </div>

                <div class="info-item">
                  <span class="info-label">用户名</span>
                  <span class="info-value">{{ userInfo.username || '-' }}</span>
                </div>

                <div class="info-item">
                  <span class="info-label">昵称</span>
                  <div class="info-value-with-action">
                    <span class="info-value">{{ userInfo.nickname || '未设置' }}</span>
                    <el-button
                      type="primary"
                      link
                      size="small"
                      :icon="Edit"
                      @click="showNicknameDialog = true"
                    >
                      修改
                    </el-button>
                  </div>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 安全信息 -->
          <el-tab-pane label="安全信息" name="security">
            <div class="info-section">
              <h3 class="section-title">账户安全</h3>

              <div class="info-list">
                <div class="info-item">
                  <span class="info-label">登录密码</span>
                  <div class="info-value-with-action">
                    <span class="info-value">{{ userInfo.is_password_set ? '已设置' : '未设置' }}</span>
                    <el-button
                      type="primary"
                      link
                      size="small"
                      @click="showPasswordDialog = true"
                    >
                      {{ userInfo.is_password_set ? '修改' : '设置' }}
                    </el-button>
                  </div>
                </div>
              </div>

              <div class="security-hint">
                <el-alert
                  title="安全提示"
                  description="建议定期更换密码，并确保密码强度足够，以保护您的账户安全。"
                  type="info"
                  :closable="false"
                  show-icon
                />
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <!-- 昵称编辑弹窗 -->
      <NicknameEditDialog
        v-model="showNicknameDialog"
        :current-nickname="userInfo.nickname"
        @success="handleNicknameSuccess"
      />

      <!-- 密码修改弹窗 -->
      <PasswordChangeDialog
        v-model="showPasswordDialog"
        @success="handlePasswordSuccess"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Edit } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { getCurrentUser } from '@/services/api'
import NicknameEditDialog from '@/components/NicknameEditDialog.vue'
import PasswordChangeDialog from '@/components/PasswordChangeDialog.vue'
import AppHeader from '@/components/AppHeader.vue'

const userStore = useUserStore()
const router = useRouter()

const activeTab = ref('basic')
const showNicknameDialog = ref(false)
const showPasswordDialog = ref(false)

// 用户信息
const userInfo = computed(() => {
  return userStore.userInfo || {
    username: '',
    nickname: '',
    phone: '',
    is_password_set: false
  }
})

// 手机号脱敏显示
const maskedPhone = computed(() => {
  const phone = userInfo.value.phone
  if (!phone) return '-'
  if (phone.length !== 11) return phone
  return phone.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2')
})

// 昵称修改成功
const handleNicknameSuccess = async (nickname: string) => {
  // 更新本地用户信息
  if (userStore.userInfo) {
    userStore.userInfo.nickname = nickname
  }
  // 重新获取用户信息
  await refreshUserInfo()
}

// 密码修改成功
const handlePasswordSuccess = () => {
  // 密码修改后会提示重新登录，这里不需要额外处理
}

// 处理登出
const handleLogout = async () => {
  await userStore.logoutUser()
  router.push('/login')
}

// 刷新用户信息
const refreshUserInfo = async () => {
  try {
    const response = await getCurrentUser()
    userStore.userInfo = response.data
  } catch (error) {
    console.error('获取用户信息失败:', error)
  }
}

onMounted(() => {
  // 如果 store 中没有用户信息，则获取
  if (!userStore.userInfo) {
    refreshUserInfo()
  }
})
</script>

<style scoped>
.personal-center {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ed 100%);
}

.page-content {
  padding: 24px;
}

.page-header {
  max-width: 800px;
  margin: 0 auto 24px;
  text-align: center;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 8px 0;
}

.page-subtitle {
  font-size: 14px;
  color: #909399;
  margin: 0;
}

.content-card {
  max-width: 800px;
  margin: 0 auto;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
  padding: 24px;
}

.center-tabs :deep(.el-tabs__header) {
  margin-bottom: 24px;
  border-bottom: 1px solid #ebeef5;
}

.center-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background-color: #ebeef5;
}

.center-tabs :deep(.el-tabs__item) {
  font-size: 15px;
  font-weight: 500;
  color: #606266;
  padding: 0 24px;
  height: 44px;
  line-height: 44px;
}

.center-tabs :deep(.el-tabs__item.is-active) {
  color: #409eff;
}

.center-tabs :deep(.el-tabs__active-bar) {
  height: 2px;
  background-color: #409eff;
}

.info-section {
  padding: 8px 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 20px 0;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid #f0f2f5;
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  min-width: 80px;
}

.info-value {
  font-size: 14px;
  color: #303133;
}

.info-value-with-action {
  display: flex;
  align-items: center;
  gap: 16px;
}

.security-hint {
  margin-top: 24px;
}

/* 响应式 */
@media (max-width: 768px) {
  .page-content {
    padding: 16px;
  }

  .content-card {
    padding: 16px;
  }

  .page-title {
    font-size: 24px;
  }

  .center-tabs :deep(.el-tabs__item) {
    padding: 0 16px;
    font-size: 14px;
  }
}
</style>
