import { useEffect, useId, useState } from 'react'
import { apiRequest } from '../../api'
import type { components } from '../../../../shared/api/generated'
import type { NodeData } from '../../editor-store'
import { Label } from '../controls/label'
import { VariableInput } from '../controls/variable-input'
import { VariableNameInput } from '../controls/variable-name-input'

type Proxy = components['schemas']['ProxyView']
type Location = components['schemas']['LocationView']
const selectClass = 'w-full rounded border border-input bg-background px-3 py-2 text-sm'

export function ProxyControlConfig({ data, onChange }: { data: NodeData; onChange: (key: string, value: unknown) => void }) {
  const id = useId()
  const [proxies, setProxies] = useState<Proxy[]>([])
  const [locations, setLocations] = useState<Location[]>([])
  const [error, setError] = useState('')
  const [locationError, setLocationError] = useState('')
  const query = data.moduleType === 'proxy_query'
  const relocate = data.moduleType === 'proxy_change_location'
  const target = String(data.target ?? 'current')
  const proxyId = String(data.proxyId ?? '')
  const connectionId = proxies.find(p => p.id === proxyId)?.connection_id
    ?? (new Set(proxies.map(p => p.connection_id)).size === 1 ? proxies[0]?.connection_id : undefined)
  useEffect(() => {
    const controller = new AbortController()
    async function load() {
      const items: Proxy[] = []
      let offset = 0
      while (!controller.signal.aborted) {
        const result = await apiRequest<components['schemas']['ProxyPage']>(`/v1/proxies?offset=${offset}&limit=100`, { signal: controller.signal })
        if (controller.signal.aborted) return
        if (!result.success || !result.data) { setError(result.error ?? '代理目录读取失败'); return }
        items.push(...result.data.items)
        offset += result.data.items.length
        if (!result.data.items.length || offset >= result.data.matched_count) break
      }
      if (!controller.signal.aborted) { setProxies(items); setError('') }
    }
    void load()
    return () => controller.abort()
  }, [])
  useEffect(() => {
    setLocations([])
    setLocationError('')
    if (!relocate || !connectionId) return
    const controller = new AbortController()
    void apiRequest<components['schemas']['LocationList']>(`/v1/proxy-panel/connections/${encodeURIComponent(connectionId)}/locations`, { signal: controller.signal }).then(result => {
      if (controller.signal.aborted) return
      if (result.success && result.data) setLocations(result.data.items)
      else setLocationError(result.error ?? '地点目录读取失败')
    })
    return () => controller.abort()
  }, [connectionId, relocate])
  function input(key: string, label: string, fallback = '') {
    const value = String(data[key] ?? fallback)
    const numeric = ['retryIntervalSeconds', 'maxAttempts', 'confirmationTimeoutSeconds'].includes(key)
    const invalid = numeric && !value.includes('{') && (!Number.isFinite(Number(value)) || Number(value) <= 0 || key === 'maxAttempts' && !Number.isInteger(Number(value)))
    return <div className="space-y-2"><Label htmlFor={`${id}-${key}`}>{label}</Label>
      <VariableInput id={`${id}-${key}`} value={value} aria-invalid={invalid} onChange={value => onChange(key, value)} />
      {invalid && <p role="alert" className="text-sm text-destructive">{key === 'maxAttempts' ? '请输入正整数或变量' : '请输入正数或变量'}</p>}
    </div>
  }
  return <div className="space-y-4">
    <div className="space-y-2"><Label htmlFor={`${id}-target`}>目标代理</Label>
      <select id={`${id}-target`} className={selectClass} value={target} onChange={e => onChange('target', e.target.value)}>
        <option value="current">当前任务代理（代理池实际成员）</option><option value="specified">指定代理</option>
      </select></div>
    {target === 'specified' && <>
      <div className="space-y-2"><Label htmlFor={`${id}-catalog`}>代理目录</Label>
        <select id={`${id}-catalog`} className={selectClass} value={proxies.some(p => p.id === proxyId) ? proxyId : ''} onChange={e => onChange('proxyId', e.target.value)}>
          <option value="">选择代理或在下方输入变量</option>{proxies.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select></div>{input('proxyId', '代理 ID／变量')}
      <p className="text-xs text-muted-foreground">指定代理不会改变当前浏览器的代理绑定。</p>
    </>}
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    {relocate && <>
      <div className="space-y-2"><Label htmlFor={`${id}-locations`}>地点目录</Label>
        <select id={`${id}-locations`} className={selectClass} value={locations.some(l => l.id === data.locationId) ? String(data.locationId) : ''} onChange={e => onChange('locationId', e.target.value)}>
          <option value="">选择地点或在下方输入变量</option>{locations.map(l => <option key={l.id} value={l.id} disabled={l.availability === 'unavailable'}>{[l.country, l.city, l.carrier].filter(Boolean).join(' · ')}{l.availability === 'unavailable' ? '（无容量）' : ''}</option>)}
        </select></div>{input('locationId', '地点 ID／变量')}
      {!connectionId && <p className="text-xs text-muted-foreground">运行时根据目标代理校验地点目录；也可指定代理后选择地点。</p>}
      {locationError && <p role="alert" className="text-sm text-destructive">{locationError}</p>}
    </>}
    {query ? input('operationId', '原操作 ID（可选）') : <>
      {input('retryIntervalSeconds', '重试间隔（秒）', '10')}
      {input('maxAttempts', '最大尝试次数（包含首次）', '5')}
      <p className="text-xs text-muted-foreground">冷却或仍在处理也计一次尝试；达到上限立即结束。</p>
    </>}
    <details><summary className="cursor-pointer text-sm">高级配置</summary><div className="mt-3">{input('confirmationTimeoutSeconds', '单次确认时限（秒）', '30')}</div></details>
    <div className="space-y-2"><Label htmlFor={`${id}-failure`}>失败处理</Label>
      <select id={`${id}-failure`} className={selectClass} value={String(data.failureMode ?? 'raise')} onChange={e => onChange('failureMode', e.target.value)}>
        <option value="raise">报错，进入错误路径</option><option value="capture">捕获结果，由流程判断</option>
      </select></div>
    <div className="space-y-2"><Label>结果变量</Label><VariableNameInput value={String(data.resultVariable ?? `${data.moduleType}_result`)} onChange={value => onChange('resultVariable', value)} /></div>
    <p className="text-xs text-muted-foreground">{query ? '只查询状态，不发送切换请求。' : '保留页面和登录上下文；切换可能中断已有网络请求。'}</p>
  </div>
}
