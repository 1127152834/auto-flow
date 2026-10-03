import { useCallback, useEffect, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'
import { Textarea } from '../../../shared/components/ui/textarea'
import { safeProjectError } from '../../projects/presentation-error'

export type ProcessingUnit = components['schemas']['ProcessingUnitView']
type State = ProcessingUnit['state']
type Action = 'reset' | 'skip' | 'resolve'
type Decision = 'confirmedSucceeded' | 'confirmedNotPerformed' | 'abandon'
export type ProcessingUnitsApi = {
  list(state: State | null, after: string | null): Promise<{ items: ProcessingUnit[]; nextAfter: string | null }>
  command(unitId: string, action: Action, body: { expectedRevision: number; reason: string; decision?: Decision }, key: string): Promise<{ unit: ProcessingUnit }>
}

// Remediation M2 R2-06: user-facing words only; no internal identifiers.
const stateLabels: Record<State, string> = {
  pending: '待处理', succeeded: '已完成', failed_retryable: '失败，稍后重试', quarantined: '多次失败，已停止重试',
  needs_review: '结果不明，需要核实', skipped: '已跳过',
}
const actionLabels: Record<Action, string> = { reset: '重置', skip: '跳过', resolve: '核实' }
const decisionOptions = [
  { value: 'confirmedNotPerformed', label: '确认没有执行，可以重新处理', disabled: false },
  { value: 'confirmedSucceeded', label: '确认已经成功', disabled: false },
  { value: 'abandon', label: '放弃这条数据', disabled: false },
]
const keyOf = (unit: ProcessingUnit) => unit.recordRef.recordKey.value

export function ProcessingUnitsPanel({ api, disabled = false }: { api: ProcessingUnitsApi; disabled?: boolean }) {
  const [state, setState] = useState<State | null>(null)
  const [pages, setPages] = useState<{ items: ProcessingUnit[]; nextAfter: string | null } | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [acting, setActing] = useState<{ unit: ProcessingUnit; action: Action; key: string } | null>(null)
  const [reason, setReason] = useState('')
  const [decision, setDecision] = useState<Decision | null>(null)
  const [busy, setBusy] = useState(false)
  const [commandError, setCommandError] = useState<string | null>(null)

  const load = useCallback(async (after: string | null) => {
    setLoadError(null)
    try {
      const page = await api.list(state, after)
      setPages(current => after && current ? { items: [...current.items, ...page.items], nextAfter: page.nextAfter } : page)
    } catch (error) {
      setLoadError(safeProjectError(error))
    }
  }, [api, state])
  useEffect(() => { void load(null) }, [load])

  const open = (unit: ProcessingUnit, action: Action) => {
    setActing({ unit, action, key: crypto.randomUUID() })
    setReason(''); setDecision(null); setCommandError(null)
  }
  const submit = async () => {
    if (!acting) return
    setBusy(true); setCommandError(null)
    try {
      const body = { expectedRevision: acting.unit.revision, reason: reason.trim(), ...(acting.action === 'resolve' && decision ? { decision } : {}) }
      const { unit } = await api.command(acting.unit.unitId, acting.action, body, acting.key)
      setPages(current => current ? { ...current, items: current.items.map(item => item.unitId === unit.unitId ? unit : item) } : current)
      setActing(null)
    } catch (error) {
      // The same request identity is kept so a retry cannot apply the change twice.
      setCommandError(safeProjectError(error))
    } finally {
      setBusy(false)
    }
  }
  const ready = reason.trim().length > 0 && (acting?.action !== 'resolve' || decision !== null)

  return <section aria-label="处理记录" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="m-0 text-base font-semibold">处理记录</h3><p className="mt-1 text-sm text-muted">批量运行时逐行处理的数据及其最近结果。结果不明的数据不会被自动重新处理，需要先核实。</p></div>
      <Select className="w-56" aria-label="处理状态" value={state} placeholder="全部状态" options={(Object.keys(stateLabels) as State[]).map(value => ({ value, label: stateLabels[value], disabled: false }))} onValueChange={value => setState((value as State | null) ?? null)}/>
    </div>
    {loadError ? <p role="alert" className="m-0 text-sm text-danger">读取失败：{loadError} <Button size="sm" onClick={() => void load(null)}>重新读取</Button></p> : null}
    {pages && pages.items.length === 0 ? <p className="m-0 text-sm text-muted">暂无处理记录。</p> : null}
    {pages && pages.items.length > 0 ? <table className="w-full min-w-0 text-left text-sm">
      <thead><tr><th scope="col">数据</th><th scope="col">状态</th><th scope="col">尝试次数</th><th scope="col">最近结果</th><th scope="col"><span className="sr-only">操作</span></th></tr></thead>
      <tbody>{pages.items.map(unit => <tr key={unit.unitId} className="border-t border-line align-top">
        <td className="py-2 pr-3 font-medium">{keyOf(unit)}</td>
        <td className="py-2 pr-3">{stateLabels[unit.state]}</td>
        <td className="py-2 pr-3">{unit.attempts}</td>
        <td className="py-2 pr-3 text-muted">{typeof unit.lastError?.message === 'string' ? unit.lastError.message : '—'}</td>
        <td className="py-2 text-right">{unit.state === 'needs_review'
          ? <Button size="sm" disabled={disabled} aria-label={`核实 ${keyOf(unit)}`} onClick={() => open(unit, 'resolve')}>核实</Button>
          : <span className="inline-flex gap-2">
            <Button size="sm" variant="ghost" disabled={disabled || unit.state === 'pending'} aria-label={`重置 ${keyOf(unit)}`} onClick={() => open(unit, 'reset')}>重置</Button>
            <Button size="sm" variant="ghost" disabled={disabled || unit.state === 'skipped'} aria-label={`跳过 ${keyOf(unit)}`} onClick={() => open(unit, 'skip')}>跳过</Button>
          </span>}</td>
      </tr>)}</tbody>
    </table> : null}
    {pages?.nextAfter ? <Button size="sm" className="justify-self-start" onClick={() => void load(pages.nextAfter)}>加载更多</Button> : null}
    {acting ? <div className="grid gap-2 rounded-control border border-line bg-surface-subtle p-3">
      <p className="m-0 text-sm font-medium">{actionLabels[acting.action]}“{keyOf(acting.unit)}”</p>
      {acting.action === 'resolve' ? <Select aria-label="核实结论" value={decision} placeholder="选择核实结论" options={decisionOptions} clearable={false} onValueChange={value => setDecision((value as Decision | null) ?? null)}/> : null}
      <Textarea aria-label="原因" value={reason} maxLength={500} placeholder="说明原因，便于以后追查" onChange={event => setReason(event.target.value)}/>
      {commandError ? <p role="alert" className="m-0 text-sm text-danger">{commandError}</p> : null}
      <div className="flex gap-2"><Button size="sm" disabled={!ready || busy || disabled} onClick={() => void submit()}>确认{actionLabels[acting.action]}</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => setActing(null)}>取消</Button></div>
    </div> : null}
  </section>
}
