import type { ReactNode } from 'react'
import { ProjectCapabilityState } from '../components/ProjectCapabilityState'
import { ProjectHeader } from '../components/ProjectHeader'
import { ProjectTabs } from '../components/ProjectTabs'
import type { ProjectTab, ProjectView } from '../types'
export function ProjectOverviewPage({ project, tab, disabled, onBack, onEdit, onTabChange, children }: { children?: ReactNode; project: ProjectView; tab: ProjectTab; disabled: boolean; onBack(): void; onEdit(): void; onTabChange(tab: ProjectTab): void }) {
  return <main className={`mx-auto grid min-w-0 w-full max-w-7xl px-6 ${tab === 'data' ? 'gap-2 py-3' : 'gap-3 py-6'}`}><ProjectHeader density={tab === 'data' ? 'compact' : 'default'} project={project} disabled={disabled} onBack={onBack} onEdit={onEdit} /><ProjectTabs value={tab} onChange={onTabChange} />{tab === 'overview' ? <section aria-label="项目概览" className="grid gap-4"><div className="rounded-card border border-line bg-surface p-6"><h2 className="m-0 text-lg font-semibold">项目资料</h2><dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2"><Info label="名称" value={project.name} /><Info label="描述" value={project.description || '暂无描述'} /><Info label="状态" value={project.lifecycleState === 'active' ? '活动' : project.lifecycleState === 'archived' ? '已归档' : '处理中'} /><Info label="创建时间" value={formatDate(project.createdAt)} /><Info label="修改时间" value={formatDate(project.updatedAt)} /><Info label="最近访问" value={project.lastOpenedAt ? formatDate(project.lastOpenedAt) : '从未访问'} /></dl></div></section> : children ?? <ProjectCapabilityState tab={tab} />}</main>
}
function Info({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs font-medium text-muted">{label}</dt><dd className="m-0 mt-1 text-sm text-ink">{value}</dd></div> }
function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'long', timeStyle: 'short' }).format(new Date(value)) }
