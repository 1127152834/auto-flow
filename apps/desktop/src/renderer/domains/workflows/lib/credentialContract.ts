import type { components } from '../../../shared/api/generated'
import type { ApiResponse, CredentialFieldsCommand } from '../api'
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


/** Reject malformed or unrelated receipts; callers retain the same command ID for recovery. */
export async function checkedCredentialFields(
  request: Promise<ApiResponse<components['schemas']['StudioCredentialFieldsConfirmed']>>,
  command: CredentialFieldsCommand,
) {
  const result = await checkedCredentialWrite(request)
  if (!result.success) return result
  const data = result.data
  const item = data?.credential
  if (data?.commandId !== command.commandId || item?.name !== command.name
    || !Number.isSafeInteger(item.revision) || Number(item.revision) <= command.expectedRevision
    || typeof item.description !== 'string' || typeof item.created_at !== 'string' || typeof item.updated_at !== 'string'
    || !Array.isArray(item.fields) || !item.fields.length
    || !item.fields.every(field => field && typeof field.key === 'string' && typeof field.masked === 'string')
    || new Set(item.fields.map(field => field.key)).size !== item.fields.length) {
    return {success:false,error:'字段操作未返回有效确认，请使用原命令重试核对'} as typeof result
  }
  const keys = new Set(item.fields.map(field => field.key))
  if (command.operations.some(op => op.kind === 'remove' ? keys.has(op.key) : !keys.has(op.newKey) || (op.newKey !== op.key && keys.has(op.key)))) {
    return {success:false,error:'字段回执与请求操作不符，请使用原命令重试核对'} as typeof result
  }
  return result
}
