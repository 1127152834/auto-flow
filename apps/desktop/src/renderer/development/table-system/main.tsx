import { useState } from 'react'
import StudioTables from './StudioTables'
import { createRoot } from 'react-dom/client'
import '../../styles/index.css'
import { Table, TableHeader, TableHead, TableBody, TableCell, TableRow, TableScroll } from '../../shared/components/ui/table'
import { TableToolbar } from '../../shared/components/ui/table-toolbar'
import { TableStatus } from '../../shared/components/ui/table-status'
import { Button } from '../../shared/components/ui/button'
import { SearchInput } from '../../shared/components/ui/search-input'
import { Checkbox } from '../../shared/components/ui/checkbox'
import { ModelDirectory } from '../../domains/models/components/ModelDirectory'
import { ProxyTable } from '../../domains/proxies/components/ProxyFleet'
import type { ProxyView, ProxyFilters } from '../../domains/proxies/api'

const models = ['资料整理模型', '文本分析模型', '长名称用于检查截断与操作栏的稳定性'].map((displayName, i) => ({
  id: String(i), providerId: 'example', modelKey: 'example-chat-' + i, displayName, contextWindow: 32768,
  tagsJson: ['示例'], description: '', enabled: i !== 1, createdAt: '', updatedAt: '',
}))
const proxies: ProxyView[] = ['东京资料代理', '新加坡测试代理', '法兰克福采集代理'].map((name, i) => ({
  id: String(i), connection_id: 'example', name, name_override: null, enabled: true, remote_status: '可用', remote_missing: false,
  carrier: '示例运营商', city: ['东京', '新加坡', '法兰克福'][i], region: null, exit_ip: '192.0.2.' + (10 + i),
  http_endpoint: { host: '192.0.2.' + (10 + i), port: 8080 }, socks5_endpoint: null, credential_available: false,
  health: { state: i === 2 ? 'unhealthy' : 'healthy', latency_ms: i === 2 ? null : 42 + i * 16, exit_ip: null, checked_at: null, source: 'local_probe', error: null },
  subscription_expires_at: null, last_synced_at: null, stale: false, revision: 1, reference_count: i, capabilities: [],
}))

function Showcase() {
  const [view, setView] = useState('基础'), [query, setQuery] = useState(''), [status, setStatus] = useState('all')
  const [selected, setSelected] = useState<Set<string>>(() => new Set()), [filters, setFilters] = useState<ProxyFilters>({}), [notice, setNotice] = useState('')
  const proxyItems = proxies.filter(p => (!filters.q || p.name.includes(filters.q)) && (!filters.health || p.health.state === filters.health) && (!filters.city || p.city === filters.city) && (!filters.carrier || p.carrier === filters.carrier))
  return <main className="mx-auto max-w-[1484px] space-y-5 p-6">
    <header><h1 className="text-xl font-semibold">全局精细网格 · 组件验收</h1><p className="text-sm text-muted">合成资料，仅验证真实组件的视觉和交互；不连接外部服务，不代替应用端到端验收。</p></header>
    <TableToolbar label="展示场景">{['基础', '代理', '模型', 'Studio'].map(name => <Button key={name} variant={name === view ? 'primary' : 'secondary'} onClick={() => setView(name)}>{name}</Button>)}</TableToolbar>
    {view === '基础' ? <section className="space-y-2"><TableToolbar label="资料查询"><strong className="mr-auto">数据记录</strong><SearchInput aria-label="搜索示例" value={query} onChange={event => setQuery(event.target.value)} onClear={() => setQuery('')} /><Button disabled>导出</Button></TableToolbar>
      <TableScroll label="基础精细网格"><Table aria-label="基础精细网格"><TableHeader><TableRow><TableHead>选择</TableHead><TableHead>标题</TableHead><TableHead>文章链接</TableHead><TableHead>发布日期</TableHead><TableHead>业务状态</TableHead></TableRow></TableHeader><TableBody>
        {['温室光照管理笔记','番茄育苗观察','灌溉设备清单','土壤湿度记录'].filter(name => name.includes(query)).map((name,i) => <TableRow key={name} aria-selected={selected.has(name)}><TableCell><Checkbox aria-label={'选择' + name} checked={selected.has(name)} onCheckedChange={value => setSelected(current => { const next = new Set(current); if (value === true) next.add(name); else next.delete(name); return next })} /></TableCell><TableCell>{name}</TableCell><TableCell>https://example.com/notes/{i + 1}</TableCell><TableCell>2026-09-14</TableCell><TableCell><TableStatus tone={i === 1 ? 'success' : 'neutral'}>{i === 1 ? '已整理' : '未设置'}</TableStatus></TableCell></TableRow>)}
      </TableBody></Table></TableScroll></section> : view === '代理' ? <ProxyTable page={{items:proxyItems,offset:0,limit:50,matched_count:proxyItems.length}} filters={filters} onFiltersChange={setFilters} onOpen={p => setNotice('组件事件：打开' + p.name)} onProbe={() => setNotice('仅展示，不执行网络检测')} /> :
      view === 'Studio' ? <StudioTables /> : <ModelDirectory models={models} search={query} status={status} busy={false} testingKey={null} onSearch={setQuery} onStatus={setStatus} onAdd={() => setNotice('组件事件：添加模型')} onEdit={m => setNotice('组件事件：编辑' + m.displayName)} onDelete={() => setNotice('组件事件：删除确认')} onToggle={() => setNotice('组件事件：切换启用')} onTest={() => setNotice('仅展示，不执行网络请求')} />}
    {notice ? <p role="status">{notice}</p> : null}
  </main>
}
createRoot(document.getElementById('root')!).render(import.meta.env.DEV ? <Showcase /> : <p>此页面仅用于开发验收。</p>)
