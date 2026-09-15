import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'

type Detail = components['schemas']['TaskDetail']; type Attempts = components['schemas']['NodeAttemptPage']; type Outputs = components['schemas']['RunOutputPage']; type Artifacts = components['schemas']['RunArtifactPage']; type Artifact = components['schemas']['RunArtifactView']
const show = (value: unknown) => value === null ? 'null' : typeof value === 'boolean' ? String(value) : typeof value === 'string' ? value : JSON.stringify(value)
const statuses = { running: '运行中', succeeded: '成功', failed: '失败' }
const time = (value: string | null) => value ? new Date(value).toLocaleString('zh-CN') : '—'
const artifactReasons: Record<string, string> = { SCREENSHOT_CAPTURE_FAILED: '截图捕获失败', SCREENSHOT_PAGE_UNAVAILABLE: '页面已不可用', LEGACY_ARTIFACT_UNAVAILABLE: '旧版证据不可用' }
const size = (value: number | null | undefined) => value === null || value === undefined ? '—' : value < 1024 ? `${value} B` : `${Math.round(value / 1024)} KB`

export function TaskEvidence({ mode, detail, attempts, outputs, artifacts, loading, error, onOpenArtifact, onLoadMoreArtifacts, onLoadMoreAttempts, onLoadMoreOutputs }: { mode: 'io' | 'evidence'; detail: Detail; attempts?: Attempts; outputs?: Outputs; artifacts?: Artifacts; loading?: boolean; error?: string; onOpenArtifact?(artifact: Artifact): void; onLoadMoreArtifacts?(): void; onLoadMoreAttempts(): void; onLoadMoreOutputs(): void }) {
  const names = new Map((detail.parameterDefinitions ?? []).map(item => [item.parameterId, item.name]))
  const failed = attempts?.items.filter(item => item.status === 'failed') ?? []
  return <div className="grid min-w-0 gap-4 lg:grid-cols-2">
    {mode === 'evidence' ? <>
      <section className={'min-w-0 rounded-control border p-5 lg:col-span-2 ' + (failed.length || detail.run.error ? 'border-danger/30 bg-danger/10' : 'border-line bg-surface')}>
        <h3 className="mt-0">异常事实</h3>
        {detail.run.error ? <pre className="whitespace-pre-wrap break-words">{show(detail.run.error)}</pre> : null}
        {failed.map(item => <div className="min-w-0" key={item.nodeVisitId + '-' + item.attempt}><strong className="block truncate" title={item.nodeId}>{item.nodeId}</strong><span>尝试 {item.attempt} · 失败</span><p className="whitespace-pre-wrap break-words">{show(item.error)}</p></div>)}
        {!detail.run.error && !failed.length ? <p className="text-muted">{attempts && !loading && !error ? '已读取的尝试中没有异常记录。' : '节点异常记录尚未读取完成。'}</p> : null}
      </section>
      <section className="min-w-0 rounded-control border border-line bg-surface p-5">
        <h3 className="mt-0">证据附件</h3>
        {artifacts?.items.length ? <div className="grid gap-3">{artifacts.items.map(item => <div className="rounded-control border border-line p-3" key={item.artifactId}>
          <strong className="block truncate" title={item.nodeId}>{item.nodeId}</strong>
          <p className="my-1 text-sm text-muted">失败截图 · {time(item.createdAt)} · {size(item.byteSize)}</p>
          {item.availability === 'available'
            ? onOpenArtifact ? <Button size="sm" onClick={() => onOpenArtifact(item)} aria-label={`查看失败截图：${item.nodeId}`}>查看截图</Button> : <span className="text-sm text-muted">截图已保存</span>
            : <span className="text-sm text-warning">{artifactReasons[item.unavailableReason ?? ''] ?? '截图不可用'}</span>}
        </div>)}</div> : <p className="text-muted">{artifacts ? '本次运行未生成失败截图。' : '失败截图尚未读取。'}</p>}
        {artifacts && artifacts.items.length < artifacts.total && onLoadMoreArtifacts ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreArtifacts}>加载更多截图</Button> : null}
      </section>
      <section className="min-w-0 rounded-control border border-line bg-surface p-5">
        <h3 className="mt-0">历史尝试</h3>
        {attempts?.items.length ? <TableScroll label="节点历史尝试"><Table><TableHeader><TableRow><TableHead>节点 / 尝试</TableHead><TableHead>开始 / 结束</TableHead><TableHead>结果</TableHead></TableRow></TableHeader><TableBody>{attempts.items.map(item => <TableRow key={item.nodeVisitId + '-' + item.attempt}><TableCell><strong className="block max-w-40 truncate" title={item.nodeId}>{item.nodeId}</strong><span>尝试 {item.attempt}</span></TableCell><TableCell>{time(item.startedAt)}<br/>{time(item.completedAt)}</TableCell><TableCell>{statuses[item.status]}</TableCell></TableRow>)}</TableBody></Table></TableScroll> : !loading && !error ? <p className="text-muted">{attempts ? '暂无节点尝试' : '尚未读取节点尝试'}</p> : null}
        {attempts && attempts.items.length < attempts.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreAttempts}>加载更多尝试</Button> : null}
      </section>
    </> : <>
      <section className="min-w-0 rounded-control border border-line bg-surface p-5">
        <h3 className="mt-0">运行时输入快照</h3><h4>批次固定参数</h4>
        <Table className="table-fixed"><TableBody>{Object.entries(detail.inputSnapshot.parameters).map(([id, value]) => <TableRow key={id}><TableCell className="w-1/3 text-muted"><span className="block truncate" title={names.get(id) ?? id}>{names.get(id) ?? id}</span></TableCell><TableCell className="whitespace-pre-wrap break-words">{show(value)}</TableCell></TableRow>)}</TableBody></Table>
        {detail.inputSnapshot.inputs.length ? <p>{detail.inputSnapshot.inputs.length} 项项目数据输入</p> : <p className="text-sm text-muted">本任务没有项目数据输入。</p>}
      </section>
      <section className="min-w-0 rounded-control border border-line bg-surface p-5">
        <h3 className="mt-0">输出与产物</h3>
        {outputs?.items.length ? <Table className="table-fixed"><TableBody>{outputs.items.map(item => <TableRow key={item.outputId}><TableCell className="w-1/3"><span className="block truncate" title={item.name}>{item.name}</span></TableCell><TableCell className="whitespace-pre-wrap break-words">{show(item.value)}</TableCell></TableRow>)}</TableBody></Table> : !loading && !error ? <p className="text-muted">{outputs ? '没有节点输出。' : '尚未读取节点输出。'}</p> : null}
        {outputs && outputs.items.length < outputs.total ? <Button className="mt-3" disabled={loading} onClick={onLoadMoreOutputs}>加载更多输出</Button> : null}
        <p className="text-xs text-muted">节点输出不代表任务最终业务成功。</p>
      </section>
    </>}
    {loading ? <p role="status" className="lg:col-span-2">正在读取运行证据…</p> : null}
    {error ? <p role="alert" className="min-w-0 break-words text-warning lg:col-span-2">{error}</p> : null}
  </div>
}
