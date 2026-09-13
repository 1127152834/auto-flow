import { useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import type { useInspection } from '../hooks/useInspection'

type Props = { inspection: ReturnType<typeof useInspection>; profiles: { id: string; name: string }[]; disabled: boolean; runActive: boolean }
export function InspectionPanel({ inspection, profiles, disabled, runActive }: Props) {
  const [expanded, setExpanded] = useState(false)
  const [profileId, setProfileId] = useState('')
  const [url, setUrl] = useState('')
  const { session, active, busy, message } = inspection
  const target = session?.targetPageId
  return <section aria-label="拾取浏览器" className="shrink-0 border-b border-line bg-surface px-4 py-2">
    <div className="flex items-center gap-3"><Button variant="ghost" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>拾取浏览器 {expanded ? '收起' : '展开'}</Button><span className="text-xs text-muted" role="status">{active ? session?.state === 'starting' ? '浏览器启动中…' : session?.state === 'closing' ? '清理中…' : `已连接 · ${session?.profileName}` : '手动进入页面后，点选元素配置节点'}</span></div>
    {expanded ? <div className="space-y-2 py-2">
      <div className="flex flex-wrap items-center gap-2"><Select aria-label="拾取浏览器配置" value={profileId} disabled={disabled || busy || active} onChange={event => setProfileId(event.target.value)}><option value="">选择浏览器配置</option>{profiles.map(profile => <option key={profile.id} value={profile.id}>{profile.name}</option>)}</Select>
        <Button disabled={disabled || busy || active || runActive || !profileId} onClick={() => void inspection.start(profileId)}>打开拾取浏览器</Button>
        <Button disabled={disabled || busy || !active} onClick={() => void inspection.close()}>关闭拾取浏览器</Button>
        <Button variant="ghost" disabled={disabled || busy} onClick={() => void inspection.refresh()}>刷新连接</Button>
      </div>
      <p className="text-xs text-muted">本次以可见模式打开，不修改配置。手动登录状态仅保留到本次拾取浏览器关闭；运行使用独立会话。</p>
      {active ? <div className="flex flex-wrap items-center gap-2"><Select aria-label="拾取目标标签页" value={target ?? ''} disabled={disabled || busy || session?.state !== 'ready'} onChange={event => void inspection.page(event.target.value)}><option value="">请选择目标标签页</option>{session?.pages.map(page => <option key={page.pageId} value={page.pageId}>{page.title || page.url}</option>)}</Select>
        <Input aria-label="拾取网页地址" placeholder="https://…" className="max-w-sm" value={url} disabled={disabled || busy} onChange={event => setUrl(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && target && url) void inspection.page(target, url) }} />
        <Button disabled={disabled || busy || !target || !url} onClick={() => { if (target) void inspection.page(target, url) }}>前往</Button>
        <Button disabled={disabled || busy || !target} onClick={() => { if (target) void inspection.page(target) }}>聚焦浏览器</Button>
      </div> : null}
    </div> : null}
    {message || session?.error ? <p role="alert" className="py-1 text-xs text-red-700">{message || session?.error}</p> : null}
  </section>
}
