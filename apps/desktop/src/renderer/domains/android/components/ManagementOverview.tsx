import { DeviceMobile, DotsThree, GearSix, Plus } from '@phosphor-icons/react'
import { Action, Badge, Dot } from './PrototypeControls'
import '../management-board.css'
import { useQuery } from '@tanstack/react-query'
import { useId, useMemo, useRef, useState } from 'react'
import type { AndroidManagementApi, ManagementDevicePage } from '../management-api'
import type { AndroidApi, AndroidDevice } from '../api'
import { BulkActions } from './BulkActions'
import { DevicePreview } from './DevicePreview'
import { OperationHistory } from './OperationHistory'

const runtimeLabels: Record<ManagementDevicePage['items'][number]['runtimeState'], string> = {
  stopped: '已停止',
  starting: '启动中',
  ready: '已就绪',
  retained: '数据已保留',
  missing: '资源缺失',
  unknown: '待核实',
}

type Props = {
  api: Pick<AndroidManagementApi, 'devices' | 'bulk' | 'bulkStatus' | 'bulkAction' | 'operations'>
  previewApi?: AndroidApi
  instanceId?: string
  onCreate?(): void
  onEnvironment?(): void
  onExternal?(): void
  onOpen?(deviceId: string): void
  onMaintain?(deviceId: string): void
  onEndControl?(deviceId: string, sessionId: string): void
  onManage?(deviceId: string, action: string, operationId?: string, requestId?: string): void
}

export function ManagementOverview({ api, previewApi, instanceId = 'default', onCreate, onEnvironment, onExternal, onOpen, onMaintain, onEndControl, onManage }: Props) {
  const [view, setView] = useState<'board' | 'list'>('board')
  const [menu, setMenu] = useState<string | null>(null)
  const menuTrigger = useRef<HTMLButtonElement>(null)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [template, setTemplate] = useState('')
  const [retained, setRetained] = useState('')
  const [historyDeviceId, setHistoryDeviceId] = useState<string | null>(null)
  const historyPanelId = useId()
  const historyTrigger = useRef<HTMLButtonElement>(null)
  const devices = useQuery({
    queryKey: ['android-management', instanceId, 'devices'],
    queryFn: async () => {
      const items: ManagementDevicePage['items'] = []
      let cursor = ''
      let total = 0
      do {
        const page = await api.devices(cursor ? `?limit=50&cursor=${encodeURIComponent(cursor)}` : '?limit=50')
        if (Array.isArray(page)) break
        items.push(...page.items)
        total = page.total
        cursor = page.nextCursor ?? ''
      } while (cursor)
      return { items, total, nextCursor: null }
    },
    refetchInterval: 3000,
  })
  const page: ManagementDevicePage = !devices.data || Array.isArray(devices.data) ? { items: [], total: 0, nextCursor: null } : devices.data
  const staleSnapshot = devices.isError && Boolean(devices.data)
  const templateOptions = useMemo(() => Array.from(new Map(page.items.map(device => {
    const spec = device.specSnapshot ?? {}
    const id = typeof spec.profileId === 'string' ? spec.profileId : typeof spec.profile_id === 'string' ? spec.profile_id : ''
    const name = typeof spec.profileName === 'string' ? spec.profileName : typeof spec.profile_name === 'string' ? spec.profile_name : id
    return [id, name] as const
  }).filter(([id]) => id)), ([id, name]) => ({ id, name })), [page.items])
  const visible = useMemo(() => page.items.filter(device => {
    const spec = device.specSnapshot ?? {}
    const profileId = typeof spec.profileId === 'string' ? spec.profileId : typeof spec.profile_id === 'string' ? spec.profile_id : ''
    const retainedValue = device.runtimeState === 'retained' || spec.dataRetained === true || spec.data_retained === true
    return (!search || device.name.toLowerCase().includes(search.toLowerCase())) &&
      (!status || device.runtimeState === status) &&
      (!template || profileId === template) &&
      (!retained || (retained === 'retained' ? retainedValue : !retainedValue))
  }), [page.items, search, status, template, retained])
  const stats = useMemo(() => ({
    total: page.total,
    running: page.items.filter(device => device.runtimeState === 'ready').length,
    stopped: page.items.filter(device => device.runtimeState === 'stopped' || device.runtimeState === 'retained').length,
    attention: page.items.filter(device => device.stale || ['unknown', 'missing'].includes(device.runtimeState) || Object.keys(device.blockedReasons ?? {}).length > 0).length,
  }), [page.items, page.total])
  const group = (device: ManagementDevicePage['items'][number]) => {
    if (staleSnapshot || device.stale || ['unknown', 'missing', 'starting', 'stopped', 'retained'].includes(device.runtimeState) || device.restoreState === 'pending') return 2
    if (device.owner.kind !== 'none') return 1
    return Object.keys(device.blockedReasons ?? {}).length ? 2 : 0
  }
  if (devices.isPending && !devices.data) return <section role="status" className="am-board-loading">正在读取实例…</section>
  if (!devices.data) return <section role="alert" className="am-board-loading">实例暂不可用。</section>
  const card = (device: ManagementDevicePage['items'][number]) => {
    const statusLabel = device.restoreState === 'pending' ? '恢复数据待核实' : runtimeLabels[device.runtimeState]
    const blocked = [...new Set(Object.values(device.blockedReasons ?? {}).filter(Boolean))]
    const operational = !staleSnapshot && !device.stale && device.runtimeState !== 'unknown'
    const ownedSession = operational && device.owner.kind === 'manualSession' && Boolean(device.owner.id)
    const openable = operational && device.runtimeState === 'ready' && (device.allowedActions.includes('open') || ownedSession && device.allowedActions.includes('return_to_console'))
    const operationId = typeof device.latestOperation?.operationId === 'string' ? device.latestOperation.operationId : typeof device.latestOperation?.operation_id === 'string' ? device.latestOperation.operation_id : typeof device.latestOperation?.id === 'string' ? device.latestOperation.id : undefined
    const requestId = typeof device.latestOperation?.requestId === 'string' ? device.latestOperation.requestId : typeof device.latestOperation?.request_id === 'string' ? device.latestOperation.request_id : undefined
    const spec = device.specSnapshot ?? {}
    const specValue = (key: string, fallback: unknown) => spec[key] ?? spec[key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`)] ?? fallback
    const previewDevice = {
      deviceId: device.deviceId,
      name: device.name,
      runtimeId: 'management',
      ownerRunId: null,
      control: device.owner.kind === 'none' ? 'idle' : 'managing',
      generation: device.revision,
      width: Number(specValue('width', 720)),
      height: Number(specValue('height', 1280)),
      imageId: String(specValue('imageId', '')),
      androidStatus: device.runtimeState,
      lastError: null,
      cpu: Number(spec.cpu ?? 1),
      memoryMb: Number(specValue('memoryMb', 1536)),
      dpi: Number(specValue('dpi', 320)),
      androidVersion: null,
      architecture: null,
      dataRetained: false,
      deleted: false,
      operation: null,
      profileId: null,
      profileName: null,
      instanceType: 'persistent',
      locale: 'zh-CN',
      timezone: 'Asia/Shanghai',
    } as unknown as AndroidDevice
    const primaryAction = device.allowedActions.find(action => ['start', 'restore', 'verify'].includes(action))
    const actionLabel = (action: string) => ({ verify: '核实状态', start: '启动设备', stop: '停止设备', restart: '重启设备', restore: '恢复实例', delete: '删除实例' })[action] ?? action
    const manage = (action: string) => onManage?.(device.deviceId, action === 'verify' ? 'recover' : action, operationId, requestId)
    return <article key={device.deviceId} className="am-device-card">
      <div className="am-device-preview">{previewApi ? <DevicePreview device={previewDevice} api={previewApi} revision={device.revision} enabled={operational && device.runtimeState === 'ready'} /> : <div className="am-preview-placeholder"><DeviceMobile size={32} weight="light" /><span>暂无在线画面</span></div>}</div>
      <div className="am-device-body">
        <div className="am-device-title"><strong>{device.name}</strong><span className={`ad-badge ad-${device.runtimeState === 'ready' && operational ? 'green' : device.runtimeState === 'starting' ? 'blue' : 'gray'} shrink-0 whitespace-nowrap`}>{statusLabel}</span></div>
        <p className="am-device-spec">{specValue('androidVersion', null) ? `Android ${String(specValue('androidVersion', ''))}` : 'Android 版本待核实'} · {specValue('width', null) && specValue('height', null) ? `${String(specValue('width', ''))} × ${String(specValue('height', ''))}` : '分辨率待核实'}</p>
        <Badge tone="brown">{specValue('instanceType', 'persistent') === 'temporary' ? '历史临时实例' : '持久实例'}</Badge>
        {ownedSession && <p className="am-device-note">手动控制会话占用中</p>}
        {!ownedSession && device.owner.kind !== 'none' && <p className="am-device-note">设备正在使用中</p>}
        {device.stale || staleSnapshot ? <p className="am-device-note">{device.stale ? '状态陈旧' : '快照陈旧'} · {statusLabel}</p> : device.runtimeState === 'starting' ? <p className="am-device-note">等待 Android 就绪…</p> : device.runtimeState === 'retained' ? <p className="am-device-note">数据已保留，可恢复实例。</p> : null}
        {blocked.length > 0 && <div className="am-device-blocked" role="status">{blocked.map(reason => <p key={reason}>阻塞原因：{reason}</p>)}</div>}
        <div className="am-device-actions">
          {onManage && primaryAction && <Action primary disabled={primaryAction !== 'verify' && !operational} onClick={() => manage(primaryAction)}>{actionLabel(primaryAction)}</Action>}
          {onOpen && <Action primary={!primaryAction} disabled={!openable} onClick={() => onOpen(device.deviceId)} aria-label={ownedSession ? `查看${device.name}控制会话` : `打开${device.name}`}>{ownedSession ? '查看控制会话' : '打开设备'}</Action>}
        </div>
      </div>
      <div className="am-device-more" onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget)) setMenu(null) }} onKeyDown={event => { if (event.key === 'Escape') { setMenu(null); menuTrigger.current?.focus() } }}>
        <button type="button" aria-label={`${device.name}更多操作`} aria-expanded={menu === device.deviceId} onClick={event => { menuTrigger.current = event.currentTarget; setMenu(menu === device.deviceId ? null : device.deviceId) }}><DotsThree size={23} /></button>
        {menu === device.deviceId && <div className="am-device-menu" role="group" aria-label={`${device.name}操作`}>
          {onMaintain && <button type="button" onClick={() => onMaintain(device.deviceId)} aria-label={`维护${device.name}`}>数据维护</button>}
          <button type="button" aria-expanded={historyDeviceId === device.deviceId} aria-controls={historyPanelId} onClick={() => { historyTrigger.current = menuTrigger.current; setHistoryDeviceId(device.deviceId); setMenu(null) }} aria-label={`查看${device.name}操作历史`}>操作历史</button>
          {onEndControl && ownedSession && device.owner.id && device.allowedActions.includes('end_control') && <button type="button" onClick={() => onEndControl(device.deviceId, device.owner.id!)} aria-label={`结束${device.name}控制会话`}>结束控制</button>}
          {onManage && device.allowedActions.filter(action => ['start', 'stop', 'restart', 'restore', 'delete', 'verify'].includes(action) && action !== primaryAction).map(action => <button type="button" key={action} disabled={action !== 'verify' && !operational} onClick={() => manage(action)}>{actionLabel(action)}</button>)}
        </div>}
      </div>
    </article>
  }
  return <section aria-label="安卓管理实例" className="am-management-board">
    <header className="ad-page-heading"><div><h1>安卓模拟器</h1><p>管理设备，查看运行状态与保留的数据。</p></div><div>{onExternal && <Action onClick={onExternal}>外接设备</Action>}{onEnvironment && <Action onClick={onEnvironment}><GearSix size={20} />环境配置</Action>}{onCreate && <Action primary onClick={onCreate}><Plus size={20} />创建实例</Action>}</div></header>
    {staleSnapshot && <p role="alert" className="am-connection-alert">连接已断开，正在显示快照陈旧的旧数据；恢复连接后才能执行操作。</p>}
    <div className="am-board-surface">
      <div className="am-board-toolbar"><div className="ad-segments"><Action primary={view === 'list'} aria-pressed={view === 'list'} onClick={() => setView('list')}>实例列表</Action><Action primary={view === 'board'} aria-pressed={view === 'board'} onClick={() => setView('board')}>资源看板</Action></div><span>{page.total} 台设备 · {page.items.filter(device => group(device) === 0).length} 台可用</span><select aria-label="筛选模板" value={template} onChange={event => setTemplate(event.target.value)}><option value="">全部环境</option>{templateOptions.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</select></div>
      <div className="am-board-filters"><input aria-label="搜索实例" placeholder="搜索实例" value={search} onChange={event => setSearch(event.target.value)} /><select aria-label="筛选状态" value={status} onChange={event => setStatus(event.target.value)}><option value="">全部状态</option>{Object.entries(runtimeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><select aria-label="筛选数据" value={retained} onChange={event => setRetained(event.target.value)}><option value="">全部数据</option><option value="retained">数据已保留</option><option value="not-retained">未保留数据</option></select><div aria-label="实例统计" className="am-board-stats"><span>总数 {stats.total}</span><span>运行中 {stats.running}</span><span>已停止 {stats.stopped}</span><span>需处理 {stats.attention}</span></div></div>
      {view === 'board' ? <div className="am-board-columns">{['可用设备', '使用中', '启动与停止'].map((title, index) => <section key={title} aria-label={`${index === 0 ? '可用' : title}设备分组`} className="am-board-column"><h2><Dot tone={index === 0 ? 'green' : index === 1 ? 'brown' : 'gray'} />{title}<span>{visible.filter(device => group(device) === index).length}</span></h2><div className="am-column-cards">{visible.filter(device => group(device) === index).map(card)}{!visible.some(device => group(device) === index) && <p className="am-column-empty">暂无{index === 0 ? '可用' : title}设备</p>}</div></section>)}</div> : <div role="region" aria-label="实例列表" className="am-device-list">{visible.map(card)}</div>}
      {!visible.length && <p className="am-empty">没有匹配的实例。</p>}
    </div>
    <fieldset className="am-board-bulk" disabled={staleSnapshot}><BulkActions api={api} devices={visible} /></fieldset>
    {historyDeviceId && <div className="am-board-history"><OperationHistory key={historyDeviceId} id={historyPanelId} api={api} instanceId={instanceId} deviceId={historyDeviceId} deviceName={page.items.find(device => device.deviceId === historyDeviceId)?.name ?? historyDeviceId} onVerify={onManage ? (operationId, requestId) => onManage(historyDeviceId, 'verify', operationId, requestId) : undefined} onClose={() => { setHistoryDeviceId(null); historyTrigger.current?.focus() }} /></div>}
  </section>
}
