import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ArrowDown, ArrowUp, Plus, Stack, X } from '@phosphor-icons/react'
import type { GroupDraft, GroupPage, GroupView, ProxyView } from '../api'
import { Button } from '../../../shared/components/ui/button'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../../../shared/components/ui/alert-dialog'
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from '../../../shared/components/ui/dialog'
import { FormField } from '../../../shared/components/FormField'
import { HealthPill, StatusPill } from './presentation'

export function LocalProxyGroupTable({ page, proxies, retryAfterSeconds = 0, onCreate, onEdit, onDelete }: {
  page: GroupPage
  proxies: ProxyView[]
  retryAfterSeconds?: number
  onCreate: () => void
  onEdit: (group: GroupView) => void
  onDelete: (group: GroupView) => Promise<void>
}) {
  const proxyById = new Map(proxies.map((proxy) => [proxy.id, proxy]))
  return (
    <section className="overflow-hidden rounded-card border border-line bg-surface shadow-sm" aria-labelledby="local-groups-title">
      <header className="flex flex-col gap-4 border-b border-line p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3"><span className="grid h-9 w-9 place-items-center rounded-control bg-clay-soft text-clay"><Stack /></span><div><div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold text-ink" id="local-groups-title">本地代理组</h2><StatusPill>AutoFlow 本地编排</StatusPill></div><p className="mt-1 text-sm text-muted">按成员顺序进行 Round Robin，供浏览器配置选择。</p></div></div>
        <Button className="shrink-0 whitespace-nowrap" variant="primary" onClick={onCreate}><Plus />新建代理组</Button>
      </header>
      {!page.items.length ? (
        <div className="grid min-h-40 place-items-center p-8 text-center"><div><p className="font-medium text-ink">还没有本地代理组</p><p className="mt-1 text-sm text-muted">可以先创建空组草稿，加入成员后才可用于浏览器启动。</p></div></div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead className="bg-surface-subtle text-xs text-muted"><tr>{['组名称', '成员', '健康概况', '关联配置', '描述', '操作'].map((label) => <th className="px-4 py-3 font-medium" key={label}>{label}</th>)}</tr></thead>
            <tbody>{page.items.map((group) => {
              const members = group.member_ids.map((id) => proxyById.get(id)).filter((proxy): proxy is ProxyView => Boolean(proxy))
              const healthy = members.filter((proxy) => proxy.health.state === 'healthy').length
              return <tr className="border-t border-line" key={group.id}><td className="px-4 py-3 font-medium text-ink">{group.name}</td><td className="px-4 py-3 text-muted">{group.member_ids.length} 个代理</td><td className="px-4 py-3 text-muted">{members.length ? `${healthy}/${members.length} 健康` : group.member_ids.length ? '成员状态未载入' : '空组'}</td><td className="px-4 py-3 text-muted">{group.reference_count}</td><td className="max-w-xs truncate px-4 py-3 text-muted">{group.description || '—'}</td><td className="px-4 py-3"><div className="flex gap-1"><Button className="h-8 px-3" variant="ghost" onClick={() => onEdit(group)}>编辑</Button><AlertDialog><AlertDialogTrigger asChild><Button className="h-8 px-3" variant="ghost" disabled={retryAfterSeconds > 0}>删除</Button></AlertDialogTrigger><AlertDialogContent><AlertDialogTitle>删除“{group.name}”？</AlertDialogTitle><AlertDialogDescription>{group.reference_count ? `该组有 ${group.reference_count} 个浏览器配置引用，请先解除这些浏览器配置的引用。` : '此操作会删除 AutoFlow 本地分组，不会删除任何 ProxyPanel 代理。'}</AlertDialogDescription><div className="flex justify-end gap-2"><AlertDialogCancel asChild><Button>取消</Button></AlertDialogCancel><AlertDialogAction asChild><Button variant="primary" onClick={() => void onDelete(group)}>确认删除</Button></AlertDialogAction></div></AlertDialogContent></AlertDialog></div></td></tr>
            })}</tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export function LocalProxyGroupEditor({ open, group, proxies, busy, retryAfterSeconds = 0, error, riskRequired, onOpenChange, onSubmit }: {
  open: boolean
  group: GroupView | null
  proxies: ProxyView[]
  busy: boolean
  retryAfterSeconds?: number
  error?: string
  riskRequired: boolean
  onOpenChange: (open: boolean) => void
  onSubmit: (draft: GroupDraft, acknowledgeRisk: boolean) => Promise<void>
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [memberIds, setMemberIds] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [health, setHealth] = useState('')

  useEffect(() => {
    if (!open) return
    setName(group?.name ?? '')
    setDescription(group?.description ?? '')
    setMemberIds(group?.member_ids ?? [])
    setQuery('')
    setHealth('')
  }, [group, open])

  const proxyById = useMemo(() => new Map(proxies.map((proxy) => [proxy.id, proxy])), [proxies])
  const ordered = memberIds.map((id) => ({ id, proxy: proxyById.get(id) }))
  const candidates = useMemo(() => proxies.filter((proxy) => {
    const searchable = `${proxy.name_override || proxy.name} ${proxy.city ?? ''} ${proxy.carrier ?? ''}`.toLowerCase()
    return !proxy.remote_missing && (!query || searchable.includes(query.toLowerCase())) && (!health || proxy.health.state === health)
  }), [health, proxies, query])

  function toggle(id: string, selected: boolean) {
    setMemberIds((current) => selected ? [...current, id] : current.filter((item) => item !== id))
  }

  function move(index: number, direction: -1 | 1) {
    const target = index + direction
    if (target < 0 || target >= memberIds.length) return
    setMemberIds((current) => {
      const next = [...current]
      ;[next[index], next[target]] = [next[target], next[index]]
      return next
    })
  }

  async function submit(event: FormEvent, acknowledgeRisk: boolean) {
    event.preventDefault()
    if (!name.trim()) return
    try {
      await onSubmit({ name: name.trim(), description: description.trim(), member_ids: memberIds }, acknowledgeRisk)
    } catch {
      // The caller keeps the structured error so the user's draft stays intact.
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} busy={busy}>
      <DialogContent className="max-h-[90dvh] w-[min(94vw,48rem)] max-w-none overflow-y-auto" aria-describedby="proxy-group-editor-description">
        <DialogTitle>{group ? '编辑本地代理组' : '新建本地代理组'}</DialogTitle>
        <DialogDescription id="proxy-group-editor-description">成员顺序决定 Round Robin 的轮换顺序。空组可以保存为草稿，但不能用于启动。</DialogDescription>
        <form className="grid gap-5" onSubmit={(event) => void submit(event, false)}>
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="组名称" htmlFor="proxy-group-name"><Input value={name} maxLength={120} onChange={(event) => setName(event.target.value)} /></FormField>
            <FormField label="描述" htmlFor="proxy-group-description"><Input value={description} maxLength={1000} onChange={(event) => setDescription(event.target.value)} /></FormField>
          </div>
          <section className="grid gap-3">
            <div><h3 className="text-sm font-semibold text-ink">选择成员</h3><p className="mt-1 text-xs text-muted">远端缺失的代理不会出现在可选列表中。</p></div>
            <div className="grid gap-2 sm:grid-cols-2"><Input aria-label="搜索组成员" value={query} placeholder="搜索名称、城市或运营商" onChange={(event) => setQuery(event.target.value)} /><Select aria-label="筛选成员健康" value={health} onChange={(event) => setHealth(event.target.value)}><option value="">全部健康状态</option><option value="healthy">健康</option><option value="unhealthy">异常</option><option value="untested">未检测</option></Select></div>
            <div className="max-h-48 overflow-y-auto rounded-control border border-line">
              {candidates.map((proxy) => <label className="flex cursor-pointer items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 hover:bg-surface-hover" key={proxy.id}><input type="checkbox" checked={memberIds.includes(proxy.id)} onChange={(event) => toggle(proxy.id, event.target.checked)} /><span className="min-w-0 flex-1 truncate text-sm text-ink">{proxy.name_override || proxy.name}</span><HealthPill health={proxy.health} /></label>)}
              {!candidates.length ? <p className="p-4 text-center text-sm text-muted">没有匹配代理</p> : null}
            </div>
          </section>
          <section className="grid gap-3">
            <h3 className="text-sm font-semibold text-ink">成员顺序</h3>
            {ordered.length ? <ol className="grid gap-2">{ordered.map(({ id, proxy }, index) => {
              const label = proxy ? proxy.name_override || proxy.name : '已失效代理'
              return <li className="flex min-w-0 items-center gap-2 rounded-control border border-line bg-surface-subtle px-3 py-2" key={id}><span className="w-6 shrink-0 text-center text-xs text-muted">{index + 1}</span><span className="min-w-0 flex-1 truncate text-sm text-ink">{label}</span>{proxy?.remote_missing ? <StatusPill tone="danger">远端缺失</StatusPill> : null}<Button type="button" className="h-8 w-8 shrink-0 px-0" variant="ghost" aria-label={`上移 ${label}`} disabled={index === 0} onClick={() => move(index, -1)}><ArrowUp /></Button><Button type="button" className="h-8 w-8 shrink-0 px-0" variant="ghost" aria-label={`下移 ${label}`} disabled={index === ordered.length - 1} onClick={() => move(index, 1)}><ArrowDown /></Button><Button type="button" className="h-8 w-8 shrink-0 px-0" variant="ghost" aria-label={`移除 ${label}`} onClick={() => toggle(id, false)}><X /></Button></li>
            })}</ol> : <p className="rounded-control border border-dashed border-line p-4 text-center text-sm text-muted">尚未选择成员</p>}
          </section>
          {error ? <div className="rounded-control bg-red-50 px-4 py-3 text-sm text-red-700" role="alert"><p>{error}</p>{riskRequired ? <Button className="mt-3" type="button" variant="primary" disabled={retryAfterSeconds > 0} onClick={(event) => void submit(event, true)}>{retryAfterSeconds > 0 ? `${retryAfterSeconds} 秒后可重试` : '了解风险并保存'}</Button> : null}</div> : null}
          <div className="flex flex-wrap justify-end gap-2"><DialogClose asChild><Button className="whitespace-nowrap" type="button">取消</Button></DialogClose><Button className="whitespace-nowrap" type="submit" variant="primary" disabled={busy || retryAfterSeconds > 0 || !name.trim()}>{busy ? '保存中…' : retryAfterSeconds > 0 ? `${retryAfterSeconds} 秒后可重试` : '保存代理组'}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  )
}
