import apiClient from './api'

// 制品条目（助手通过 save_artifact 保存的产物文件）
export interface ArtifactItem {
  id: number
  conversation_id: number
  filename: string
  size: number
  description: string
  created_at: string | null
  archived: boolean
  archived_at: string | null
}

// 列表查询：可按会话过滤，返回分页数据（当前仅消费首页）；archived=true 查回收站
export async function listArtifacts(
  conversationId?: number,
  archived = false,
): Promise<{ items: ArtifactItem[]; total: number }> {
  const { data } = await apiClient.get('/api/artifacts', {
    params: {
      archived,
      ...(conversationId != null ? { conversation_id: conversationId } : {}),
    },
  })
  return data
}

// 获取预签名下载地址（在新标签页打开即下载）
export async function getArtifactDownloadUrl(artifactId: number): Promise<string> {
  const { data } = await apiClient.get(`/api/artifacts/${artifactId}/download`)
  return data.url
}

// 归档进回收站（对象保留，可恢复）
export async function archiveArtifact(artifactId: number): Promise<void> {
  await apiClient.post(`/api/artifacts/${artifactId}/archive`)
}

// 从回收站恢复
export async function restoreArtifact(artifactId: number): Promise<void> {
  await apiClient.post(`/api/artifacts/${artifactId}/restore`)
}

// 彻底删除（MinIO 对象 + 记录）
export async function purgeArtifact(artifactId: number): Promise<void> {
  await apiClient.delete(`/api/artifacts/${artifactId}`)
}
