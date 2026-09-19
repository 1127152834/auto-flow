import { ArrowLeft } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { Button } from '../../../shared/components/ui/button'
import { ActivityFeed } from '../components/ActivityFeed'
import { AttentionList } from '../components/AttentionList'
import { ContinueWork } from '../components/ContinueWork'
import { OverviewCounts } from '../components/OverviewCounts'
import { resourceKey, type ResourceLocator } from '../components/overview-resource'
import { ProjectCapabilityState } from '../components/ProjectCapabilityState'
import { ProjectHeader } from '../components/ProjectHeader'
import { ProjectTabs } from '../components/ProjectTabs'
import type { ProjectOverview, ProjectRoute, ProjectTab, ProjectView } from '../types'

const tabLabels: Record<ProjectTab, string> = {
  overview: '概览',
  automations: '自动化',
  runs: '运行记录',
  statistics: '统计',
  data: '数据',
  environments: '环境',
}

export function ProjectOverviewPage({
  project,
  tab,
  disabled,
  onBack,
  onTableBack,
  tableBackLabel = '返回数据表',
  onEdit,
  onTabChange,
  children,
  tableDetail = false,
  tableName,
  detailContext,
  overview,
  overviewError,
  onOpenResource,
}: {
  detailContext?: { name: string; onBack(): void; label: string }
  children?: ReactNode
  tableDetail?: boolean
  tableName?: string
  overview?: ProjectOverview | null
  overviewError?: string | null
  onOpenResource?(route: ProjectRoute): void
  project: ProjectView
  tab: ProjectTab
  disabled: boolean
  onBack(): void
  onTableBack?(): void
  tableBackLabel?: string
  onEdit(): void
  onTabChange(tab: ProjectTab): void
}) {
  return (
    <main className="mx-auto grid min-w-0 w-full max-w-7xl gap-4 px-6 py-6">
      <nav
        aria-label="当前位置"
        className="mb-2 flex min-w-0 items-center gap-3 border-b border-line pb-4 text-sm"
      >
        <Button
          size="sm"
          variant="ghost"
          className="shrink-0 px-0"
          aria-label={
            detailContext?.label ??
            (tableDetail && onTableBack ? tableBackLabel : '返回项目目录')
          }
          onClick={
            detailContext?.onBack ??
            (tableDetail && onTableBack ? onTableBack : onBack)
          }
        >
          <ArrowLeft size={20} />
        </Button>
        <span className="min-w-0 break-words">
          {tableDetail && onTableBack ? (
            <button
              type="button"
              className="text-inherit hover:text-clay"
              aria-label="返回项目目录"
              onClick={onBack}
            >
              项目
            </button>
          ) : (
            '项目'
          )}{' '}
          / {project.name} / {tabLabels[tab]}
          {detailContext
            ? ` / ${detailContext.name}`
            : tableDetail && tableName
              ? ` / ${tableName}`
              : ''}
        </span>
      </nav>

      <ProjectHeader
        density={tableDetail || detailContext ? 'compact' : 'default'}
        project={project}
        disabled={disabled}
        onBack={onBack}
        onEdit={onEdit}
      />
      <ProjectTabs value={tab} onChange={onTabChange} />

      {tab === 'overview' ? (
        <section aria-label="项目概览" className="grid gap-4">
          {overviewError ? <p role="status" className="m-0 rounded-control border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-ink">概览刷新失败：{overviewError}。{overview ? '以下是上次加载的结果。' : '暂无可显示的上次结果，其他页签仍可使用。'}</p> : null}
          {overview ? <OverviewCounts counts={overview.counts} dataChanges={overview.dataChanges} /> : null}
          {overview ? (
            <div className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
              <ActivityFeed current={overview.current} items={overview.recent} onOpen={route => onOpenResource?.(route)} />
              <div className="grid min-w-0 content-start gap-4">
                <AttentionList items={overview.activity} onOpen={route => onOpenResource?.(route)} />
                <ContinueWork items={resumable(overview)} onOpen={route => onOpenResource?.(route)} />
              </div>
            </div>
          ) : (
          <div className="rounded-card border border-line bg-surface p-6">
            <h2 className="m-0 text-lg font-semibold">项目资料</h2>
            <dl className="mt-5 grid gap-x-8 gap-y-5 sm:grid-cols-2">
              <Info label="名称" value={project.name} />
              <Info label="描述" value={project.description || '暂无描述'} />
              <Info
                label="状态"
                value={
                  project.lifecycleState === 'active'
                    ? '活动'
                    : project.lifecycleState === 'archived'
                      ? '已归档'
                      : '处理中'
                }
              />
              <Info label="创建时间" value={formatDate(project.createdAt)} />
              <Info label="修改时间" value={formatDate(project.updatedAt)} />
              <Info
                label="最近访问"
                value={project.lastOpenedAt ? formatDate(project.lastOpenedAt) : '从未访问'}
              />
            </dl>
          </div>
          )}
        </section>
      ) : (
        children ?? <ProjectCapabilityState tab={tab} />
      )}
    </main>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs font-medium text-muted">{label}</dt>
      <dd className="m-0 mt-1 text-sm text-ink">{value}</dd>
    </div>
  )
}

/** Anything already listed under 需要关注 stays there, so the two panels never repeat one object. */
function resumable(overview: ProjectOverview) {
  const flagged = new Set(overview.activity.map(item => resourceKey(item.resource as ResourceLocator)))
  return overview.recent.filter(item => !flagged.has(resourceKey(item.resource as ResourceLocator)))
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'long',
    timeStyle: 'short',
  }).format(new Date(value))
}
