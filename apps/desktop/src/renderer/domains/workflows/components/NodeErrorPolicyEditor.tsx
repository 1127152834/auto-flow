import { activePolicy, candidatePolicy, defaultPolicy, describePolicy, LEGACY_POLICY_KEYS, type ErrorPolicyV2 } from '../lib/errorPolicy'
import { Button } from './controls/button'
import { Label } from './controls/label'
import { NumberInput } from './controls/number-input'
import { SelectNative as Select } from './controls/select-native'

type Patch = Record<string, unknown>
export type NodeErrorPolicyEditorProps = {
  data: Record<string, unknown>
  /** Other nodes a failure may jump to. */
  targets: { id: string; label: string }[]
  onChange(patch: Patch): void
}

// Remediation M2 R2-12: one "出错时" control; old settings are shown as a candidate and only take
// effect after the person enables them (R2-08).
export function NodeErrorPolicyEditor({ data, targets, onChange }: NodeErrorPolicyEditorProps) {
  const policy = activePolicy(data)
  const candidate = policy ? null : candidatePolicy(data)
  const label = (id: string) => targets.find(target => target.id === id)?.label ?? id
  const clearLegacy: Patch = Object.fromEntries(LEGACY_POLICY_KEYS.map(key => [key, undefined]))
  const save = (next: ErrorPolicyV2 | null) => onChange({ ...clearLegacy, errorPolicy: next ?? undefined })
  const set = (patch: Partial<ErrorPolicyV2>) => policy && save({ ...policy, ...patch })
  const mode = policy?.onError ?? 'stop'
  return <div className="pt-4 border-t space-y-3">
    <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider">出错处理</h3>
    {candidate ? <div role="status" aria-label="未生效的出错设置" className="space-y-2 rounded-md border border-[hsl(var(--warning-500)/0.4)] bg-[hsl(var(--warning-500)/0.08)] p-2 text-xs">
      <p className="m-0">以前保存的设置“{describePolicy(candidate, label)}”尚未生效，运行时会按失败即停处理。</p>
      <Button size="sm" variant="outline" onClick={() => save(candidate)}>启用这项设置</Button>
    </div> : null}
    <div className="space-y-2">
      <Label htmlFor="node-error-mode">出错时</Label>
      <Select id="node-error-mode" aria-label="出错时" value={mode} onChange={event => {
        const next = event.target.value as ErrorPolicyV2['onError']
        save(next === 'stop' ? null : { ...defaultPolicy(next), ...(policy && policy.onError !== 'stop' ? { backoff: policy.backoff, onExhausted: policy.onExhausted } : {}) })
      }}>
        <option value="stop">失败即停（默认）</option>
        <option value="continue">跳过并继续</option>
        <option value="retry">原地重试当前模块</option>
        <option value="goto">跳到指定模块重新执行</option>
      </Select>
    </div>
    {policy && policy.onError === 'goto' ? <div className="space-y-2">
      <Label htmlFor="node-error-goto">跳到</Label>
      <Select id="node-error-goto" aria-label="出错后跳到" value={policy.gotoNodeId ?? ''} placeholder="选择模块…" onChange={event => set({ gotoNodeId: event.target.value || null })}>
        {targets.map(target => <option key={target.id} value={target.id}>{target.label}</option>)}
      </Select>
    </div> : null}
    {policy && (policy.onError === 'retry' || policy.onError === 'goto') ? <>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-2"><Label htmlFor="node-error-retries">最多次数</Label><NumberInput id="node-error-retries" aria-label="最多次数" value={policy.maxRetries} min={1} max={10} onChange={value => set({ maxRetries: Math.max(1, Math.min(10, Math.trunc(Number(value) || 1))) })}/></div>
        <div className="space-y-2"><Label htmlFor="node-error-interval">间隔(秒)</Label><NumberInput id="node-error-interval" aria-label="间隔(秒)" value={policy.backoff.initialSeconds} min={0} max={3600} onChange={value => { const seconds = Math.max(0, Math.min(3600, Number(value) || 0)); set({ backoff: { ...policy.backoff, initialSeconds: seconds, maxSeconds: Math.max(policy.backoff.kind === 'fixed' ? seconds : policy.backoff.maxSeconds, seconds) } }) }}/></div>
      </div>
      <div className="space-y-2"><Label htmlFor="node-error-exhausted">用尽后</Label>
        <Select id="node-error-exhausted" aria-label="用尽后" value={policy.onExhausted} onChange={event => set({ onExhausted: event.target.value as ErrorPolicyV2['onExhausted'] })}>
          <option value="stop">停止流程</option>
          <option value="continue">继续往下</option>
        </Select>
      </div>
    </> : null}
    {policy ? <div className="space-y-2"><Label htmlFor="node-error-when">适用于</Label>
      <Select id="node-error-when" aria-label="适用于" value={policy.retryOn} onChange={event => set({ retryOn: event.target.value as ErrorPolicyV2['retryOn'] })}>
        <option value="any">任何失败</option>
        <option value="timeout">仅超时</option>
      </Select>
    </div> : null}
    <p className="text-xs text-muted-foreground">{policy?.onError === 'retry'
      ? '只读的模块才会自动重试；点击、提交等可能已经对外产生影响的模块不会自动重试。'
      : policy?.onError === 'goto'
        ? '跳回前面的模块时，如果中间执行过可能对外产生影响的模块，会拒绝跳转并按失败处理。'
        : policy?.onError === 'continue' ? '出错时记一条警告并继续执行后续模块。' : '默认：该模块出错时立即停止流程。'}</p>
  </div>
}
