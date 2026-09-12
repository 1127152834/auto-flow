import { SearchInput } from '../../../shared/components/ui/search-input'
import { Plus } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import type { ModelProvider } from '../model'
import { ProviderLogo } from './ProviderLogo'

export function ProviderSidebar({ providers, selectedId, search, onSearch, onSelect, onAdd }: {
  providers: ModelProvider[]; selectedId: string; search: string
  onSearch(value: string): void; onSelect(id: string): void; onAdd(): void
}) {
  const query = search.trim().toLocaleLowerCase()
  const visible = providers.filter(provider => `${provider.name} ${provider.providerKind}`.toLocaleLowerCase().includes(query))
  return <aside aria-label="供应商" className="border-b border-line bg-surface-subtle p-4 min-[920px]:border-b-0 min-[920px]:border-r">
    <div className="mb-4 flex items-center gap-2 px-1"><h2 className="m-0 text-sm font-semibold">供应商</h2><span className="text-xs text-muted">{providers.length}</span><Button onClick={onAdd} variant="ghost" aria-label="添加供应商" className="ml-auto h-8 w-8 p-0"><Plus size={18} /></Button></div>
    <div className="relative mb-4"><SearchInput onClear={() => onSearch('')} aria-label="搜索供应商" placeholder="搜索供应商" value={search} onChange={event => onSearch(event.target.value)}  /></div>
    <div className="grid gap-1 max-[919px]:grid-cols-2 max-[600px]:grid-cols-1">
      {visible.map(provider => <Button variant="ghost" key={provider.id} type="button" onClick={() => onSelect(provider.id)} aria-pressed={selectedId === provider.id} className={`h-auto justify-start whitespace-normal font-normal flex min-w-0 items-center gap-3 rounded-control border-l-[3px] p-3 text-left transition-colors ${selectedId === provider.id ? 'border-clay bg-clay-soft/60' : 'border-transparent hover:bg-surface-hover'}`}>
        <ProviderLogo presetId={provider.presetId} name={provider.name} size="small" />
        <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{provider.name}</span><span className="mt-1 block text-xs text-muted">{provider.models.length} 个模型</span></span>
        <span aria-label={!provider.enabled ? '已停用' : provider.connectionStatus === 'connected' ? '连接正常' : provider.connectionStatus === 'failed' ? '连接异常' : '未测试'} className={`h-1.5 w-1.5 shrink-0 rounded-full ${!provider.enabled ? 'bg-line-strong' : provider.connectionStatus === 'connected' ? 'bg-sage' : provider.connectionStatus === 'failed' ? 'bg-danger' : 'bg-warning'}`} />
      </Button>)}
    </div>
    {visible.length === 0 && <p className="px-2 py-6 text-center text-sm text-muted">{providers.length ? '没有匹配的供应商' : '尚未配置模型供应商'}</p>}
  </aside>
}
