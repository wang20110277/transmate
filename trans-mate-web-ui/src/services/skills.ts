import apiClient from './api'

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

export async function listRegistry(userId: string): Promise<RegistryItem[]> {
  const { data } = await apiClient.get(`/api/skills/registry/${encodeURIComponent(userId)}`)
  return data.items
}

export async function listInstalled(userId: string): Promise<InstalledItem[]> {
  const { data } = await apiClient.get('/api/skills/installed', { params: { user_id: userId } })
  return data.items
}

export async function installSkill(userId: string, name: string): Promise<void> {
  await apiClient.post('/api/skills/install', { user_id: userId, name })
}

export async function uninstallSkill(userId: string, name: string): Promise<void> {
  await apiClient.delete(`/api/skills/${encodeURIComponent(name)}`, { params: { user_id: userId } })
}

export async function refreshRegistry(): Promise<void> {
  await apiClient.post('/api/skills/refresh')
}
