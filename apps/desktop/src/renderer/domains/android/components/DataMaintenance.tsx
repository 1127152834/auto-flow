import { useEffect, useState } from 'react'
import { ApiClientError } from '../../../shared/api/client'
import type { AndroidManagementApi } from '../management-api'

type Preview = { items: Record<string, unknown>[]; previewId?: string; confirmationDigest: string }
type SaveDiagnostic = (id: string) => Promise<{ ok: true; value: { saved: boolean; path?: string } } | { ok: false; error: { message: string } }>

export function DataMaintenance({ api, saveDiagnostic, resourceIds, diagnosticDeviceIds = resourceIds }: { api: Pick<AndroidManagementApi, 'cleanupPreview' | 'cleanup' | 'diagnostics'> & Partial<Pick<AndroidManagementApi, 'operationByRequest' | 'verify' | 'cleanupResources'>>; saveDiagnostic?: SaveDiagnostic; resourceIds: string[]; diagnosticDeviceIds?: string[] }) {
  const [preview, setPreview] = useState<Preview | null>(null)
  const [message, setMessage] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  const [requestId, setRequestId] = useState<string | null>(null), [needsVerification, setNeedsVerification] = useState(false)
  const [diagnosticId, setDiagnosticId] = useState<string | null>(null)
  const [diagnosticSelection, setDiagnosticSelection] = useState<string[] | null>(null)
  const advancedDeviceIds = (diagnosticSelection ?? diagnosticDeviceIds.slice(0, 5)).filter((id) => diagnosticDeviceIds.includes(id))
  const [inventory, setInventory] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<string[]>([])
  const [loadingInventory, setLoadingInventory] = useState(Boolean(api.cleanupResources))
  const [inventoryRevision, setInventoryRevision] = useState(0)
  const readInventory = api.cleanupResources
  useEffect(() => {
    if (!readInventory) return
    let current = true
    setLoadingInventory(true); setError(''); setPreview(null); setInventory([]); setSelected([])
    void readInventory().then((page) => {
      if (!Array.isArray(page.items)) throw new Error('清理对象响应无效，请刷新后重试')
      if (current) setInventory(page.items)
    }).catch((cause) => {
      if (current) setError(cause instanceof Error ? cause.message : '无法读取清理对象')
    }).finally(() => { if (current) setLoadingInventory(false) })
    return () => { current = false }
  }, [readInventory, inventoryRevision])
  const inspect = async () => {
    setBusy(true); setError(''); setMessage(''); setPreview(null); setRequestId(null); setNeedsVerification(false)
    try { setPreview(await api.cleanupPreview(readInventory ? selected : resourceIds)) } catch (cause) { setError(cause instanceof Error ? cause.message : '清理预览失败') } finally { setBusy(false) }
  }
  const verify = async () => {
    if (!requestId) return
    setBusy(true); setError('')
    if (!api.operationByRequest) { setBusy(false); setError('当前服务不支持按原请求核实'); return }
    try {
      const operation = await api.operationByRequest(requestId)
      if (operation.state === 'needs_verification' && api.verify) {
        const verified = await api.verify(operation.operationId, { requestId })
        if (verified.state === 'succeeded') { setPreview(null); setNeedsVerification(false); setMessage('清理已完成'); setInventoryRevision((value) => value + 1) }
        else setMessage(`清理操作状态：${verified.stageLabel}`)
      } else {
        setMessage(`清理操作状态：${operation.stageLabel}`)
        if (operation.state === 'succeeded') { setPreview(null); setNeedsVerification(false); setInventoryRevision((value) => value + 1) }
      }
    } catch (cause) { setError(cause instanceof Error ? cause.message : '清理操作仍待核实') } finally { setBusy(false) }
  }
  const execute = async () => {
    if (!preview) return
    if (needsVerification) return void verify()
    setBusy(true); setError(''); setMessage('')
    const request = requestId ?? crypto.randomUUID(); setRequestId(request)
    try {
      const result = await api.cleanup({ requestId: request, previewId: preview.previewId ?? preview.confirmationDigest, confirmationDigest: preview.confirmationDigest })
      if (result.state === 'succeeded') { setPreview(null); setNeedsVerification(false); setMessage('清理已完成'); setInventoryRevision((value) => value + 1) }
      else { setNeedsVerification(true); setMessage(`清理请求已${result.state === 'running' ? '执行' : '接收'}，结果待核实`) }
    } catch (cause) {
      if (cause instanceof ApiClientError && cause.status === 409) { setPreview(null); setError('清理预览已变化，请重新预览后确认') }
      else { setNeedsVerification(true); setError(cause instanceof Error ? cause.message : '清理结果尚未确认，请核实原请求') }
    } finally { setBusy(false) }
  }
  const diagnostic = async (advanced = false) => {
    setBusy(true); setError(''); setMessage(''); setDiagnosticId(null)
    try { const result = await api.diagnostics({ requestId: crypto.randomUUID(), deviceIds: advanced ? advancedDeviceIds : diagnosticDeviceIds, ...(advanced ? { includeAdvancedLogs: true, advancedLogsConsent: true } : {}) }); setDiagnosticId(result.id); setMessage(advanced ? '高级日志摘要已生成，内容已脱敏' : '诊断已生成，内容已脱敏') }
    catch (cause) { setError(cause instanceof Error ? cause.message : '诊断结果尚未确认，请刷新核实') } finally { setBusy(false) }
  }
  const save = async () => {
    if (!diagnosticId || !saveDiagnostic) return
    setBusy(true); setError('')
    try {
      const result = await saveDiagnostic(diagnosticId)
      if (!result.ok) throw new Error(result.error.message)
      if (result.value.saved) setMessage('诊断已保存')
    } catch (cause) { setError(cause instanceof Error ? cause.message : '无法保存诊断') } finally { setBusy(false) }
  }
  const kind = (value: unknown) => ({ device: '保留的数据', backup: '备份', 'backup-staging': '备份暂存文件', 'backup-orphan': '未登记备份' }[String(value)] ?? String(value ?? '清理对象'))
  const display = (value: unknown): string => {
    if (Array.isArray(value)) return value.map(display).join('、') || '无'
    if (value && typeof value === 'object') {
      const reference = value as Record<string, unknown>
      return reference.name ? String(reference.name) : reference.kind && reference.id ? `${reference.kind}：${reference.id}` : JSON.stringify(value)
    }
    return value == null || value === '' ? '无' : String(value)
  }
  const purpose = (value: unknown) => ({ android: '安卓数据', 'backup-staging': '未完成发布的备份暂存文件', 'unregistered-backup': '尚未登记的备份文件', 'retained-data': '移除实例后保留的数据' }[String(value)] ?? display(value))
  return <section aria-label="数据维护" aria-busy={busy} className="rounded-card border border-line bg-surface p-5"><h2 className="font-semibold">数据维护</h2><div className="mt-3 flex flex-wrap gap-2">{readInventory && <button type="button" disabled={busy || needsVerification || loadingInventory} onClick={() => setInventoryRevision((value) => value + 1)}>刷新清理对象</button>}<button type="button" disabled={busy || needsVerification || loadingInventory || Boolean(readInventory && selected.length === 0)} onClick={() => void inspect()}>预览清理</button><button type="button" disabled={busy} onClick={() => void diagnostic()}>生成脱敏诊断</button><button type="button" disabled={busy || advancedDeviceIds.length === 0} onClick={() => { if (window.confirm('仅本次采集所选设备最近 5 分钟、最多 64 KiB 的日志元数据，不导出消息正文。确认生成？')) void diagnostic(true) }}>生成高级日志诊断</button>{diagnosticId && saveDiagnostic && <button type="button" disabled={busy} onClick={() => void save()}>保存诊断</button>}{preview && <button type="button" disabled={busy} onClick={() => void execute()}>{needsVerification ? '核实原清理请求' : `确认清理 ${preview.items.length} 项`}</button>}</div>{diagnosticDeviceIds.length > 1 && <fieldset className="mt-4 grid gap-2" disabled={busy}><legend className="text-sm font-medium">高级日志设备（最多 5 台）</legend>{diagnosticDeviceIds.map((id) => <label key={id} className="flex items-center gap-2 break-all text-sm"><input type="checkbox" aria-label={`诊断设备 ${id}`} checked={advancedDeviceIds.includes(id)} disabled={!advancedDeviceIds.includes(id) && advancedDeviceIds.length >= 5} onChange={(event) => setDiagnosticSelection(event.target.checked ? [...advancedDeviceIds, id] : advancedDeviceIds.filter((item) => item !== id))} />{id}</label>)}</fieldset>}{readInventory && <fieldset className="mt-4 grid gap-2" disabled={busy || needsVerification || loadingInventory}><legend className="text-sm font-medium">选择清理对象</legend>{loadingInventory ? <p role="status">正在读取清理对象…</p> : inventory.length === 0 ? <p className="text-sm text-muted">暂无可清理对象</p> : inventory.map((item) => <label key={String(item.id)} className="flex items-start gap-2 break-all text-sm"><input type="checkbox" checked={selected.includes(String(item.id))} onChange={(event) => { const id = String(item.id); setPreview(null); setSelected((items) => event.target.checked ? [...items, id] : items.filter((value) => value !== id)) }} />{kind(item.kind)}：{String(item.id)} · {display(item.size)} bytes</label>)}</fieldset>}{preview && <div className="mt-4 grid gap-2" aria-label="清理预览">{preview.items.map((item, index) => <article key={String(item.id ?? index)} className="rounded-control border border-line bg-surface-subtle p-3 text-xs"><p><strong>对象：</strong>{display(item.id)} · {kind(item.kind)}</p><p className="mt-1"><strong>用途：</strong>{purpose(item.purpose)} · <strong>大小：</strong>{display(item.size)} bytes</p><p className="mt-1"><strong>归属：</strong>{display(item.ownership ?? item.workspaceId)}</p><p className="mt-1"><strong>引用：</strong>{display(item.references ?? item.reference ?? item.workspaceId)}</p><p className="mt-1"><strong>{item.reversible === false ? '不可逆' : '可恢复'}</strong> · {display(item.irreversibleImpact)} · <strong>指纹：</strong>{display(item.fingerprint)}</p></article>)}</div>}{error && <p role="alert" className="mt-3 text-sm text-danger">{error}</p>}{message && <p role="status" className="mt-3 text-sm">{message}</p>}</section>
}
