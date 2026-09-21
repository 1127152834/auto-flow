import { useState } from 'react'
import type { ManagementDevicePage, AndroidManagementApi, Bulk } from '../management-api'

export function BulkActions({ api, devices }: { api: Pick<AndroidManagementApi, 'bulk'>; devices: ManagementDevicePage['items'] }) {
  const [selected, setSelected] = useState<string[]>([])
  const [action, setAction] = useState<'start' | 'stop' | 'restart' | 'delete'>('start')
  const [result, setResult] = useState<Bulk | null>(null)
  const submit = async () => {
    const batch = await api.bulk({ requestId: crypto.randomUUID(), action, items: devices.filter(device => selected.includes(device.deviceId)).map(device => ({ deviceId: device.deviceId, expectedRevision: device.revision })) })
    setResult(batch)
  }
  return <section aria-label="批量操作" className="rounded-card border border-line bg-surface p-5"><header><h2 className="font-semibold">批量操作</h2><p className="mt-1 text-sm text-muted">目标在提交时冻结，单批最多 20 台。</p></header><div className="mt-3 grid gap-2">{devices.map(device => <label key={device.deviceId} className="flex items-center gap-2 text-sm"><input id={`bulk-${device.deviceId}`} aria-label={device.name} type="checkbox" checked={selected.includes(device.deviceId)} onChange={event => setSelected(current => event.target.checked ? [...current, device.deviceId] : current.filter(id => id !== device.deviceId))} />{device.name} · 修订 {device.revision}</label>)}</div><div className="mt-3 flex gap-2"><select aria-label="批量动作" value={action} onChange={event => setAction(event.target.value as typeof action)}><option value="start">启动</option><option value="stop">停止</option><option value="restart">重启</option><option value="delete">删除</option></select><button type="button" disabled={!selected.length || selected.length > 20} onClick={() => void submit()}>提交批量操作</button></div>{result && <p role="status" className="mt-3 text-sm">批次 {result.state} · {result.items.length} 项</p>}</section>
}
