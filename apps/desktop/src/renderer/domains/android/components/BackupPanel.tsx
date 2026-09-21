import { useQuery } from '@tanstack/react-query'
import type { AndroidManagementApi, Backup } from '../management-api'

export function BackupPanel({ api, deviceId, revision }: { api: Pick<AndroidManagementApi, 'backups' | 'backup' | 'restoreBackup'>; deviceId: string; revision: number }) {
  const backups = useQuery({ queryKey: ['android-management', 'backups'], queryFn: api.backups })
  const own = (backups.data ?? []).filter((backup: Backup) => backup.deviceId === deviceId)
  const create = async () => { await api.backup({ requestId: crypto.randomUUID(), deviceId, expectedRevision: revision }); await backups.refetch() }
  return <section aria-label="实例备份" className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">数据备份</h2><p className="mt-1 text-sm text-muted">仅允许已停止且无控制会话的实例。</p><button type="button" onClick={() => void create()}>创建停机备份</button><div className="mt-3 grid gap-2">{own.map(backup => <article key={backup.id} className="rounded-control border border-line p-3"><span>{backup.id} · {backup.bytes} bytes</span><button type="button" onClick={() => void api.restoreBackup(backup.id, { requestId: crypto.randomUUID(), newName: '恢复实例' })}>恢复为新实例</button></article>)}</div></section>
}
