import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { useApi } from '../../../app/ApiProvider'
import { androidApi, type AndroidDevice, type DeviceCommand } from '../api'
import { fleetApi, type ConsoleSession, type Profile, type DeviceRun, type AllocationRequest } from '../fleet-api'
import { androidManagementApi } from '../management-api'
import { ResourceBoard } from '../components/ResourceBoard'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
import { Action } from '../components/PrototypeControls'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../../shared/components/ui/dialog'
import { RuntimeDiagnostics } from '../components/RuntimeDiagnostics'
import '../android.css'

export function AndroidPage({ connected = true }: { connected?: boolean }) {
  const { client, instanceId } = useApi(),
    api = useMemo(() => androidApi(client), [client]),
    managementApi = useMemo(() => androidManagementApi(client), [client]),
    fleet = useMemo(() => fleetApi(client), [client]),
    workflows = useMemo(() => ({
      list: async () => ({ items: await client.request<Array<{ id: string; name: string }>>('/api/workflows') }),
      get: (id: string) => client.request<{ document: { variables: Array<{ name: string; type: string; value?: unknown }> } }>(`/api/workflows/${encodeURIComponent(id)}`),
    }), [client])
  const [page, setPage] = useState<'board' | 'create' | 'detail'>('board'),
    [selected, setSelected] = useState<string | null>(null),
    [source, setSource] = useState<AndroidDevice>()
  const [session, setSession] = useState<ConsoleSession | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  const [profilesOpen, setProfilesOpen] = useState(false),
    [profileDraft, setProfileDraft] = useState<Profile | null>(null),
    [allocateOpen, setAllocateOpen] = useState(false)
  const [allocation, setAllocation] = useState<AllocationRequest | null>(null),
    [management, setManagement] = useState<{ device: AndroidDevice; action: string } | null>(null),
    [name, setName] = useState(''),
    [deleteData, setDeleteData] = useState(false)
  const [allocationInputs, setAllocationInputs] = useState<Record<string, string>>({})
  const allocationWorkflow = useQuery({
    queryKey: ['android', instanceId, 'allocation-workflow', allocation?.workflowId],
    queryFn: () => workflows.get(allocation!.workflowId),
    enabled: Boolean(connected && allocateOpen && allocation?.workflowId),
  })
  const [historyPage, setHistoryPage] = useState(0)
  const detailHistory = useQuery({
    queryKey: ['android', instanceId, 'device-history-page', selected, historyPage],
    queryFn: () => fleet.history(selected!, historyPage * 50),
    enabled: Boolean(connected && selected && page === 'detail'),
    refetchInterval: 3000,
  })
  const pendingManagement = useRef<DeviceCommand | null>(null),
    pendingOpen = useRef<{ deviceId: string; requestId: string } | null>(null)
  const devices = useQuery({
    queryKey: ['android', instanceId, 'devices'],
    queryFn: api.devices,
    enabled: connected,
    refetchInterval: 3000,
  })
  const environment = useQuery({
    queryKey: ['android', instanceId, 'environment'],
    queryFn: api.environment,
    enabled: connected,
    refetchInterval: 15000,
  })
  const profiles = useQuery({
    queryKey: ['android', instanceId, 'profiles'],
    queryFn: fleet.profiles,
    enabled: connected,
  })
  const batches = useQuery({
    queryKey: ['android', instanceId, 'batches'],
    queryFn: fleet.batches,
    enabled: connected,
    refetchInterval: 3000,
  })
  const allocations = useQuery({
    queryKey: ['android', instanceId, 'allocations'],
    queryFn: fleet.allocations,
    enabled: connected,
    refetchInterval: 3000,
  })
  const workflowList = useQuery({
    queryKey: ['android', instanceId, 'workflows'],
    queryFn: workflows.list,
    enabled: connected && allocateOpen,
  })
  const sessionStatus = useQuery({
    queryKey: ['android', instanceId, 'session', session?.id],
    queryFn: () => fleet.heartbeat(session!, session!.clientSessionId ?? session!.id),
    enabled: Boolean(connected && session && session.state !== 'closed'),
    refetchInterval: 5000,
  })
  useEffect(() => {
    if (sessionStatus.data)
      setSession((previous) =>
        previous &&
        (previous.id !== sessionStatus.data.id ||
          previous.generation > sessionStatus.data.generation ||
          (previous.state === 'closed' && sessionStatus.data.state !== 'closed'))
          ? previous
          : sessionStatus.data,
      )
  }, [sessionStatus.data])
  const all = devices.data ?? [],
    device = all.find((d) => d.deviceId === selected)
  const histories = useQueries({
    queries: all.map((d) => ({
      queryKey: ['android', instanceId, 'history', d.deviceId],
      queryFn: () => fleet.history(d.deviceId),
      enabled: connected,
      refetchInterval: 3000,
    })),
  })
  const historyMap = Object.fromEntries(all.map((d, i) => [d.deviceId, histories[i]?.data ?? []])) as Record<
    string,
    DeviceRun[]
  >
  const runs = Object.fromEntries(
    all.map((d) => [
      d.deviceId,
      historyMap[d.deviceId]?.find((r) => !['succeeded', 'failed', 'stopped', 'interrupted'].includes(r.state)),
    ]),
  )
  const apps = useQuery({
    queryKey: ['android', instanceId, 'apps', session?.id, session?.generation],
    queryFn: () => fleet.apps(session!.id),
    enabled: Boolean(connected && session && session.state !== 'closed'),
    refetchInterval: 10000,
  })
  const refresh = () => {
    void devices.refetch()
    void batches.refetch()
    void allocations.refetch()
    void apps.refetch()
    histories.forEach((h) => {
      void h.refetch()
    })
  }
  const perform = async (fn: () => Promise<unknown>) => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await fn()
      refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : '结果尚未确认，请刷新核实')
    } finally {
      setBusy(false)
    }
  }
  const open = async (d: AndroidDevice) => {
    if (selected !== d.deviceId) setHistoryPage(0)
    setSelected(d.deviceId)
    setPage('detail')
    if (session?.deviceId === d.deviceId && session.state !== 'closed') {
      await sessionStatus.refetch()
      return
    }
    if (d.androidStatus !== 'ready') return
    await perform(async () => {
      if (session && session.state !== 'closed') await fleet.action(session, 'end')
      if (pendingOpen.current?.deviceId !== d.deviceId)
        pendingOpen.current = { deviceId: d.deviceId, requestId: crypto.randomUUID() }
      const next = await fleet.session(
        d.deviceId,
        d.ownerRunId || d.control !== 'idle' ? 'readonly' : 'manual',
        pendingOpen.current.requestId,
      )
      setSession(next)
      pendingOpen.current = null
    })
  }
  const onSession = useCallback((s: ConsoleSession) => {
    setSession(s)
  }, [])
  const manage = (d: AndroidDevice, action: string) => {
    if (action === 'copy') {
      setSource(d)
      setPage('create')
      return
    }
    setError('')
    setManagement({ device: d, action })
    setName(d.name)
    setDeleteData(false)
    pendingManagement.current = null
  }
  const confirmManage = async () => {
    if (!management) return
    await perform(async () => {
      if (management.action === 'rename') await api.rename(management.device.deviceId, name)
      else {
        pendingManagement.current ??= {
          requestId: crypto.randomUUID(),
          action: management.action as DeviceCommand['action'],
          deleteData,
        }
        await api.operate(management.device.deviceId, pendingManagement.current)
      }
      setManagement(null)
    })
  }
  const allocate = (d?: AndroidDevice) => {
    setAllocationInputs({})
    setAllocation({
      requestId: crypto.randomUUID(),
      workflowId: '',
      profileId: d?.profileId ?? profiles.data?.[0]?.id ?? '',
      mode: d ? 'specified' : 'automatic',
      deviceId: d?.deviceId ?? null,
      values: {},
    })
    setAllocateOpen(true)
  }
  const studio = () => {
    void perform(async () => {
      if (!window.autoflow?.openAutomationStudio) throw new Error('请使用 AutoFlow 桌面应用打开工作流工作台')
      await window.autoflow.openAutomationStudio()
    })
  }
  return (
    <>
      <div
        className="ad-page"
        style={{
          display: error && !management && !profilesOpen && !allocateOpen ? 'block' : 'none',
          minHeight: 0,
          paddingBottom: 0,
        }}
      >
        <p role="alert" className="ad-error">
          {error}
        </p>
      </div>
      {devices.isError && <div className="ad-error">设备状态无法核实，请检查本机服务。</div>}
      {page === 'create' ? (
        <CreateInstances
          profiles={profiles.data ?? []}
          environment={environment.data}
          source={source}
          onBack={() => setPage('board')}
          onProfiles={() => setProfilesOpen(true)}
          onSubmit={async (body) => {
            await fleet.batch(body)
            setPage('board')
            refresh()
          }}
        />
      ) : page === 'detail' && device ? (
        <DeviceConsole
          device={device}
          session={session?.deviceId === device.deviceId ? session : null}
          api={fleet}
          deviceApi={api}
          run={runs[device.deviceId]}
          history={detailHistory.data ?? historyMap[device.deviceId]}
          historyPage={historyPage}
          onHistoryPage={setHistoryPage}
          apps={apps.data}
          onBack={() => setPage('board')}
          onSession={onSession}
          onOpen={() => void open(device)}
          onManage={(action) => manage(device, action)}
          onAllocate={() => allocate(device)}
          onRefresh={refresh}
        />
      ) : (
        <div className="space-y-5"><RuntimeDiagnostics api={managementApi} /><ResourceBoard
          devices={all}
          profiles={profiles.data ?? []}
          allocations={allocations.data ?? []}
          batches={batches.data ?? []}
          runs={runs}
          api={api}
          onCreate={() => {
            setSource(undefined)
            setPage('create')
          }}
          onProfiles={() => setProfilesOpen(true)}
          onOpen={(d) => void open(d)}
          onAllocate={allocate}
          onManage={manage}
          onRuns={studio}
          onBatch={(id, action) => void perform(() => fleet.batchAction(id, action))}
          onCancelAllocation={(id) => void perform(() => fleet.cancelAllocation(id))}
        /></div>
      )}
      <Dialog
        open={Boolean(management)}
        onOpenChange={(v) => {
          if (!v) setManagement(null)
        }}
        busy={busy}
      >
        <DialogContent>
          <DialogTitle>
            {
              (
                {
                  rename: '重命名实例',
                  start: '启动设备',
                  stop: '停止设备',
                  restart: '重启设备',
                  recover: '核实状态',
                  delete: '删除实例',
                } as Record<string, string>
              )[management?.action ?? '']
            }
          </DialogTitle>
          <DialogDescription>{management?.device.name} · 操作进度将在资源看板中显示。</DialogDescription>
          <div className="ad-page" style={{ minHeight: 0, padding: 0 }}>
            {management?.action === 'rename' && (
              <input aria-label="新的实例名称" value={name} onChange={(e) => setName(e.target.value)} />
            )}
            {management?.action === 'delete' && (
              <label>
                <input
                  type="checkbox"
                  disabled={Boolean(pendingManagement.current)}
                  checked={deleteData}
                  onChange={(e) => setDeleteData(e.target.checked)}
                />
                同时永久删除此实例的应用和数据
              </label>
            )}
            {error && (
              <p role="alert" className="ad-error">
                {error}
              </p>
            )}
            <div className="flex justify-end gap-3 mt-5">
              <Action disabled={busy} onClick={() => setManagement(null)}>
                取消
              </Action>
              <Action primary disabled={busy} onClick={() => void confirmManage()}>
                {busy ? '正在提交…' : '确认操作'}
              </Action>
            </div>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={profilesOpen} onOpenChange={setProfilesOpen} busy={busy}>
        <DialogContent>
          <DialogTitle>环境配置</DialogTitle>
          <DialogDescription>为创建实例保存系统、资源、语言和时区配置。</DialogDescription>
          <div className="ad-page ad-profile-editor" style={{ minHeight: 0, padding: 0 }}>
            {profileDraft ? (
              <>
                <label>
                  配置名称
                  <input
                    value={profileDraft.name}
                    onChange={(e) => setProfileDraft({ ...profileDraft, name: e.target.value })}
                  />
                </label>
                {(['cpu', 'memoryMb', 'dpi'] as const).map((key) => (
                  <label key={key}>
                    {{ cpu: 'CPU 核数', memoryMb: '内存 MB', dpi: '显示密度' }[key]}
                    <input
                      type="number"
                      value={profileDraft[key]}
                      onChange={(e) => setProfileDraft({ ...profileDraft, [key]: Number(e.target.value) })}
                    />
                  </label>
                ))}
                <label>
                  语言
                  <select
                    value={profileDraft.locale}
                    onChange={(e) => setProfileDraft({ ...profileDraft, locale: e.target.value })}
                  >
                    <option value="zh-CN">简体中文</option>
                    <option value="en-US">English</option>
                  </select>
                </label>
                <label>
                  时区
                  <input
                    value={profileDraft.timezone}
                    onChange={(e) => setProfileDraft({ ...profileDraft, timezone: e.target.value })}
                  />
                </label>
                <Action
                  primary
                  onClick={() =>
                    void perform(async () => {
                      await fleet.saveProfile(profileDraft)
                      await profiles.refetch()
                      setProfileDraft(null)
                    })
                  }
                >
                  保存配置
                </Action>
                <Action onClick={() => setProfileDraft(null)}>返回</Action>
              </>
            ) : (
              <>
                {profiles.data?.map((profile) => (
                  <div className="ad-profile-row" key={profile.id}>
                    <span>{profile.name}</span>
                    <Action onClick={() => setProfileDraft(profile)}>编辑</Action>
                    <Action
                      onClick={() =>
                        setProfileDraft({
                          ...profile,
                          id: crypto.randomUUID(),
                          name: `${profile.name} 副本`,
                          revision: 0,
                        })
                      }
                    >
                      复制
                    </Action>
                  </div>
                ))}
                {!profiles.data?.length && <p>{environment.data?.message ?? '正在检查运行环境…'}</p>}
                <Action
                  onClick={() => {
                    void profiles.refetch()
                    void environment.refetch()
                  }}
                >
                  重新检查
                </Action>
              </>
            )}
            {error && (
              <p role="alert" className="ad-error">
                {error}
              </p>
            )}
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={allocateOpen} onOpenChange={setAllocateOpen} busy={busy}>
        <DialogContent>
          <DialogTitle>分配给工作流</DialogTitle>
          <DialogDescription>工作流执行期间独占设备；失败或中断时保留设备检查。</DialogDescription>
          {allocation && (
            <div className="ad-page ad-profile-editor" style={{ minHeight: 0, padding: 0 }}>
              <label>
                工作流
                <select
                  value={allocation.workflowId}
                  onChange={(e) => {
                    setAllocationInputs({})
                    setAllocation({ ...allocation, workflowId: e.target.value })
                  }}
                >
                  <option value="">选择已保存的工作流</option>
                  {workflowList.data?.items.map((w) => (
                    <option key={w.id} value={w.id}>
                      {w.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                所需环境
                <select
                  value={allocation.profileId}
                  onChange={(e) => setAllocation({ ...allocation, profileId: e.target.value })}
                >
                  {profiles.data?.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                分配方式
                <select
                  value={allocation.mode}
                  onChange={(e) =>
                    setAllocation({
                      ...allocation,
                      mode: e.target.value as AllocationRequest['mode'],
                      deviceId: e.target.value === 'specified' ? (all[0]?.deviceId ?? null) : null,
                    })
                  }
                >
                  <option value="automatic">自动分配</option>
                  <option value="specified">指定设备</option>
                  <option value="temporary">新建临时实例</option>
                </select>
              </label>
              {allocation.mode === 'specified' && (
                <select
                  aria-label="指定设备"
                  value={allocation.deviceId ?? ''}
                  onChange={(e) => setAllocation({ ...allocation, deviceId: e.target.value })}
                >
                  {all.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.name}
                    </option>
                  ))}
                </select>
              )}
              {allocationWorkflow.data?.document.variables.map((v) => (
                <label key={v.name}>
                  {v.name}
                  {v.type === 'boolean' ? (
                    <select
                      value={allocationInputs[v.name] ?? String(v.value)}
                      onChange={(e) => setAllocationInputs({ ...allocationInputs, [v.name]: e.target.value })}
                    >
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  ) : (
                    <input
                      type={v.type === 'number' ? 'number' : 'text'}
                      value={
                        allocationInputs[v.name] ??
                        (v.type === 'string' ? String(v.value ?? '') : JSON.stringify(v.value))
                      }
                      onChange={(e) => setAllocationInputs({ ...allocationInputs, [v.name]: e.target.value })}
                    />
                  )}
                </label>
              ))}
              {error && (
                <p role="alert" className="ad-error">
                  {error}
                </p>
              )}
              <Action
                primary
                disabled={busy || !allocation.workflowId || !allocation.profileId}
                onClick={() =>
                  void perform(async () => {
                    const values = Object.fromEntries(
                      (allocationWorkflow.data?.document.variables ?? []).map((v) => {
                        const input = allocationInputs[v.name]
                        if (input === undefined) return [v.name, v.value]
                        try {
                          return [v.name, v.type === 'string' ? input : JSON.parse(input)]
                        } catch {
                          throw new Error(`${v.name} 的输入格式无效`)
                        }
                      }),
                    )
                    await fleet.allocate({ ...allocation, values })
                    setAllocateOpen(false)
                  })
                }
              >
                加入分配队列
              </Action>
              <Action onClick={studio}>打开工作流工作台</Action>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
