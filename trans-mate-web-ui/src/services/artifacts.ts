import apiClient from './api'

// 制品条目（助手通过 save_artifact 保存的产物文件）
export interface ArtifactItem {
  id: number
  conversation_id: number
  filename: string
  size: number
  description: string
  created_at: string | null
}

// 列表查询：可按会话过滤，返回分页数据（当前仅消费首页）
export async function listArtifacts(
  userId: string,
  conversationId?: number,
): Promise<{ items: ArtifactItem[]; total: number }> {
  const { data } = await apiClient.get('/api/artifacts', {
    params: { user_id: userId, ...(conversationId != null ? { conversation_id: conversationId } : {}) },
  })
  return data
}

// 获取预签名下载地址（在新标签页打开即下载）
export async function getArtifactDownloadUrl(artifactId: number, userId: string): Promise<string> {
  const { data } = await apiClient.get(`/api/artifacts/${artifactId}/download`, {
    params: { user_id: userId },
  })
  return data.url
}
