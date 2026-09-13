import { ArrowLeft, PencilSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import type { ProjectView } from '../types'

type HeaderDensity = 'default' | 'compact'

export function ProjectHeader({ project, density = 'default', disabled, onBack, onEdit }: { project: ProjectView; density?: HeaderDensity; disabled: boolean; onBack(): void; onEdit(): void }) {
  const title = density === 'compact' ? <p className="m-0 truncate text-base font-semibold text-ink" title={project.name}>{project.name}</p> : <h1 className="m-0 truncate text-2xl font-semibold text-ink" title={project.name}>{project.name}</h1>
  return <header data-project-header-density={density} className={`flex min-w-0 flex-wrap items-start justify-between gap-3 border-b border-line ${density === 'compact' ? 'pb-3' : 'pb-5'}`}>
    <div className="flex min-w-0 flex-1 gap-3"><Button variant="ghost" className="h-9 w-9 shrink-0 p-0" aria-label="返回项目目录" onClick={onBack}><ArrowLeft /></Button><div className="min-w-0"><div className="flex min-w-0 items-center gap-2">{title}{project.lifecycleState !== 'active' ? <span className="shrink-0 rounded-full bg-surface-subtle px-2 py-1 text-xs text-muted">{project.lifecycleState === 'archived' ? '已归档' : '处理中'}</span> : null}</div>{density === 'default' ? <p className="mb-0 mt-1 break-all text-sm text-muted">{project.description || '暂无项目描述'}</p> : null}</div></div>
    <Button variant="ghost" disabled={disabled || project.lifecycleState !== 'active'} onClick={onEdit}><PencilSimple />编辑项目</Button>
  </header>
}
