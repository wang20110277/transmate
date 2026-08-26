<template>
  <div class="skills-page">
    <header class="skills-header">
      <h1>{{ t('skills.title') }}</h1>
      <el-button :loading="refreshing" @click="onRefresh">{{ t('skills.refresh') }}</el-button>
    </header>

    <el-row :gutter="16">
      <el-col :span="14">
        <el-card>
          <template #header>{{ t('skills.registry') }}</template>
          <el-input
            v-model="keyword"
            :placeholder="t('skills.searchPlaceholder')"
            clearable
            class="skills-search"
          />
          <div v-loading="loadingRegistry">
            <div v-for="item in filteredRegistry" :key="item.name" class="skill-row">
              <div class="skill-info">
                <div class="skill-name">{{ item.name }}</div>
                <div class="skill-desc">{{ item.description }}</div>
                <div v-if="item.license" class="skill-license">{{ item.license }}</div>
              </div>
              <el-button
                v-if="item.installed"
                type="danger"
                plain
                size="small"
                :loading="pending === item.name"
                @click="onUninstall(item.name)"
                >{{ t('skills.uninstall') }}</el-button
              >
              <el-button
                v-else
                type="primary"
                size="small"
                :loading="pending === item.name"
                @click="onInstall(item.name)"
                >{{ t('skills.install') }}</el-button
              >
            </div>
            <el-empty
              v-if="!loadingRegistry && filteredRegistry.length === 0"
              :description="t('skills.emptyRegistry')"
            />
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card>
          <template #header>{{ t('skills.installed') }}</template>
          <div v-loading="loadingInstalled">
            <div v-for="item in installed" :key="item.name" class="skill-row">
              <div class="skill-info">
                <div class="skill-name">{{ item.name }}</div>
                <div class="skill-desc">{{ item.description }}</div>
              </div>
              <span class="skill-version">{{ item.version.slice(0, 7) }}</span>
            </div>
            <el-empty
              v-if="!loadingInstalled && installed.length === 0"
              :description="t('skills.emptyInstalled')"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useI18n } from '@/i18n'
import { ElMessage } from 'element-plus'
import {
  installSkill,
  listInstalled,
  listRegistry,
  refreshRegistry,
  uninstallSkill,
  type InstalledItem,
  type RegistryItem,
} from '@/services/skills'
import { useUserStore } from '@/stores/user'

const { t } = useI18n()
const userStore = useUserStore()

// 适配说明：stores/user.ts 未在顶层导出 user_id，经 userInfo?.user_id 取
const userId = computed(() => userStore.userInfo?.user_id || '')

const registry = ref<RegistryItem[]>([])
const installed = ref<InstalledItem[]>([])
const keyword = ref('')
const loadingRegistry = ref(false)
const loadingInstalled = ref(false)
const refreshing = ref(false)
const pending = ref('')

const filteredRegistry = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  if (!kw) return registry.value
  return registry.value.filter(
    (i) => i.name.toLowerCase().includes(kw) || i.description.toLowerCase().includes(kw),
  )
})

async function loadAll() {
  if (!userId.value) return
  loadingRegistry.value = true
  loadingInstalled.value = true
  try {
    ;[registry.value, installed.value] = await Promise.all([
      listRegistry(userId.value),
      listInstalled(userId.value),
    ])
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.loadFailed'))
  } finally {
    loadingRegistry.value = false
    loadingInstalled.value = false
  }
}

async function onRefresh() {
  refreshing.value = true
  try {
    await refreshRegistry()
    await loadAll()
  } finally {
    refreshing.value = false
  }
}

async function onInstall(name: string) {
  pending.value = name
  try {
    await installSkill(userId.value, name)
    ElMessage.success(t('skills.installDone', { name }))
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.installFailed'))
  } finally {
    pending.value = ''
  }
}

async function onUninstall(name: string) {
  pending.value = name
  try {
    await uninstallSkill(userId.value, name)
    ElMessage.success(t('skills.uninstallDone', { name }))
    await loadAll()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || t('skills.uninstallFailed'))
  } finally {
    pending.value = ''
  }
}

onMounted(loadAll)
</script>

<style scoped>
.skills-page { max-width: 1100px; margin: 0 auto; padding: 24px; }
.skills-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.skills-search { margin-bottom: 12px; }
.skill-row { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--el-border-color-lighter); }
.skill-info { flex: 1; min-width: 0; }
.skill-name { font-weight: 600; }
.skill-desc { color: var(--el-text-color-secondary); font-size: 13px; }
.skill-license { color: var(--el-text-color-placeholder); font-size: 12px; }
.skill-version { color: var(--el-text-color-placeholder); font-size: 12px; }
</style>
