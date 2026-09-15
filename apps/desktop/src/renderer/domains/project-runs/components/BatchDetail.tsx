import { Stack, WarningCircle } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { BatchStatus, type BatchStatusValue } from './BatchStatus'

type Detail = components['schemas']['BatchDetail']
type JsonRecord = Record<string, unknown>
export type BatchDetailProps = { detail: Detail; automationName?: string; onBack(): void; onStop?: () => void; onForceStop?: () => void; stopping?: boolean; showConfiguration?: boolean }

const terminal = new Set(['completed', 'failed', 'stopped', 'interrupted'])
const endReasons: Record<string, string> = { completed: '本批次任务已结束', stopped: '批次已按停止请求结束', failed: '批次运行失败', interrupted: '批次运行被中断' }
const environmentLabels: Record<string, string> = { newFromProfile: '按浏览器配置新建环境', fixedEnvironment: '使用固定环境', inputEnvironment: '随项目数据输入选择环境' }
const record = (value: unknown): JsonRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {}
const scalar = (value: unknown) => value === null ? '未指定' : typeof value === 'boolean' ? value ? '是' : '否' : typeof value === 'string' || typeof value === 'number' ? String(value) : Array.isArray(value) ? `${value.length} 项` : value && typeof value === 'object' ? `已冻结（${Object.keys(value).length} 项）` : '—'
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
function duration(start: string | null | undefined, end: string | null | undefined) {
  if (!start || !end) return end ? '—' : '进行中'
  const seconds = Math.max(0, Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60), rest = seconds % 60
  return rest ? `${minutes} 分 ${rest} 秒` : `${minutes} 分钟`
}

export function BatchConfigurationSnapshot({ value }: { value: JsonRecord }) {
  const automation = record(value.automation), parameters = record(value.parameters)
  const definitions = Array.isArray(automation.parameterSchema) ? automation.parameterSchema.map(record) : []
  const names = new Map(definitions.map(item => [String(item.parameterId ?? ''), String(item.name ?? '参数')]))
  const execution = [
    ['自动化', automation.name ?? '自动化'],
    ['自动化版本', typeof automation.managementRevision === 'number' ? `第 ${automation.managementRevision} 版` : '—'],
    ['工作流版本', typeof value.workflowRevision === 'number' ? `第 ${value.workflowRevision} 版` : '—'],
    ['任务数', value.maxTasks],
    ['并发数', value.concurrency],
  ] as const
  const environment = record(automation.environmentPolicy), resources = record(value.resourceRequest)
  const resourceRows = [
    ['环境策略', environmentLabels[String(environment.source ?? '')] ?? '已冻结环境策略'],
    ['浏览器资源', resources.browser === 'none' ? '无需浏览器' : resources.browser ? '已冻结浏览器资源' : '未指定'],
    ['模型资源', resources.modelProviderId ? '已冻结模型资源' : '未指定'],
  ] as const
  return <details className="border-t border-line px-5 py-4">
    <summary className="cursor-pointer font-semibold">本次运行的配置快照 <span className="ml-2 text-sm font-normal text-muted">只读 · 不随自动化配置变化</span></summary>
    <div className="mt-4 grid gap-4 lg:grid-cols-2">
      <section><h4 className="mb-2 mt-0">执行设置</h4><TableScroll label="运行配置执行设置" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{execution.map(([label, item]) => <TableRow key={label}><TableHead scope="row" className="w-36">{label}</TableHead><TableCell>{scalar(item)}</TableCell></TableRow>)}</TableBody></Table></TableScroll></section>
      <section><h4 className="mb-2 mt-0">资源设置</h4><TableScroll label="运行配置资源设置" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{resourceRows.map(([label, item]) => <TableRow key={label}><TableHead scope="row" className="w-36">{label}</TableHead><TableCell>{item}</TableCell></TableRow>)}</TableBody></Table></TableScroll></section>
      <section className="lg:col-span-2"><h4 className="mb-2 mt-0">固定参数</h4>{Object.keys(parameters).length ? <TableScroll label="运行配置固定参数" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{Object.entries(parameters).map(([id, item]) => <TableRow key={id}><TableHead scope="row" className="w-1/3">{names.get(id) ?? '参数'}</TableHead><TableCell className="whitespace-pre-wrap break-words">{scalar(item)}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-sm text-muted">本批次没有固定参数。</p>}</section>
    </div>
  </details>
}

export function BatchDetail({ detail, automationName, onBack, onStop, onForceStop, stopping = false, showConfiguration = true }: BatchDetailProps) {
  const { batch, statusCounts } = detail, ended = terminal.has(batch.status)
  const configuration = record((detail as Detail & { configurationSnapshot?: JsonRecord }).configurationSnapshot)
  const frozenAutomationName = (batch as typeof batch & { automationName?: string | null }).automationName
  const failures = (statusCounts.failed ?? 0) + (statusCounts.timed_out ?? 0) + (statusCounts.interrupted ?? 0) + (statusCounts.cancelled ?? 0)
  const batchName = frozenAutomationName || automationName || '自动化'
  return <section className="grid min-w-0 gap-4">
    <Button variant="ghost" className="w-fit" onClick={onBack}>← 返回批次列表</Button>
    <section className="overflow-hidden rounded-card border border-line bg-surface">
      <header className="flex flex-wrap items-start gap-4 p-5">
        <span className="grid size-14 shrink-0 place-items-center rounded-control border border-clay/10 bg-clay/5 text-clay"><Stack size={28}/></span>
        <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-3"><h2 className="m-0 text-2xl">{batchName}</h2><BatchStatus status={batch.status as BatchStatusValue}/></div><p className="mb-0 mt-1 text-sm text-muted">批次开始于 {time(batch.createdAt)}</p></div>
        {!ended && onStop ? <Button disabled={stopping} onClick={onStop}>停止批次</Button> : null}
        {!ended && onForceStop ? <Button variant="danger" disabled={stopping} onClick={onForceStop}>强制停止</Button> : null}
      </header>
      <dl className="m-0 grid border-y border-line sm:grid-cols-2 xl:grid-cols-4 [&>div]:px-5 [&>div]:py-4 [&>div+div]:border-l [&>div+div]:border-line">
        <div><dt className="text-sm text-muted">开始</dt><dd className="m-0 mt-1"><time dateTime={batch.createdAt}>{time(batch.createdAt)}</time></dd></div>
        <div><dt className="text-sm text-muted">结束</dt><dd className="m-0 mt-1">{batch.completedAt ? <time dateTime={batch.completedAt}>{time(batch.completedAt)}</time> : '—'}</dd></div>
        <div><dt className="text-sm text-muted">耗时</dt><dd className="m-0 mt-1">{duration(batch.createdAt, batch.completedAt)}</dd></div>
        <div><dt className="text-sm text-muted">结束原因</dt><dd className="m-0 mt-1">{endReasons[batch.status] ?? '尚未结束'}</dd></div>
      </dl>
      <div className="m-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-control border border-line px-4 py-3"><Stack className="text-muted" size={24}/><strong>本批次 {detail.taskCount} 个任务</strong><span className="text-success">成功 {statusCounts.succeeded ?? 0}</span><span className={failures ? 'text-danger' : ''}>失败或异常 {failures}</span><span>进行中 {batch.activeTaskCount}</span>{failures ? <span role="alert" className="ml-auto inline-flex items-center gap-2 rounded-control border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"><WarningCircle size={20} weight="fill"/> {failures} 个任务失败或异常，可进入任务查看日志；批次结束不代表全部成功。</span> : null}</div>
      {showConfiguration ? <BatchConfigurationSnapshot value={configuration}/> : null}
    </section>
  </section>
}
