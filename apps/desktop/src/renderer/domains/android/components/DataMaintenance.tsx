import { useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { AndroidManagementApi } from '../management-api'

export function DataMaintenance({ api, resourceIds, diagnosticDeviceIds = resourceIds }: { api: Pick<AndroidManagementApi, 'cleanupPreview' | 'cleanup' | 'diagnostics'> & Partial<Pick<AndroidManagementApi, 'operationByRequest'>>; resourceIds: string[]; diagnosticDeviceIds?: string[] }) {
  const [preview, setPreview] = useState<{ items: Record<string, unknown>[]; previewId?: string; confirmationDigest: string } | null>(null)
  const [message, setMessage] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [requestId, setRequestId] = useState<string | null>(null), [needsVerification, setNeedsVerification] = useState(false)
  const inspect = async () => {
    setBusy(true); setError(''); setMessage(''); setPreview(null); setRequestId(null); setNeedsVerification(false)
    try { setPreview(await api.cleanupPreview(resourceIds)) } catch (cause) { setError(cause instanceof Error ? cause.message : '清理预览失败') } finally { setBusy(false) }
  }
  const execute = async () => {
    if (!preview) return
    setBusy(true); setError(''); setMessage('')
    if (needsVerification) return void verify()
    const request = requestId ?? crypto.randomUUID(); setRequestId(request)
    try { await api.cleanup({ requestId: request, previewId: preview.previewId ?? preview.confirmationDigest, confirmationDigest: preview.confirmationDigest }); setPreview(null); setNeedsVerification(false); setMessage('清理已完成') }
    catch (cause) {
      if (cause instanceof ApiClientError && cause.status === 409) { setPreview(null); setError('清理预览已变化，请重新预览后确认') }
      else { setNeedsVerification(true); setError(cause instanceof Error ? cause.message : '清理结果尚未确认，请核实原请求') }
    } finally { setBusy(false) }
  }
  const verify = async () => {
    if (!requestId) return
    setBusy(true); setError('')
    if (!api.operationByRequest) return setError('当前服务不支持按原请求核实')
    try { const operation = await api.operationByRequest(requestId); setMessage(`清理操作状态：${operation.stageLabel}`); if (operation.state === 'succeeded') { setPreview(null); setNeedsVerification(false) } }
    catch (cause) { setError(cause instanceof Error ? cause.message : '清理操作仍待核实') }
    finally { setBusy(false) }
  }
  const diagnostic = async () => {
    setBusy(true); setError(''); setMessage('')
    try { await api.diagnostics({ requestId: crypto.randomUUID(), deviceIds: diagnosticDeviceIds }); setMessage('诊断已生成，内容已脱敏') }
    catch (cause) { setError(cause instanceof Error ? cause.message : '诊断结果尚未确认，请刷新核实') } finally { setBusy(false) }
  }
  const display = (value: unknown) => Array.isArray(value) ? value.join('、') : value == null || value === '' ? '无' : String(value)
  return <section aria-label="数据维护" aria-busy={busy} className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">数据维护</h2><div className="mt-3 flex flex-wrap gap-2"><button type="button" disabled={busy} onClick={() => void inspect()}>预览清理</button><button type="button" disabled={busy} onClick={() => void diagnostic()}>生成脱敏诊断</button>{preview && <button type="button" disabled={busy} onClick={() => void execute()}>{needsVerification ? '核实原清理请求' : `确认清理 ${preview.items.length} 项`}</button>}</div>{preview && <div className="mt-4 grid gap-2" aria-label="清理预览">{preview.items.map((item, index) => <article key={String(item.id ?? index)} className="rounded-control border border-line bg-surface-subtle p-3 text-xs"><p><strong>对象：</strong>{display(item.id)} · {display(item.kind ?? 'cleanup')}</p><p className="mt-1"><strong>用途：</strong>{display(item.purpose)} · <strong>大小：</strong>{display(item.size)} bytes</p><p className="mt-1"><strong>引用：</strong>{display(item.references ?? item.reference ?? item.workspaceId)}</p><p className="mt-1"><strong>{item.reversible === false ? '不可逆' : '可恢复'}</strong> · <strong>指纹：</strong>{display(item.fingerprint)}</p></article>)}</div>}{error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}{message && <p role="status" className="mt-3 text-sm">{message}</p>}</section>
}
