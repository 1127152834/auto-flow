import { DotsThree, PencilSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { ProjectSummary } from '../types'

const lifecycleLabel: Record<string, string> = { active: '活动', closing: '正在归档', archived: '已归档', deleting: '正在删除', deleted: '已删除' }

function formatDate(value: string | null | undefined) {
  if (!value) return '从未打开'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function ProjectCard({ project, compact = false, disabled, onOpen, onEdit }: { project: ProjectSummary; compact?: boolean; disabled: boolean; onOpen(project: ProjectSummary): void; onEdit(project: ProjectSummary): void }) {
  const canOpen = !disabled && project.lifecycleState !== 'deleting' && project.lifecycleState !== 'deleted'
  const open = () => { if (canOpen) onOpen(project) }
  return <article aria-disabled={!canOpen || undefined} className={`group relative min-w-0 rounded-card border border-line bg-surface ${compact ? 'px-4 py-3' : 'min-h-36 p-5'} ${canOpen ? 'cursor-pointer hover:border-clay/50 hover:bg-surface-hover' : 'opacity-60'}`} onClick={event => { if (!(event.target as Element).closest('button')) open() }}>
    <div className={compact ? 'flex min-w-0 flex-wrap items-center gap-4 sm:flex-nowrap' : 'grid min-w-0 gap-3'}><div className="min-w-0 flex-1"><Button variant="ghost" className="h-auto max-w-full justify-start whitespace-normal break-all p-0 text-left text-base text-ink hover:bg-transparent" disabled={!canOpen} onClick={open}>{project.name}</Button><p className={`mb-0 mt-1 break-words text-sm text-muted ${compact ? 'line-clamp-1' : 'line-clamp-2'}`}>{project.description || '暂无项目描述'}</p></div>
    <div className={`flex min-w-0 items-center gap-3 text-xs text-muted ${compact ? 'w-full flex-wrap sm:w-auto sm:flex-nowrap' : 'justify-between'}`}>
      {compact ? <span>{lifecycleLabel[project.lifecycleState] ?? project.lifecycleState}</span> : null}<span className="truncate">最近打开：{formatDate(project.lastOpenedAt)}</span>
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" className="h-8 w-8 p-0" aria-label={`更多${project.name}操作`} onClick={event => event.stopPropagation()}><DotsThree size={20} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end" onClick={event => event.stopPropagation()}><DropdownMenuItem disabled={disabled || project.lifecycleState !== 'active'} onSelect={() => onEdit(project)}><PencilSimple className="mr-2" />编辑项目</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
    </div></div>
  </article>
}
