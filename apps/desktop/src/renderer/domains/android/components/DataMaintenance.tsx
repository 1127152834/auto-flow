import { useState } from 'react'
import type { AndroidManagementApi } from '../management-api'

export function DataMaintenance({ api, resourceIds }: { api: Pick<AndroidManagementApi, 'cleanupPreview' | 'cleanup' | 'diagnostics'>; resourceIds: string[] }) {
  const [preview, setPreview] = useState<{ items: Record<string, unknown>[]; confirmationDigest: string } | null>(null)
  const [message, setMessage] = useState('')
  const inspect = async () => setPreview(await api.cleanupPreview(resourceIds))
  const execute = async () => { if (!preview) return; await api.cleanup({ requestId: crypto.randomUUID(), confirmationDigest: preview.confirmationDigest }); setMessage('清理已接受') }
  const diagnostic = async () => { await api.diagnostics({ requestId: crypto.randomUUID(), deviceIds: resourceIds }); setMessage('诊断已生成，内容已脱敏') }
  return <section aria-label="数据维护" className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">数据维护</h2><div className="mt-3 flex flex-wrap gap-2"><button type="button" onClick={() => void inspect()}>预览清理</button><button type="button" onClick={() => void diagnostic()}>生成脱敏诊断</button>{preview && <button type="button" onClick={() => void execute()}>确认清理 {preview.items.length} 项</button>}</div>{message && <p role="status" className="mt-3 text-sm">{message}</p>}</section>
}
