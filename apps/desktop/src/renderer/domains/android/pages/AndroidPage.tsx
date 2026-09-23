import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useApi } from '../../../app/ApiProvider'
import { ApiClientError } from '../../../shared/api/client'
import { androidApi, type AndroidDevice, type DeviceCommand } from '../api'
import { fleetApi, type ConsoleSession, type Profile } from '../fleet-api'
import { androidManagementApi, type ManagementDevicePage } from '../management-api'
import { CreateInstances } from '../components/CreateInstances'
import { DeviceConsole } from '../components/DeviceConsole'
import { Action } from '../components/PrototypeControls'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../../shared/components/ui/dialog'
import { RuntimeDiagnostics } from '../components/RuntimeDiagnostics'
import { ManagementOverview } from '../components/ManagementOverview'
import { ImageManager } from '../components/ImageManager'
import { TemplateManager } from '../components/TemplateManager'
import { DataMaintenance } from '../components/DataMaintenance'
import { BackupPanel } from '../components/BackupPanel'
import '../android.css'

const specValue = (spec: Record<string, unknown>, key: string, fallback: unknown) => spec[key] ?? spec[key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)] ?? fallback

function managementDeviceToLegacy(device: ManagementDevicePage['items'][number]): AndroidDevice {
  const spec = device.specSnapshot ?? {}, operation = device.latestOperation
  const operationId = typeof operation?.operationId === 'string' ? operation.operationId : typeof operation?.operation_id === 'string' ? operation.operation_id : typeof operation?.id === 'string' ? operation.id : undefined
  const stale = device.stale || device.runtimeState === 'unknown'
  return {
    deviceId: device.deviceId,
    name: device.name,
    runtimeId: String(specValue(spec, 'runtimeId', 'management')),
    ownerRunId: device.owner.kind === 'legacyWorkflow' ? device.owner.id ?? null : null,
    control: stale ? 'recovery_required' : device.owner.kind === 'manualSession' ? 'manual' : operation && ['queued', 'running', 'waiting_capacity'].includes(String(operation.state)) ? 'managing' : operation && ['needs_verification', 'interrupted', 'failed'].includes(String(operation.state)) ? 'recovery_required' : 'idle',
    generation: device.revision,
    width: Number(specValue(spec, 'width', 720)),
    height: Number(specValue(spec, 'height', 1280)),
    imageId: String(specValue(spec, 'imageId', '')),
    androidStatus: stale ? 'unknown' : device.runtimeState,
    lastError: typeof operation?.message === 'string' ? operation.message : typeof operation?.error === 'string' ? operation.error : null,
    cpu: Number(specValue(spec, 'cpu', 1)),
    memoryMb: Number(specValue(spec, 'memoryMb', 1536)),
    dpi: Number(specValue(spec, 'dpi', 320)),
    androidVersion: typeof specValue(spec, 'androidVersion', null) === 'string' ? String(specValue(spec, 'androidVersion', null)) : null,
    architecture: typeof specValue(spec, 'architecture', null) === 'string' ? String(specValue(spec, 'architecture', null)) : null,
    dataRetained: Boolean(specValue(spec, 'dataRetained', device.runtimeState === 'retained')),
    deleted: Boolean(specValue(spec, 'deleted', false)),
    operation: operationId ? {
      id: operationId,
      action: String(specValue(operation ?? {}, 'action', '')),
      state: String(specValue(operation ?? {}, 'state', '')),
      stage: String(specValue(operation ?? {}, 'stageLabel', specValue(operation ?? {}, 'stage', ''))),
      error: typeof specValue(operation ?? {}, 'message', specValue(operation ?? {}, 'error', null)) === 'string' ? String(specValue(operation ?? {}, 'message', specValue(operation ?? {}, 'error', null))) : null,
      startedAt: String(specValue(operation ?? {}, 'startedAt', specValue(operation ?? {}, 'createdAt', new Date(0).toISOString()))),
      finishedAt: typeof specValue(operation ?? {}, 'finishedAt', null) === 'string' ? String(specValue(operation ?? {}, 'finishedAt', null)) : null,
    } : null,
    profileId: typeof specValue(spec, 'profileId', null) === 'string' ? String(specValue(spec, 'profileId', null)) : null,
    profileName: String(specValue(spec, 'profileName', 'Android 实例')),
    instanceType: String(specValue(spec, 'instanceType', 'persistent')),
    locale: String(specValue(spec, 'locale', 'zh-CN')),
    timezone: String(specValue(spec, 'timezone', 'Asia/Shanghai')),
  }
}

export function AndroidPage({ connected = true, registerLeaveGuard }: { connected?: boolean; registerLeaveGuard?: (guard: (() => Promise<boolean>) | null) => void }) {
  const { client, instanceId } = useApi(),
    api = useMemo(() => androidApi(client), [client]),
    managementApi = useMemo(() => androidManagementApi(client), [client]),
    fleet = useMemo(() => fleetApi(client), [client])
  const queryClient = useQueryClient()
  const [page, setPage] = useState<'board' | 'create' | 'detail'>('board'),
    [selected, setSelected] = useState<string | null>(null),
    [source, setSource] = useState<AndroidDevice>()
  const [session, setSession] = useState<ConsoleSession | null>(null),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  const saveAndroidDiagnostic = typeof window !== 'undefined' ? window.autoflow?.saveAndroidDiagnostic : undefined
  const [profilesOpen, setProfilesOpen] = useState(false),
    [profileDraft, setProfileDraft] = useState<Profile | null>(null)
  const [management, setManagement] = useState<{ device: AndroidDevice; action: string; operationId?: string; requestId?: string } | null>(null),
    [name, setName] = useState(''),
    [deleteData, setDeleteData] = useState(false)
  const pendingManagement = useRef<DeviceCommand | null>(null),
    pendingOpen = useRef<{ deviceId: string; requestId: string } | null>(null),
    openingEpoch = useRef(0),
    endingSession = useRef<string | null>(null),
    pendingLeave = useRef<{ page: 'board' | 'create'; source?: AndroidDevice } | null>(null),
    backend = useRef({ client, instanceId }),
    active = useRef(true),
    currentSession = useRef<ConsoleSession | null>(null),
    leaveGuard = useRef<() => Promise<boolean>>(async () => true)
  useEffect(() => { currentSession.current = session }, [session])
  useEffect(() => {
    if (backend.current.client !== client || backend.current.instanceId !== instanceId) {
      backend.current = { client, instanceId }
      pendingOpen.current = null
      pendingLeave.current = null
      currentSession.current = null
      setSession(null)
      setSelected(null)
      setPage('board')
      setBusy(false)
      setError('本机服务已切换，旧控制会话需重新核实')
    }
    active.current = true
    return () => {
      active.current = false
      openingEpoch.current += 1
      const orphan = currentSession.current
      if (orphan && orphan.endpoint === 'embedded' && orphan.state !== 'closed' && endingSession.current !== orphan.id)
        void Promise.resolve().then(() => fleet.action(orphan, 'end')).catch(() => { /* The server lease still expires if navigation loses the response. */ })
    }
  }, [client, instanceId, fleet])
  const isCurrentBackend = () => active.current && backend.current.client === client && backend.current.instanceId === instanceId
  const managementDevices = useQuery({
    queryKey: ['android-management', instanceId, 'devices'],
    queryFn: async () => {
      const items: ManagementDevicePage['items'] = []
      let cursor = ''
      let total = 0
      do {
        const page = await managementApi.devices(cursor ? `?limit=50&cursor=${encodeURIComponent(cursor)}` : '?limit=50')
        if (Array.isArray(page)) break
        items.push(...page.items)
        total = page.total
        cursor = page.nextCursor ?? ''
      } while (cursor)
      return { items, total, nextCursor: null }
    },
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
  const backups = useQuery({
    queryKey: ['android-management', instanceId, 'backups'],
    queryFn: managementApi.backups,
    enabled: connected,
  })
  const sessionStatus = useQuery({
    queryKey: ['android', instanceId, 'session', session?.id],
    queryFn: () => fleet.heartbeat(session!, session!.clientSessionId ?? session!.id),
    enabled: Boolean(connected && page === 'detail' && session?.state === 'connected'),
    retry: false,
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
  useEffect(() => {
    if (!sessionStatus.error || !session) return
    setSession((previous) => previous && previous.id === session.id && previous.state === 'connected'
      ? { ...previous, state: 'unknown', latestOperation: '控制会话状态待核实' }
      : previous)
    setError('控制会话状态未知，请重新连接并核实设备')
  }, [sessionStatus.error, session?.id])
  const managementRecord = managementDevices.data?.items.find((item) => item.deviceId === selected),
    all = managementDevices.data?.items.map(managementDeviceToLegacy) ?? [],
    device = all.find((d) => d.deviceId === selected)
  const apps = useQuery({
    queryKey: ['android', instanceId, 'apps', session?.id, session?.generation],
    queryFn: () => fleet.apps(session!.id),
    enabled: Boolean(connected && page === 'detail' && session?.state === 'connected'),
    refetchInterval: 10000,
  })
  const refresh = () => {
    void apps.refetch()
    void queryClient.invalidateQueries({ queryKey: ['android-management', instanceId] })
  }
  const perform = async (fn: () => Promise<unknown>) => {
    if (busy) return
    setBusy(true)
    setError('')
    try {
      await fn()
      if (isCurrentBackend()) refresh()
    } catch (e) {
      if (isCurrentBackend()) setError(e instanceof Error ? e.message : '结果尚未确认，请刷新核实')
    } finally {
      if (isCurrentBackend()) setBusy(false)
    }
  }
  const finishLeave = () => {
    const target = pendingLeave.current
    if (!target || !isCurrentBackend()) return
    pendingLeave.current = null
    currentSession.current = null
    setSession(null)
    if (target.page === 'create') setSource(target.source)
    setPage(target.page)
  }
  const sessionReleased = async (candidate: ConsoleSession) => {
    let closed = false
    try {
      const observed = await fleet.readSession(candidate.id)
      closed = observed.deviceId === candidate.deviceId && observed.state === 'closed'
    } catch (cause) {
      closed = cause instanceof ApiClientError && cause.status === 410 && cause.code === 'ANDROID_SESSION_EXPIRED'
    }
    if (!closed) return false
    try {
      const snapshot = await managementDevices.refetch()
      const record = snapshot.data?.items.find((item) => item.deviceId === candidate.deviceId)
      return Boolean(snapshot.isSuccess && record && !record.stale && record.runtimeState !== 'unknown' &&
        record.owner.kind !== 'unknown' && record.owner.id !== candidate.id &&
        (record.owner.kind !== 'manualSession' || record.owner.id))
    } catch {
      return false
    }
  }
  const open = async (d: AndroidDevice) => {
    if (busy) {
      setError('当前操作尚未完成，请等待结果后再打开设备')
      return
    }
    if (d.androidStatus !== 'ready') {
      setError('设备尚未就绪，不能打开控制台')
      return
    }
    const epoch = ++openingEpoch.current
    pendingLeave.current = null
    setSelected(d.deviceId)
    setPage('detail')
    if (session?.deviceId === d.deviceId && session.state === 'connected') {
      await sessionStatus.refetch()
      return
    }
    const owner = managementDevices.data?.items.find((item) => item.deviceId === d.deviceId)?.owner
    if (owner?.kind === 'manualSession' && owner.id) {
      await perform(async () => {
        const existing = await fleet.readSession(owner.id!)
        if (existing.deviceId !== d.deviceId) throw new Error('控制会话与设备不匹配，请刷新列表核实')
        if (epoch !== openingEpoch.current) {
          if (existing.endpoint === 'embedded' && existing.state !== 'closed') await fleet.action(existing, 'end')
          return
        }
        currentSession.current = existing
        setSession(existing)
      })
      return
    }
    await perform(async () => {
      if (session && session.state !== 'closed' && session.endpoint !== 'native') await fleet.action(session, 'end')
      if (epoch !== openingEpoch.current) return
      if (pendingOpen.current?.deviceId !== d.deviceId)
        pendingOpen.current = { deviceId: d.deviceId, requestId: crypto.randomUUID() }
      const requestId = pendingOpen.current.requestId
      let next: ConsoleSession
      try {
        next = await fleet.session(
          d.deviceId,
          d.ownerRunId || d.control !== 'idle' ? 'readonly' : 'manual',
          requestId,
        )
      } catch (cause) {
        if (cause instanceof ApiClientError && ['ANDROID_CONSOLE_BUSY', 'ANDROID_SESSION_EXPIRED', 'ANDROID_REQUEST_CONFLICT', 'ANDROID_WORKFLOW_OWNS_DEVICE'].includes(cause.code ?? '')) {
          if (pendingOpen.current?.requestId === requestId) pendingOpen.current = null
          finishLeave()
        }
        throw cause
      }
      if (epoch !== openingEpoch.current) {
        try {
          const closed = await fleet.action(next, 'end')
          if (closed.state !== 'closed') throw new Error('过期控制会话结束结果待核实')
          if (pendingOpen.current?.requestId === requestId) pendingOpen.current = null
          finishLeave()
        } catch (cause) {
          if (isCurrentBackend()) {
            if (pendingOpen.current?.requestId === requestId) pendingOpen.current = null
            pendingLeave.current = null
            currentSession.current = { ...next, state: 'unknown', latestOperation: '控制会话结束结果待核实' }
            setSession(currentSession.current)
          }
          throw cause
        }
        return
      }
      currentSession.current = next
      setSession(next)
      pendingOpen.current = null
    })
  }
  const leaveDetail = async (destination: 'board' | 'create' = 'board', copySource?: AndroidDevice) => {
    openingEpoch.current += 1
    pendingLeave.current = { page: destination, source: copySource }
    const current = session
    if (!current) {
      if (pendingOpen.current) {
        setError(busy ? '正在核实打开结果并结束控制会话，请等待确认' : '打开结果未知；请点击“打开设备”按原请求核实后再返回')
        return false
      }
      finishLeave()
      return true
    }
    if (current.endpoint === 'native' && current.state === 'connected') {
      pendingLeave.current = null
      if (destination === 'create') setSource(copySource)
      setPage(destination)
      return true
    }
    if (endingSession.current === current.id) return false
    endingSession.current = current.id
    setSession((previous) => previous?.id === current.id ? { ...previous, state: 'unknown', latestOperation: '正在结束控制会话' } : previous)
    await queryClient.cancelQueries({ queryKey: ['android', instanceId, 'session', current.id] })
    queryClient.removeQueries({ queryKey: ['android', instanceId, 'session', current.id] })
    if (current.state === 'closed') {
      finishLeave()
      endingSession.current = null
      return true
    }
    try {
      const closed = await fleet.action(current, 'end')
      if (closed.state === 'closed') {
        finishLeave()
        return true
      } else {
        pendingLeave.current = null
        setSession((previous) => previous?.id === current.id ? { ...closed, state: 'unknown', latestOperation: '控制会话结束结果待核实' } : previous)
        setError('控制会话结束结果待核实，请留在详情页重试')
        return false
      }
    } catch (cause) {
      if (await sessionReleased(current)) {
        finishLeave()
        return true
      }
      pendingLeave.current = null
      setSession((previous) => previous?.id === current.id ? { ...previous, state: 'unknown', latestOperation: '控制会话结束结果待核实' } : previous)
      setError(cause instanceof Error ? `控制会话结束结果未知：${cause.message}` : '控制会话结束结果未知，请重新核实')
      return false
    } finally {
      endingSession.current = null
    }
  }
  leaveGuard.current = () => page === 'detail' ? leaveDetail() : Promise.resolve(true)
  useEffect(() => {
    registerLeaveGuard?.(() => leaveGuard.current())
    return () => registerLeaveGuard?.(null)
  }, [registerLeaveGuard])
  const sessionEpoch = openingEpoch.current
  const onSession = useCallback((s: ConsoleSession) => {
    if (sessionEpoch === openingEpoch.current && !endingSession.current && !pendingLeave.current &&
      active.current && backend.current.client === client && backend.current.instanceId === instanceId) {
      currentSession.current = s
      setSession(s)
    }
  }, [client, instanceId, sessionEpoch])
  const manage = (d: AndroidDevice, action: string, operationId?: string, requestId?: string) => {
    if (action === 'copy') {
      void leaveDetail('create', d)
      return
    }
    setError('')
    setManagement({ device: d, action, operationId, requestId })
    setName(d.name)
    setDeleteData(false)
    pendingManagement.current = null
  }
  const endControl = async (deviceId: string, sessionId: string) => {
    if (busy) {
      setError('当前操作尚未完成，请等待结果后再结束控制')
      return
    }
    await perform(async () => {
      const existing = await fleet.readSession(sessionId)
      if (existing.deviceId !== deviceId) throw new Error('控制会话与设备不匹配，请刷新列表核实')
      if (existing.state !== 'closed') {
        const closed = await fleet.action(existing, 'end')
        if (closed.state !== 'closed') throw new Error('控制会话结束结果待核实')
      }
      if (currentSession.current?.id === sessionId) {
        currentSession.current = null
        setSession(null)
      }
    })
  }
  const confirmManage = async () => {
    if (!management) return
    await perform(async () => {
      if (management.action === 'rename') await api.rename(management.device.deviceId, name)
      else if (management.action === 'verify') {
        if (!management.operationId) throw new Error('缺少待核实操作编号，请从操作历史打开')
        const operation = management.requestId ? null : await managementApi.operation(management.operationId)
        const requestId = management.requestId ?? operation?.requestId
        if (!requestId) throw new Error('缺少原操作请求编号，请从操作历史打开')
        await managementApi.verify(management.operationId, { requestId })
      }
      else {
        pendingManagement.current ??= {
          requestId: crypto.randomUUID(),
          action: (management.action === 'verify' ? 'recover' : management.action) as DeviceCommand['action'],
          deleteData,
        }
        await api.operate(management.device.deviceId, pendingManagement.current)
      }
      setManagement(null)
    })
  }
  const loadDevice = async (deviceId: string) => {
    return all.find((item) => item.deviceId === deviceId)
  }
  return (
    <>
      <div
        className="ad-page"
        style={{
          display: error && !management && !profilesOpen ? 'block' : 'none',
          minHeight: 0,
          paddingBottom: 0,
        }}
      >
        <p role="alert" className="ad-error">
          {error}
        </p>
      </div>
      {managementDevices.isError && <div className="ad-error">设备状态无法核实，请检查本机服务。</div>}
      {page === 'create' ? (
        <CreateInstances
          profiles={profiles.data ?? []}
          environment={environment.data}
          source={source}
          sourceSnapshot={managementDevices.data?.items.find((item) => item.deviceId === source?.deviceId)?.specSnapshot}
          onBack={() => setPage('board')}
          onProfiles={() => setProfilesOpen(true)}
          onSubmit={async (body) => {
            await fleet.batch(body)
            setPage('board')
            refresh()
          }}
        />
      ) : page === 'detail' && device ? (
        <>
        <DeviceConsole
          device={device}
          session={session?.deviceId === device.deviceId ? session : null}
          api={fleet}
          deviceApi={api}
          run={undefined}
          apps={apps.data}
          onBack={() => void leaveDetail()}
          onSession={onSession}
          onOpen={() => void open(device)}
          onManage={(action) => manage(device, action)}
          onRefresh={refresh}
        />
        <BackupPanel
          api={managementApi}
          deviceId={device.deviceId}
          revision={device.generation}
          runtimeState={managementRecord?.runtimeState ?? device.androidStatus}
          control={device.control}
          hasControlSession={Boolean(session?.deviceId === device.deviceId && session.state !== 'closed')}
          stale={Boolean(managementRecord?.stale || device.androidStatus === 'unknown')}
        />
        </>
      ) : (
        <div className="space-y-5"><RuntimeDiagnostics api={managementApi} /><ManagementOverview
          api={managementApi}
          previewApi={api}
          instanceId={instanceId}
          onCreate={() => {
            setSource(undefined)
            setPage('create')
          }}
          onOpen={(id) => {
            void loadDevice(id).then((target) => {
              if (target) return open(target)
              setError('实例详情暂不可用，请刷新后重试')
            }).catch((cause) => setError(cause instanceof Error ? cause.message : '实例详情暂不可用，请刷新后重试'))
          }}
          onEndControl={(id, sessionId) => { void endControl(id, sessionId) }}
          onManage={(id, action, operationId, requestId) => {
            void loadDevice(id).then((target) => {
              if (target) return manage(target, action, operationId, requestId)
              setError('实例详情暂不可用，请刷新后重试')
            }).catch((cause) => setError(cause instanceof Error ? cause.message : '实例详情暂不可用，请刷新后重试'))
          }}
        /><ImageManager api={managementApi} /><TemplateManager api={{ ...fleet, images: managementApi.images, archiveProfile: managementApi.archiveProfile }} /><DataMaintenance api={managementApi} saveDiagnostic={saveAndroidDiagnostic} resourceIds={[...all.map((item) => item.deviceId), ...(backups.data ?? []).map((item) => item.id)]} diagnosticDeviceIds={all.map((item) => item.deviceId)} /></div>
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
                  restore: '恢复保留数据',
                  recover: '核实状态',
                  verify: '核实状态',
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
                {!profiles.data?.length && (
                  <Action
                    primary
                    onClick={() =>
                      void perform(async () => {
                        await fleet.standardProfile()
                        await profiles.refetch()
                      })
                    }
                  >
                    创建标准模板
                  </Action>
                )}
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
    </>
  )
}
