import { useState } from 'react'
import type { LocationList } from '../api'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Dialog, DialogContent, DialogTitle, DialogDescription } from '../../../shared/components/ui/dialog'

export function LocationPicker({ locations, loading, error, busy, currentCity, currentCarrier, onClose, onReload, onSelect }: {
  locations?: LocationList; loading: boolean; error?: string; busy: boolean
  currentCity?: string | null; currentCarrier?: string | null
  onClose: () => void; onReload: () => void; onSelect: (id: string) => void
}) {
  const [query, setQuery] = useState('')
  const [carrier, setCarrier] = useState('')
  const [selected, setSelected] = useState('')
  const all = locations?.items ?? []
  const items = all.filter(item => (!carrier || item.carrier === carrier) && `${item.country} ${item.city} ${(item.cities ?? []).join(' ')} ${item.carrier}`.toLowerCase().includes(query.trim().toLowerCase()))
  const carriers = [...new Set(all.flatMap(item => item.carrier ? [item.carrier] : []))]
  const target = all.find(item => item.id === selected)
  return <Dialog open onOpenChange={open => { if (!open) onClose() }} busy={busy}>
    <DialogContent className="w-[min(92vw,42rem)]">
      <DialogTitle>选择代理地点</DialogTitle>
      <DialogDescription>部分地点由多个城市共用同一个目标，切换后城市由 ProxyPanel 分配。可用容量可能随时变化。</DialogDescription>
      <div className="flex gap-2"><Input aria-label="搜索地点" placeholder="搜索城市或运营商" value={query} onChange={e => setQuery(e.target.value)} /><Select aria-label="地点运营商" value={carrier} onChange={e => setCarrier(e.target.value)}><option value="">全部运营商</option>{carriers.map(item => <option key={item}>{item}</option>)}</Select></div>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <div className="max-h-80 overflow-y-auto rounded-control border border-line" aria-busy={loading}>
        {loading ? <p role="status" className="p-5 text-sm text-muted">正在读取可用地点…</p> : items.map(item => <label key={item.id} className="flex items-start gap-3 border-b border-line p-3 last:border-0">
          <input type="radio" name="remote-location" className="mt-1" checked={selected === item.id} disabled={item.availability !== 'available' || Boolean(error)} onChange={() => setSelected(item.id)} />
          <span className="min-w-0 text-sm"><span className="block font-medium">{item.city}{item.cities?.includes(currentCity ?? '') && (!item.carrier || item.carrier === currentCarrier) && <span className="ml-2 text-xs text-muted">覆盖当前城市</span>}</span><span className="block text-muted">{item.country} · {item.carrier || '运营商未指定'} · 可用 {item.available_slots ?? '未知'}</span>{(item.cities?.length ?? 0) > 1 && <details className="mt-1 text-xs text-muted"><summary>查看共用目标的覆盖城市</summary>{item.cities?.join('、')}</details>}</span>
        </label>)}
        {!loading && !items.length && <p className="p-5 text-sm text-muted">{error ? '地点列表暂不可用' : '没有匹配地点'}</p>}
      </div>
      <div className="flex justify-between gap-2"><Button disabled={busy || loading} onClick={onReload}>刷新地点</Button><div className="flex gap-2"><Button disabled={busy} onClick={onClose}>取消</Button><Button variant="primary" disabled={busy || loading || Boolean(error) || target?.availability !== 'available'} onClick={() => onSelect(selected)}>下一步</Button></div></div>
    </DialogContent>
  </Dialog>
}
