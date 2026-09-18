import { useQuery, useQueryClient } from '@tanstack/react-query'
import { GoogleLogo, PlugsConnected, WarningCircle } from '@phosphor-icons/react'
import { useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsConnection } from '../sheets-api'

const states: Record<SheetsConnection['credentialState'], string> = { available: '可用', missing: '需要重新授权', invalid: '凭据已失效' }

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
            <TableHead><TableRow><TableCell>账号</TableCell><TableCell>凭据</TableCell><TableCell>权限</TableCell><TableCell>更新时间</TableCell><TableCell /></TableRow></TableHead>
            <TableBody>
              {connections.data!.items.map(connection => <TableRow key={connection.connectionId} data-selected={connection.connectionId === selectedId ? 'true' : undefined}>
                <TableCell className="font-medium">{connection.accountLabel}</TableCell>
                <TableCell><span className={connection.credentialState === 'available' ? 'text-success' : 'text-warning'}>{states[connection.credentialState]}</span></TableCell>
                <TableCell>{connection.writable ? '可读可写' : connection.readable ? '只读' : '无权限'}</TableCell>
                <TableCell>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(connection.updatedAt))}</TableCell>
                <TableCell>{onSelect ? <Button size="sm" variant={connection.connectionId === selectedId ? 'primary' : 'ghost'} disabled={connection.credentialState !== 'available'} onClick={() => onSelect(connection.connectionId)}>{connection.connectionId === selectedId ? <><PlugsConnected size={16} aria-hidden="true" />已选择</> : '选择'}</Button> : null}</TableCell>
              </TableRow>)}
            </TableBody>
          </Table>
        </TableScroll>}
  </section>
}
