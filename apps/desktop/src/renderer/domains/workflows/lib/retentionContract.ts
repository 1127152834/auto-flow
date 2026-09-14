import type { components } from '../../../shared/api/generated'
import type { ApiResponse } from '../api'
import { getStudioTransportRevision } from '../api/transport'
export type RetentionConfig = components['schemas']['StudioRetentionConfig']
export type RetentionUsage = components['schemas']['StudioRetentionUsage']
export const retentionDefaults: RetentionConfig = { enabled: false, recordings_max_days: 30, recordings_max_total_mb: 0, data_max_days: 30, data_max_total_mb: 0, cleanup_interval_hours: 24 }
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const integer = (v: unknown, min = 0) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min
const size = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0
export function isRetentionConfig(v: unknown): v is RetentionConfig {
  return record(v) && typeof v.enabled === 'boolean' && Object.keys(v).every(key => Object.hasOwn(retentionDefaults, key))
    && Object.keys(retentionDefaults).every(key => key === 'enabled' || integer(v[key], key === 'cleanup_interval_hours' ? 1 : 0))
}
export function isRetentionUsage(v: unknown): v is RetentionUsage {
  return record(v) && ['recordings', 'data'].every(key => { const e = v[key]; return record(e) && integer(e.count) && size(e.sizeMB) })
}
export async function checkedRetention<T>(request: Promise<ApiResponse<T>>, kind: 'load' | 'save' | 'usage' | 'cleanup'): Promise<ApiResponse<T>> {
  const revision = getStudioTransportRevision()
  const result = await request
  if (revision !== getStudioTransportRevision()) return { success: false, error: '服务连接已变更，请重新读取留存策略；旧操作结果未应用' }
  if (!result.success) return result
  const v: unknown = result.data
  const valid = record(v) && v.success === true && !v.error && (v.mock == null || typeof v.mock === 'boolean')
    && (kind === 'load' || kind === 'save' ? isRetentionConfig(v.config) : true)
    && (kind === 'load' || kind === 'usage' ? isRetentionUsage(v.usage) : true)
    && (kind !== 'cleanup' || ['recordings', 'data'].every(key => { const e = v[key]; return record(e) && integer(e.removed) && size(e.freedMB) }))
  return valid ? result : { success: false, error: '留存操作未返回有效确认，请重新读取后核对' }
}
