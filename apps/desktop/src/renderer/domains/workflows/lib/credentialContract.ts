import type { ApiResponse } from '../api'
import { getStudioTransportRevision } from '../api/transport'

/** A transport success alone cannot confirm a credential mutation. */
export async function checkedCredentialWrite<T>(request: Promise<ApiResponse<T>>, expectedName?: string): Promise<ApiResponse<T>> {
  const revision = getStudioTransportRevision()
  const result = await request
  if (revision !== getStudioTransportRevision()) return { success: false, error: '服务连接已变更，凭据操作结果未应用；请在原工作区核对' }
  if (!result.success) return result
  const data = result.data as Record<string, unknown> | undefined
  if (!data || data.success !== true || data.error || (expectedName !== undefined && data.name !== expectedName)) {
    return { success: false, error: '凭据操作未返回有效确认，请刷新凭据后核对' }
  }
  return result
}
