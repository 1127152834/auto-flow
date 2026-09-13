import { DotsThree, Folder, PencilSimple } from '@phosphor-icons/react'
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
  return <article aria-disabled={!canOpen || undefined} className={`group relative flex min-w-0 items-start rounded-card border border-line bg-surface ${compact ? 'gap-3 p-3 pr-12' : 'gap-4 p-5 pr-14'} ${canOpen ? 'cursor-pointer hover:border-clay/50 hover:bg-surface-hover' : 'opacity-60'}`} onClick={event => { if (!(event.target as Element).closest('button')) open() }}>
    <div data-project-icon className={`flex shrink-0 items-center justify-center rounded-control bg-clay/10 text-clay ${compact ? 'h-10 w-10' : 'h-12 w-12'}`}><Folder aria-hidden="true" size={compact ? 22 : 26} weight="duotone" /></div>
    <div data-project-info className="min-w-0 flex-1">
      <Button variant="ghost" title={project.name} className="h-auto max-w-full justify-start truncate p-0 text-left text-base font-medium text-ink hover:bg-transparent" disabled={!canOpen} onClick={open}>{project.name}</Button>
      <p className="mb-0 mt-1 line-clamp-2 break-words text-sm leading-5 text-muted">{project.description || '暂无项目描述'}</p>
      <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {compact ? <span>{lifecycleLabel[project.lifecycleState] ?? project.lifecycleState}</span> : null}<span className="truncate">最近打开：{formatDate(project.lastOpenedAt)}</span>
      </div>
    </div>
    <div data-project-menu className="absolute right-3 top-3">
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" className="h-8 w-8 p-0" aria-label={`更多${project.name}操作`} onClick={event => event.stopPropagation()}><DotsThree aria-hidden="true" size={20} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end" onClick={event => event.stopPropagation()}><DropdownMenuItem disabled={disabled || project.lifecycleState !== 'active'} onSelect={() => onEdit(project)}><PencilSimple aria-hidden="true" className="mr-2" />编辑项目</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
    </div>
  </article>
}
