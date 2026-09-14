import { ArrowClockwise, CircleNotch, DotsThree, MagnifyingGlass, Plus, Pulse } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { TableStatus } from '../../../shared/components/ui/table-status'
import { Badge } from '../../../shared/components/ui/badge'
import { Input } from '../../../shared/components/ui/input'
import { Select } from '../../../shared/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableToolbar } from '../../../shared/components/ui/table-toolbar'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { AiModel } from '../model'

export function ModelDirectory({ models, search, status, busy, testingKey, onSearch, onStatus, onAdd, onTest, onEdit, onToggle, onDelete }: {
  models: AiModel[]; search: string; status: string; busy: boolean; testingKey: string | null
  onSearch(value: string): void; onStatus(value: string): void; onAdd(sync: boolean): void
  onTest(model: AiModel): void; onEdit(model: AiModel): void; onToggle(model: AiModel): void; onDelete(model: AiModel): void
}) {
  const query = search.trim().toLocaleLowerCase()
  const visible = models.filter(model => `${model.displayName} ${model.modelKey} ${model.tagsJson.join(' ')}`.toLocaleLowerCase().includes(query) && (status === 'all' || model.enabled === (status === 'enabled')))
  return <section aria-label="模型目录" className="mt-7">
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3"><h3 className="m-0 text-base font-semibold">模型目录</h3><div className="flex gap-2"><Button size="sm" className="text-sm" onClick={() => onAdd(true)}><ArrowClockwise size={17} />同步并添加</Button><Button size="sm" className="text-sm" onClick={() => onAdd(false)} variant="primary"><Plus size={17} />添加模型</Button></div></div>
    <TableToolbar label="模型查询" className="mb-4 flex flex-wrap items-center gap-3"><div className="relative min-w-48 flex-1"><MagnifyingGlass size={17} className="pointer-events-none absolute left-3 top-2 text-muted" /><Input aria-label="搜索模型" placeholder="搜索模型名称、标识或标签" value={search} onChange={event => onSearch(event.target.value)} className="pl-9" /></div><Select clearable={false} aria-label="模型状态" value={status} onValueChange={value => onStatus(value ?? 'all')} className="w-40" options={[{ value: 'all', label: '全部状态' }, { value: 'enabled', label: '已启用' }, { value: 'disabled', label: '已停用' }]} /></TableToolbar>
    <TableScroll label="模型目录列表" className="rounded-control border border-line"><Table className="min-w-[640px]"><TableHeader><TableRow>{['模型', '标签', '上下文', '状态', '操作'].map(label => <TableHead key={label}>{label}</TableHead>)}</TableRow></TableHeader><TableBody>
      {visible.map(model => <TableRow key={model.id}><TableCell className="max-w-64"><span className="block truncate font-medium">{model.displayName}</span><span className="mt-1 block truncate font-mono text-sm text-muted">{model.modelKey}</span></TableCell><TableCell className="max-w-48"><span className="flex flex-wrap gap-1">{model.tagsJson.length ? model.tagsJson.map(tag => <Badge key={tag} className="bg-surface-subtle text-muted">{tag}</Badge>) : <span className="text-muted">—</span>}</span></TableCell><TableCell className="whitespace-nowrap font-mono text-sm text-muted">{model.contextWindow?.toLocaleString('zh-CN') ?? '—'}</TableCell><TableCell className="whitespace-nowrap"><TableStatus tone={model.enabled ? 'success' : 'neutral'}>{model.enabled ? '已启用' : '已停用'}</TableStatus></TableCell><TableCell><div className="flex items-center gap-1"><Button variant="ghost" className="h-8 px-2 text-xs" disabled={testingKey !== null} aria-label={`${model.displayName} 测试模型`} aria-busy={testingKey === model.modelKey} onClick={() => onTest(model)}>{testingKey === model.modelKey ? <CircleNotch className="animate-spin" size={15} /> : <Pulse size={15} />}测试</Button><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" aria-label={`${model.displayName} 更多操作`} className="h-8 w-8 p-0"><DotsThree size={22} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => onEdit(model)}>编辑模型</DropdownMenuItem><DropdownMenuItem disabled={busy} onSelect={() => onToggle(model)}>{model.enabled ? '停用模型' : '启用模型'}</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem className="text-red-700" onSelect={() => onDelete(model)}>删除模型</DropdownMenuItem></DropdownMenuContent></DropdownMenu></div></TableCell></TableRow>)}
      {!visible.length && <TableRow><TableCell colSpan={5} className="py-14 text-center text-muted">{models.length ? '没有匹配的模型' : '尚未添加模型，从供应商目录选择或手动添加模型。'}</TableCell></TableRow>}
    </TableBody></Table></TableScroll>
    <p className="mb-0 mt-3 text-xs text-muted">{visible.length} / {models.length} 个模型</p>
  </section>
}
