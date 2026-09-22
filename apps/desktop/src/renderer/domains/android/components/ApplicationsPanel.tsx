import { useMemo, useState } from 'react'
import type { Apps, ConsoleSession, FleetApi } from '../fleet-api'
import { Action } from './PrototypeControls'

type DestructiveAction = 'uninstall' | 'clearData'
type RequestId = ReturnType<typeof crypto.randomUUID>
type Props = { api?: Pick<FleetApi, 'launch' | 'appAction'> & Partial<Pick<FleetApi, 'verifyApp'>>; apps?: Apps; session: ConsoleSession | null; onSession(s: ConsoleSession): void; onRefresh(): void }

export function ApplicationsPanel({ api, apps, session, onSession, onRefresh }: Props) {
  const [search, setSearch] = useState('')
  const [pending, setPending] = useState<{ action: DestructiveAction; packageName: string; requestId: RequestId } | null>(null)
  const [error, setError] = useState('')
  const [unknownRequest, setUnknownRequest] = useState<{ requestId: string; generation: number } | null>(null)
  const canWrite = !unknownRequest && session?.access === 'manual' && session.state === 'connected' && session.endpoint === 'embedded'
  const visible = useMemo(() => (apps?.applications ?? (apps?.packages ?? []).map((packageName) => ({ packageName, versionCode: null, versionName: null, system: false, protected: false }))).filter((app) => app.packageName.toLowerCase().includes(search.toLowerCase())), [apps, search])
  const run = async (action: 'launch' | 'stop' | DestructiveAction, packageName: string, requestId = crypto.randomUUID()) => {
    if (!session || !api || !canWrite) return
    const app = visible.find((item) => item.packageName === packageName)
    const metadataKnown = apps?.applications?.some((record) => record.packageName === packageName && record.system === false && record.protected === false) === true
    if ((action === 'uninstall' || action === 'clearData') && (!app || !metadataKnown)) return
    setError('')
    try {
      const next = action === 'launch' ? await api.launch(session, packageName, requestId) : await api.appAction(session, action, packageName, requestId)
      onSession(next); onRefresh(); setPending(null)
    } catch (cause) {
      const code = typeof cause === 'object' && cause !== null && 'code' in cause ? String((cause as { code?: unknown }).code) : ''
      if (!['ANDROID_PROTECTED_APP', 'ANDROID_APP_INFO_UNKNOWN', 'ANDROID_SESSION_STALE', 'ANDROID_INPUT_FORBIDDEN'].includes(code)) setUnknownRequest({ requestId, generation: session.generation })
      setError(cause instanceof Error ? cause.message : '应用操作结果未知')
    }
  }
  const refreshUnknown = () => {
    const target = pending
    onRefresh()
    setPending(null)
    setError(target ? `${target.packageName} 操作结果未知，已刷新应用信息，请核对设备状态` : '应用操作结果未知，已刷新应用信息，请核对设备状态')
  }
  const verifyUnknown = async () => {
    if (!session || !api?.verifyApp || !unknownRequest) return
    try {
      onSession(await api.verifyApp(session, unknownRequest.requestId, unknownRequest.generation))
      setUnknownRequest(null)
      setPending(null)
      setError('应用操作已按原请求核实')
      onRefresh()
    } catch (cause) { setError(cause instanceof Error ? cause.message : '应用操作仍未核实') }
  }
  return <section aria-label="应用管理" className="rounded-card border border-line bg-surface p-5">
    <h2 className="font-semibold">应用管理</h2>
    <input aria-label="搜索应用" role="searchbox" placeholder="搜索包名" value={search} onChange={(event) => setSearch(event.target.value)} className="mt-3" />
    <div className="mt-3 grid gap-2">{visible.map((app) => {
      const appMetadataKnown = apps?.applications?.some((record) => record.packageName === app.packageName && record.system === false && record.protected === false) === true
      return <article key={app.packageName} className="rounded-control border border-line p-3"><div className="flex items-start justify-between gap-3"><div><strong>{app.packageName}</strong><p className="text-xs text-muted">{app.protected ? '受保护应用' : app.system ? '系统应用' : appMetadataKnown ? '用户应用' : '应用类型待核实'} · {app.versionName ?? (app.versionCode == null ? '版本待核实' : `版本 ${app.versionCode}`)}</p></div><div className="flex flex-wrap gap-2"><Action disabled={!canWrite} onClick={() => void run('launch', app.packageName)}>启动</Action><Action disabled={!canWrite} onClick={() => void run('stop', app.packageName)}>停止</Action><Action disabled={!canWrite || !appMetadataKnown} onClick={() => setPending({ action: 'clearData', packageName: app.packageName, requestId: crypto.randomUUID() })}>清除数据</Action><Action disabled={!canWrite || !appMetadataKnown} onClick={() => setPending({ action: 'uninstall', packageName: app.packageName, requestId: crypto.randomUUID() })}>卸载</Action></div></div></article>
    })}</div>
    {!visible.length && <p className="mt-3 text-sm text-muted">没有匹配的应用。</p>}
    {error && <div role="alert" className="mt-3 text-sm text-danger">{error}{unknownRequest && api?.verifyApp && <button type="button" onClick={() => void verifyUnknown()}>按原请求核实</button>}<button type="button" onClick={refreshUnknown}>刷新应用状态</button></div>}
    {pending && <div role="dialog" aria-modal="true" className="mt-4 rounded-control border border-line bg-surface-subtle p-4"><h3 className="font-semibold">确认{pending.action === 'clearData' ? '清除数据' : '卸载'}</h3><p className="mt-2 text-sm">将对 {pending.packageName} 执行不可逆操作。</p><div className="mt-3 flex gap-2"><button type="button" onClick={() => setPending(null)}>取消</button><button type="button" disabled={!canWrite || !apps?.applications?.some((record) => record.packageName === pending.packageName && record.system === false && record.protected === false)} onClick={() => void run(pending.action, pending.packageName, pending.requestId)}>确认{pending.action === 'clearData' ? '清除数据' : '卸载'}</button></div></div>}
  </section>
}
