import { WarningCircle } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'

type Schema = components['schemas']
type Detail = Omit<Schema['TaskDetail'], 'task'> & { nodeNames?: Record<string, string>; task: Omit<Schema['TaskView'], 'taskOrdinal'> & { taskOrdinal?: number | null } }
type Attempt = Omit<Schema['NodeAttemptView'], 'nodeName'> & { nodeName?: string }
type Attempts = Omit<Schema['NodeAttemptPage'], 'items'> & { items: Attempt[] }; type Outputs = Schema['RunOutputPage']; type Artifact = Omit<Schema['RunArtifactView'], 'nodeName'> & { nodeName?: string }; type Artifacts = Omit<Schema['RunArtifactPage'], 'items'> & { items: Artifact[] }
type JsonRecord = Record<string, unknown>
const record = (value: unknown): JsonRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {}
const show = (value: unknown): string => value === null ? 'null' : typeof value === 'boolean' ? String(value) : typeof value === 'string' || typeof value === 'number' ? String(value) : Array.isArray(value) ? value.map(show).join('、') || '空列表' : value && typeof value === 'object' ? Object.entries(value).map(([key, item]) => `${key}：${show(item)}`).join('；') || '空对象' : '—'
const statuses: Record<string, string> = { running: '运行中', succeeded: '成功', failed: '失败' }
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—'
const artifactReasons: Record<string, string> = { SCREENSHOT_CAPTURE_FAILED: '截图捕获失败', SCREENSHOT_PAGE_UNAVAILABLE: '页面已不可用', LEGACY_ARTIFACT_UNAVAILABLE: '旧版证据不可用' }
const size = (value: number | null | undefined) => value === null || value === undefined ? '—' : value < 1024 ? `${value} B` : `${Math.round(value / 1024)} KB`
const taskNumber = (ordinal: number | null | undefined) => `T${String(ordinal ?? 1).padStart(4, '0')}`
const nodeName = (detail: Detail, nodeId: string | null | undefined, frozen?: string) => nodeId && detail.nodeNames?.[nodeId]?.trim() || frozen?.trim() || '步骤'
const errorCode = (value: unknown) => typeof record(value).code === 'string' ? String(record(value).code) : 'UNKNOWN_ERROR'
const errorMessage = (value: unknown) => typeof record(value).message === 'string' ? String(record(value).message) : null

export function TaskEvidence({ mode, detail, attempts, outputs, artifacts, loading, error, onOpenArtifact, onLoadMoreArtifacts, onLoadMoreAttempts, onLoadMoreOutputs }: { mode: 'io' | 'evidence'; detail: Detail; attempts?: Attempts; outputs?: Outputs; artifacts?: Artifacts; loading?: boolean; error?: string; onOpenArtifact?(artifact: Artifact): void; onLoadMoreArtifacts?(): void; onLoadMoreAttempts(): void; onLoadMoreOutputs(): void }) {
  const names = new Map((detail.parameterDefinitions ?? []).map(item => [item.parameterId, item.name]))
  const failed = attempts?.items.filter(item => item.status === 'failed') ?? [], primary = failed.at(-1)
  const summaryError = detail.run.error ?? primary?.error
  return <div className="grid min-w-0 gap-4 lg:grid-cols-2">
    {mode === 'evidence' ? <>
      <section className={'min-w-0 rounded-card border p-5 lg:col-span-2 ' + (failed.length || detail.run.error ? 'border-danger/30 bg-danger/10' : 'border-line bg-surface')}>
        <div className="flex items-start gap-3"><WarningCircle className="mt-0.5 shrink-0 text-danger" size={28} weight="fill"/><div className="min-w-0 flex-1"><h3 className="m-0 text-xl">{errorMessage(summaryError) ?? (summaryError ? '任务运行异常' : '未发现运行异常')}</h3>{summaryError ? <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5"><div><dt className="text-muted">错误代码</dt><dd className="m-0 break-words">{errorCode(summaryError)}</dd></div><div><dt className="text-muted">发生节点</dt><dd className="m-0">{nodeName(detail, primary?.nodeId, primary?.nodeName)}</dd></div><div><dt className="text-muted">尝试次数</dt><dd className="m-0">{primary ? `第 ${primary.attempt} 次尝试` : '—'}</dd></div><div><dt className="text-muted">发生时间</dt><dd className="m-0">{time(primary?.completedAt)}</dd></div><div><dt className="text-muted">问题说明</dt><dd className="m-0 break-words">{errorMessage(summaryError) ?? '请查看错误记录与对应日志。'}</dd></div></dl> : <p className="mb-0 text-muted">{attempts && !loading && !error ? '已读取的尝试中没有异常记录。' : '节点异常记录尚未读取完成。'}</p>}</div></div>
      </section>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">失败时页面截图</h3>
        {artifacts?.items.length ? <div className="grid gap-3">{artifacts.items.map(item => <article className="rounded-control border border-line p-3" key={item.artifactId}><strong className="block truncate">{nodeName(detail, item.nodeId, item.nodeName)}</strong><p className="my-1 text-sm text-muted">失败截图 · {time(item.createdAt)} · {size(item.byteSize)}</p>{item.availability === 'available' ? onOpenArtifact ? <Button size="sm" onClick={() => onOpenArtifact(item)} aria-label={`查看失败截图：${nodeName(detail, item.nodeId, item.nodeName)}`}>查看截图</Button> : <span className="text-sm text-muted">截图已保存</span> : <span className="text-sm text-warning">{artifactReasons[item.unavailableReason ?? ''] ?? '截图不可用'}</span>}</article>)}</div> : <p className="text-muted">{artifacts ? '本次运行未生成失败截图。' : '失败截图尚未读取。'}</p>}
        {artifacts && artifacts.items.length < artifacts.total && onLoadMoreArtifacts ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreArtifacts}>加载更多截图</Button> : null}
      </section>
      <div className="grid min-w-0 gap-4">
        <section className="min-w-0 rounded-card border border-line bg-surface p-5"><h3 className="mt-0">错误记录</h3>{failed.length ? <TableScroll label="错误记录表" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{failed.map(item => <TableRow key={item.nodeVisitId + '-' + item.attempt}><TableHead scope="row" className="w-28">{nodeName(detail, item.nodeId, item.nodeName)}</TableHead><TableCell><span className="block">任务 {taskNumber(detail.task.taskOrdinal)} · 尝试 {item.attempt}</span><span className="text-danger">{errorCode(item.error)}</span></TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-muted">{attempts ? '没有节点错误记录。' : '错误记录尚未读取。'}</p>}</section>
        <section className="min-w-0 rounded-card border border-line bg-surface p-5"><h3 className="mt-0">历史尝试</h3>{attempts?.items.length ? <TableScroll label="节点历史尝试" className="rounded-control border border-line"><Table><TableHeader><TableRow><TableHead>节点 / 尝试</TableHead><TableHead>开始 / 结束</TableHead><TableHead>结果</TableHead></TableRow></TableHeader><TableBody>{attempts.items.map(item => <TableRow key={item.nodeVisitId + '-' + item.attempt}><TableCell><strong className="block max-w-40 truncate">{nodeName(detail, item.nodeId, item.nodeName)}</strong><span>尝试 {item.attempt}</span></TableCell><TableCell>{time(item.startedAt)}<br/>{time(item.completedAt)}</TableCell><TableCell>{statuses[item.status] ?? item.status}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : !loading && !error ? <p className="text-muted">{attempts ? '暂无节点尝试' : '尚未读取节点尝试'}</p> : null}{attempts && attempts.items.length < attempts.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreAttempts}>加载更多尝试</Button> : null}</section>
      </div>
    </> : <>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">运行时输入快照</h3><h4>批次固定参数</h4>
        {Object.keys(detail.inputSnapshot.parameters).length ? <TableScroll label="批次固定参数" className="rounded-control border border-line"><Table data-variant="facts" className="table-fixed"><TableBody>{Object.entries(detail.inputSnapshot.parameters).map(([id, value]) => <TableRow key={id}><TableHead scope="row" className="w-1/3"><span className="block truncate">{names.get(id) ?? '参数'}</span></TableHead><TableCell className="whitespace-pre-wrap break-words">{show(value)}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-sm text-muted">本批次没有固定参数。</p>}
        <h4 className="mb-2 mt-5">本任务数据输入</h4>{detail.inputSnapshot.inputs.length ? <TableScroll label="本任务数据输入" className="rounded-control border border-line"><Table data-variant="facts"><TableBody>{detail.inputSnapshot.inputs.map((input, index) => <TableRow key={index}><TableHead scope="row" className="w-1/3">输入 {index + 1}</TableHead><TableCell className="whitespace-pre-wrap break-words">{show(input)}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : <p className="text-sm text-muted">本任务没有项目数据输入。</p>}
      </section>
      <section className="min-w-0 rounded-card border border-line bg-surface p-5">
        <h3 className="mt-0">输出与产物</h3>
        {outputs?.items.length ? <TableScroll label="节点输出" className="rounded-control border border-line"><Table data-variant="facts" className="table-fixed"><TableBody>{outputs.items.map(item => <TableRow key={item.outputId}><TableHead scope="row" className="w-1/3"><span className="block truncate">{item.name}</span></TableHead><TableCell className="whitespace-pre-wrap break-words">{show(item.value)}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : !loading && !error ? <p className="text-muted">{outputs ? '没有节点输出。' : '尚未读取节点输出。'}</p> : null}
        {outputs && outputs.items.length < outputs.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreOutputs}>加载更多输出</Button> : null}
        <p className="text-xs text-muted">节点输出不代表任务最终业务成功。</p>
      </section>
    </>}
    {loading ? <p role="status" className="lg:col-span-2">正在读取运行证据…</p> : null}
    {error ? <p role="alert" className="min-w-0 break-words text-warning lg:col-span-2">{error}</p> : null}
  </div>
}
