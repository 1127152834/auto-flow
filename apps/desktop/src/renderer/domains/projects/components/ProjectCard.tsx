import { Archive, ArrowCounterClockwise, DotsThree, Folder, PencilSimple, Trash, WarningCircle } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../../../shared/components/ui/dropdown-menu'
import type { ProjectSummary } from '../types'

export type ProjectLifecycleChoice = 'archive' | 'restore' | 'delete'

const lifecycleLabel: Record<string, string> = { active: '活动', closing: '正在归档', archived: '已归档', deleting: '正在删除', deleted: '已删除' }

function formatDate(value: string | null | undefined) {
  if (!value) return '从未打开'
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function ProjectCard({ project, disabled, cleanupResidue = [], onOpen, onEdit, onLifecycle }: { project: ProjectSummary; disabled: boolean; cleanupResidue?: string[]; onOpen(project: ProjectSummary): void; onEdit(project: ProjectSummary): void; onLifecycle?(project: ProjectSummary, action: ProjectLifecycleChoice): void }) {
  const canOpen = !disabled && project.lifecycleState !== 'deleting' && project.lifecycleState !== 'deleted'
  const residue = cleanupResidue.length > 0
  const open = () => { if (canOpen) onOpen(project) }
  return <article aria-disabled={!canOpen || undefined} className={`group relative flex min-h-[150px] min-w-0 items-start gap-5 rounded-card border border-line bg-surface p-5 pr-14 shadow-card ${canOpen ? 'cursor-pointer hover:border-clay/50 hover:bg-surface-hover' : 'opacity-60'}`} onClick={event => { if (!(event.target as Element).closest('button')) open() }}>
    <div data-project-icon className="flex h-[58px] w-[58px] shrink-0 items-center justify-center rounded-control bg-clay/10 text-clay"><Folder aria-hidden="true" size={30} weight="duotone" /></div>
    <div data-project-info className="min-w-0 flex-1">
      <Button variant="ghost" title={project.name} className="h-auto max-w-full min-w-0 justify-start p-0 text-left text-xl font-semibold text-ink hover:bg-transparent" disabled={!canOpen} onClick={open}><span className="min-w-0 truncate">{project.name}</span></Button>
      <p className="mb-0 mt-1.5 line-clamp-2 break-words text-sm leading-5 text-muted">{project.description || '暂无项目描述'}</p>
      <div className="mt-4 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
        {project.lifecycleState !== 'active' ? <span>{lifecycleLabel[project.lifecycleState] ?? project.lifecycleState}</span> : null}
        {residue ? <span className="inline-flex items-center gap-1 rounded-control border border-clay/40 bg-clay/10 px-2 py-0.5 font-medium text-clay"><WarningCircle aria-hidden="true" size={14} weight="fill" />清理未完成</span> : null}
        <span className="truncate">最近打开：{formatDate(project.lastOpenedAt)}</span>
      </div>
    </div>
    <div data-project-menu className="absolute right-3 top-3">
      <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" className="h-8 w-8 p-0" aria-label={`更多${project.name}操作`} onClick={event => event.stopPropagation()}><DotsThree aria-hidden="true" size={20} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end" onClick={event => event.stopPropagation()}><DropdownMenuItem disabled={disabled || project.lifecycleState !== 'active'} onSelect={() => onEdit(project)}><PencilSimple aria-hidden="true" className="mr-2" />编辑项目</DropdownMenuItem>{project.lifecycleState === 'active' ? <DropdownMenuItem disabled={disabled} onSelect={() => onLifecycle?.(project, 'archive')}><Archive aria-hidden="true" className="mr-2" />归档项目</DropdownMenuItem> : null}{project.lifecycleState === 'archived' ? <><DropdownMenuItem disabled={disabled} onSelect={() => onLifecycle?.(project, 'restore')}><ArrowCounterClockwise aria-hidden="true" className="mr-2" />恢复项目</DropdownMenuItem><DropdownMenuItem disabled={disabled} onSelect={() => onLifecycle?.(project, 'delete')}><Trash aria-hidden="true" className="mr-2" />永久删除</DropdownMenuItem></> : null}{residue ? <DropdownMenuItem disabled={disabled} onSelect={() => onLifecycle?.(project, 'delete')}><Trash aria-hidden="true" className="mr-2" />重试清理</DropdownMenuItem> : null}</DropdownMenuContent></DropdownMenu>
    </div>
  </article>
}
