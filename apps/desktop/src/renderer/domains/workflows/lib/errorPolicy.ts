// Remediation M2 R2-08/R2-12. Mirrors apps/backend/src/autoflow/domain/workflows/error_policy.py;
// both sides are tested against apps/backend/tests/fixtures/error_policy_candidates.json.
export type ErrorPolicyV2 = {
  version: 2
  onError: 'stop' | 'continue' | 'retry' | 'goto'
  maxRetries: number
  backoff: { kind: 'fixed' | 'exponential'; initialSeconds: number; maxSeconds: number; jitter: boolean }
  retryOn: 'any' | 'timeout'
  gotoNodeId: string | null
  onExhausted: 'stop' | 'continue'
}

type Record_ = Record<string, unknown>
const isRecord = (value: unknown): value is Record_ => typeof value === 'object' && value !== null && !Array.isArray(value)
const MAX_RETRIES = 10, MAX_DELAY = 3600, LEGACY_EXPONENTIAL_CAP = 60
/** Saved by older editors; converted into a candidate, never executed until the user enables it. */
export const LEGACY_POLICY_KEYS = ['retryCount', 'retryDelay', 'retryBackoff', 'retryExhaustedAction', 'timeoutAction'] as const

const config = (data: Record_): Record_ => isRecord(data.config) ? { ...data, ...data.config } : data
const int = (value: unknown, fallback: number) => { const parsed = Math.trunc(Number(value)); return Number.isFinite(parsed) ? Math.max(0, parsed) : fallback }
const seconds = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.min(value, MAX_DELAY)) : 0

function build(onError: ErrorPolicyV2['onError'], options: Partial<{ retries: number; kind: 'fixed' | 'exponential'; initial: number; ceiling: number; retryOn: 'any' | 'timeout'; goto: string | null; exhausted: 'stop' | 'continue' }> = {}): ErrorPolicyV2 {
  const initial = options.initial ?? 0
  return {
    version: 2, onError, maxRetries: options.retries ?? 0,
    backoff: { kind: options.kind ?? 'fixed', initialSeconds: initial, maxSeconds: options.ceiling ?? initial, jitter: false },
    retryOn: options.retryOn ?? 'any', gotoNodeId: options.goto ?? null, onExhausted: options.exhausted ?? 'stop',
  }
}

export function activePolicy(data: Record_): ErrorPolicyV2 | null {
  const raw = config(data).errorPolicy
  return isRecord(raw) && raw.version === 2 ? raw as unknown as ErrorPolicyV2 : null
}

export function candidatePolicy(data: Record_): ErrorPolicyV2 | null {
  const value = config(data)
  const old = value.errorPolicy
  if (isRecord(old) && old.version === 2) return null
  if (isRecord(old) && old.mode != null && old.mode !== 'stop') {
    const retries = int(old.maxRetries, 1), initial = seconds(old.interval)
    const exhausted = old.onExhausted === 'continue' ? 'continue' : 'stop'
    if (old.mode === 'continue') return build('continue')
    if (old.mode === 'retry-self') return build('retry', { retries, initial, exhausted })
    if (old.mode === 'retry-from' && typeof old.targetId === 'string' && old.targetId) return build('goto', { retries, initial, goto: old.targetId, exhausted })
  }
  const retries = int(value.retryCount, 0)
  if (retries > 0) {
    const delay = seconds(value.retryDelay), exponential = value.retryBackoff === 'exponential'
    return build('retry', { retries: Math.min(retries, MAX_RETRIES), kind: exponential ? 'exponential' : 'fixed', initial: delay, ceiling: exponential ? LEGACY_EXPONENTIAL_CAP : delay, exhausted: value.retryExhaustedAction === 'skip' || value.retryExhaustedAction === 'continue' ? 'continue' : 'stop' })
  }
  if (value.timeoutAction === 'skip') return build('continue', { retryOn: 'timeout' })
  return null
}

export function defaultPolicy(onError: ErrorPolicyV2['onError']): ErrorPolicyV2 {
  return build(onError, { retries: onError === 'retry' || onError === 'goto' ? 1 : 0 })
}

export function describePolicy(policy: ErrorPolicyV2, label: (nodeId: string) => string): string {
  const when = policy.retryOn === 'timeout' ? '超时时' : '出错时'
  const after = policy.onExhausted === 'continue' ? '，仍失败则继续' : ''
  if (policy.onError === 'continue') return `${when}跳过并继续`
  if (policy.onError === 'retry') return `${when}重试 ${policy.maxRetries} 次${after}`
  if (policy.onError === 'goto') return `${when}跳到「${policy.gotoNodeId ? label(policy.gotoNodeId) : '未选择'}」×${policy.maxRetries}${after}`
  return ''
}
