import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useApi } from '../../../app/ApiProvider'
import { androidApi } from '../api'
import { DeviceCard } from '../components/DeviceControls'
import { Button } from '../../../shared/components/ui/button'
import { useWorkflowRun } from '../../workflows/hooks/useWorkflowRun'
import { createWorkflowRunApi } from '../../workflows/run-api'
import { ManualHandoffPanel } from '../../workflows/components/ManualHandoffPanel'
import { runStateLabel } from '../../workflows/run-types'
import type { AndroidDevice } from '../api'
import type { WorkflowContent } from '../../workflows/types'

export function AndroidPage({ connected = true }: { connected?: boolean }) {
  const { client, instanceId } = useApi()
  const api = useMemo(() => androidApi(client), [client])
  const runApi = useMemo(() => createWorkflowRunApi(client), [client])
  const run = useWorkflowRun(runApi, connected)
  const intent = useRef<{ workflowId: string; requestId: string } | null>(null)
  const [openError, setOpenError] = useState('')
  const active = run.active
  const standalone = active?.document.nodes.length === 1 && active.document.nodes[0].id === 'device-manual'
  // Only an explicit click creates this intent. Reconnecting/remounting never opens a window.
  useEffect(() => {
    const pending = intent.current
    if (!connected || !pending || !active || active.workflowId !== pending.workflowId || active.state !== 'waiting_manual' || !active.handoff) return
    intent.current = null
    let current = true
    void runApi.handoff(active.runId, active.handoff.handoffId, 'open', pending.requestId).catch(error => {
      if (current) setOpenError(error instanceof Error ? error.message : '打开结果未知，请检查会话状态')
    })
    return () => { current = false }
  }, [active, connected, runApi])
  const open = async (device: AndroidDevice) => {
    setOpenError('')
    const workflowId = crypto.randomUUID()
    intent.current = { workflowId, requestId: crypto.randomUUID() }
    const content: WorkflowContent = {
      document: { id: workflowId, schemaVersion: 1, name: `手动操作 · ${device.name}`, variables: [], edges: [], nodes: [{ id: 'device-manual', type: 'android_manual', label: '设备页手动操作', config: { prompt: '在原生窗口操作，完成后点击“结束操作”释放设备。会话最长 60 分钟。', timeoutSeconds: 3600 } }] },
      layout: { nodes: { 'device-manual': { x: 120, y: 100 } }, viewport: { x: 0, y: 0, zoom: 1 } },
    }
    await run.start(content, { kind: 'android', deviceId: device.deviceId })
  }
  const environment = useQuery({ queryKey: ['android', instanceId, 'environment'], queryFn: api.environment, refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['android', instanceId, 'devices'], queryFn: api.devices, refetchInterval: 3000 })
  return <main className="mx-auto max-w-6xl px-8 py-8"><p className="text-xs tracking-widest text-muted">AUTOFLOW / ANDROID</p><h1 className="mt-2 text-2xl font-semibold">安卓设备</h1>
    <p className="mt-2 text-sm text-muted">点击“打开操作窗口”直接使用安卓设备，也可以在工作流中调用它。</p>
    <p role="status" className="my-5 text-sm">{environment.data?.message ?? '正在检查运行环境…'}</p>
    {(environment.error || devices.error) && <p role="alert">无法读取安卓运行环境，请检查本机服务。</p>}
    {devices.isPending && <p>正在读取设备…</p>}
    {devices.data?.length === 0 && <p className="rounded-xl border border-dashed border-line p-8 text-sm text-muted">尚未登记设备。请先按部署说明准备独立测试设备，再在工作流中选择它。</p>}
    {run.message && <p role="alert" className="mb-3 text-sm text-red-700">{run.message}</p>}
    {openError && <p role="alert" className="mb-3 text-sm text-red-700">{openError}</p>}
    {run.canRetryStart && <Button onClick={() => void run.retryStart()} disabled={run.busy}>按原编号重试启动</Button>}
    {active && <p role="status" className="mb-4 text-sm">{active.targetName} · {runStateLabel[active.state]}{active.target.kind !== 'android' ? '，请先结束当前工作流，再操作安卓设备。' : ''}</p>}
    {!active && run.run?.document.nodes[0]?.id === 'device-manual' && run.run.error && <p role="alert" className="mb-3 text-sm text-red-700">{run.run.error.message}</p>}
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{devices.data?.map(device => <DeviceCard key={device.deviceId} onOpen={() => void open(device)} disabled={!connected || run.busy || run.uncertain || Boolean(active) || devices.isError || environment.isError || !environment.data?.available} device={devices.isError ? { ...device, androidStatus: 'unknown', lastError: '无法核实当前设备状态' } : device} />)}</div>
    {active?.target.kind === 'android' && active.handoff && <div className="mt-5"><ManualHandoffPanel key={`${active.runId}:${active.handoff.handoffId}`} run={active} api={runApi} connected={connected} standalone={standalone} onRefresh={() => { void run.refresh(); void devices.refetch() }} onStop={() => void run.stop()} /></div>}
    {active?.target.kind === 'android' && !active.handoff && <Button className="mt-4" disabled={run.busy || !connected} onClick={() => void run.stop()}>取消打开</Button>}
  </main>
}
