import { useQuery } from '@tanstack/react-query'
import { useId, useRef, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { AndroidManagementApi, Backup } from '../management-api'

export function BackupPanel({ api, deviceId, revision, runtimeState, control, hasControlSession, stale }: { api: Pick<AndroidManagementApi, 'backups' | 'backup' | 'restoreBackup' | 'operationByRequest'>; deviceId: string; revision: number; runtimeState?: string; control?: string; hasControlSession?: boolean; stale?: boolean }) {
  const noticeId = useId()
  const backups = useQuery({ queryKey: ['android-management', 'backups'], queryFn: api.backups })
  const own = (backups.data ?? []).filter((backup: Backup) => backup.deviceId === deviceId)
  const [busy, setBusy] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState('')
  const [needsVerification, setNeedsVerification] = useState(false)
  const pending = useRef<{ kind: 'create' | 'restore'; backupId?: string; requestId: string } | null>(null)
  const canCreate = (runtimeState === 'stopped' || runtimeState === 'retained') && control === 'idle' && hasControlSession === false && stale === false
  const create = async () => {
    const sameRequest = pending.current?.kind === 'create'
    const requestId = sameRequest ? pending.current!.requestId : crypto.randomUUID()
    if (!sameRequest) setNeedsVerification(false)
    pending.current = { kind: 'create', requestId }; setBusy(true); setError(''); setMessage('')
    if (needsVerification) return void verify()
    try { await api.backup({ requestId, deviceId, expectedRevision: revision }); pending.current = null; setNeedsVerification(false); setMessage('备份已创建'); await backups.refetch() }
    catch (cause) { if (cause instanceof ApiClientError && cause.status === 409) { setNeedsVerification(false); setError(cause.message) } else { setNeedsVerification(true); setError(cause instanceof Error ? cause.message : '备份结果尚未确认，请核实原请求') } }
    finally { setBusy(false) }
  }
  const restore = async (backupId: string) => {
    const sameRequest = pending.current?.kind === 'restore' && pending.current.backupId === backupId
    const requestId = sameRequest ? pending.current!.requestId : crypto.randomUUID()
    if (!sameRequest) setNeedsVerification(false)
    pending.current = { kind: 'restore', backupId, requestId }; setBusy(true); setError(''); setMessage('')
    if (needsVerification) return void verify()
    try { const result = await api.restoreBackup(backupId, { requestId, newName: '恢复实例' }); pending.current = null; setNeedsVerification(false); setMessage(`恢复已提交，操作 ${result.operationId ?? '已接收'} 将在资源看板中显示`); await backups.refetch() }
    catch (cause) { if (cause instanceof ApiClientError && cause.status === 409) { setNeedsVerification(false); setError(cause.message) } else { setNeedsVerification(true); setError(cause instanceof Error ? cause.message : '恢复结果尚未确认，请核实原请求') } }
    finally { setBusy(false) }
  }
  const verify = async () => {
    const request = pending.current
    if (!request) return
    setBusy(true); setError('')
    try { const operation = await api.operationByRequest(request.requestId); if (operation.state === 'succeeded') { pending.current = null; setNeedsVerification(false); setMessage('已核实操作完成'); await backups.refetch() } else setError(`操作状态：${operation.stageLabel}`) }
    catch (cause) { setError(cause instanceof Error ? cause.message : '操作仍待核实') }
    finally { setBusy(false) }
  }
  const retry = () => pending.current ? (needsVerification ? void verify() : pending.current.kind === 'create' ? void create() : pending.current.backupId ? void restore(pending.current.backupId) : undefined) : undefined
  return <section aria-label="实例备份" aria-busy={busy} className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">数据备份</h2><p className="mt-1 text-sm text-muted">仅允许已停止且无控制会话的实例。</p><p id={`${noticeId}-storage`} className="mt-2 text-sm text-muted">备份保存在本机，未加密，可能包含账号和应用私密数据。</p><p id={`${noticeId}-restore`} className="mt-2 text-sm text-muted">恢复会创建新实例并还原应用数据；不保证登录状态、DRM 或私有密钥可用。</p>{!canCreate && <p role="status" className="mt-2 text-sm text-muted">备份创建已禁用：实例必须已停止、状态新鲜、未被控制且没有活动控制会话。</p>}{backups.isError && <p role="alert" className="mt-2 text-sm">备份目录暂不可用。<button type="button" onClick={() => void backups.refetch()}>重新读取</button></p>}{!backups.isError && <button type="button" aria-describedby={`${noticeId}-storage`} disabled={busy || !canCreate} onClick={() => void create()}>{busy && pending.current?.kind === 'create' ? '正在创建…' : '创建停机备份'}</button>}{own.length === 0 && !backups.isPending && !backups.isError && <p className="mt-3 text-sm text-muted">此实例尚无备份。</p>}<div className="mt-3 grid gap-2">{own.map(backup => <article key={backup.id} className="rounded-control border border-line p-3"><span>{backup.id} · {backup.bytes} bytes</span><button type="button" aria-describedby={`${noticeId}-restore`} disabled={busy} onClick={() => void restore(backup.id)}>{busy && pending.current?.kind === 'restore' && pending.current.backupId === backup.id ? '正在恢复…' : '恢复为新实例'}</button></article>)}</div>{error && <p role="alert" className="mt-3 text-sm text-danger">{error}{pending.current && <button type="button" onClick={retry}>{needsVerification ? '核实原请求' : `重试${pending.current.kind === 'create' ? '创建备份' : '恢复'}`}</button>}</p>}{message && <p role="status" className="mt-3 text-sm">{message}</p>}</section>
}
