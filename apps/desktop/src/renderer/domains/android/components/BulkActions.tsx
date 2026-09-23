import { useEffect, useState } from 'react'
import type { ManagementDevicePage, AndroidManagementApi, Bulk } from '../management-api'

export function BulkActions({ api, devices }: { api: Pick<AndroidManagementApi, 'bulk'> & Partial<Pick<AndroidManagementApi, 'bulkAction' | 'bulkStatus'>>; devices: ManagementDevicePage['items'] }) {
  const [selected, setSelected] = useState<string[]>([]), [action, setAction] = useState<'start' | 'stop' | 'restart' | 'delete'>('start'), [deleteData, setDeleteData] = useState(false), [result, setResult] = useState<Bulk | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [request, setRequest] = useState<Record<string, unknown> | null>(null)
  const [pendingAction, setPendingAction] = useState<{ requestId: string; action: 'verify' | 'retryFailed' | 'cancelPending' } | null>(null)
  const [statusUnavailable, setStatusUnavailable] = useState(false)
  const batchId = result?.id
  const active = Boolean(result && ['queued', 'running', 'waiting_capacity'].includes(result.state))
  useEffect(() => {
    const read = api.bulkStatus
    if (!read || !batchId || !active || busy || pendingAction) return
    const controller = new AbortController()
    let disposed = false
    let timer: number
    const poll = async () => {
      try {
        if (document.visibilityState === 'hidden') return
        const next = await read(batchId, controller.signal)
        if (!disposed) { setResult(next); setStatusUnavailable(false) }
      } catch {
        if (!disposed) setStatusUnavailable(true)
      } finally {
        if (!disposed) timer = window.setTimeout(poll, 3000)
      }
    }
    timer = window.setTimeout(poll, 3000)
    return () => { disposed = true; controller.abort(); window.clearTimeout(timer) }
  }, [api.bulkStatus, batchId, active, busy, pendingAction])
  const targets = devices.filter(device => selected.includes(device.deviceId) && device.allowedActions.includes(action) && !device.stale && device.runtimeState !== 'unknown' && (device.owner?.kind ?? 'none') === 'none')
  const submit = async () => {
    if (!request && (!targets.length || targets.length > 20)) return
    const body = request ?? { requestId: crypto.randomUUID(), action, deleteData: action === 'delete' ? deleteData : false, items: targets.map(device => ({ deviceId: device.deviceId, expectedRevision: device.revision })) }
    setRequest(body); setBusy(true); setError('')
    try { setResult(await api.bulk(body)); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : '批次结果尚未确认，请重试') } finally { setBusy(false) }
  }
  const actOnBatch = async (action: 'verify' | 'retryFailed' | 'cancelPending') => {
    if (!result || !api.bulkAction) return
    const body = pendingAction ?? { requestId: crypto.randomUUID(), action }
    setPendingAction(body); setBusy(true); setError('')
    try { setResult(await api.bulkAction(result.id, body)); setPendingAction(null) } catch (cause) { setError(cause instanceof Error ? cause.message : '批次动作结果尚未确认，请重试原动作') } finally { setBusy(false) }
  }
  const newBatch = () => {
    setSelected([]); setAction('start'); setDeleteData(false); setResult(null); setRequest(null); setPendingAction(null); setError(''); setStatusUnavailable(false)
  }
  const unknown = result?.state === 'needs_verification' || result?.items.some(item => ['accepted', 'needs_verification'].includes(String(item.state)))
  const failedItems = result?.items.filter(item => String(item.state) === 'failed') ?? []
  const cancellable = result?.items.some(item => ['queued', 'waiting_capacity', 'waiting_device'].includes(String(item.state)))
  const settled = result && ['succeeded', 'failed', 'partially_failed', 'cancelled'].includes(result.state) && result.items.every(item => ['succeeded', 'failed', 'cancelled'].includes(String(item.state)))
  return <section aria-label="批量操作" aria-busy={busy} className="rounded-card border border-line bg-surface p-5"><header><h2 className="font-semibold">批量操作</h2><p className="mt-1 text-sm text-muted">目标在提交时冻结，单批最多 20 台。</p></header><div className="mt-3 grid gap-2">{devices.map(device => { const blocked = device.stale || device.runtimeState === 'unknown' || (device.owner?.kind ?? 'none') !== 'none' || !device.allowedActions.includes(action); return <label key={device.deviceId} className="flex items-center gap-2 text-sm"><input id={`bulk-${device.deviceId}`} aria-label={device.name} type="checkbox" checked={selected.includes(device.deviceId)} disabled={busy || Boolean(request) || blocked} onChange={event => setSelected(current => event.target.checked ? [...current, device.deviceId] : current.filter(id => id !== device.deviceId))} />{device.name} · 修订 {device.revision}{blocked && ' · 待核实或不可操作'}</label> })}</div><div className="mt-3 flex flex-wrap items-center gap-2"><select aria-label="批量动作" value={action} disabled={busy || Boolean(request)} onChange={event => { setAction(event.target.value as typeof action); setSelected(current => current.filter(id => { const device = devices.find(item => item.deviceId === id); return Boolean(device && device.allowedActions.includes(event.target.value) && !device.stale && device.runtimeState !== 'unknown' && (device.owner?.kind ?? 'none') === 'none') })); setDeleteData(false) }}><option value="start">启动</option><option value="stop">停止</option><option value="restart">重启</option><option value="delete">删除</option></select>{action === 'delete' && <label className="flex items-center gap-1 text-sm"><input type="checkbox" aria-label="同时删除数据（不可恢复）" checked={deleteData} disabled={busy || Boolean(request)} onChange={event => setDeleteData(event.target.checked)} />同时删除数据（不可恢复）</label>}{!error && <button type="button" disabled={busy || Boolean(request) || !targets.length || targets.length > 20} onClick={() => void submit()}>{busy && !result ? '正在提交…' : '提交批量操作'}</button>}</div>{error && <p role="alert" className="mt-3 text-sm">{error}<button type="button" disabled={busy} onClick={() => pendingAction ? void actOnBatch(pendingAction.action) : void submit()}>{pendingAction ? '重试批次动作' : '重试批量操作'}</button></p>}{active && statusUnavailable && <p role="status" className="mt-3 text-sm">批次状态暂不可读，将自动重试读取。</p>}{result && <p aria-label="批次结果" role={unknown ? 'alert' : 'status'} className="mt-3 text-sm">批次{unknown ? '结果未知' : ` ${result.state}`} · {result.items.length} 项{failedItems.length > 0 && <span> · 失败项：{failedItems.map(item => `${String(item.name ?? item.deviceId ?? '设备')}（重试自 ${String(item.retryOf ?? item.operationId ?? '原操作')}）`).join('、')}</span>}{unknown && <button type="button" disabled={busy || Boolean(pendingAction && pendingAction.action !== 'verify')} onClick={() => void actOnBatch('verify')}>核实批次</button>}{failedItems.length > 0 && api.bulkAction && <button type="button" disabled={busy || Boolean(pendingAction && pendingAction.action !== 'retryFailed')} onClick={() => void actOnBatch('retryFailed')}>重试失败项</button>}</p>}{cancellable && api.bulkAction && <div className="mt-3 text-sm"><p>仅取消尚未准入的项目，已开始项目继续执行。</p><button type="button" disabled={busy || Boolean(pendingAction && pendingAction.action !== 'cancelPending')} onClick={() => void actOnBatch('cancelPending')}>取消未开始项</button></div>}{result && <button type="button" className="mt-3" disabled={busy || Boolean(pendingAction) || !settled} onClick={newBatch}>开始新批次</button>}</section>
}
