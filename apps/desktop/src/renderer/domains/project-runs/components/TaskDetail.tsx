import { ListBullets } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../../shared/components/ui/tabs'
import { TableStatus } from '../../../shared/components/ui/table-status'
import { TaskEvidence } from './TaskEvidence'
import { TaskLog } from './TaskLog'

type Schema = components['schemas']
type Detail = Omit<Schema['TaskDetail'], 'task'> & { nodeNames?: Record<string, string>; task: Omit<Schema['TaskView'], 'taskOrdinal'> & { taskOrdinal?: number | null } }
type Attempt = Omit<Schema['NodeAttemptView'], 'nodeName'> & { nodeName?: string }
type Attempts = Omit<Schema['NodeAttemptPage'], 'items'> & { items: Attempt[] }; type Logs = Schema['RunLogPage']; type Outputs = Schema['RunOutputPage']; type Artifacts = Schema['RunArtifactPage']; type Artifact = Schema['RunArtifactView']
export type TaskDetailTab = 'logs' | 'io' | 'evidence'
export type TaskDetailProps = { detail: Detail; attempts?: Attempts; logs?: Logs; outputs?: Outputs; artifacts?: Artifacts; selectedTab: TaskDetailTab; selectedNode: string | null; level: string | null; query: string; loading?: boolean; error?: string; onTabChange(tab: TaskDetailTab): void; onNodeChange(value: string | null): void; onLevelChange(value: string | null): void; onQueryChange(value: string): void; onOpenArtifact?(artifact: Artifact): void; onLoadMoreArtifacts?(): void; onLoadMoreLogs(): void; onLoadMoreAttempts(): void; onLoadMoreOutputs(): void; onRetry(): void; onBack(): void }

const statuses: Record<string, string> = { queued: '排队中', running: '运行中', waiting_manual: '等待人工', resume_queued: '等待恢复', finishing: '正在结束', stopping: '正在停止', reconciling: '正在核对', succeeded: '成功', failed: '失败', cancelled: '已取消', timed_out: '已超时', interrupted: '已中断' }
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const taskNumber = (ordinal: number | null | undefined) => `T${String(ordinal ?? 1).padStart(4, '0')}`
function duration(start: string | null | undefined, end: string | null | undefined) {
  if (!start || !end) return end ? '—' : '进行中'
  const seconds = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60), rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`
}
function inputIdentifier(inputs: Record<string, unknown>[]) {
  if (!inputs.length) return '参数任务'
  const first = inputs[0]
  for (const key of ['inputIdentifier', 'identifier', 'recordIdentifier', 'identity', 'label', 'name']) {
    const value = first[key]
    if (typeof value === 'string' || typeof value === 'number') return String(value)
  }
  return inputs.length === 1 ? '项目数据输入' : `${inputs.length} 项项目数据输入`
}

export function TaskDetail({ detail, attempts, logs, outputs, artifacts, selectedTab, selectedNode, level, query, loading, error, onTabChange, onNodeChange, onLevelChange, onQueryChange, onOpenArtifact, onLoadMoreArtifacts, onLoadMoreLogs, onLoadMoreAttempts, onLoadMoreOutputs, onRetry, onBack }: TaskDetailProps) {
  const task = detail.task, startedAt = detail.run.startedAt, endedAt = detail.run.finishedAt ?? task.completedAt
  const tone = ['failed', 'timed_out', 'interrupted'].includes(task.status) ? 'danger' : task.status === 'succeeded' ? 'success' : ['waiting_manual', 'stopping'].includes(task.status) ? 'warning' : 'neutral'
  return <Tabs className="min-w-0" value={selectedTab} onValueChange={value => onTabChange(value as TaskDetailTab)}>
    <section className="grid min-w-0 gap-4">
      <header className="overflow-hidden rounded-card border border-line bg-surface">
        <div className="flex flex-wrap items-start gap-4 p-5">
          <Button variant="ghost" onClick={onBack}>← 返回批次</Button>
          <span className="grid size-14 shrink-0 place-items-center rounded-control border border-clay/10 bg-clay/5 text-clay"><ListBullets size={28}/></span>
          <div className="min-w-52 flex-1"><div className="flex flex-wrap items-center gap-3"><h2 className="m-0 text-2xl">任务 {taskNumber(task.taskOrdinal)}</h2><TableStatus tone={tone}>{statuses[task.status] ?? task.status}</TableStatus></div><dl className="mb-0 mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm"><div className="flex gap-2"><dt className="text-muted">自动化</dt><dd className="m-0">{detail.automationName || '自动化'}</dd></div><div className="flex gap-2"><dt className="text-muted">输入标识</dt><dd className="m-0">{inputIdentifier(detail.inputSnapshot.inputs)}</dd></div></dl></div>
          <dl className="m-0 grid min-w-[28rem] grid-cols-3 divide-x divide-line"><div className="px-4"><dt className="text-xs text-muted">开始时间</dt><dd className="m-0 mt-1">{startedAt ? <time dateTime={startedAt}>{time(startedAt)}</time> : '尚未开始'}</dd></div><div className="px-4"><dt className="text-xs text-muted">结束时间</dt><dd className="m-0 mt-1">{endedAt ? <time dateTime={endedAt}>{time(endedAt)}</time> : '—'}</dd></div><div className="px-4"><dt className="text-xs text-muted">耗时</dt><dd className="m-0 mt-1">{duration(startedAt, endedAt)}</dd></div></dl>
        </div>
        <TabsList className="w-full px-4"><TabsTrigger value="logs">日志</TabsTrigger><TabsTrigger value="io">输入与输出</TabsTrigger><TabsTrigger value="evidence">异常与证据</TabsTrigger></TabsList>
      </header>
      <TabsContent value="logs"><TaskLog attempts={attempts} logs={logs} nodeNames={detail.nodeNames} selectedNode={selectedNode} level={level} query={query} loading={loading} error={error} onNodeChange={onNodeChange} onLevelChange={onLevelChange} onQueryChange={onQueryChange} onLoadMore={onLoadMoreLogs} onLoadMoreAttempts={onLoadMoreAttempts} onRetry={onRetry}/></TabsContent>
      <TabsContent value="io"><TaskEvidence mode="io" detail={detail} outputs={outputs} loading={loading} error={error} onLoadMoreAttempts={onLoadMoreAttempts} onLoadMoreOutputs={onLoadMoreOutputs}/></TabsContent>
      <TabsContent value="evidence"><TaskEvidence mode="evidence" detail={detail} attempts={attempts} artifacts={artifacts} loading={loading} error={error} onOpenArtifact={onOpenArtifact} onLoadMoreArtifacts={onLoadMoreArtifacts} onLoadMoreAttempts={onLoadMoreAttempts} onLoadMoreOutputs={onLoadMoreOutputs}/></TabsContent>
    </section>
  </Tabs>
}
