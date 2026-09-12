import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiProvider } from './ApiProvider'
import { useDesktopSession } from './useDesktopSession'
import { StudioPage } from '../domains/workflows/pages/StudioPage'
import type { StudioLeaveReason } from '../../shared/automation-studio'

export function StudioApp() {
  const { session, status, message, reconnect, workspaceChanging } = useDesktopSession()
  const [transition, setTransition] = useState(false)
  const prepare = useRef<((reason: StudioLeaveReason) => Promise<boolean>) | null>(null)
  const registerLeave = useCallback((handler: ((reason: StudioLeaveReason) => Promise<boolean>) | null) => { prepare.current = handler }, [])
  useEffect(() => {
    const leave = window.autoflow.onPrepareStudioLeave?.(reason => prepare.current?.(reason) ?? Promise.resolve(false))
    const changed = window.autoflow.onStudioTransition?.(setTransition)
    return () => { leave?.(); changed?.() }
  }, [])
  return <div className="flex h-dvh flex-col bg-canvas text-ink">
    {status !== 'connected' || workspaceChanging ? <div role={status === 'offline' ? 'alert' : 'status'} className="flex shrink-0 items-center justify-between border-b border-line bg-surface px-5 py-2 text-sm"><span>{workspaceChanging ? '正在切换工作区…' : message || '正在连接本地服务…'}</span>{status === 'offline' ? <button className="font-semibold text-clay" onClick={() => void reconnect()}>恢复连接</button> : null}</div> : null}
    {session ? <ApiProvider key={session.workspaceKey} baseUrl={session.baseUrl} token={session.token} instanceId={session.instanceId} client={session.client}><div className="min-h-0 flex-1 overflow-hidden [&>div]:h-full"><StudioPage connected={status === 'connected'} locked={transition || workspaceChanging} registerLeave={registerLeave} /></div></ApiProvider> : <div className="flex flex-1 items-center justify-center text-sm text-muted">工作流工作台正在准备…</div>}
  </div>
}
