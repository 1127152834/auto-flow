import { useCallback, useEffect, useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { safeProjectError } from '../../projects/presentation-error'

export type Schedule = components['schemas']['ScheduleView']
export type ScheduleTrigger = components['schemas']['ScheduleTriggerView']
export type ScheduleWrite = components['schemas']['ScheduleWrite']
export type SchedulesApi = {
  list(): Promise<Schedule[]>
  create(body: ScheduleWrite): Promise<Schedule>
  update(scheduleId: string, body: ScheduleWrite & { expectedRevision: number }): Promise<Schedule>
  remove(scheduleId: string): Promise<unknown>
  triggers(scheduleId: string): Promise<ScheduleTrigger[]>
}

// Remediation M2 R2-25..27: plain words for every option; the backend reads each one.
const overlapOptions = [
  { value: 'skip', label: '上一批未结束时跳过', disabled: false },
  { value: 'queue', label: '上一批结束后再开始', disabled: false },
  { value: 'parallel', label: '允许同时运行', disabled: false },
]
const missedOptions = [
  { value: 'latestOnly', label: '错过时补跑最近一次', disabled: false },
  { value: 'ignore', label: '错过时不补跑', disabled: false },
]
const kindOptions = [
  { value: 'cron', label: '定时', disabled: false },
  { value: 'webhook', label: '外部调用', disabled: false },
]
const triggerStates: Record<ScheduleTrigger['state'], string> = {
  pending: '处理中', started: '已开始运行', skipped: '已跳过', queued: '排队等待', failed: '未能开始',
}
const blank: ScheduleWrite = { kind: 'cron', cron: '0 9 * * *', timezone: 'Asia/Shanghai', overlap: 'skip', missed: 'latestOnly', enabled: true, parameters: {}, concurrency: 1 }
// Server messages can carry internal identities; only schedule validation text (authored for
// people, e.g. why a time expression is invalid) is shown as is, everything else is mapped.
const message = (error: unknown) => error instanceof Error && 'code' in error && error.code === 'SCHEDULE_INVALID' && error.message
  ? error.message : safeProjectError(error)
const writable = ({ kind, cron, timezone, overlap, missed, enabled, parameters, maxTasks, concurrency }: Schedule): ScheduleWrite =>
  ({ kind, cron, timezone, overlap, missed, enabled, parameters, maxTasks, concurrency })

export function SchedulesPanel({ api, disabled = false }: { api: SchedulesApi; disabled?: boolean }) {
  const [items, setItems] = useState<Schedule[] | null>(null)
  const [draft, setDraft] = useState<ScheduleWrite | null>(null)
  const [secret, setSecret] = useState<string | null>(null)
  const [history, setHistory] = useState<{ scheduleId: string; items: ScheduleTrigger[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setError(null)
    try { setItems(await api.list()) } catch (failure) { setError(`读取失败：${message(failure)}`) }
  }, [api])
  useEffect(() => { void load() }, [load])

  const run = async (action: () => Promise<void>) => {
    setBusy(true); setError(null)
    try { await action() } catch (failure) { setError(message(failure)) } finally { setBusy(false) }
  }
  const create = () => run(async () => {
    if (!draft) return
    const created = await api.create({ ...draft, cron: draft.kind === 'cron' ? draft.cron : null })
    setSecret(created.webhookSecret ?? null)
    setDraft(null)
    await load()
  })
  const toggle = (schedule: Schedule, enabled: boolean) => run(async () => {
    const updated = await api.update(schedule.scheduleId, { ...writable(schedule), enabled, expectedRevision: schedule.revision })
    setItems(current => current?.map(item => item.scheduleId === updated.scheduleId ? updated : item) ?? null)
  })
  const remove = (schedule: Schedule) => run(async () => { await api.remove(schedule.scheduleId); await load() })
  const showHistory = (schedule: Schedule) => run(async () => setHistory({ scheduleId: schedule.scheduleId, items: await api.triggers(schedule.scheduleId) }))

  return <section aria-label="调度" className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-4">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="m-0 text-base font-semibold">调度</h3><p className="mt-1 text-sm text-muted">按时间或外部调用自动开始一批运行。每个时间点或调用最多开始一次。</p></div>
      <Button size="sm" disabled={disabled || busy || draft !== null} onClick={() => setDraft(blank)}>添加调度</Button>
    </div>
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {secret ? <div role="status" className="grid gap-1 rounded-control border border-warning/40 p-3 text-sm">
      <p className="m-0">调用密钥只显示这一次，请立即保存。调用时放在请求头 X-AutoFlow-Webhook-Secret 中。</p>
      <code className="break-all">{secret}</code>
      <Button size="sm" variant="ghost" className="justify-self-start" onClick={() => setSecret(null)}>我已保存</Button>
    </div> : null}
    {draft ? <div className="grid gap-2 rounded-control border border-line bg-surface-subtle p-3 sm:grid-cols-2">
      <Select aria-label="触发方式" value={draft.kind} options={kindOptions} clearable={false} onValueChange={value => setDraft({ ...draft, kind: value === 'webhook' ? 'webhook' : 'cron' })}/>
      {draft.kind === 'cron' ? <Input aria-label="时间表达式" placeholder="分 时 日 月 周，例如 0 9 * * *" value={draft.cron ?? ''} onChange={event => setDraft({ ...draft, cron: event.target.value })}/> : null}
      {draft.kind === 'cron' ? <Input aria-label="时区" value={draft.timezone ?? ''} onChange={event => setDraft({ ...draft, timezone: event.target.value })}/> : null}
      <Select aria-label="运行重叠时" value={draft.overlap ?? 'skip'} options={overlapOptions} clearable={false} onValueChange={value => setDraft({ ...draft, overlap: value as ScheduleWrite['overlap'] })}/>
      {draft.kind === 'cron' ? <Select aria-label="错过时间时" value={draft.missed ?? 'latestOnly'} options={missedOptions} clearable={false} onValueChange={value => setDraft({ ...draft, missed: value as ScheduleWrite['missed'] })}/> : null}
      <Input aria-label="每批最多任务数" type="number" min={1} max={100} placeholder="不限" value={draft.maxTasks ?? ''} onChange={event => setDraft({ ...draft, maxTasks: event.target.value ? Number(event.target.value) : null })}/>
      <Input aria-label="同时运行数" type="number" min={1} max={100} value={draft.concurrency ?? 1} onChange={event => setDraft({ ...draft, concurrency: Number(event.target.value) || 1 })}/>
      <div className="flex gap-2 sm:col-span-2"><Button size="sm" disabled={busy || disabled} onClick={() => void create()}>保存调度</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => setDraft(null)}>取消</Button></div>
    </div> : null}
    {items && items.length === 0 && !draft ? <p className="m-0 text-sm text-muted">还没有调度。</p> : null}
    {items?.map(schedule => <div key={schedule.scheduleId} className="grid gap-2 border-t border-line pt-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 text-sm">
          <p className="m-0 font-medium">{schedule.kind === 'cron' ? `定时 ${schedule.cron}（${schedule.timezone}）` : '外部调用'}</p>
          <p className="m-0 text-muted">{overlapOptions.find(item => item.value === schedule.overlap)?.label}{schedule.kind === 'cron' ? `；${missedOptions.find(item => item.value === schedule.missed)?.label}` : ''}</p>
        </div>
        <span className="inline-flex items-center gap-2">
          <Switch aria-label={`启用调度 ${schedule.kind === 'cron' ? schedule.cron : '外部调用'}`} checked={schedule.enabled} disabled={disabled || busy} onCheckedChange={checked => void toggle(schedule, checked)}/>
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => void showHistory(schedule)}>最近触发</Button>
          <Button size="sm" variant="ghost" disabled={disabled || busy} onClick={() => void remove(schedule)}>删除</Button>
        </span>
      </div>
      {history?.scheduleId === schedule.scheduleId ? (history.items.length === 0
        ? <p className="m-0 text-sm text-muted">还没有触发记录。</p>
        : <ul aria-label="最近触发" className="m-0 grid gap-1 pl-5 text-sm">{history.items.map(trigger => <li key={trigger.triggerId}>
          {new Date(trigger.plannedAt ?? trigger.receivedAt).toLocaleString()} · {triggerStates[trigger.state]}{trigger.reason ? `：${trigger.reason}` : ''}
        </li>)}</ul>) : null}
    </div>)}
  </section>
}
