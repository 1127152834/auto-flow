import { ArrowLeft, PencilSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import type { ProjectView } from '../types'

export function ProjectHeader({ project, disabled, onBack, onEdit }: { project: ProjectView; disabled: boolean; onBack(): void; onEdit(): void }) {
  return <header className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
    <div className="flex min-w-0 gap-3"><Button variant="ghost" className="h-9 w-9 shrink-0 p-0" aria-label="返回项目目录" onClick={onBack}><ArrowLeft /></Button><div className="min-w-0"><div className="flex items-center gap-2"><h1 className="m-0 truncate text-2xl font-semibold text-ink">{project.name}</h1>{project.lifecycleState !== 'active' ? <span className="rounded-full bg-surface-subtle px-2 py-1 text-xs text-muted">{project.lifecycleState === 'archived' ? '已归档' : '处理中'}</span> : null}</div><p className="mb-0 mt-1 text-sm text-muted">{project.description || '暂无项目描述'}</p></div></div>
    <Button variant="ghost" disabled={disabled || project.lifecycleState !== 'active'} onClick={onEdit}><PencilSimple />编辑项目</Button>
  </header>
}
