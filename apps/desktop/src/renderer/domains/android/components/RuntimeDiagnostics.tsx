import { useQuery } from '@tanstack/react-query'
import type { AndroidManagementApi } from '../management-api'

const labels: Record<string, string> = { platform: '平台', adb: 'ADB', lima: 'Lima', ssh: 'SSH', scrcpy: 'scrcpy', vm: '虚拟机', docker: 'Docker', binder: '设备绑定', images: '镜像', capacity: '容量', disk: '磁盘' }
const statusLabels = { pass: '通过', fail: '失败', unknown: '未知', unsupported: '不支持' }

export function RuntimeDiagnostics({ api }: { api: AndroidManagementApi }) {
  const environment = useQuery({ queryKey: ['android-management', 'environment'], queryFn: api.environment })
  const capabilities = useQuery({ queryKey: ['android-management', 'capabilities'], queryFn: api.capabilities })
  if (environment.isPending || capabilities.isPending) return <section role="status" className="rounded-card border border-line bg-surface p-5">正在检查安卓运行环境…</section>
  if (environment.isError || capabilities.isError || !environment.data || !capabilities.data) return <section role="alert" className="rounded-card border border-line bg-surface p-5">环境诊断暂不可用，请稍后重试。</section>
  const checks = environment.data.checks ?? {}, reasons = capabilities.data.reasons ?? {}
  return <section aria-label="安卓运行环境诊断" className="space-y-5 rounded-card border border-line bg-surface p-5"><header><h2 className="font-semibold">运行环境诊断</h2><p className="mt-1 text-sm text-muted">{environment.data.message ?? '尚未采集'} · {environment.data.runtimeId ?? 'unknown'}</p></header><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(checks).map(([name, check]) => <div key={name} className="rounded-control border border-line p-3"><div className="flex justify-between gap-3 text-sm"><strong>{labels[name] ?? name}</strong><span>{statusLabels[check.status]}</span></div><p className="mt-1 text-xs text-muted">{check.message}</p></div>)}</div><div className="rounded-control bg-surface-subtle p-3 text-sm"><h3 className="font-medium">能力</h3><p className="mt-2">管理：{String(capabilities.data.management)} · 控制：{String(capabilities.data.control)} · 镜像：{String(capabilities.data.images)}</p>{Object.values(reasons).map(reason => <p key={reason} className="mt-1 text-xs text-muted">{reason}</p>)}</div></section>
}
