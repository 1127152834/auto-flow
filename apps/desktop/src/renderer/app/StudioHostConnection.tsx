import { useLayoutEffect, useState, type ReactNode } from 'react'
import { configureStudioConnection } from '../domains/workflows/api/config'
import { createStudioHttpTransport } from '../domains/workflows/api/http-transport'
import { useDesktopSession } from './useDesktopSession'

/** Bind the standalone Studio renderer to the authenticated service owned by Electron. */
export function StudioHostConnection({ children }: { children: ReactNode }) {
  const connection = useDesktopSession()
  const session = connection.session
  const sessionKey = session ? `${session.workspaceKey}:${session.instanceId}:${session.baseUrl}` : null
  const [configuredKey, setConfiguredKey] = useState<string | null>(null)

  useLayoutEffect(() => {
    if (!session || !sessionKey) return
    const restore = configureStudioConnection(
      session.baseUrl,
      createStudioHttpTransport(session.baseUrl, session.token),
    )
    setConfiguredKey(sessionKey)
    return () => {
      restore()
      setConfiguredKey(current => current === sessionKey ? null : current)
    }
  }, [session, sessionKey])

  if (!session || configuredKey === null) {
    return <main className="studio-shell grid min-h-screen place-items-center" aria-label="工作流工作台连接状态">
      <div className="rounded-lg border bg-white p-5 text-sm shadow-sm">
        <p role="status">{connection.status === 'offline' ? connection.message || '本地服务暂不可用' : '正在连接本地工作区服务…'}</p>
        {connection.status === 'offline' && <button className="mt-3 rounded border px-3 py-1.5" onClick={() => void connection.reconnect(false)}>重新连接</button>}
      </div>
    </main>
  }

  return children
}
