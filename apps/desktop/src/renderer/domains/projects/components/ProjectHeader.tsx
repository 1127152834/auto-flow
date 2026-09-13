import { Folder, PencilSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import type { ProjectView } from '../types'

type HeaderDensity = 'default' | 'compact'

export function ProjectHeader({ project, density = 'default', disabled, onEdit }: { project: ProjectView; density?: HeaderDensity; disabled: boolean; onBack(): void; onEdit(): void }) {
  const titleClassName = 'm-0 break-all text-[28px] leading-tight font-bold text-ink'
  const title = <h1 className={titleClassName} title={project.name}>{project.name}</h1>
  return <header data-project-header-density={density} className="flex min-w-0 flex-wrap items-start justify-between gap-5">
    <div className="flex min-w-0 flex-1 items-start gap-5">
      <span data-testid="project-header-icon" className="grid h-20 w-20 shrink-0 place-items-center rounded-card border border-clay/10 bg-clay-soft text-clay" aria-hidden="true"><Folder size={34} weight="duotone" /></span>
      <div className="min-w-0"><div className="flex min-w-0 flex-wrap items-center gap-2">{title}{project.lifecycleState !== 'active' ? <span className="shrink-0 rounded-full bg-surface-subtle px-2 py-1 text-xs text-muted">{project.lifecycleState === 'archived' ? '已归档' : '处理中'}</span> : null}</div><p className="mb-0 mt-2 break-all text-base text-muted">{project.description || '暂无项目描述'}</p>{density === 'default' && project.updatedAt ? <p className="mb-0 mt-1 text-sm text-muted">最近修改：{new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(project.updatedAt))}</p> : null}</div>
    </div>
    {density === 'default' ? <Button variant="secondary" disabled={disabled || project.lifecycleState !== 'active'} onClick={onEdit}><PencilSimple />编辑项目</Button> : null}
  </header>
}
