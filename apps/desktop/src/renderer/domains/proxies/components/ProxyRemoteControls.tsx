import { useEffect, useState, type ReactNode } from 'react'
import { ArrowsClockwise, CircleNotch, MapPin } from '@phosphor-icons/react'
import { capability, type ProxyApi, type ProxyView, type RotationSchedule } from '../api'
import { useProxyRemoteControls } from '../hooks/useProxyRemoteControls'
import { Button } from '../../../shared/components/ui/button'
import { AlertDialog, AlertDialogContent, AlertDialogTitle, AlertDialogDescription, AlertDialogCancel } from '../../../shared/components/ui/alert-dialog'
import { LocationPicker } from './LocationPicker'
import { RotationScheduleForm } from './RotationScheduleForm'
import { ProxyOperationStatus } from './ProxyOperationStatus'

type Confirmation = {kind:'rotate' | 'relocate' | 'save' | 'clear' | 'ack'; locationId?:string; schedule?:RotationSchedule}
export function ProxyRemoteControls({ api, proxy, onChanged, onDirtyChange, onSubmittingChange }: {
  api: ProxyApi; proxy: ProxyView; onChanged: () => Promise<void>
  onDirtyChange: (dirty:boolean) => void; onSubmittingChange: (busy:boolean) => void
}) {
  const state = useProxyRemoteControls(api, proxy, onChanged)
  const [picker, setPicker] = useState(false)
  const [confirm, setConfirm] = useState<Confirmation>()
  useEffect(() => { onSubmittingChange(state.submitting); return () => onSubmittingChange(false) }, [state.submitting, onSubmittingChange])
  const caps = state.remote?.capabilities ?? []
  const rotate = capability(caps, 'change_ip'), relocate = capability(caps, 'relocate'), schedule = capability(caps, 'rotation_schedule')
  const blocked = state.busy || state.loading || Boolean(state.error) || state.retrySeconds > 0
  const target = state.locations?.items.find(item => item.id === confirm?.locationId)
  const confirmAction = async () => {
    if (!confirm) return
    if (confirm.kind === 'ack') { await state.acknowledge(); setConfirm(undefined); return }
    const accepted = await state.submit(() => confirm.kind === 'rotate' ? api.changeIp(proxy) : confirm.kind === 'relocate' ? api.relocate(proxy, confirm.locationId!) : confirm.kind === 'clear' ? api.clearRotation(proxy) : api.saveRotation(proxy, confirm.schedule!))
    if (accepted) { setConfirm(undefined); setPicker(false) }
  }
  return <div className="grid gap-4">
    <div className="flex items-center justify-between gap-3"><p className="text-xs text-muted">{state.remote ? `远程状态更新于 ${new Date(state.remote.fetched_at).toLocaleTimeString()}` : '从 ProxyPanel 读取实时状态'}</p><Button disabled={state.loading || state.submitting || state.retrySeconds > 0} onClick={() => void state.refresh()}>{state.loading ? <CircleNotch className="animate-spin" /> : <ArrowsClockwise />}刷新状态</Button></div>
    {state.error && <p role="alert" className="rounded-control bg-red-50 p-3 text-sm text-red-700">{state.error}</p>}
    {state.retrySeconds > 0 && <p role="status" className="text-sm text-muted">请求受限，{state.retrySeconds} 秒后可重试。</p>}
    <ProxyOperationStatus operation={state.operation} busy={state.submitting || state.loading || state.retrySeconds > 0} onReconcile={() => void state.reconcile()} onAcknowledge={() => setConfirm({kind:'ack'})} />
    <Section title="即时操作"><p className="text-sm text-muted">更换 IP 或地点可能中断正在使用此代理的浏览器会话。</p><dl className="grid gap-2 text-sm"><div className="flex gap-1"><dt>当前位置：</dt><dd>{state.remote?.city || '—'} · {state.remote?.carrier || '—'}</dd></div><div className="flex gap-1"><dt>出口 IP：</dt><dd className="font-mono">{state.remote?.current_ip || '—'}</dd></div></dl>
      <div className="flex gap-2"><Button disabled={blocked || !rotate?.available || !state.remote?.current_ip} onClick={() => setConfirm({kind:'rotate'})}><ArrowsClockwise />更换 IP</Button><Button variant="primary" disabled={blocked || !relocate?.available} onClick={() => { setPicker(true); void state.loadLocations() }}><MapPin />改变地点</Button></div>
      {!rotate?.available && <p className="text-xs text-muted">{rotate?.reason || '正在读取换 IP 条件…'}</p>}{!relocate?.available && relocate?.reason && <p className="text-xs text-muted">地点切换：{relocate.reason}</p>}
    </Section>
    <Section title="轮换计划">{state.scheduleError ? <p role="alert" className="text-sm text-red-700">{state.scheduleError}。请刷新状态后重试。</p> : state.schedule ? <RotationScheduleForm value={state.schedule} disabled={blocked} canSave={Boolean(schedule?.available)} onDirtyChange={onDirtyChange} onSave={value => setConfirm({kind:'save', schedule:value})} onClear={() => setConfirm({kind:'clear'})} /> : <p role="status" className="text-sm text-muted">正在读取轮换计划…</p>}{schedule?.reason && <p className="text-xs text-muted">{schedule.reason}</p>}</Section>
    {picker && <LocationPicker currentCity={state.remote?.city} currentCarrier={state.remote?.carrier} locations={state.locations} error={state.locationError} loading={state.locationsLoading} busy={state.submitting || state.retrySeconds > 0} onClose={() => setPicker(false)} onReload={() => void state.loadLocations()} onSelect={locationId => setConfirm({kind:'relocate',locationId})} />}
    <AlertDialog open={Boolean(confirm)} onOpenChange={open => { if (!open && !state.submitting) setConfirm(undefined) }}>
      <AlertDialogContent onEscapeKeyDown={e => { if (state.submitting) e.preventDefault() }}>
        <AlertDialogTitle>{confirm?.kind === 'ack' ? '确认结束本次结果核实？' : confirm?.kind === 'relocate' ? '确认切换代理地点？' : confirm?.kind === 'rotate' ? '确认更换出口 IP？' : confirm?.kind === 'clear' ? '确认关闭轮换计划？' : '确认保存轮换计划？'}</AlertDialogTitle>
        <AlertDialogDescription>{confirm?.kind === 'ack' ? '此操作可能已经在 ProxyPanel 生效。结束核实后才能发起新操作；新操作可能再次切换 IP 或地点。结束核实本身不会重复执行远程操作。' : confirm?.kind === 'relocate' ? `目标：${target?.city ?? ''} · ${target?.carrier ?? ''}。该目标覆盖的城市由 ProxyPanel 分配，现有连接可能短暂中断。` : confirm?.kind === 'rotate' ? `当前 IP：${state.remote?.current_ip}。现有连接可能短暂中断，提交后不会自动重发。` : confirm?.kind === 'clear' ? '关闭后 ProxyPanel 将停止自动轮换。' : `每 ${confirm?.schedule?.interval_minutes} 分钟自动轮换，关闭 AutoFlow 后仍继续执行。`}</AlertDialogDescription>
        {state.error && <p role="alert" className="text-sm text-red-700">{state.error}</p>}
        <div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button disabled={state.submitting}>取消</Button></AlertDialogCancel><Button variant="primary" disabled={state.submitting || state.retrySeconds > 0} onClick={() => void confirmAction()}>{state.submitting ? <><CircleNotch className="animate-spin" />正在提交…</> : '确认'}</Button></div>
      </AlertDialogContent>
    </AlertDialog>
  </div>
}
function Section({title,children}:{title:string;children:ReactNode}) { return <section className="grid gap-3 rounded-card border border-line bg-surface p-5"><h3 className="font-semibold">{title}</h3>{children}</section> }
