import { useState } from 'react'
import type { ModelDiscoveryRead } from '../model'
import { Input } from '../../../shared/components/ui/input'

type RemoteModel = ModelDiscoveryRead['items'][number]

export function ModelIdInput({ id, value, options, onChange }: { id?: string; value: string; options: RemoteModel[]; onChange(value: string, option?: RemoteModel): void }) {
  const [query, setQuery] = useState(value)
  const visible = options.filter((option) => `${option.displayName} ${option.modelKey}`.toLowerCase().includes(query.toLowerCase()))
  return <div className="grid gap-2">
    <Input id={id} aria-label="模型标识" value={query} placeholder="搜索或输入模型标识" onChange={(event) => { setQuery(event.target.value); onChange(event.target.value) }} onKeyDown={(event) => { if (event.key === 'Enter' && !event.nativeEvent.isComposing) { event.preventDefault(); onChange(query.trim()) } }} />
    {visible.length ? <div className="grid max-h-40 gap-1 overflow-y-auto" role="listbox" aria-label="模型目录">
      {visible.map((option) => <button className="rounded-control px-3 py-2 text-left text-sm hover:bg-surface-hover" key={option.modelKey} role="option" aria-selected={option.modelKey === value} onClick={() => { setQuery(option.modelKey); onChange(option.modelKey, option) }}>{option.displayName === option.modelKey ? option.modelKey : `${option.displayName} · ${option.modelKey}`}</button>)}
    </div> : null}
  </div>
}
