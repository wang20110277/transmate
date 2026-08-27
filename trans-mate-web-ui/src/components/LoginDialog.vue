<template>
  <el-dialog
    v-model="visible"
    :title="registerMode ? t('home.registerTitle') : t('home.loginTitle')"
    width="400px"
    :close-on-click-modal="false"
    class="login-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent
    >
      <el-form-item :label="t('home.phoneLabel')" prop="phone">
        <el-input
          v-model="form.phone"
          :placeholder="t('home.phonePlaceholder')"
          maxlength="11"
          clearable
        >
          <template #prefix><i class="fas fa-mobile-screen"></i></template>
        </el-input>
      </el-form-item>
      <el-form-item :label="t('home.passwordLabel')" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          :placeholder="t('home.passwordPlaceholder')"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>
      <el-form-item
        v-if="registerMode"
        :label="t('home.confirmPasswordLabel')"
        prop="confirmPassword"
      >
        <el-input
          v-model="form.confirmPassword"
          type="password"
          :placeholder="t('home.confirmPasswordPlaceholder')"
          show-password
          @keyup.enter="handleLogin"
        />
      </el-form-item>
    </el-form>

    <!-- 首次登录（新手机号）需确认密码，由后端登录/注册一体接口自动注册 -->
    <div class="login-switch">
      <a href="#" @click.prevent="toggleRegister">
        {{ registerMode ? t('home.backToLogin') : t('home.firstLoginLink') }}
      </a>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleCancel">{{ t('home.cancel') }}</el-button>
        <el-button type="primary" :loading="loading" @click="handleLogin">
          {{ registerMode ? t('home.registerButton') : t('home.loginButton') }}
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { useI18n } from '@/i18n'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': []
}>()

const { t } = useI18n()
const userStore = useUserStore()

const visible = ref(props.modelValue)
const loading = ref(false)
const registerMode = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  phone: '',
  password: '',
  confirmPassword: ''
})

// 验证规则（与后端 PasswordLoginRequest 约束一致：手机号 ^1\d{10}$，密码 ≥6 位）
const rules = computed<FormRules>(() => ({
  phone: [
    { required: true, message: t('home.phoneRequired'), trigger: 'blur' },
    { pattern: /^1\d{10}$/, message: t('home.phoneInvalid'), trigger: 'blur' }
  ],
  password: [
    { required: true, message: t('home.passwordRequired'), trigger: 'blur' },
    { min: 6, message: t('home.passwordTooShort'), trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: t('home.confirmPasswordRequired'), trigger: 'blur' },
    {
      validator: (_rule: any, value: string, callback: Function) => {
        if (registerMode.value && value !== form.password) {
          callback(new Error(t('home.passwordMismatch')))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}))

// 监听 props.modelValue 变化
watch(
  () => props.modelValue,
  (newVal) => {
    visible.value = newVal
    if (newVal) resetForm()
  }
)

// 监听 visible 变化，同步到父组件
watch(
  () => visible.value,
  (newVal) => {
    emit('update:modelValue', newVal)
  }
)

const resetForm = () => {
  form.phone = ''
  form.password = ''
  form.confirmPassword = ''
  registerMode.value = false
  formRef.value?.clearValidate()
}

const toggleRegister = () => {
  registerMode.value = !registerMode.value
  formRef.value?.clearValidate()
}

const handleCancel = () => {
  visible.value = false
  resetForm()
}

const handleLogin = async () => {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await userStore.loginWithPassword(
        form.phone.trim(),
        form.password,
        registerMode.value ? form.confirmPassword : undefined
      )
      ElMessage.success(t('home.loginSuccess'))
      visible.value = false
      resetForm()
      emit('success')
    } catch (error: any) {
      // 透出后端 detail（如"密码错误"/"首次登录需要确认密码"）供用户自纠
      ElMessage.error(error?.response?.data?.detail || t('home.loginFailed'))
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.login-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 10px;
}

.login-switch {
  display: flex;
  justify-content: center;
  margin-top: 2px;
}

.login-switch a {
  font-size: 13px;
  color: var(--color-primary, #2563eb);
  text-decoration: none;
  cursor: pointer;
}

.login-switch a:hover {
  text-decoration: underline;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
