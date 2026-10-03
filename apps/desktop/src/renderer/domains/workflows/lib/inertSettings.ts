// Remediation M1 R1-02 / spec §5.1. Mirrors apps/backend/src/autoflow/domain/workflows/inert_settings.py.
export const INERT_SETTING_KEYS = ['errorPolicy', 'retryCount', 'retryDelay', 'retryBackoff', 'retryExhaustedAction', 'timeoutAction', 'onTimeout'] as const
export type InertSettingKey = typeof INERT_SETTING_KEYS[number]
export type InertNodeSettings = { nodeId: string; label: string; keys: InertSettingKey[] }

const LOOP_TYPES = new Set(['loop', 'foreach', 'foreach_dict', 'infinite_loop'])
type Record_ = Record<string, unknown>
const isRecord = (value: unknown): value is Record_ => typeof value === 'object' && value !== null && !Array.isArray(value)

export function inertKeys(data: Record_, moduleType: string): InertSettingKey[] {
  const config = isRecord(data.config) ? { ...data, ...data.config } : data
  const keys: InertSettingKey[] = []
  const policy = config.errorPolicy
  if (isRecord(policy) && policy.mode != null && policy.mode !== 'stop') keys.push('errorPolicy')
  const retryCount = Number(config.retryCount)
  if (Number.isFinite(retryCount) && retryCount > 0) {
    keys.push('retryCount')
    for (const key of ['retryDelay', 'retryBackoff', 'retryExhaustedAction'] as const) if (config[key] != null && config[key] !== '') keys.push(key)
  }
  if (config.timeoutAction === 'retry' || config.timeoutAction === 'skip') keys.push('timeoutAction')
  if (LOOP_TYPES.has(moduleType) && (config.onTimeout === 'retry' || config.onTimeout === 'skip')) keys.push('onTimeout')
  return keys
}

export function findInertSettings(nodes: readonly { id: string; data?: unknown }[]): InertNodeSettings[] {
  return nodes.flatMap(node => {
    if (!isRecord(node.data)) return []
    const moduleType = String(node.data.moduleType ?? '')
    const keys = inertKeys(node.data, moduleType)
    return keys.length ? [{ nodeId: node.id, label: String(node.data.label || moduleType || node.id), keys }] : []
  })
}

const LABELS: Record<InertSettingKey, string> = {
  errorPolicy: '出错时', retryCount: '重试次数', retryDelay: '重试间隔', retryBackoff: '退避策略',
  retryExhaustedAction: '重试耗尽后', timeoutAction: '运行超时后', onTimeout: '循环超时后',
}

export function describeInertSettings(found: InertNodeSettings[]): string {
  return `以下旧设置不会自动生效，可在「出错时」查看转换建议并启用：${found.map(item => `「${item.label}」${item.keys.map(key => LABELS[key]).join('、')}`).join('；')}`
}
