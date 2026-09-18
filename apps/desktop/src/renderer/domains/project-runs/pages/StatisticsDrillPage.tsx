import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import type { StreamingApiClient } from '../../../shared/api/client'
import { Skeleton } from '../../../shared/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { createAutomationApi } from '../../project-automations/api'
import { createProjectStatisticsApi } from '../../projects/statistics-api'
import type { RunFrozen } from '../../projects/types'
import { TaskDirectory } from '../components/TaskDirectory'

const resultLabels: Record<RunFrozen['result'], string> = {
  succeeded: '成功',
  failed: '失败',
  cancelled: '已取消',
  timed_out: '已超时',
  interrupted: '已中断',
}
const momentLabel = new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
const zone = () => Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
const emptyFilters = { q: null, batchId: null, status: null, period: null }

/**
 * 统计下钻：冻结结果集是独立页面（原型 04-statistics/007），不是统计页里的内联卡片。
 * 集合身份来自地址，页面只读；离开后统计页仍保留自己的范围与快照。
 */
export function StatisticsDrillPage({ workspaceKey, instanceId, projectId, client, disabled, frozen, onNavigate }: {
  workspaceKey: string
  instanceId: string
  projectId: string
  client: StreamingApiClient
  disabled: boolean
  frozen: RunFrozen
  onNavigate(route: { tab: 'runs'; runView?: 'batches' | 'tasks' | 'manual'; taskId?: string; taskTab?: 'logs' | 'io' | 'evidence' }): void
}) {
  const statistics = useMemo(() => createProjectStatisticsApi(client, projectId), [client, projectId])
  const automations = useMemo(() => createAutomationApi(client, projectId), [client, projectId])
  const timezone = useMemo(zone, [])
  const [page, setPage] = useState(1)
  const tasks = useQuery({
    queryKey: [workspaceKey, instanceId, 'project-statistics-tasks', projectId, frozen, page],
    queryFn: ({ signal }) => statistics.tasks(frozen.resultSetId, { result: frozen.result, ...(frozen.intervalStart ? { intervalStart: frozen.intervalStart } : {}), page, pageSize: 50 }, signal),
    enabled: !disabled,
  })
  // 只为了把自动化标识显示成名称；读不到名称时退回标识本身，不隐藏筛选事实。
  const names = useQuery({
    queryKey: [workspaceKey, instanceId, 'project-statistics-automations', projectId],
    enabled: Boolean(frozen.automationId) && !disabled,
    queryFn: async ({ signal }) => {
      const result: { id: string; name: string }[] = []
      for (let index = 1; ; index++) {
        const data = await automations.list({ page: index, pageSize: 200, sort: 'name', query: '' }, signal)
        result.push(...data.items.map(item => ({ id: item.automationId, name: item.name })))
        if (index * 200 >= data.total || data.items.length === 0) return result
      }
    },
  })
  const automationName = frozen.automationId ? (names.data ?? []).find(item => item.id === frozen.automationId)?.name ?? frozen.automationId : null
  const resultLabel = resultLabels[frozen.result]
  const total = tasks.data?.total
  return <section aria-label="失败任务记录" className="grid min-w-0 gap-4">
    <Tabs value="tasks" onValueChange={value => onNavigate({ tab: 'runs', runView: value as 'batches' | 'tasks' | 'manual' })}>
      <div className="flex flex-wrap items-center gap-3 border-b border-line">
        <TabsList className="border-0">
          <TabsTrigger value="batches">批次</TabsTrigger>
          <TabsTrigger value="tasks">任务</TabsTrigger>
          <TabsTrigger value="manual">等待人工</TabsTrigger>
        </TabsList>
      </div>
    </Tabs>
    <header className="grid gap-2">
      <h2 className="m-0 flex flex-wrap items-baseline gap-2 text-xl font-semibold text-ink">任务记录<span className="text-sm font-normal text-muted">来自统计 · {resultLabel}任务</span></h2>
      <ul aria-label="冻结筛选" className="m-0 flex list-none flex-wrap items-center gap-2 p-0 text-sm">
        {automationName ? <li className="rounded-control border border-clay/30 bg-clay-soft px-3 py-1"><span className="text-muted">自动化：</span>{automationName}</li> : null}
        <li className="rounded-control border border-clay/30 bg-clay-soft px-3 py-1"><span className="text-muted">状态：</span>{resultLabel}</li>
      </ul>
      <p className="m-0 text-sm text-muted">按任务结束时间{frozen.intervalStart ? ` · ${momentLabel.format(new Date(frozen.intervalStart))}` : ''} · {timezone}</p>
      <p role="status" className="m-0 flex items-center gap-2 rounded-control border border-line bg-surface-subtle px-3 py-2 text-sm text-muted">统计快照 · 不自动刷新；与统计中的{resultLabel}任务数一致。</p>
    </header>
    {disabled && !tasks.data ? <p role="status" className="m-0 text-sm text-muted">本地服务暂不可用，冻结结果集会在连接恢复后重新读取。</p> : null}
    {tasks.isLoading && !tasks.data ? <Skeleton className="h-40 w-full"/> : null}
    {tasks.data || tasks.isError ? <TaskDirectory
      context="frozen"
      page={tasks.data}
      filters={emptyFilters}
      loading={tasks.isLoading}
      refreshing={disabled || tasks.isFetching}
      error={tasks.isError ? tasks.error : disabled ? '本地服务暂不可用，请等待连接恢复' : undefined}
      footerNote={<div className="flex flex-wrap items-center gap-3 text-sm text-muted">
        <span>共 {total ?? tasks.data?.items.length ?? 0} 条符合条件的任务</span>
        <span className="text-xs">任务记录只读。</span>
        <span className="flex items-center gap-2 text-xs">与统计中的{resultLabel}任务 {total ?? 0} 个一致；返回后保留统计范围与快照。</span>
      </div>}
      onFiltersChange={() => undefined}
      onPageChange={setPage}
      onOpen={task => onNavigate({ tab: 'runs', taskId: task.taskId, taskTab: 'logs' })}
      onRetry={() => void tasks.refetch()}
    /> : null}
  </section>
}
