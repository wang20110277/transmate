import apiClient from './api'

// 模型供应商（BYOK）：身份由 localStorage 里的 token 决定（见 api.ts 拦截器），
// API Key 只进不出 —— 读取时后端只返回 api_key_masked。

export interface LLMProvider {
  id: number
  name: string
  provider: string
  api_url: string
  api_key_masked: string
  models: string[]
  active_model: string
  temperature: number
  enabled: boolean
  is_default: boolean
  created_at: string | null
  updated_at: string | null
}

export interface ProviderListResponse {
  items: LLMProvider[]
  /** user=我的配置，env=平台默认 */
  source: 'user' | 'env'
  active_model: string
  active_provider_name: string
}

export interface ProviderPayload {
  name: string
  api_url: string
  /** 更新时留空表示沿用原 Key */
  api_key?: string
  provider?: string
  models: string[]
  active_model?: string
  temperature?: number
  enabled?: boolean
}

export interface TestResult {
  success: boolean
  message: string
  latency_ms?: number | null
  sample?: string | null
}

export async function listProviders(): Promise<ProviderListResponse> {
  const { data } = await apiClient.get('/api/settings/llm/providers')
  return data
}

export async function createProvider(payload: ProviderPayload): Promise<LLMProvider> {
  const { data } = await apiClient.post('/api/settings/llm/providers', payload)
  return data
}

export async function updateProvider(
  id: number,
  payload: Partial<ProviderPayload>,
): Promise<LLMProvider> {
  const { data } = await apiClient.put(`/api/settings/llm/providers/${id}`, payload)
  return data
}

export async function deleteProvider(id: number): Promise<void> {
  await apiClient.delete(`/api/settings/llm/providers/${id}`)
}

export async function setDefaultProvider(id: number): Promise<LLMProvider> {
  const { data } = await apiClient.post(`/api/settings/llm/providers/${id}/default`)
  return data
}

/** 真实发一次极短请求验证 Base URL / Key / 模型名 */
export async function testProvider(id: number): Promise<TestResult> {
  const { data } = await apiClient.post(
    `/api/settings/llm/providers/${id}/test`,
    {},
    { timeout: 30000 },
  )
  return data
}
