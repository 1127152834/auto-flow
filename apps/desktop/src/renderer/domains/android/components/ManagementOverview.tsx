import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { AndroidManagementApi, ManagementDevicePage } from '../management-api'
import type { AndroidApi, AndroidDevice } from '../api'
import { BulkActions } from './BulkActions'
import { DevicePreview } from './DevicePreview'

const runtimeLabels: Record<ManagementDevicePage['items'][number]['runtimeState'], string> = {
  stopped: '已停止',
  starting: '启动中',
  ready: '已就绪',
  retained: '数据已保留',
  missing: '资源缺失',
  unknown: '待核实',
}

type Props = {
  api: Pick<AndroidManagementApi, 'devices' | 'bulk' | 'bulkAction'>
  previewApi?: AndroidApi
  instanceId?: string
  onCreate?(): void
  onOpen?(deviceId: string): void
  onManage?(deviceId: string, action: string, operationId?: string, requestId?: string): void
}

export function ManagementOverview({ api, previewApi, instanceId = 'default', onCreate, onOpen, onManage }: Props) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [template, setTemplate] = useState('')
  const [retained, setRetained] = useState('')
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
  if (devices.isPending && !devices.data) return <section role="status" className="rounded-card border border-line bg-surface p-5">正在读取实例快照…</section>
  if (!devices.data) return <section role="alert" className="rounded-card border border-line bg-surface p-5">实例快照暂不可用。</section>
  return <section aria-label="安卓管理实例" className="rounded-card border border-line bg-surface p-5"><header className="flex items-center justify-between gap-3"><div><h2 className="font-semibold">实例管理</h2><p className="mt-1 text-sm text-muted">显示 {visible.length} / {page.total} 台实例 · 快照读取不触发运行时探测</p></div>{onCreate && <button type="button" onClick={onCreate}>创建实例</button>}</header>{staleSnapshot && <p role="alert" className="mt-3 rounded-control bg-surface-subtle p-2 text-sm">连接已断开，正在显示快照陈旧的旧数据；恢复连接后才能执行操作。</p>}<div aria-label="实例统计" className="mt-4 grid grid-cols-2 gap-2 text-sm md:grid-cols-4"><span>总数 {stats.total}</span><span>运行中 {stats.running}</span><span>已停止 {stats.stopped}</span><span>需处理 {stats.attention}</span></div><div className="mt-4 flex flex-wrap gap-2"><input aria-label="搜索实例" placeholder="搜索实例" value={search} onChange={event => setSearch(event.target.value)} /><select aria-label="筛选状态" value={status} onChange={event => setStatus(event.target.value)}><option value="">全部状态</option><option value="ready">已就绪</option><option value="stopped">已停止</option><option value="retained">数据已保留</option><option value="unknown">待核实</option></select><select aria-label="筛选模板" value={template} onChange={event => setTemplate(event.target.value)}><option value="">全部模板</option>{templateOptions.map(option => <option key={option.id} value={option.id}>{option.name}</option>)}</select><select aria-label="筛选数据" value={retained} onChange={event => setRetained(event.target.value)}><option value="">全部数据</option><option value="retained">数据已保留</option><option value="not-retained">未保留数据</option></select></div><div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{visible.map(device => {
    const statusLabel = runtimeLabels[device.runtimeState]
    const blocked = Object.values(device.blockedReasons ?? {}).filter(Boolean)
    const operational = !staleSnapshot && !device.stale && device.runtimeState !== 'unknown'
    const openable = operational && device.runtimeState === 'ready' && device.allowedActions.includes('open')
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
    return <article key={device.deviceId} className="rounded-control border border-line p-4"><div className="flex items-start justify-between gap-3"><strong className="break-words">{device.name}</strong><span className="text-xs text-muted">{statusLabel}</span></div><p className="mt-2 text-xs text-muted">修订 {device.revision} · {device.stale ? `状态陈旧 · ${statusLabel}` : staleSnapshot ? `快照陈旧 · ${statusLabel}` : '快照有效'}</p>{previewApi && <DevicePreview device={previewDevice} api={previewApi} revision={device.revision} enabled={operational && device.runtimeState === 'ready'} />}{blocked.length > 0 && <div className="mt-2 rounded-control bg-surface-subtle p-2 text-xs" role="status"><strong>已阻塞</strong>{blocked.map(reason => <p key={reason} className="mt-1">阻塞原因：{reason}</p>)}</div>}{device.allowedActions.length ? <p className="mt-2 text-xs">可操作：{device.allowedActions.join('、')}</p> : <p className="mt-2 text-xs text-muted">当前无可用操作</p>}<div className="mt-3 flex flex-wrap gap-2">{onOpen && <button type="button" disabled={!openable} onClick={() => onOpen(device.deviceId)} aria-label={`打开${device.name}`}>打开{device.name}</button>}{onManage && device.allowedActions.filter(action => ['start', 'stop', 'restart', 'delete', 'verify'].includes(action)).map(action => <button type="button" key={action} disabled={action !== 'verify' && !operational} onClick={() => onManage(device.deviceId, action, operationId, requestId)}>{action === 'verify' ? '核实状态' : action === 'start' ? '启动设备' : action === 'stop' ? '停止设备' : action === 'restart' ? '重启设备' : '删除实例'}</button>)}</div></article>
  })}</div>{!visible.length && <p className="mt-4 text-sm text-muted">没有匹配的实例。</p>}{visible.length > 0 && <div className="mt-5"><BulkActions api={api} devices={visible} /></div>}</section>
}
