import { useQuery, useQueryClient } from '@tanstack/react-query'
import { GoogleLogo, PlugsConnected, WarningCircle } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsConnection, SheetsImpact } from '../sheets-api'

const states: Record<SheetsConnection['credentialState'], string> = { available: '可用', missing: '需要重新授权', invalid: '凭据已失效' }
type DisconnectMode = 'disconnect' | 'forgetCredential'
const modeLabels: Record<DisconnectMode, string> = { disconnect: '断开连接', forgetCredential: '断开并删除本机凭据' }

export type SheetsConnectionPanelProps = {
  api: SheetsApi
  scopeKey: string
  readonly?: boolean
  disabled?: boolean
  selectedId?: string | null
  onSelect?(connectionId: string): void
  onChanged?(): void
}

/** Lists the project's Google accounts and runs the desktop handshake to add one. */
export function SheetsConnectionPanel({ api, scopeKey, readonly = false, disabled = false, selectedId, onSelect, onChanged }: SheetsConnectionPanelProps) {
  const queries = useQueryClient()
  const connections = useQuery({ queryKey: ['sheets-connections', scopeKey], queryFn: () => api.connections(), retry: false })
  const [label, setLabel] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<{ connectionId: string; mode: DisconnectMode; revision: number; impacts: SheetsImpact[] } | null>(null)
  const locked = disabled || readonly

  const connect = async () => {
    const accountLabel = label.trim()
    if (!accountLabel || busy) return
    setBusy(true); setError(null)
    try {
      const authorization = await api.authorize(accountLabel)
      // A cancelled handshake is a normal outcome, not a failure.
      if (!authorization) return
      const operation = await api.connect(accountLabel, authorization.authorizationToken, crypto.randomUUID(), () => true)
      if (operation.status === 'failed') { setError(safeProjectError(operation.error ?? new Error('连接未建立'))); return }
      setLabel('')
      await queries.invalidateQueries({ queryKey: ['sheets-connections', scopeKey] })
      onChanged?.()
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  /**
   * Disconnecting revokes the local connection; deleting the credential touches
   * the operating system store. Both are confirmed against the shared impact
   * report first, because an in-use connection can still refuse the change.
   */
  const preview = async (connectionId: string, mode: DisconnectMode) => {
    if (busy) return
    setBusy(true); setError(null); setPending(null)
    try {
      const report = await api.previewDisconnect(connectionId, mode)
      if (report.blockers.length > 0) { setError(report.blockers.map(blocker => blocker.message).join(' ')); return }
      setPending({ connectionId, mode, revision: report.impactRevision, impacts: report.impacts })
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  const confirmDisconnect = async (action: { connectionId: string; mode: DisconnectMode; revision: number }) => {
    if (busy) return
    setBusy(true); setError(null)
    try {
      const operation = await api.disconnect(action.connectionId, { impactRevision: action.revision, mode: action.mode }, crypto.randomUUID(), () => true)
      if (operation.status === 'failed') { setError(safeProjectError(operation.error ?? new Error('断开未完成'))); return }
      setPending(null)
      await queries.invalidateQueries({ queryKey: ['sheets-connections', scopeKey] })
      onChanged?.()
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  return <section className="grid gap-4" aria-label="Google 账号">
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div><h4 className="text-lg font-semibold">Google 账号</h4><p className="mt-1 text-sm text-muted">凭据保存在系统凭据库，页面只保存一次性授权结果。</p></div>
      <div className="flex items-end gap-2">
        <label className="grid gap-1 text-sm"><span>账号名称</span><Input aria-label="Google 账号名称" className="h-9 w-56" value={label} disabled={locked || busy} placeholder="例如：运营账号" onChange={event => setLabel(event.target.value)} /></label>
        <Button size="sm" disabled={locked || busy || !label.trim()} onClick={() => void connect()}><GoogleLogo size={16} aria-hidden="true" />连接 Google 账号</Button>
      </div>
    </header>
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {connections.isPending ? <Skeleton className="h-24" /> : connections.error ? <p role="alert" className="m-0 text-sm text-danger">连接列表暂时无法读取。<Button size="sm" variant="ghost" onClick={() => void connections.refetch()}>重新载入</Button></p> :
      (connections.data?.items.length ?? 0) === 0 ? <p className="m-0 flex items-center gap-2 text-sm text-muted"><WarningCircle size={18} aria-hidden="true" />还没有连接 Google 账号。</p> :
        <TableScroll label="Google 账号" className="rounded-control border border-line">
          <Table data-variant="compact" aria-label="Google 账号">
            <TableHead><TableRow><TableCell>账号</TableCell><TableCell>凭据</TableCell><TableCell>权限</TableCell><TableCell>更新时间</TableCell><TableCell>选择</TableCell><TableCell /></TableRow></TableHead>
            <TableBody>
              {connections.data!.items.map(connection => <TableRow key={connection.connectionId} data-selected={connection.connectionId === selectedId ? 'true' : undefined}>
                <TableCell className="font-medium">{connection.accountLabel}</TableCell>
                <TableCell><span className={connection.credentialState === 'available' ? 'text-success' : 'text-warning'}>{states[connection.credentialState]}</span></TableCell>
                <TableCell>{connection.writable ? '可读可写' : connection.readable ? '只读' : '无权限'}</TableCell>
                <TableCell>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(connection.updatedAt))}</TableCell>
                <TableCell>{onSelect ? <Button size="sm" variant={connection.connectionId === selectedId ? 'primary' : 'ghost'} disabled={connection.credentialState !== 'available'} onClick={() => onSelect(connection.connectionId)}>{connection.connectionId === selectedId ? <><PlugsConnected size={16} aria-hidden="true" />已选择</> : '选择'}</Button> : null}</TableCell>
                <TableCell><div className="flex flex-wrap justify-end gap-2">
                  <Button size="sm" variant="ghost" disabled={locked || busy} onClick={() => void preview(connection.connectionId, 'disconnect')}>断开…</Button>
                  <Button size="sm" variant="ghost" disabled={locked || busy} onClick={() => void preview(connection.connectionId, 'forgetCredential')}>删除凭据…</Button>
                </div></TableCell>
              </TableRow>)}
            </TableBody>
          </Table>
        </TableScroll>}
    {pending ? <section className="grid gap-3 rounded-control border border-clay bg-surface p-4" aria-label="断开连接的确认">
      <h5 className="m-0 text-sm font-semibold">确认{modeLabels[pending.mode]}</h5>
      <ul className="m-0 grid gap-1 pl-5 text-sm text-muted">{pending.impacts.map((impact, index) => <li key={`${impact.code}-${index}`}>{impact.message}</li>)}</ul>
      <div className="flex flex-wrap gap-3">
        <Button size="sm" variant="primary" disabled={busy} onClick={() => void confirmDisconnect(pending)}>{modeLabels[pending.mode]}</Button>
        <Button size="sm" disabled={busy} onClick={() => setPending(null)}>取消</Button>
      </div>
    </section> : null}
  </section>
}
