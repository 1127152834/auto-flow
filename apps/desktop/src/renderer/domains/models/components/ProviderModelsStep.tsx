import { Check, MagnifyingGlass } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Input } from '../../../shared/components/ui/input'
import type { ModelDiscoveryRead } from '../model'

export function ProviderModelsStep({ discovery, selected, onSelected }: { discovery: ModelDiscoveryRead; selected: Set<string>; onSelected(value: Set<string>): void }) {
  const [search, setSearch] = useState('')
  const visible = useMemo(() => discovery.items.filter((model) => `${model.displayName} ${model.modelKey}`.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())), [discovery.items, search])
  const allSelected = discovery.items.length > 0 && selected.size === discovery.items.length
  const toggle = (key: string, checked: boolean) => { const next = new Set(selected); if (checked) next.add(key); else next.delete(key); onSelected(next) }
  return <section className="grid gap-4">
    <div className="flex gap-3 rounded-xl border border-green-200 bg-green-50 p-4 text-green-900"><Check size={20} /><span><strong className="block">连接测试成功</strong><small>{discovery.message} · {Math.round(discovery.latencyMs)} ms</small></span></div>
    <div className="flex gap-3"><label className="relative grow"><MagnifyingGlass className="absolute left-3 top-3 text-muted" size={16} /><Input aria-label="搜索发现的模型" value={search} onChange={(event) => setSearch(event.target.value)} className="pl-9" /></label><Button type="button" variant="ghost" onClick={() => onSelected(allSelected ? new Set() : new Set(discovery.items.map((item) => item.modelKey)))}>{allSelected ? '取消全选' : '选择全部'}</Button></div>
    <div className="grid max-h-72 gap-2 overflow-auto">{visible.map((model) => <label key={model.modelKey} className="flex items-center gap-3 rounded-xl border border-line p-3"><Checkbox aria-label={`选择 ${model.displayName}`} checked={selected.has(model.modelKey)} onCheckedChange={(checked) => toggle(model.modelKey, checked === true)} /><span className="min-w-0 grow"><strong className="block text-sm text-ink">{model.displayName}</strong><code className="text-xs text-muted">{model.modelKey}</code></span><small className="shrink-0 text-muted">{model.contextWindow == null ? '上下文长度未知' : `${model.contextWindow.toLocaleString('en-US')} tokens`}</small></label>)}</div>
    {!discovery.items.length && <p className="rounded-xl bg-surface-subtle p-5 text-center text-sm text-muted">供应商当前没有返回模型，可以先保存连接。</p>}
  </section>
}
