import { useMemo, useState } from 'react'
import type { Apps, ConsoleSession, FleetApi } from '../fleet-api'
import { Action } from './PrototypeControls'

type DestructiveAction = 'uninstall' | 'clearData'
type RequestId = ReturnType<typeof crypto.randomUUID>
type Props = { api?: Pick<FleetApi, 'launch' | 'appAction'>; apps?: Apps; session: ConsoleSession | null; onSession(s: ConsoleSession): void; onRefresh(): void }

export function ApplicationsPanel({ api, apps, session, onSession, onRefresh }: Props) {
  const [search, setSearch] = useState('')
  const [pending, setPending] = useState<{ action: DestructiveAction; packageName: string; requestId: RequestId } | null>(null)
  const [error, setError] = useState('')
  const visible = useMemo(() => (apps?.applications ?? (apps?.packages ?? []).map((packageName) => ({ packageName, versionCode: null, versionName: null, system: false, protected: false }))).filter((app) => app.packageName.toLowerCase().includes(search.toLowerCase())), [apps, search])
  const run = async (action: 'launch' | 'stop' | DestructiveAction, packageName: string, requestId = crypto.randomUUID()) => {
    if (!session || !api) return
    setError('')
    try {
      const next = action === 'launch' ? await api.launch(session, packageName, requestId) : await api.appAction(session, action, packageName, requestId)
      onSession(next); onRefresh(); setPending(null)
    } catch (cause) { setError(cause instanceof Error ? cause.message : '应用操作结果未知') }
  }
  return <section aria-label="应用管理" className="rounded-card border border-line bg-surface p-5">
    <h2 className="font-semibold">应用管理</h2>
    <input aria-label="搜索应用" role="searchbox" placeholder="搜索包名" value={search} onChange={(event) => setSearch(event.target.value)} className="mt-3" />
    <div className="mt-3 grid gap-2">{visible.map((app) => <article key={app.packageName} className="rounded-control border border-line p-3"><div className="flex items-start justify-between gap-3"><div><strong>{app.packageName}</strong><p className="text-xs text-muted">{app.protected ? '受保护应用' : app.system ? '系统应用' : '用户应用'} · {app.versionName ?? (app.versionCode == null ? '版本待核实' : `版本 ${app.versionCode}`)}</p></div><div className="flex flex-wrap gap-2"><Action disabled={!session} onClick={() => void run('launch', app.packageName)}>启动</Action><Action disabled={!session} onClick={() => void run('stop', app.packageName)}>停止</Action><Action disabled={!session || app.protected} onClick={() => setPending({ action: 'clearData', packageName: app.packageName, requestId: crypto.randomUUID() })}>清除数据</Action><Action disabled={!session || app.protected} onClick={() => setPending({ action: 'uninstall', packageName: app.packageName, requestId: crypto.randomUUID() })}>卸载</Action></div></div></article>)}</div>
    {!visible.length && <p className="mt-3 text-sm text-muted">没有匹配的应用。</p>}
    {error && <div role="alert" className="mt-3 text-sm text-danger">{error}<button type="button" onClick={() => pending && void run(pending.action, pending.packageName, pending.requestId)}>按原请求核实</button></div>}
    {pending && <div role="dialog" aria-modal="true" className="mt-4 rounded-control border border-line bg-surface-subtle p-4"><h3 className="font-semibold">确认{pending.action === 'clearData' ? '清除数据' : '卸载'}</h3><p className="mt-2 text-sm">将对 {pending.packageName} 执行不可逆操作。</p><div className="mt-3 flex gap-2"><button type="button" onClick={() => setPending(null)}>取消</button><button type="button" onClick={() => void run(pending.action, pending.packageName, pending.requestId)}>确认{pending.action === 'clearData' ? '清除数据' : '卸载'}</button></div></div>}
  </section>
}
