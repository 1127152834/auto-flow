import { Folder, PencilSimple } from '@phosphor-icons/react'
import { Button } from '../../../shared/components/ui/button'
import type { ProjectView } from '../types'

type HeaderDensity = 'default' | 'compact'

export function ProjectHeader({ project, density = 'default', disabled, onEdit }: { project: ProjectView; density?: HeaderDensity; disabled: boolean; onBack(): void; onEdit(): void }) {
  const compact = density === 'compact'
  const titleClassName = `m-0 break-all leading-tight font-bold text-ink ${compact ? 'text-[22px]' : 'text-[28px]'}`
  const title = <h1 className={titleClassName} title={project.name}>{project.name}</h1>
  return <header data-project-header-density={density} className={`flex min-w-0 flex-wrap items-start justify-between ${compact ? 'gap-3' : 'gap-5'}`}>
    {project.lifecycleState !== 'active' ? <p role="status" className="order-first m-0 w-full rounded-control border border-line bg-surface-subtle px-3 py-2 text-sm text-muted">{project.lifecycleState === 'archived' ? '项目已归档，仅可查看与导出' : project.lifecycleState === 'closing' ? '项目正在收尾，新操作已停止' : '项目正在删除'}</p> : null}
    <div className={`flex min-w-0 flex-1 items-start ${compact ? 'gap-3' : 'gap-5'}`}>
      <span data-testid="project-header-icon" className={`grid shrink-0 place-items-center rounded-card border border-clay/10 bg-clay-soft text-clay ${compact ? 'size-12' : 'h-20 w-20'}`} aria-hidden="true"><Folder size={compact ? 24 : 34} weight="duotone" /></span>
      <div className="min-w-0"><div className="flex min-w-0 flex-wrap items-center gap-2">{title}{project.lifecycleState !== 'active' ? <span className="shrink-0 rounded-control bg-surface-subtle px-2 py-1 text-xs text-muted">{project.lifecycleState === 'archived' ? '已归档' : '处理中'}</span> : null}</div><p className={`mb-0 break-all text-muted ${compact ? 'mt-1 text-sm' : 'mt-2 text-base'}`}>{project.description || '暂无项目描述'}</p>{density === 'default' && project.updatedAt ? <p className="mb-0 mt-1 text-sm text-muted">最近修改：{new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(project.updatedAt))}</p> : null}</div>
    </div>
    {density === 'default' ? <Button variant="secondary" disabled={disabled || project.lifecycleState !== 'active'} onClick={onEdit}><PencilSimple />编辑项目</Button> : null}
  </header>
}
