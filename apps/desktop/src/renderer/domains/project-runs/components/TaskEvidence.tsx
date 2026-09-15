import { WarningCircle } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { presentRunFailure } from '../presentation'
import { DataInputPreview, type DataInputPreviewItem } from './DataInputPreview'
import { TaskDataWrites, type TaskDataWrite } from './TaskDataWrites'

type Schema = components['schemas']
type Detail = Schema['TaskDetail']; type Attempts = Schema['NodeAttemptPage']; type Outputs = Schema['RunOutputPage']; type Artifact = Schema['RunArtifactView']; type Artifacts = Schema['RunArtifactPage']
type JsonRecord = Record<string, unknown>
const record = (value: unknown): JsonRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {}
const show = (value: unknown): string => {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    const item = value as JsonRecord
    if (item.executor === 'fake' && item.browser === 'notExecuted' && item.studio === 'notExecuted') return '隔离测试执行器 · 未调用浏览器 · 未调用 Studio'
  }
  return value === null ? 'null' : typeof value === 'boolean' ? String(value) : typeof value === 'string' || typeof value === 'number' ? String(value) : Array.isArray(value) ? value.map(show).join('、') || '空列表' : value && typeof value === 'object' ? Object.entries(value).map(([key, item]) => `${key}：${show(item)}`).join('；') || '空对象' : '—'
}
const statuses: Record<string, string> = { running: '运行中', succeeded: '成功', failed: '失败' }
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const artifactReasons: Record<string, string> = { SCREENSHOT_CAPTURE_FAILED: '截图捕获失败', SCREENSHOT_PAGE_UNAVAILABLE: '页面已不可用', LEGACY_ARTIFACT_UNAVAILABLE: '旧版证据不可用' }
const size = (value: number | null | undefined) => value === null || value === undefined ? '—' : value < 1024 ? `${value} B` : `${Math.round(value / 1024)} KB`
const taskNumber = (ordinal: number) => String(ordinal)
const nodeName = (detail: Detail, nodeId: string | null | undefined, frozen?: string) => nodeId && detail.nodeNames?.[nodeId]?.trim() || frozen?.trim() || '未命名节点'
const errorLabels: Record<string, string> = {
  E_PAGE_TIMEOUT: '读取页面超时',
  ELEMENT_NOT_FOUND: '未找到页面元素',
  CLICK_TARGET_NOT_FOUND: '未找到点击目标',
  NODE_FAILED: '节点执行失败',
  WORKFLOW_NODE_FAILED: '节点执行失败',
  AUTOMATIC_EXECUTION_TIMEOUT: '执行超时',
  EXECUTION_INTERRUPTED: '执行被中断',
  BROWSER_ACTION_FAILED: '浏览器操作失败',
}
const errorLabel = (value: unknown) => {
  const code = typeof record(value).code === 'string' ? String(record(value).code) : ''
  return errorLabels[code] ?? '运行失败'
}

function projectInputs(detail: Detail): DataInputPreviewItem[] {
  return detail.inputSnapshot.inputs.map((input, index) => {
    const item = record(input)
    const ref = record(item.recordRef)
    const key = record(ref.recordKey)
    const keyType = typeof key.type === 'string' ? key.type : '记录'
    const keyValue = typeof key.value === 'string' || typeof key.value === 'number' ? String(key.value) : null
    const values = Array.isArray(item.values) ? item.values.flatMap(value => {
      const field = record(value)
      if (typeof field.fieldName !== 'string') return []
      return [{ label: field.fieldName, value: show(field.value) }]
    }) : []
    const businessDisplay = values.slice(0, 2).map(value => value.value).filter(value => value && value !== '—').join(' · ')
    const unavailableReason = item.unavailableReason
    const outcome: DataInputPreviewItem['outcome'] = unavailableReason === 'busy'
      ? 'temporarilyBusy'
      : unavailableReason === 'no_match'
        ? 'noMatch'
        : 'ready'
    return {
      alias: typeof item.alias === 'string' && item.alias.trim() ? item.alias : `数据输入 ${index + 1}`,
      tableDisplay: typeof item.tableDisplay === 'string' ? item.tableDisplay : '项目数据表',
      recordDisplay: businessDisplay || (keyValue ? `${keyType} · ${keyValue}` : null),
      values,
      outcome,
      required: typeof item.required === 'boolean' ? item.required : unavailableReason ? false : true,
      detail: unavailableReason === 'busy' ? '任务创建时该可选记录暂时被其他任务占用' : unavailableReason === 'no_match' ? '任务创建时没有符合条件的可选记录' : undefined,
    }
  })
}

function projectWrites(detail: Detail): TaskDataWrite[] {
  const result: TaskDataWrite[] = []
  for (const write of detail.dataWrites ?? []) {
    const outcome: TaskDataWrite['outcome'] = write.outcome === 'conflict' || write.outcome === 'unknown' ? write.outcome : 'succeeded'
    const base = {
      tableDisplay: write.tableDisplay,
      recordDisplay: write.recordDisplay,
      outcome,
      referenceDisplay: write.referenceDisplay,
      beforeSummary: write.beforeSummary,
      afterSummary: write.afterSummary,
      detail: write.detail,
    }
    if (write.kind === 'statusChange') result.push({ ...base, kind: 'statusChange', previousStatus: write.previousStatus ?? null, nextStatus: write.nextStatus ?? null })
    else result.push({ ...base, kind: write.kind })
  }
  return result
}

type TaskEvidenceProps = {
  mode: 'io' | 'evidence'
  detail: Detail
  attempts?: Attempts
  outputs?: Outputs
  artifacts?: Artifacts
  inlineScreenshotUrl?: string
  inlineScreenshotLabel?: string
  loading?: boolean
  error?: string
  onOpenArtifact?(artifact: Artifact): void
  onLocateLog?(nodeId: string | null): void
  onLoadMoreArtifacts?(): void
  onLoadMoreAttempts(): void
  onLoadMoreOutputs(): void
}

function OutputTable({ items, label }: { items: Outputs['items']; label: string }) {
  return <TableScroll label={label} className="rounded-control border border-line">
    <Table data-variant="facts" className="table-fixed"><TableBody>{items.map(item => <TableRow key={item.outputId}>
      <TableHead scope="row" className="w-1/3"><span className="block truncate">{item.name}</span></TableHead>
      <TableCell className="whitespace-pre-wrap break-words">{show(item.value)}</TableCell>
    </TableRow>)}</TableBody></Table>
  </TableScroll>
}

export function TaskEvidence({ mode, detail, attempts, outputs, artifacts, inlineScreenshotUrl, inlineScreenshotLabel = '失败时页面截图', loading, error, onOpenArtifact, onLocateLog, onLoadMoreArtifacts, onLoadMoreAttempts, onLoadMoreOutputs }: TaskEvidenceProps) {
  const names = new Map((detail.parameterDefinitions ?? []).map(item => [item.parameterId, item.name]))
  const failed = attempts?.items.filter(item => item.status === 'failed') ?? [], primary = failed.at(-1)
  const summaryError = primary?.error ?? detail.run.error
  const finalOutputs = outputs?.items.filter(item => !item.nodeId) ?? []
  const nodeOutputs = outputs?.items.filter(item => item.nodeId) ?? []
  const inlineArtifact = artifacts?.items.find(item => item.availability === 'available')
  const enlargementLabel = inlineScreenshotLabel.startsWith('失败截图：')
    ? `放大${inlineScreenshotLabel}`
    : `放大失败截图：${inlineScreenshotLabel}`
  const renderArtifacts = (items: Artifact[]) => <div className="grid gap-3">{items.map(item => <article className="rounded-control border border-line p-3" key={item.artifactId}>
    <strong className="block truncate">{nodeName(detail, item.nodeId, item.nodeName)}</strong>
    <p className="my-1 text-sm text-muted">失败截图 · {time(item.createdAt)} · {size(item.byteSize)}</p>
    {item.availability === 'available'
      ? onOpenArtifact ? <Button size="sm" onClick={() => onOpenArtifact(item)} aria-label={`查看失败截图：${nodeName(detail, item.nodeId, item.nodeName)}`}>查看截图</Button> : <span className="text-sm text-muted">截图已保存</span>
      : <span className="text-sm text-warning">{artifactReasons[item.unavailableReason ?? ''] ?? '截图不可用'}</span>}
  </article>)}</div>
  return <div className="grid min-w-0 items-start gap-4 lg:grid-cols-2">
    {mode === 'evidence' ? <>
      <section className={'min-w-0 rounded-card border p-5 lg:col-span-2 ' + (failed.length || detail.run.error ? 'border-danger/30 bg-danger/10' : 'border-line bg-surface')}>
        <div className="flex flex-wrap items-start gap-3">
          <WarningCircle className="mt-0.5 shrink-0 text-danger" size={28} weight="fill"/>
          <div className="min-w-0 flex-1"><h3 className="m-0 text-xl">{summaryError ? errorLabel(summaryError) : '未发现运行异常'}</h3>{summaryError ? <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5"><div><dt className="text-muted">错误类型</dt><dd className="m-0 break-words">{errorLabel(summaryError)}</dd></div><div><dt className="text-muted">发生节点</dt><dd className="m-0">{nodeName(detail, primary?.nodeId, primary?.nodeName)}</dd></div><div><dt className="text-muted">尝试次数</dt><dd className="m-0">{primary ? `第 ${primary.attempt} 次尝试` : '—'}</dd></div><div><dt className="text-muted">发生时间</dt><dd className="m-0">{time(primary?.completedAt)}</dd></div><div><dt className="text-muted">问题说明</dt><dd className="m-0 break-words">请查看对应节点日志；修正配置后重新运行。</dd></div></dl> : <p className="mb-0 text-muted">{attempts && !loading && !error ? '已读取的尝试中没有异常记录。' : '节点异常记录尚未读取完成。'}</p>}</div>
          {summaryError && onLocateLog ? <Button variant="ghost" aria-label="定位对应日志" onClick={() => onLocateLog(primary?.nodeId ?? null)}>定位对应日志 →</Button> : null}
        </div>
      </section>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">失败时页面截图</h3>
        {inlineScreenshotUrl ? <div className="grid gap-2">
          {inlineArtifact && onOpenArtifact
            ? <button type="button" className="overflow-hidden rounded-control border border-line bg-canvas text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" aria-label={enlargementLabel} onClick={() => onOpenArtifact(inlineArtifact)}><img className="max-h-[32rem] w-full object-contain" src={inlineScreenshotUrl} alt={inlineScreenshotLabel}/></button>
            : <img className="max-h-[32rem] w-full rounded-control border border-line object-contain" src={inlineScreenshotUrl} alt={inlineScreenshotLabel}/>}
          {inlineArtifact ? <p className="m-0 text-sm text-muted">{nodeName(detail, inlineArtifact.nodeId, inlineArtifact.nodeName)} · {time(inlineArtifact.createdAt)} · {size(inlineArtifact.byteSize)}</p> : null}
          {artifacts?.items.filter(item => item.artifactId !== inlineArtifact?.artifactId).length ? renderArtifacts(artifacts.items.filter(item => item.artifactId !== inlineArtifact?.artifactId)) : null}
        </div> : artifacts?.items.length ? renderArtifacts(artifacts.items) : <p className="text-muted">{artifacts ? '本次运行未生成失败截图。' : '失败截图尚未读取。'}</p>}
        {artifacts && artifacts.items.length < artifacts.total && onLoadMoreArtifacts ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreArtifacts}>加载更多截图</Button> : null}
      </section>
      <div className="grid min-w-0 gap-4">
        <section className="min-w-0 rounded-card border border-line bg-surface p-5"><h3 className="mt-0">错误记录</h3>{failed.length ? <TableScroll label="错误记录表" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{failed.map(item => <TableRow key={item.nodeVisitId + '-' + item.attempt}><TableHead scope="row" className="w-28">{nodeName(detail, item.nodeId, item.nodeName)}</TableHead><TableCell><span className="block">任务 {taskNumber(detail.task.taskOrdinal)} · 尝试 {item.attempt}</span><span className="text-danger">{errorLabel(item.error)}</span></TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-muted">{attempts ? '没有节点错误记录。' : '错误记录尚未读取。'}</p>}</section>
        <section className="min-w-0 rounded-card border border-line bg-surface p-5"><h3 className="mt-0">历史尝试</h3>{attempts?.items.length ? <TableScroll label="节点历史尝试" className="rounded-control border border-line"><Table><TableHeader><TableRow><TableHead>节点 / 尝试</TableHead><TableHead>开始 / 结束</TableHead><TableHead>结果</TableHead></TableRow></TableHeader><TableBody>{attempts.items.map(item => <TableRow key={item.nodeVisitId + '-' + item.attempt}><TableCell><strong className="block max-w-40 truncate">{nodeName(detail, item.nodeId, item.nodeName)}</strong><span>尝试 {item.attempt}</span></TableCell><TableCell>{time(item.startedAt)}<br/>{time(item.completedAt)}</TableCell><TableCell>{statuses[item.status] ?? item.status}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : !loading && !error ? <p className="text-muted">{attempts ? '暂无节点尝试' : '尚未读取节点尝试'}</p> : null}{attempts && attempts.items.length < attempts.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreAttempts}>加载更多尝试</Button> : null}</section>
      </div>
    </> : <>
      <DataInputPreview
        title="原始数据输入"
        description="任务创建时已经固定，之后的数据修改不会改写这份输入。"
        tableLabel="原始数据输入表格"
        inputs={projectInputs(detail)}
        loading={loading && !detail.inputSnapshot.inputs.length}
      />
      <TaskDataWrites writes={projectWrites(detail)} loading={loading}/>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">批次固定参数</h3>
        {Object.keys(detail.inputSnapshot.parameters).length ? <TableScroll label="批次固定参数" className="rounded-control border border-line"><Table data-variant="facts" className="table-fixed"><TableBody>{Object.entries(detail.inputSnapshot.parameters).map(([id, value]) => <TableRow key={id}><TableHead scope="row" className="w-1/3"><span className="block truncate">{names.get(id) ?? '未知参数'}</span></TableHead><TableCell className="whitespace-pre-wrap break-words">{show(value)}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-sm text-muted">本批次没有固定参数。</p>}
      </section>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">输出与产物</h3>
        <section aria-label="最终业务输出"><h4>最终业务输出</h4>{finalOutputs.length ? <OutputTable items={finalOutputs} label="最终业务输出"/> : <p className="text-sm text-muted">{outputs ? '没有最终业务输出。' : '最终业务输出尚未读取。'}</p>}</section>
        <section aria-label="节点中间输出"><h4 className="mb-2 mt-5">节点中间输出</h4>{nodeOutputs.length ? <OutputTable items={nodeOutputs} label="节点中间输出"/> : <p className="text-sm text-muted">{outputs ? '没有节点中间输出。' : '节点中间输出尚未读取。'}</p>}</section>
        <section aria-label="证据附件"><h4 className="mb-2 mt-5">证据附件</h4>{artifacts?.items.length ? renderArtifacts(artifacts.items) : <p className="text-sm text-muted">{artifacts ? '没有证据附件。' : '证据附件尚未读取。'}</p>}</section>
        {outputs && outputs.items.length < outputs.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreOutputs}>加载更多输出</Button> : null}
        <p className="text-xs text-muted">节点输出不代表任务最终业务成功。</p>
      </section>
    </>}
    {loading ? <p role="status" className="lg:col-span-2">正在读取运行证据…</p> : null}
    {error ? <p role="alert" className="min-w-0 break-words text-warning lg:col-span-2">{presentRunFailure(error)}</p> : null}
  </div>
}
