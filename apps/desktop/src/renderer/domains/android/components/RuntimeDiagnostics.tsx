import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { AndroidManagementApi } from '../management-api'

const labels: Record<string, string> = { platform: '平台', adb: 'ADB', lima: 'Lima', ssh: 'SSH', scrcpy: 'scrcpy', vm: '虚拟机', docker: 'Docker', binder: '设备绑定', images: '镜像', capacity: '容量', disk: '磁盘' }
const statusLabels = { pass: '通过', fail: '失败', unknown: '未知', unsupported: '不支持' }

type DiagnosticsApi = Pick<AndroidManagementApi, 'environment' | 'capabilities'> & Partial<Pick<AndroidManagementApi, 'checkEnvironment' | 'operationByRequest' | 'verify'>>

export function RuntimeDiagnostics({ api }: { api: DiagnosticsApi }) {
  const environment = useQuery({ queryKey: ['android-management', 'environment'], queryFn: api.environment })
  const capabilities = useQuery({ queryKey: ['android-management', 'capabilities'], queryFn: api.capabilities })
  const [checking, setChecking] = useState(false), [checkError, setCheckError] = useState(''), [checkRequestId, setCheckRequestId] = useState<string | null>(null), [checkPending, setCheckPending] = useState(false)
  const refresh = async () => {
    if (!api.checkEnvironment) { setCheckError('当前服务不支持持久环境检查'); return }
    const requestId = crypto.randomUUID(); setCheckRequestId(requestId); setChecking(true); setCheckPending(false); setCheckError('')
    try {
      const operation = await api.checkEnvironment({ requestId })
      if (['queued', 'running', 'needs_verification'].includes(operation.state)) { setCheckPending(true); return }
      const refreshed = await Promise.all([environment.refetch(), capabilities.refetch()])
      if (refreshed.some(result => result.error)) setCheckError('检查已完成，但最新环境快照暂不可读；已保留旧快照')
    } catch (cause) { setCheckPending(true); setCheckError(cause instanceof Error ? cause.message : '环境检查结果未知，请核实原请求') }
    finally { setChecking(false) }
  }
  const verifyCheck = async () => {
    if (!checkRequestId || !api.operationByRequest) return
    setChecking(true); setCheckError('')
    try {
      const operation = await api.operationByRequest(checkRequestId)
      const verified = operation.state === 'needs_verification' && api.verify ? await api.verify(operation.operationId, { requestId: checkRequestId }) : operation
      if (verified.state === 'succeeded') {
        setCheckPending(false)
        const refreshed = await Promise.all([environment.refetch(), capabilities.refetch()])
        if (refreshed.some(result => result.error)) setCheckError('检查已核实，但最新环境快照暂不可读；已保留旧快照')
      }
      else {
        setCheckPending(['queued', 'running', 'needs_verification'].includes(verified.state))
        setCheckError(`环境检查状态：${verified.stageLabel}`)
      }
    } catch (cause) { setCheckError(cause instanceof Error ? cause.message : '环境检查结果仍待核实') }
    finally { setChecking(false) }
  }
  if (environment.isPending || capabilities.isPending) return <section role="status" className="rounded-card border border-line bg-surface p-5">正在检查安卓运行环境…</section>
  if (!environment.data || !capabilities.data) return <section role="alert" className="rounded-card border border-line bg-surface p-5">环境诊断暂不可用，请稍后重试。</section>
  const checks = environment.data.checks ?? {}, reasons = capabilities.data.reasons ?? {}
  const stale = Boolean(environment.isError || capabilities.isError || checkPending || checkError)
  return <section aria-label="安卓运行环境诊断" aria-busy={checking} className="space-y-5 rounded-card border border-line bg-surface p-5"><header><div className="flex items-start justify-between gap-3"><div><h2 className="font-semibold">运行环境诊断</h2><p className="mt-1 text-sm text-muted">{environment.data.message ?? '尚未采集'} · {environment.data.runtimeId ?? 'unknown'}</p></div><button type="button" disabled={checking} onClick={() => void refresh()}>{checking ? '检查中…' : '重新检查'}</button></div><p className="mt-2 text-xs text-muted">检查时间：<time dateTime={environment.data.checkedAt}>{environment.data.checkedAt}</time>{stale && <span className="ml-2 text-danger">快照可能陈旧</span>}</p></header><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(checks).map(([name, check]) => <div key={name} className="rounded-control border border-line p-3"><div className="flex justify-between gap-3 text-sm"><strong>{labels[name] ?? name}</strong><span>{statusLabels[check.status]}</span></div><p className="mt-1 text-xs text-muted">{check.message}</p>{check.action && <p className="mt-1 text-xs text-muted">处理：{check.action}</p>}</div>)}</div><div className="rounded-control bg-surface-subtle p-3 text-sm"><h3 className="font-medium">能力</h3><p className="mt-2">管理：{String(capabilities.data.management)} · 控制：{String(capabilities.data.control)} · 镜像：{String(capabilities.data.images)}</p>{Object.values(reasons).map(reason => <p key={reason} className="mt-1 text-xs text-muted">{reason}</p>)}</div>{checkError && <p role="alert" className="text-sm text-danger">{checkError}</p>}{checkPending && checkRequestId && <p className="text-sm text-muted">本次检查结果未知，保留旧快照直到核实。<button type="button" disabled={checking} onClick={() => void verifyCheck()}>核实原检查请求</button></p>}</section>
}
