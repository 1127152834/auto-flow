import { MagnifyingGlass } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Input } from '../../../shared/components/ui/input'
import { ProviderLogo } from './ProviderLogo'
import { providerPresets, type ProviderPreset } from '../provider-catalog'

export function ProviderCatalogStep({ selectedId, onSelect }: { selectedId: string; onSelect(preset: ProviderPreset): void }) {
  const [search, setSearch] = useState('')
  const common = useMemo(() => providerPresets.filter((item) => item.category !== '自定义' && `${item.displayName} ${item.aliases.join(' ')}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())), [search])
  const custom = providerPresets.at(-1)!
  return <section className="grid gap-5">
    <label className="relative"><MagnifyingGlass className="absolute left-3 top-3 text-muted" size={16} /><Input autoFocus aria-label="搜索供应商目录" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索供应商名称" className="pl-9" /></label>
    <div className="flex items-center justify-between"><h3 className="font-semibold text-ink">常用供应商</h3><span className="text-xs text-muted">{common.length} 个可用连接</span></div>
    <div className="grid gap-3 sm:grid-cols-2">
      {common.map((preset) => <button type="button" key={preset.id} aria-pressed={preset.id === selectedId} onClick={() => onSelect(preset)} className="flex items-center gap-3 rounded-xl border border-line bg-surface p-4 text-left hover:bg-surface-hover aria-pressed:border-clay aria-pressed:ring-2 aria-pressed:ring-clay/15"><ProviderLogo presetId={preset.id} name={preset.displayName} /><span><strong className="block text-sm text-ink">{preset.displayName}</strong><small className="text-muted">{preset.category}</small></span></button>)}
    </div>
    {!common.length && <p className="rounded-xl bg-surface-subtle p-4 text-sm text-muted">没有匹配的常用供应商，可以使用自定义兼容接口。</p>}
    <button type="button" aria-pressed={custom.id === selectedId} onClick={() => onSelect(custom)} className="flex items-center gap-3 rounded-xl border border-dashed border-clay/60 bg-clay/5 p-4 text-left"><ProviderLogo presetId={custom.id} name={custom.displayName} /><span><strong className="block text-sm text-ink">{custom.displayName}</strong><small className="text-muted">连接其他支持 OpenAI 协议的服务</small></span></button>
  </section>
}
