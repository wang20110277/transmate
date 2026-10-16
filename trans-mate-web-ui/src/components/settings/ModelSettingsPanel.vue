<template>
  <!-- 作为设置页「模型」分区的内容面板嵌入，标题由设置页头部提供 -->
  <div class="models-page">
    <!-- 当前实际生效的模型（用户配置优先，未配置则平台默认） -->
    <el-card class="current-card" shadow="never">
      <div class="current-row">
        <div class="current-info">
          <span class="current-label">{{ t('settings.models.current') }}</span>
          <span class="current-model">{{ status.active_model || '—' }}</span>
          <el-tag
            size="small"
            effect="plain"
            :type="status.source === 'user' ? 'success' : 'info'"
          >
            {{ status.source === 'user' ? t('settings.models.sourceUser') : t('settings.models.sourceEnv') }}
          </el-tag>
          <span v-if="status.source === 'user'" class="current-from">
            {{ status.active_provider_name }}
          </span>
        </div>
        <el-button size="small" :loading="loading" @click="reload">
          <i class="fas fa-rotate-right"></i>
        </el-button>
      </div>
    </el-card>

    <el-alert
      v-if="!userStore.isLoggedIn"
      type="info"
      :closable="false"
      show-icon
      :title="t('settings.models.needLogin')"
    />

    <el-row v-else :gutter="16">
      <!-- 左：已配置的供应商列表 -->
      <el-col :xs="24" :md="14">
        <el-card>
          <template #header>
            <div class="card-head">
              <span>{{ t('settings.models.listTitle') }}</span>
              <el-button type="primary" size="small" @click="startCreate">
                <i class="fas fa-plus"></i>
                {{ t('settings.models.add') }}
              </el-button>
            </div>
          </template>

          <div v-loading="loading">
            <el-empty
              v-if="!providers.length"
              :description="t('settings.models.empty')"
              :image-size="70"
            />
            <div
              v-for="item in providers"
              :key="item.id"
              :class="['provider-row', { active: item.is_default, off: !item.enabled }]"
            >
              <div class="provider-main">
                <div class="provider-title">
                  <span class="provider-name">{{ item.name }}</span>
                  <el-tag v-if="item.is_default" size="small" type="success" effect="dark">
                    {{ t('settings.models.badgeDefault') }}
                  </el-tag>
                  <el-tag v-if="!item.enabled" size="small" type="info" effect="plain">
                    {{ t('settings.models.badgeDisabled') }}
                  </el-tag>
                </div>
                <div class="provider-url">{{ item.api_url }}</div>
                <div class="provider-meta">
                  <span>
                    {{ t('settings.models.activeModel') }}：<b>{{ item.active_model }}</b>
                  </span>
                  <span class="sep">·</span>
                  <span class="provider-key">{{ item.api_key_masked || '—' }}</span>
                </div>
                <div v-if="item.models.length" class="provider-models">
                  <el-tag
                    v-for="m in item.models"
                    :key="m"
                    size="small"
                    effect="plain"
                    :type="m === item.active_model ? 'primary' : 'info'"
                  >
                    {{ m }}
                  </el-tag>
                </div>
              </div>

              <div class="provider-actions">
                <el-button
                  size="small"
                  :disabled="item.is_default || !item.enabled"
                  @click="onSetDefault(item)"
                >
                  {{ t('settings.models.setDefault') }}
                </el-button>
                <el-button size="small" :loading="testingId === item.id" @click="onTest(item)">
                  {{ t('settings.models.test') }}
                </el-button>
                <el-button size="small" @click="startEdit(item)">
                  {{ t('settings.models.edit') }}
                </el-button>
                <el-button size="small" type="danger" plain @click="onRemove(item)">
                  {{ t('settings.models.remove') }}
                </el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右：新增 / 编辑表单 -->
      <el-col :xs="24" :md="10">
        <el-card>
          <template #header>
            {{ mode === 'edit' ? t('settings.models.edit') : t('settings.models.add') }}
          </template>
          <el-form label-position="top" @submit.prevent>
            <el-form-item :label="t('settings.models.name')" required>
              <el-input v-model="form.name" :placeholder="t('settings.models.namePlaceholder')" />
            </el-form-item>

            <el-form-item :label="t('settings.models.provider')">
              <el-select
                v-model="form.provider"
                filterable
                allow-create
                default-first-option
                style="width: 100%"
              >
                <el-option label="openai（OpenAI 兼容）" value="openai" />
                <el-option label="deepseek" value="deepseek" />
              </el-select>
            </el-form-item>

            <el-form-item :label="t('settings.models.apiUrl')" required>
              <el-input
                v-model="form.api_url"
                :placeholder="t('settings.models.apiUrlPlaceholder')"
              />
            </el-form-item>

            <el-form-item :label="t('settings.models.apiKey')" :required="mode === 'create'">
              <el-input
                v-model="form.api_key"
                type="password"
                show-password
                autocomplete="new-password"
                :placeholder="
                  mode === 'edit'
                    ? t('settings.models.apiKeyKeep')
                    : t('settings.models.apiKeyPlaceholder')
                "
              />
            </el-form-item>

            <el-form-item :label="t('settings.models.modelList')" required>
              <el-select
                v-model="form.models"
                multiple
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                :placeholder="t('settings.models.modelListPlaceholder')"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item :label="t('settings.models.activeModel')">
              <el-select v-model="form.active_model" style="width: 100%">
                <el-option v-for="m in form.models" :key="m" :label="m" :value="m" />
              </el-select>
            </el-form-item>

            <el-form-item :label="t('settings.models.temperature')">
              <el-input-number
                v-model="form.temperature"
                :min="0"
                :max="2"
                :step="0.1"
                :precision="1"
              />
            </el-form-item>

            <el-form-item :label="t('settings.models.enabled')">
              <el-switch v-model="form.enabled" />
            </el-form-item>

            <div class="form-actions">
              <el-button v-if="mode === 'edit'" @click="startCreate">
                {{ t('settings.models.cancel') }}
              </el-button>
              <el-button type="primary" :loading="saving" @click="onSave">
                {{ t('settings.models.save') }}
              </el-button>
            </div>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from '@/i18n'
import { useUserStore } from '@/stores/user'
import {
  createProvider,
  deleteProvider,
  listProviders,
  setDefaultProvider,
  testProvider,
  updateProvider,
  type LLMProvider,
} from '@/services/llmProviders'

const { t } = useI18n()
const userStore = useUserStore()

const providers = ref<LLMProvider[]>([])
const status = ref<{ source: 'user' | 'env'; active_model: string; active_provider_name: string }>({
  source: 'env',
  active_model: '',
  active_provider_name: '',
})

const loading = ref(false)
const saving = ref(false)
const testingId = ref<number | null>(null)
const mode = ref<'create' | 'edit'>('create')

function emptyForm() {
  return {
    id: null as number | null,
    name: '',
    provider: 'openai',
    api_url: '',
    api_key: '',
    models: [] as string[],
    active_model: '',
    temperature: 0.1,
    enabled: true,
  }
}
const form = reactive(emptyForm())

function startCreate() {
  mode.value = 'create'
  Object.assign(form, emptyForm())
}

function startEdit(item: LLMProvider) {
  mode.value = 'edit'
  Object.assign(form, {
    id: item.id,
    name: item.name,
    provider: item.provider,
    api_url: item.api_url,
    api_key: '', // 留空 = 沿用原 Key
    models: [...item.models],
    active_model: item.active_model,
    temperature: item.temperature,
    enabled: item.enabled,
  })
}

// 模型列表变化后，保证「当前模型」仍是列表里的一项
watch(
  () => form.models,
  (models) => {
    if (!models.length) {
      form.active_model = ''
    } else if (!models.includes(form.active_model)) {
      form.active_model = models[0]
    }
  },
)

// 面板先于登录态恢复而挂载时（或用户就在本页登录），登录态就绪后补一次加载
watch(
  () => userStore.isLoggedIn,
  (loggedIn) => {
    if (loggedIn) reload()
  },
)

async function reload() {
  if (!userStore.isLoggedIn) return
  loading.value = true
  try {
    const data = await listProviders()
    providers.value = data.items
    status.value = {
      source: data.source,
      active_model: data.active_model,
      active_provider_name: data.active_provider_name,
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('settings.models.loadFailed'))
  } finally {
    loading.value = false
  }
}

async function onSave() {
  if (!form.name.trim()) return ElMessage.warning(t('settings.models.needName'))
  if (!form.api_url.trim()) return ElMessage.warning(t('settings.models.needUrl'))
  if (mode.value === 'create' && !form.api_key.trim()) {
    return ElMessage.warning(t('settings.models.needKey'))
  }
  if (!form.models.length) return ElMessage.warning(t('settings.models.needModel'))

  saving.value = true
  try {
    const base = {
      name: form.name.trim(),
      provider: form.provider,
      api_url: form.api_url.trim(),
      models: form.models,
      active_model: form.active_model,
      temperature: form.temperature,
      enabled: form.enabled,
    }
    if (mode.value === 'edit' && form.id != null) {
      // api_key 为空表示不修改
      await updateProvider(form.id, form.api_key.trim() ? { ...base, api_key: form.api_key.trim() } : base)
      ElMessage.success(t('settings.models.saved'))
    } else {
      await createProvider({ ...base, api_key: form.api_key.trim() })
      ElMessage.success(t('settings.models.created'))
    }
    startCreate()
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('settings.models.saveFailed'))
  } finally {
    saving.value = false
  }
}

async function onSetDefault(item: LLMProvider) {
  try {
    await setDefaultProvider(item.id)
    ElMessage.success(t('settings.models.switched'))
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('settings.models.switchFailed'))
  }
}

async function onTest(item: LLMProvider) {
  testingId.value = item.id
  try {
    const result = await testProvider(item.id)
    if (result.success) {
      ElMessage.success(
        result.latency_ms != null ? `${result.message} · ${result.latency_ms}ms` : result.message,
      )
    } else {
      ElMessage.error(result.message)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('settings.models.testFailed'))
  } finally {
    testingId.value = null
  }
}

async function onRemove(item: LLMProvider) {
  try {
    await ElMessageBox.confirm(
      t('settings.models.confirmRemove', { name: item.name }),
      t('settings.models.remove'),
      {
        type: 'warning',
        confirmButtonText: t('settings.models.remove'),
        cancelButtonText: t('settings.models.cancel'),
      },
    )
  } catch {
    return // 用户取消
  }
  try {
    await deleteProvider(item.id)
    ElMessage.success(t('settings.models.removed'))
    if (form.id === item.id) startCreate()
    await reload()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('settings.models.removeFailed'))
  }
}

onMounted(reload)
</script>

<style scoped>
.models-page {
  width: 100%;
  max-width: 1100px;
  margin: 0 auto;
}

.current-card {
  margin-bottom: 16px;
}

.current-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.current-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  min-width: 0;
}

.current-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.current-model {
  font-size: 15px;
  font-weight: 600;
}

.current-from {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.provider-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  margin-bottom: 10px;
}

.provider-row.active {
  border-color: var(--el-color-success-light-5);
  background: var(--el-color-success-light-9);
}

.provider-row.off {
  opacity: 0.6;
}

.provider-main {
  flex: 1;
  min-width: 0;
}

.provider-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.provider-name {
  font-weight: 600;
}

.provider-url {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

.provider-meta {
  margin-top: 6px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.provider-meta .sep {
  margin: 0 6px;
  color: var(--el-text-color-placeholder);
}

.provider-key {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.provider-models {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.provider-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex-shrink: 0;
}

.provider-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
