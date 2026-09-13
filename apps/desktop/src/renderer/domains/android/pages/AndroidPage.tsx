import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useApi } from '../../../app/ApiProvider'
import { androidApi } from '../api'
import { DeviceCard, type DeviceAction } from '../components/DeviceControls'
import { Plus, GearSix, MagnifyingGlass, SquaresFour, ListBullets, ArrowClockwise, Info } from '@phosphor-icons/react'
import { ApiClientError } from '../../../shared/api/client'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../../shared/components/ui/dialog'
import { CreateDeviceForm } from '../components/CreateDeviceForm'
import { DeviceDetails } from '../components/DeviceDetails'
import { groups, deviceGroup } from '../model'
import { RunPanel } from '../../workflows/components/RunPanel'
import { Button } from '../../../shared/components/ui/button'
import { useWorkflowRun } from '../../workflows/hooks/useWorkflowRun'
import { createWorkflowRunApi } from '../../workflows/run-api'
import { ManualHandoffPanel } from '../../workflows/components/ManualHandoffPanel'
import { runStateLabel } from '../../workflows/run-types'
import type { AndroidDevice, DeviceCommand } from '../api'
import type { WorkflowContent } from '../../workflows/types'

export function AndroidPage({ connected = true }: { connected?: boolean }) {
  const { client, instanceId } = useApi()
  const api = useMemo(() => androidApi(client), [client])
  const runApi = useMemo(() => createWorkflowRunApi(client), [client])
  const run = useWorkflowRun(runApi, connected)
  const intent = useRef<{ workflowId: string; requestId: string } | null>(null)
  const [openError, setOpenError] = useState('')
  const [view, setView] = useState<'board' | 'list'>('board')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [creating, setCreating] = useState<{ source?: AndroidDevice } | null>(null)
  const [detailId, setDetailId] = useState<string | null>(null)
  const [environmentOpen, setEnvironmentOpen] = useState(false)
  const [confirmation, setConfirmation] = useState<{ device: AndroidDevice; action: DeviceAction } | null>(null)
  const [deleteData, setDeleteData] = useState(false)
  const [name, setName] = useState('')
  const pendingOperation = useRef<DeviceCommand | null>(null)
  const [mutating, setMutating] = useState(false)
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
  const environment = useQuery({ queryKey: ['android', instanceId, 'environment'], queryFn: api.environment, enabled: connected, refetchInterval: 10000 })
  const devices = useQuery({ queryKey: ['android', instanceId, 'devices'], queryFn: api.devices, enabled: connected, refetchInterval: 3000 })
  const all = (devices.data ?? []).map(device => devices.isError ? { ...device, androidStatus: 'unknown', lastError: '无法核实当前设备状态' } : device)
  const selected = all.find(device => device.deviceId === detailId)
  const blocked = !connected || run.busy || run.uncertain || Boolean(active) || mutating || devices.isError || environment.isError || !environment.data?.available || all.some(d => d.control === 'managing')
  const refresh = () => { void devices.refetch(); void environment.refetch(); void run.refresh() }
  const action = (device: AndroidDevice, value: DeviceAction) => {
    if (value === 'copy') { setCreating({ source: device }); return }
    pendingOperation.current = null
    setOpenError(''); setDeleteData(false); setName(device.name); setConfirmation({ device, action: value })
  }
  const confirm = async () => {
    if (!confirmation || mutating) return
    setMutating(true); setOpenError('')
    try {
      if (confirmation.action === 'rename') await api.rename(confirmation.device.deviceId, name.trim())
      else if (confirmation.action !== 'copy') {
        pendingOperation.current ??= { requestId: crypto.randomUUID(), action: confirmation.action, deleteData }
        await api.operate(confirmation.device.deviceId, pendingOperation.current)
      }
      setConfirmation(null); refresh()
    } catch (e) {
      if (e instanceof ApiClientError && e.status < 500) pendingOperation.current = null
      setOpenError(pendingOperation.current ? '操作结果尚未确认，请按原编号重试或刷新状态核实。' : e instanceof Error ? e.message : '操作未完成')
    }
    finally { setMutating(false) }
  }
  const studio = async () => {
    try {
      if (!window.autoflow?.openAutomationStudio) throw new Error('请从 AutoFlow 桌面应用打开工作流工作台')
      await window.autoflow.openAutomationStudio()
    } catch (e) { setOpenError(e instanceof Error ? e.message : '工作台打开失败') }
  }
  const manual = active?.target.kind === 'android' && active.handoff ? <ManualHandoffPanel key={`${active.runId}:${active.handoff.handoffId}`} run={active} api={runApi} connected={connected} standalone={standalone} onRefresh={refresh} onStop={() => void run.stop()} /> : active?.target.kind === 'android' ? <Button disabled={run.busy || !connected} onClick={() => void run.stop()}>停止并清理</Button> : null
  const visible = all.filter(d => d.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()) && (!filter || deviceGroup(d) === filter))
  const card = (device: AndroidDevice) => <DeviceCard key={device.deviceId} device={device} api={api} previewEnabled={connected && !devices.isError} onOpen={() => void open(device)} onDetail={() => setDetailId(device.deviceId)} onAction={value => action(device, value)} disabled={blocked} />
  const history = <RunPanel run={run.run?.target.kind === 'android' && run.run.target.deviceId === detailId ? run.run : null} events={run.events ?? []} history={(run.history ?? []).filter(item => item.target.kind === 'android' && item.target.deviceId === detailId)} nextOffset={run.nextOffset ?? null} sameDocument connected={connected} message={run.message} api={runApi} onSelect={id => run.select(id)} onLocate={() => {}} onMore={() => void run.more()} />
  return <main className="mx-auto max-w-[1600px] px-8 py-7">
    {(environment.error || devices.error) && <p role="alert" className="mb-4 rounded-control border border-red-200 bg-red-50 p-3 text-sm text-red-700">无法核实设备状态，请检查本机服务后刷新。</p>}
    {(run.message || openError) && !confirmation && <p role="alert" className="mb-4 text-sm text-red-700">{openError || run.message}</p>}
    {run.canRetryStart && <Button onClick={() => void run.retryStart()} disabled={run.busy}>按原编号重试启动</Button>}
    {creating && environment.data ? <CreateDeviceForm environment={environment.data} source={creating.source} api={api} onCancel={() => setCreating(null)} disabled={blocked} onCreated={() => { setCreating(null); setDetailId(null); refresh() }} /> : selected ? <DeviceDetails device={selected} api={api} disabled={blocked} connected={connected} onBack={() => setDetailId(null)} onOpen={() => void open(selected)} onStudio={() => void studio()} history={history}>{active?.target.kind === 'android' && active.target.deviceId === selected.deviceId ? manual : null}</DeviceDetails> : <>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4"><div><h1 className="text-2xl font-semibold">安卓模拟器</h1><p className="mt-2 text-sm text-muted">管理独立设备，为工作流分配运行环境。</p></div><div className="flex gap-3"><Button onClick={() => setEnvironmentOpen(true)}><GearSix size={18} />运行环境</Button><Button variant="primary" disabled={blocked} onClick={() => setCreating({})}><Plus size={18} />创建实例</Button></div></header>
      <div className="mb-3 flex items-center justify-between gap-3 text-xs text-muted"><p role="status">{environment.data?.message ?? '正在检查运行环境…'}</p><Button variant="ghost" className="h-8 text-xs" disabled={!connected || devices.isFetching} onClick={refresh}><ArrowClockwise size={14} />刷新状态</Button></div>
      {active && <p role="status" className="mb-4 rounded-control border border-line bg-surface p-3 text-sm">{active.targetName} · {runStateLabel[active.state]}{active.target.kind !== 'android' ? '，请先结束当前工作流，再操作安卓设备。' : ''}</p>}
      {!active && run.run?.document.nodes[0]?.id === 'device-manual' && run.run.error && <p role="alert" className="mb-3 text-sm text-red-700">{run.run.error.message}</p>}
      <div className="rounded-card border border-line bg-surface/60 p-2"><div className="flex flex-wrap items-center gap-3 px-1 pb-3 pt-1"><div className="flex gap-1 rounded-control border border-line bg-surface p-1" role="group" aria-label="显示方式"><Button className="h-8 px-3 text-xs" variant={view === 'list' ? 'primary' : 'ghost'} aria-pressed={view === 'list'} onClick={() => setView('list')}><ListBullets size={15} />实例列表</Button><Button className="h-8 px-3 text-xs" variant={view === 'board' ? 'primary' : 'ghost'} aria-pressed={view === 'board'} onClick={() => setView('board')}><SquaresFour size={15} />资源看板</Button></div><span className="text-xs text-muted">{all.length} 台设备 · {all.filter(d => deviceGroup(d) === '可分配').length} 台可分配</span><div className="ml-auto flex flex-wrap gap-2"><div className="relative"><MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-3 text-muted" /><Input aria-label="搜索设备" placeholder="搜索实例名称" className="w-48 pl-9" value={search} onChange={e => setSearch(e.target.value)} /></div><Select aria-label="筛选设备状态" value={filter} onChange={e => setFilter(e.target.value)}><option value="">全部状态</option>{groups.map(g => <option key={g}>{g}</option>)}</Select></div></div>
        {devices.isPending ? <p role="status" className="p-8 text-sm text-muted">正在读取设备…</p> : !all.length ? <div className="rounded-control border border-dashed border-line px-8 py-16 text-center"><h2 className="font-semibold">创建第一台安卓实例</h2><p className="mt-2 text-sm text-muted">每台设备独立保存应用和数据，支持原生窗口与工作流操作。</p><Button className="mt-5" variant="primary" disabled={blocked} onClick={() => setCreating({})}><Plus size={16} />创建实例</Button></div> : view === 'board' ? <div className="grid gap-2 xl:grid-cols-3">{groups.map((group, index) => <section key={group} className="min-w-0 rounded-control border border-line bg-surface-subtle/60 p-3" aria-label={group}><h2 className="mb-4 flex items-center gap-2 text-sm font-semibold"><span className={`h-2.5 w-2.5 rounded-full ${index === 0 ? 'bg-sage' : index === 1 ? 'bg-clay' : 'bg-muted'}`} />{group}<span className="rounded bg-surface px-1.5 text-xs">{visible.filter(d => deviceGroup(d) === group).length}</span></h2><div className="space-y-3">{visible.filter(d => deviceGroup(d) === group).map(card)}{!visible.some(d => deviceGroup(d) === group) && <p className="py-16 text-center text-xs text-muted">暂无{group}设备</p>}</div></section>)}</div> : <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{visible.map(card)}</div>}
      </div>
      {(search || filter) && <p className="mt-3 text-xs text-muted">匹配 {visible.length} / {all.length} 台设备</p>}
      <section className="mt-5 rounded-card border border-line bg-surface p-5"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-sm font-semibold">工作流与设备</h2><Button className="h-8 text-xs" variant="ghost" onClick={() => void studio()}>打开工作流工作台 →</Button></div><p className="mt-3 flex items-start gap-2 text-xs text-muted"><Info size={16} className="shrink-0" />在工作台中选择安卓设备。执行期间独占设备；到达人工处理节点后可打开原生窗口，结束运行后保留数据。</p>{manual && <div className="mt-4">{manual}</div>}</section>
    </>}
    <Dialog open={environmentOpen} onOpenChange={setEnvironmentOpen}><DialogContent><DialogTitle>Mac 安卓运行环境</DialogTitle><DialogDescription>{environment.data?.message ?? '正在检查运行环境'}</DialogDescription><dl className="space-y-3 text-sm"><div>环境：{environment.data?.runtimeId ?? '—'}</div><div>CPU：{environment.data?.cpuCount ?? '—'} · 内存：{environment.data?.memoryMb ?? '—'} MiB</div><div>已缓存系统：{environment.data?.images?.map(item => item.name).join('、') || '未找到兼容镜像'}</div></dl><p className="text-xs text-muted">当前使用 Lima 中的 Docker Engine。设备管理继续按串行执行，原生窗口由本机服务维护。</p><div className="flex justify-end gap-2"><Button onClick={refresh}>重新检查</Button><Button onClick={() => setEnvironmentOpen(false)}>关闭</Button></div></DialogContent></Dialog>
    <Dialog open={Boolean(confirmation)} busy={mutating} onOpenChange={value => { if (!value) { setConfirmation(null); setOpenError('') } }}><DialogContent><DialogTitle>{confirmation?.action === 'delete' ? '删除实例' : confirmation?.action === 'rename' ? '重命名实例' : confirmation?.action === 'stop' ? '停止设备' : confirmation?.action === 'restart' ? '重启设备' : confirmation?.action === 'recover' ? '核实设备状态' : '启动设备'}</DialogTitle><DialogDescription>{confirmation?.device.name} · {confirmation?.action === 'delete' ? '仅操作此实例及其独立数据，其他设备不受影响。' : '设备操作进度和结果会显示在卡片中。'}</DialogDescription>{confirmation?.action === 'delete' ? <><label className="flex items-start gap-3 rounded-control border border-line p-4 text-sm"><input type="checkbox" disabled={mutating || Boolean(pendingOperation.current)} checked={deleteData} onChange={e => setDeleteData(e.target.checked)} className="mt-1 accent-clay" />同时永久删除应用和数据</label><p className="text-sm text-muted">{deleteData ? '容器和独立数据卷都会删除，此操作无法恢复。' : '移除运行环境，保留数据和登记记录；之后可以恢复实例。'}</p></> : confirmation?.action === 'rename' ? <Input aria-label="新的实例名称" maxLength={80} value={name} onChange={e => setName(e.target.value)} /> : <p className="text-sm text-muted">{confirmation?.action === 'recover' ? '只核实上一操作是否结束及当前资源状态，不自动重放失败命令。' : '应用和数据会保留。请等待操作结果后再打开设备。'}</p>}{openError && <p role="alert" className="text-sm text-red-700">{openError}</p>}<div className="flex justify-end gap-2"><Button disabled={mutating} onClick={() => setConfirmation(null)}>取消</Button><Button variant={confirmation?.action === 'delete' && deleteData ? 'danger' : 'primary'} disabled={mutating || confirmation?.action === 'rename' && !name.trim()} onClick={() => void confirm()}>{mutating ? '正在提交…' : openError && pendingOperation.current ? '按原编号重试' : confirmation?.action === 'delete' ? deleteData ? '删除实例和数据' : '移除实例并保留数据' : '确认操作'}</Button></div></DialogContent></Dialog>
  </main>
}
