<template>
  <el-dialog
    v-model="visible"
    title="修改昵称"
    width="400px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    class="nickname-edit-dialog"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent
    >
      <el-form-item label="昵称" prop="nickname">
        <el-input
          v-model="form.nickname"
          placeholder="请输入昵称（最多10个字符）"
          maxlength="10"
          show-word-limit
          clearable
        />
        <div class="form-hint">支持中英文、数字和表情符号</div>
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
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { updateNickname } from '@/services/api'

const props = defineProps<{
  modelValue: boolean
  currentNickname?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'success': [nickname: string]
}>()

const visible = ref(props.modelValue)
const loading = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  nickname: ''
})

// 验证规则
const rules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    {
      validator: (rule: any, value: string, callback: Function) => {
        if (!value || !value.trim()) {
          callback(new Error('昵称不能为空'))
        } else if (value.length > 10) {
          callback(new Error('昵称最多10个字符'))
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
      // 打开时填充当前昵称
      form.nickname = props.currentNickname || ''
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
  form.nickname = ''
  formRef.value?.resetFields()
}

// 保存
const handleSave = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    const nickname = form.nickname.trim()
    if (!nickname) {
      ElMessage.warning('昵称不能为空')
      return
    }

    loading.value = true
    try {
      await updateNickname(nickname)
      ElMessage.success('昵称修改成功')
      emit('success', nickname)
      visible.value = false
      form.nickname = ''
    } catch (error: any) {
      const message = error.response?.data?.detail || '昵称修改失败，请重试'
      ElMessage.error(message)
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped>
.nickname-edit-dialog :deep(.el-dialog__body) {
  padding: 20px 24px 10px;
}

.form-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 6px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
