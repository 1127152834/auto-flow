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
const issueText = (value: string) => {
  const exact: Record<string, string> = {
    'Selected field no longer exists.': '所选字段已不存在，请重新检查输入配置。',
    'input mode is invalid': '输入模式无效，请重新配置。',
    'table identity is invalid': '数据表身份无效，请重新选择数据表。',
    'table generation is no longer current': '数据表已更新，请重新选择当前数据。',
    'fixed record reference is invalid': '固定记录引用无效，请重新选择。',
    'fixed record reference is outside this input': '固定记录不属于当前输入的数据表。',
    'related input has no relation': '关联输入缺少关联条件。',
    'relation source is invalid': '关联来源输入无效。',
    'same-record relation uses another table generation': '同一记录关联必须使用同一数据表版本。',
    'record slot relation is invalid': '记录槽关联已失效。',
    'field relation reference is invalid': '字段关联引用已失效。',
    'field relation types are incompatible': '关联字段类型不一致。',
    'relation type is invalid': '关联方式无效。',
    'record slot value is invalid': '记录槽保存的数据引用无效。',
    'record scan budget exceeded': '候选记录仍有后续页面。',
    'candidate binding budget exceeded': '候选组合检查预算已用完。',
    'candidate scan has a continuation': '候选记录仍有后续页面。',
  }
  if (exact[value]) return exact[value]
  if (value.startsWith('ambiguous value ') && value.includes('; records ')) {
    const [condition, records] = value.slice('ambiguous value '.length).split('; records ', 2)
    return `关联值 ${condition} 同时匹配记录 ${records}，请先清理重复数据。`
  }
  return /[\u3400-\u9fff]/u.test(value) ? value : '输入配置引用的内容已变化，请重新检查。'
}
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
    ['任务数', value.maxTasks === null ? '不限次数' : value.maxTasks],
    ['并发数', value.concurrency],
    ['失败策略', record(automation.runPolicy).continueAfterFailure === true ? '失败后继续领取' : record(automation.runPolicy).continueAfterFailure === false ? (Array.isArray(record(automation.inputPlan).inputs) && (record(automation.inputPlan).inputs as unknown[]).length === 0 ? '首次确认失败后停止执行后续排队任务' : '首次确认失败后停止领取新任务') : '—'],
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
  const selectionStatus = typeof batch.selectionOutcome?.status === 'string' ? batch.selectionOutcome.status : undefined
  const selectionCategory = typeof batch.selectionOutcome?.category === 'string' ? batch.selectionOutcome.category : undefined
  const hasContinuation = batch.selectionOutcome?.hasContinuation === true
  const configuration = record((detail as Detail & { configurationSnapshot?: JsonRecord }).configurationSnapshot)
  const frozenInputs = Array.isArray(record(record(configuration.automation).inputPlan).inputs) ? (record(record(configuration.automation).inputPlan).inputs as unknown[]).map(record) : []
  const issueIds = Array.isArray(batch.selectionOutcome?.issueInputIds) ? batch.selectionOutcome.issueInputIds.filter((value): value is string => typeof value === 'string') : []
  const issueAliases = issueIds.map(id => String(frozenInputs.find(input => input.inputId === id)?.alias ?? '数据输入')).join('、')
  const issueDetails = record(batch.selectionOutcome?.issueDetails)
  const issueDescriptions = issueIds.map(id => {
    const alias = String(frozenInputs.find(input => input.inputId === id)?.alias ?? '数据输入')
    const explanation = issueDetails[id]
    return typeof explanation === 'string' && explanation.trim() ? `${alias}：${issueText(explanation)}` : alias
  }).join('；')
  const selectionIssue = issueDescriptions || issueAliases
  const scanBudgetMessage = selectionCategory === 'candidatePage' && hasContinuation
    ? '正在继续检查下一页候选数据；尚未确认数据耗尽。'
    : selectionCategory === 'candidateBindingBudget'
      ? '候选组合检查预算已用完；请收紧筛选或关联条件后重试。尚未确认数据耗尽。'
      : '候选数据检查尚未得出结论；尚未确认数据耗尽。'
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
        <div><dt className="text-sm text-muted">结束原因</dt><dd className="m-0 mt-1">{batch.status === 'completed' && selectionStatus === 'noMatch' ? '当前没有符合条件的数据' : batch.status === 'completed' && selectionStatus === 'limitReached' ? '已达到本次任务数' : batch.status === 'failed' && selectionStatus === 'configurationError' ? `数据输入配置已失效${selectionIssue ? `：${selectionIssue}` : ''}` : batch.status === 'failed' && selectionStatus === 'ambiguous' ? `数据关联存在歧义${selectionIssue ? `：${selectionIssue}` : ''}` : endReasons[batch.status] ?? '尚未结束'}</dd></div>
      </dl>
      <div className="m-5 flex flex-wrap items-center gap-x-5 gap-y-2 rounded-control border border-line px-4 py-3"><Stack className="text-muted" size={24}/><strong>本批次 {detail.taskCount} 个任务</strong><span className="text-success">成功 {statusCounts.succeeded ?? 0}</span><span className={failures ? 'text-danger' : ''}>失败或异常 {failures}</span><span>进行中 {batch.activeTaskCount}</span>{failures ? <span role="alert" className="ml-auto inline-flex items-center gap-2 rounded-control border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-warning"><WarningCircle size={20} weight="fill"/> {failures} 个任务失败或异常，可进入任务查看日志；批次结束不代表全部成功。</span> : null}</div>
      {(detail.reusedInputGroupCount ?? 0) > 0 || (detail.unchangedInputStreak ?? 0) > 0 ? <p className="mx-5 rounded-control border border-line bg-surface-subtle px-3 py-2 text-sm">已重复使用相同输入组 {detail.reusedInputGroupCount ?? 0} 次；当前输入条件连续 {detail.unchangedInputStreak ?? 0} 次未变化。计数仅用于解释运行事实，不限制继续领取。</p> : null}
      {batch.status === 'blocked' ? <p role="status" className="mx-5 text-sm text-muted">{selectionStatus === 'scanBudgetExceeded' ? scanBudgetMessage : selectionStatus === 'temporarilyBusy' ? '符合条件的数据正在被其他任务使用，释放后将继续领取。' : '正在等待可用资源或数据；尚未确认数据耗尽。'}</p> : null}
      {batch.status === 'draining' ? <p role="status" className="mx-5 text-sm text-muted">{selectionStatus === 'configurationError' ? `数据输入配置已失效${selectionIssue ? `（${selectionIssue}）` : ''}；已停止领取，等待已领取任务结束。` : selectionStatus === 'ambiguous' ? `数据关联存在歧义${selectionIssue ? `（${selectionIssue}）` : ''}；已停止领取，等待已领取任务结束。` : '已停止领取新任务，等待已领取任务结束。'}</p> : null}
      {showConfiguration ? <BatchConfigurationSnapshot value={configuration}/> : null}
    </section>
  </section>
}
