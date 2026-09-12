import { useEffect, useState, type ReactNode } from 'react'
import { ArrowsClockwise, CircleNotch, Copy, MapPin, Pulse, X } from '@phosphor-icons/react'
import { capability, type Capability, type IpAllowlist, type LocationList, type ProxyMetadataDraft, type ProxyReferences, type ProxyView, type RotationSchedule } from '../api'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Switch } from '../../../shared/components/ui/switch'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../../shared/components/ui/alert-dialog'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { CapabilityNotice, formatTime, HealthPill, StatusPill } from './presentation'

type ProxyDetailDrawerProps = {
  open: boolean
  proxy: ProxyView | null
  references?: ProxyReferences
  probing: boolean
  actionBusy?: boolean
  retryAfterSeconds?: number
  canCopyCredentials?: boolean
  copying?: string
  onOpenChange: (open: boolean) => void
  onProbe: (proxy: ProxyView, protocol?: 'http' | 'socks5') => void
  onUpdateMetadata: (proxy: ProxyView, draft: ProxyMetadataDraft) => Promise<void>
  onCopyCredentials: (proxy: ProxyView, protocol: 'http' | 'socks5', format: 'username' | 'password' | 'url') => void
  onChangeIp?: (proxy: ProxyView) => void
  onOpenLocations?: (proxy: ProxyView) => void
}

function verifiedWrite(item?: Capability): boolean {
  return Boolean(item?.available && item.evidence === 'fixture-verified')
}

export function ProxyDetailDrawer({ open, proxy, references, probing, actionBusy = false, retryAfterSeconds = 0, canCopyCredentials = false, copying, onOpenChange, onProbe, onUpdateMetadata, onCopyCredentials, onChangeIp, onOpenLocations }: ProxyDetailDrawerProps) {
  const [nameOverride, setNameOverride] = useState(proxy?.name_override ?? '')
  const [enabled, setEnabled] = useState(proxy?.enabled ?? false)
  const [protocol, setProtocol] = useState<'http' | 'socks5'>(proxy?.socks5_endpoint ? 'socks5' : 'http')
  useEffect(() => {
    if (!proxy) return
    setNameOverride(proxy.name_override ?? '')
    setEnabled(proxy.enabled)
  }, [proxy])
  const hasSocks5 = Boolean(proxy?.socks5_endpoint)
  useEffect(() => { setProtocol(hasSocks5 ? 'socks5' : 'http') }, [proxy?.id, hasSocks5])
  if (!proxy) return null
  const capabilities = proxy.capabilities ?? []
  const changeIp = capability(capabilities, 'change_ip')
  const relocate = capability(capabilities, 'relocate')
  const rotation = capability(capabilities, 'rotation_schedule')
  const credentials = capability(capabilities, 'credentials')
  const allowlist = capability(capabilities, 'ip_allowlist')
  const usage = capability(capabilities, 'usage')

  return (
    <Dialog open={open} onOpenChange={onOpenChange} busy={actionBusy}>
      <DialogContent className="left-auto right-0 top-0 h-dvh w-[min(100vw,43rem)] max-w-none translate-x-0 translate-y-0 content-start overflow-y-auto rounded-none border-y-0 border-r-0 p-0 motion-safe:data-[state=open]:animate-in motion-safe:data-[state=open]:slide-in-from-right-2" aria-describedby="proxy-detail-description">
        <header className="sticky top-0 z-10 flex items-start justify-between border-b border-line bg-surface/95 px-6 py-5 backdrop-blur">
          <div className="min-w-0">
            <DialogTitle className="break-words">{proxy.name_override || proxy.name}</DialogTitle>
            <DialogDescription id="proxy-detail-description" className="mt-1">ProxyPanel 投影详情</DialogDescription>
          </div>
          <Button className="h-9 w-9 shrink-0 px-0" variant="ghost" aria-label="关闭代理详情" onClick={() => onOpenChange(false)} disabled={actionBusy}><X size={18} /></Button>
        </header>
        <Tabs defaultValue="overview" className="p-6">
          <TabsList className="w-full justify-start overflow-x-auto">
            <TabsTrigger value="overview">概览</TabsTrigger>
            <TabsTrigger value="rotation">位置与轮换</TabsTrigger>
            <TabsTrigger value="credentials">凭据与白名单</TabsTrigger>
            <TabsTrigger value="usage">用量</TabsTrigger>
          </TabsList>
          <TabsContent value="overview" className="grid gap-4">
            <section className="flex flex-col gap-4 rounded-card border border-line p-5 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2"><HealthPill health={proxy.health} /><StatusPill>{proxy.remote_status || '远程状态未知'}</StatusPill></div>
              <Select aria-label="检测协议" value={protocol} disabled={probing} onChange={event => setProtocol(event.target.value as 'http' | 'socks5')}>
                {proxy.socks5_endpoint && <option value="socks5">SOCKS5</option>}
                {proxy.http_endpoint && <option value="http">HTTP</option>}
              </Select>
              <Button aria-busy={probing} disabled={probing || retryAfterSeconds > 0 || !proxy.credential_available || proxy.remote_missing || (!proxy.http_endpoint && !proxy.socks5_endpoint)} onClick={() => onProbe(proxy, protocol)}>{probing ? <CircleNotch className="animate-spin" aria-hidden="true" /> : <Pulse aria-hidden="true" />}{probing ? '检测中…' : retryAfterSeconds > 0 ? `${retryAfterSeconds} 秒后可重试` : '测试连接'}</Button>
            </section>
            <DetailSection title="本地设置">
              <label className="grid gap-2 text-sm text-ink">显示名称<Input value={nameOverride} maxLength={120} placeholder={proxy.name} onChange={(event) => setNameOverride(event.target.value)} /></label>
              <label className="flex items-center justify-between text-sm text-ink">启用此代理<Switch checked={enabled} onCheckedChange={setEnabled} /></label>
              <div className="flex justify-end"><Button className="whitespace-nowrap" variant="primary" disabled={actionBusy || retryAfterSeconds > 0 || (nameOverride.trim() === (proxy.name_override ?? '') && enabled === proxy.enabled)} onClick={() => void onUpdateMetadata(proxy, { name_override: nameOverride.trim() || null, enabled })}>{actionBusy ? '保存中…' : retryAfterSeconds > 0 ? `${retryAfterSeconds} 秒后可重试` : '保存本地设置'}</Button></div>
            </DetailSection>
            <DetailSection title="网络信息">
              <DetailRow label="当前位置" value={[proxy.city, proxy.region].filter(Boolean).join(', ') || '—'} />
              <DetailRow label="运营商" value={proxy.carrier || '—'} />
              <DetailRow label="出口 IP" value={proxy.health.exit_ip || proxy.exit_ip || '—'} mono />
              <EndpointRow label="HTTP 代理" endpoint={proxy.http_endpoint} />
              <EndpointRow label="SOCKS5 代理" endpoint={proxy.socks5_endpoint} />
            </DetailSection>
            <DetailSection title="健康状态">
              <p className="text-xs text-muted">显示最近一次所选协议的 HTTPS 检测结果，不代表所有协议同时可用。</p>
              <DetailRow label="探测来源" value={proxy.health.source === 'local_probe' ? 'AutoFlow 本地 HTTPS 探测' : proxy.health.source === 'provider_probe' ? 'Provider 探测' : '未检测'} />
              <DetailRow label="请求耗时" value={proxy.health.latency_ms == null ? '—' : `${Math.round(proxy.health.latency_ms)} ms`} />
              <DetailRow label="上次检测" value={formatTime(proxy.health.checked_at)} />
              <DetailRow label="到期时间" value={formatTime(proxy.subscription_expires_at)} />
              <DetailRow label="上次同步" value={formatTime(proxy.last_synced_at)} />
              {proxy.health.error ? <p className="rounded-control bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{proxy.health.error.message}</p> : null}
            </DetailSection>
            <DetailSection title="关联资源">
              <DetailRow label="浏览器配置" value={references ? names(references.profiles) : `${proxy.reference_count} 个引用`} />
              <DetailRow label="本地代理组" value={references ? names(references.groups) : '载入中…'} />
            </DetailSection>
          </TabsContent>
          <TabsContent value="rotation" className="grid gap-4">
            <DetailSection title="即时操作">
              <p className="text-sm text-muted">更换 IP 或地点可能导致正在使用此代理的浏览器会话短暂重连。</p>
              <div className="flex flex-wrap gap-2">
                <AlertDialog>
                  <AlertDialogTrigger asChild><Button disabled={!verifiedWrite(changeIp) || !onChangeIp}><ArrowsClockwise />更换 IP</Button></AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogTitle>确认更换出口 IP？</AlertDialogTitle>
                    <AlertDialogDescription>当前出口 IP：{proxy.exit_ip || '未知'}。操作可能中断现有浏览器会话，提交后不会自动重试。</AlertDialogDescription>
                    <div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button>取消</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="primary" onClick={() => onChangeIp?.(proxy)}>确认更换</Button></AlertDialogAction></div>
                  </AlertDialogContent>
                </AlertDialog>
                <Button variant="primary" disabled={!verifiedWrite(relocate) || !onOpenLocations} onClick={() => onOpenLocations?.(proxy)}><MapPin />改变地点</Button>
              </div>
              {!verifiedWrite(changeIp) || !verifiedWrite(relocate) ? <CapabilityNotice capability={!verifiedWrite(changeIp) ? changeIp : relocate} fallback="远程操作尚未通过真实契约验证。" /> : null}
            </DetailSection>
            <DetailSection title="轮换计划">
              <CapabilityNotice capability={rotation} fallback="轮换模式和间隔尚未通过真实契约验证。" />
            </DetailSection>
          </TabsContent>
          <TabsContent value="credentials" className="grid gap-4">
            <DetailSection title="代理凭据">
              <DetailRow label="凭据状态" value={proxy.credential_available ? '可用，操作时从 ProxyPanel 获取' : '不可用'} />
              <Select aria-label="凭据协议" value={protocol} onChange={(event) => setProtocol(event.target.value as 'http' | 'socks5')}>
                {proxy.http_endpoint ? <option value="http">HTTP</option> : null}
                {proxy.socks5_endpoint ? <option value="socks5">SOCKS5</option> : null}
              </Select>
              <div className="flex flex-wrap gap-2">
                {(['username', 'password', 'url'] as const).map((format) => {
                  const key = `${protocol}:${format}`
                  const label = format === 'username' ? '复制用户名' : format === 'password' ? '复制密码' : '复制代理 URL'
                  const endpointAvailable = protocol === 'http' ? Boolean(proxy.http_endpoint) : Boolean(proxy.socks5_endpoint)
                  return <CopyButton key={format} label={copying === key ? '复制中…' : label} disabled={!endpointAvailable || !proxy.credential_available || !canCopyCredentials || Boolean(copying)} onCopy={() => onCopyCredentials(proxy, protocol, format)} />
                })}
              </div>
              {!canCopyCredentials || !proxy.credential_available ? <CapabilityNotice capability={credentials} fallback={proxy.credential_available ? '当前预览环境未提供受控复制通道。' : '代理凭据尚不可用。'} /> : null}
            </DetailSection>
            <DetailSection title="IP 白名单">
              <CapabilityNotice capability={allowlist} fallback="白名单接口尚未通过真实契约验证。" />
            </DetailSection>
          </TabsContent>
          <TabsContent value="usage">
            <DetailSection title="用量">
              <CapabilityNotice capability={usage} fallback="暂无经过验证的用量数据。" />
            </DetailSection>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  )
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return <section className="grid gap-3 rounded-card border border-line bg-surface p-5"><h3 className="font-semibold text-ink">{title}</h3>{children}</section>
}

function DetailRow({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return <div className="grid gap-1 sm:grid-cols-[9rem_1fr]"><dt className="text-sm text-muted">{label}</dt><dd className={`m-0 break-all text-sm text-ink ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd></div>
}

function EndpointRow({ label, endpoint }: { label: string; endpoint: ProxyView['http_endpoint'] }) {
  const value = endpoint ? `${endpoint.host}:${endpoint.port}` : '—'
  return <DetailRow label={label} value={value} mono />
}

function names(items: Array<{ id: string; name: string }> | undefined): string {
  if (!items) return '无'
  return items.length ? items.map((item) => item.name).join('、') : '无'
}

export function LocationPicker({ open, locations, selectedId, busy, onOpenChange, onSubmit }: {
  open: boolean
  locations: LocationList | null
  selectedId?: string
  busy: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (locationId: string) => void
}) {
  const [query, setQuery] = useState('')
  const [carrier, setCarrier] = useState('')
  const [value, setValue] = useState(selectedId ?? '')
  useEffect(() => { if (!open) { setQuery(''); setCarrier(''); setValue(selectedId ?? '') } }, [open, selectedId])
  const items = (locations?.items ?? []).filter((item) => (!query || `${item.city} ${item.region ?? ''}`.toLowerCase().includes(query.toLowerCase())) && (!carrier || item.carrier === carrier))
  const carriers = [...new Set((locations?.items ?? []).map((item) => item.carrier).filter((item): item is string => Boolean(item)))]
  return (
    <Dialog open={open} onOpenChange={onOpenChange} busy={busy}>
      <DialogContent>
        <DialogTitle>改变地点</DialogTitle>
        <DialogDescription>选择 API 返回的稳定地点；列表不显示未经测量的地点延迟。</DialogDescription>
        <div className="grid gap-3 sm:grid-cols-2"><Input aria-label="搜索地点" placeholder="搜索城市" value={query} onChange={(event) => setQuery(event.target.value)} /><Select aria-label="地点运营商" value={carrier} onChange={(event) => setCarrier(event.target.value)}><option value="">全部运营商</option>{carriers.map((item) => <option key={item}>{item}</option>)}</Select></div>
        <div className="max-h-72 overflow-y-auto rounded-control border border-line">
          {items.map((item) => <label className="flex cursor-pointer items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 hover:bg-surface-hover" key={item.id}><input type="radio" name="proxy-location" value={item.id} checked={value === item.id} disabled={item.availability === 'unavailable'} onChange={() => setValue(item.id)} /><span className="flex-1 text-sm text-ink">{item.city}{item.region ? `, ${item.region}` : ''}</span><span className="text-xs text-muted">{item.carrier || '运营商未知'} · {item.availability === 'available' ? '可用' : item.availability === 'unavailable' ? '不可用' : '可用性未知'}</span></label>)}
          {!items.length ? <p className="p-5 text-center text-sm text-muted">没有匹配地点</p> : null}
        </div>
        <div className="flex justify-end gap-2"><Button onClick={() => onOpenChange(false)}>取消</Button><Button variant="primary" disabled={!value || busy} onClick={() => onSubmit(value)}>{busy ? '正在切换…' : '切换地点'}</Button></div>
      </DialogContent>
    </Dialog>
  )
}

export function RotationForm({ value, disabled, onSave }: { value: RotationSchedule; disabled?: string; onSave: (value: RotationSchedule) => void }) {
  return <fieldset className="grid gap-3" disabled={Boolean(disabled)}><Select aria-label="轮换模式" value={value.mode ?? ''} onChange={(event) => onSave({ ...value, mode: event.target.value as RotationSchedule['mode'] })}><option value="">不轮换</option><option value="same_city">同城轮换</option><option value="random_city">随机城市</option><option value="same_carrier">保持运营商</option></Select>{disabled ? <p className="text-sm text-muted">{disabled}</p> : null}</fieldset>
}

export function AllowlistEditor({ value, disabled, onChange }: { value: IpAllowlist; disabled?: string; onChange: (value: IpAllowlist) => void }) {
  return <fieldset className="grid gap-3" disabled={Boolean(disabled)}><label className="flex items-center justify-between text-sm text-ink">启用 IP 白名单<Switch checked={value.enabled} onCheckedChange={(enabled) => onChange({ ...value, enabled })} /></label><Input value={value.ipv4s.join(', ')} placeholder="IPv4 地址，以逗号分隔" onChange={(event) => onChange({ ...value, ipv4s: event.target.value.split(',').map((item) => item.trim()).filter(Boolean) })} />{disabled ? <p className="text-sm text-muted">{disabled}</p> : null}</fieldset>
}

export function CopyButton({ label, onCopy, disabled }: { label: string; onCopy: () => void; disabled?: boolean }) {
  return <Button disabled={disabled} onClick={onCopy}><Copy />{label}</Button>
}
