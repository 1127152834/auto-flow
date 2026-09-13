import { useState } from 'react'
import { ArrowsOutCardinal, MagnifyingGlass, Plus } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import type { NodeDefinition } from '../types'

type Props = { items: NodeDefinition[]; onAdd(type: string): void; disabled?: boolean }

export function NodeCatalog({ items, onAdd, disabled = false }: Props) {
  const [query, setQuery] = useState('')
  const search = query.trim().toLocaleLowerCase()
  const entries = items.filter(item => !item.type.endsWith('_end')).flatMap(item => item.type === 'loop' ? [['count', '重复指定次数'], ['foreach', '遍历列表'], ['while', '条件成立时循环']].map(([mode, title]) => ({ ...item, type: `loop:${mode}`, title })) : [item])
  const visible = entries.filter((item) => `${item.title} ${item.type}`.toLocaleLowerCase().includes(search))

  return <section className="flex h-full min-h-0 flex-col" aria-label="动作库">
    <div className="border-b border-line p-4">
      <h2 className="mb-3 text-sm font-semibold text-ink">动作库</h2>
      <div className="relative">
        <MagnifyingGlass className="pointer-events-none absolute left-3 top-3 text-muted" size={16} />
        <Input aria-label="搜索动作" placeholder="搜索名称或类型" className="pl-9" value={query} onChange={(event) => setQuery(event.target.value)} />
      </div>
    </div>
    <div className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
      {visible.map((item) => <Button
        key={item.type}
        type="button"
        className="h-auto w-full justify-start gap-3 px-3 py-3 text-left font-normal"
        draggable={!disabled}
        disabled={disabled}
        aria-label={`添加${item.title}`}
        onClick={() => onAdd(item.type)}
        onDragStart={(event) => {
          event.dataTransfer.setData('application/autoflow-node', item.type)
          event.dataTransfer.effectAllowed = 'copy'
        }}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-clay-soft text-clay"><Plus size={16} weight="bold" /></span>
        <span className="min-w-0 flex-1"><span className="block text-sm font-medium">{item.title}</span><span className="mt-0.5 block truncate font-mono text-[10px] text-muted">{item.type}</span></span>
      </Button>)}
      {!visible.length ? <p className="py-8 text-center text-sm text-muted" role="status">{items.length ? '没有匹配的动作' : '动作目录尚未加载'}</p> : null}
    </div>
    <p className="flex items-center gap-2 border-t border-line px-4 py-3 text-xs text-muted"><ArrowsOutCardinal size={14} />点击添加，或拖到画布</p>
  </section>
}
