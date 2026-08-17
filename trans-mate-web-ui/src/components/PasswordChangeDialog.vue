<template>
  <el-dialog
    v-model="visible"
    title="修改密码"
    width="400px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    class="password-change-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent
    >
      <el-form-item label="新密码" prop="newPassword">
        <el-input
          v-model="form.newPassword"
          type="password"
          placeholder="请输入新密码（至少6位）"
          show-password
          clearable
        />
      </el-form-item>

      <el-form-item label="确认密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="请再次输入新密码"
          show-password
          clearable
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSave">
          保存
        </el-button>
      </div>
    </template>
  </el-dialog>

  <!-- 重新登录提示弹窗 -->
  <el-dialog
    v-model="reloginVisible"
    title="密码修改成功"
    width="360px"
    :show-close="false"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    class="relogin-dialog"
  >
    <div class="relogin-content">
      <el-icon class="success-icon" :size="48" color="#67c23a"><CircleCheck /></el-icon>
      <p class="relogin-text">密码修改成功！</p>
      <p class="relogin-hint">请使用新密码重新登录</p>
    </div>
    <template #footer>
      <el-button type="primary" @click="handleRelogin">去登录</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { CircleCheck } from '@element-plus/icons-vue'
import { changePassword } from '@/services/api'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

const visible = ref(props.modelValue)
const reloginVisible = ref(false)
const loading = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  newPassword: '',
  confirmPassword: ''
})

// 验证规则
const rules: FormRules = {
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: Function) => {
        if (value !== form.newPassword) {
          callback(new Error('两次输入的密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

// 监听 props.modelValue 变化
watch(
  () => props.modelValue,
  (newVal) => {
    visible.value = newVal
    if (newVal) {
      // 打开时清空表单
      form.newPassword = ''
      form.confirmPassword = ''
      formRef.value?.resetFields()
    }
  }
)

// 监听 visible 变化，同步到父组件
watch(
  () => visible.value,
  (newVal) => {
    emit('update:modelValue', newVal)
  }
)

// 取消
const handleCancel = () => {
  visible.value = false
  form.newPassword = ''
  form.confirmPassword = ''
  formRef.value?.resetFields()
}

// 保存
const handleSave = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    if (form.newPassword !== form.confirmPassword) {
      ElMessage.error('两次输入的密码不一致')
      return
    }

    loading.value = true
    try {
      await changePassword(
        form.newPassword,
        form.confirmPassword
      )
      emit('success')
      visible.value = false
      // 显示重新登录提示
      reloginVisible.value = true
    } catch (error: any) {
      const message = error.response?.data?.detail || '密码修改失败，请重试'
      ElMessage.error(message)
    } finally {
      loading.value = false
    }
  })
}

// 重新登录
const handleRelogin = () => {
  // 清除登录态
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('user_id')
  localStorage.removeItem('device_id')
  localStorage.removeItem('user_code')

  // 跳转到登录页
  window.location.href = '/login'
}
</script>

<style scoped>
.password-change-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 10px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.relogin-dialog :deep(.el-dialog__body) {
  padding: 10px 24px;
}

.relogin-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 20px 0;
}

.success-icon {
  margin-bottom: 16px;
}

.relogin-text {
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  margin: 0 0 8px 0;
}

.relogin-hint {
  font-size: 14px;
  color: #909399;
  margin: 0;
}
</style>
