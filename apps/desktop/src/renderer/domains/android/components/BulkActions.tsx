import { useState } from 'react'
import type { ManagementDevicePage, AndroidManagementApi, Bulk } from '../management-api'

export function BulkActions({ api, devices }: { api: Pick<AndroidManagementApi, 'bulk'> & Partial<Pick<AndroidManagementApi, 'bulkAction'>>; devices: ManagementDevicePage['items'] }) {
  const [selected, setSelected] = useState<string[]>([]), [action, setAction] = useState<'start' | 'stop' | 'restart' | 'delete'>('start'), [result, setResult] = useState<Bulk | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [request, setRequest] = useState<Record<string, unknown> | null>(null)
  const submit = async () => {
    const body = request ?? { requestId: crypto.randomUUID(), action, items: devices.filter(device => selected.includes(device.deviceId)).map(device => ({ deviceId: device.deviceId, expectedRevision: device.revision })) }
    setRequest(body); setBusy(true); setError('')
    try { setResult(await api.bulk(body)); setError('') } catch (cause) { setError(cause instanceof Error ? cause.message : '批次结果尚未确认，请重试') } finally { setBusy(false) }
  }
  const reconcile = async () => {
    if (!result || !api.bulkAction) return
    setBusy(true); setError('')
    try { setResult(await api.bulkAction(result.id, { requestId: String(request?.requestId ?? crypto.randomUUID()), action: 'verify' })) } catch (cause) { setError(cause instanceof Error ? cause.message : '批次核实失败') } finally { setBusy(false) }
  }
  const unknown = result?.state === 'needs_verification' || result?.items.some(item => ['accepted', 'needs_verification'].includes(String(item.state)))
  return <section aria-label="批量操作" aria-busy={busy} className="rounded-card border border-line bg-surface p-5"><header><h2 className="font-semibold">批量操作</h2><p className="mt-1 text-sm text-muted">目标在提交时冻结，单批最多 20 台。</p></header><div className="mt-3 grid gap-2">{devices.map(device => <label key={device.deviceId} className="flex items-center gap-2 text-sm"><input id={`bulk-${device.deviceId}`} aria-label={device.name} type="checkbox" checked={selected.includes(device.deviceId)} disabled={busy} onChange={event => setSelected(current => event.target.checked ? [...current, device.deviceId] : current.filter(id => id !== device.deviceId))} />{device.name} · 修订 {device.revision}</label>)}</div><div className="mt-3 flex gap-2"><select aria-label="批量动作" value={action} disabled={busy || Boolean(request)} onChange={event => setAction(event.target.value as typeof action)}><option value="start">启动</option><option value="stop">停止</option><option value="restart">重启</option><option value="delete">删除</option></select>{!error && <button type="button" disabled={busy || !selected.length || selected.length > 20} onClick={() => void submit()}>{busy && !result ? '正在提交…' : '提交批量操作'}</button>}</div>{error && <p role="alert" className="mt-3 text-sm">{error}<button type="button" disabled={busy} onClick={() => void submit()}>重试批量操作</button></p>}{result && <p role={unknown ? 'alert' : 'status'} className="mt-3 text-sm">批次{unknown ? '结果未知' : ` ${result.state}`} · {result.items.length} 项{unknown && <button type="button" disabled={busy} onClick={() => void reconcile()}>核实批次</button>}</p>}</section>
}
