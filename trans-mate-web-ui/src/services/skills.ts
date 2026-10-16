import apiClient from './api'

// 会话/制品/技能等业务接口的身份一律由 localStorage 里的 token 决定
// （见 api.ts 请求拦截器），不再由调用方传 user_id。

export interface RegistryItem {
  name: string
  description: string
  license: string
  installed: boolean
}

export interface InstalledItem {
  name: string
  version: string
  description: string
  source: string
  installed_at: string | null
}

export async function listRegistry(): Promise<RegistryItem[]> {
  const { data } = await apiClient.get('/api/skills/registry/me')
  return data.items
}

export async function listInstalled(): Promise<InstalledItem[]> {
  const { data } = await apiClient.get('/api/skills/installed')
  return data.items
}

export async function installSkill(name: string): Promise<void> {
  await apiClient.post('/api/skills/install', { name })
}

export async function uninstallSkill(name: string): Promise<void> {
  await apiClient.delete(`/api/skills/${encodeURIComponent(name)}`)
}

export async function refreshRegistry(): Promise<void> {
  await apiClient.post('/api/skills/refresh')
}
