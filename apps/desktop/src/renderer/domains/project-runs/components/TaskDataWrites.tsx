import { useId } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'

export type TaskDataWriteOutcome = 'succeeded' | 'conflict' | 'unknown'

type TaskDataWriteBase = {
  kind: string
  tableDisplay: string
  recordDisplay: string
  outcome: TaskDataWriteOutcome
  referenceDisplay?: string | null
  beforeSummary?: string | null
  afterSummary?: string | null
  detail?: string | null
  nodeName?: string | null
}

export type TaskDataWrite = TaskDataWriteBase & {
  previousStatus?: string | null
  nextStatus?: string | null
}

export type TaskDataWritesProps = {
  writes?: TaskDataWrite[]
  loading?: boolean
  error?: string | null
}

const outcomes: Record<TaskDataWriteOutcome, { label: string; tone: 'success' | 'warning' | 'danger' }> = {
  succeeded: { label: '已确认', tone: 'success' },
  conflict: { label: '写入冲突', tone: 'danger' },
  unknown: { label: '结果待核对', tone: 'warning' },
}

const kindLabels: Record<string, string> = {
  query: '查询记录',
  read: '读取记录',
  recordUpdated: '编辑记录',
  recordDeleted: '删除记录',
  statusChange: '变更状态',
  recordCreated: '新增记录',
  fieldAdded: '新增字段',
  fieldEnsured: '确保字段',
  fieldModified: '修改字段',
  fieldDeleted: '删除字段',
}

const compactRecordReference = (value: string) => value.replace(
  /(?:uuid\s*·\s*)?([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}([0-9a-f]{4})/gi,
  '记录 · $1…$2',
)

const operationFact = (write: TaskDataWrite): string => {
  if (write.kind === 'statusChange') return `${write.previousStatus ?? '未设置'} → ${write.nextStatus ?? '已清空'}`
  if (write.kind === 'recordDeleted') return write.beforeSummary ? `${write.beforeSummary} → 已删除` : '记录已删除'
  if (write.beforeSummary && write.afterSummary) return `${write.beforeSummary} → ${write.afterSummary}`
  if (write.kind === 'recordCreated' && write.afterSummary) return `新增后：${write.afterSummary}`
  if (write.afterSummary) return write.afterSummary
  if (write.beforeSummary) return write.beforeSummary
  if (write.detail) return write.detail
  if (write.outcome === 'conflict') return '发生版本冲突'
  if (write.outcome === 'unknown') return '最终结果尚未确认'
  return '操作已确认'
}

export function TaskDataWrites({ writes, loading = false, error }: TaskDataWritesProps) {
  const titleId = useId()
  return <section aria-labelledby={titleId} className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-5">
    <div>
      <h3 id={titleId} className="m-0 text-xl font-semibold">项目数据操作</h3>
      <p className="mb-0 mt-1 text-sm text-muted">显示本任务确认过的查询、读取和显式数据变化。</p>
    </div>
    {error ? <p role="alert" className="m-0 break-words text-sm text-danger">项目数据操作读取失败：{error}</p> : null}
    <TableScroll label="项目数据操作表格" className="rounded-control border border-line">
      <Table aria-label="项目数据操作结果" aria-busy={loading} className="min-w-[36rem] table-fixed text-sm">
        <TableHeader><TableRow><TableHead className="w-24">操作</TableHead><TableHead className="w-[24%]">数据表与对象</TableHead><TableHead>操作事实</TableHead><TableHead className="w-[20%]">来源节点</TableHead><TableHead className="w-[18%]">稳定引用</TableHead><TableHead className="w-24">结果</TableHead></TableRow></TableHeader>
        <TableBody>
          {writes?.map((write, index) => {
            const result = outcomes[write.outcome]
            const fact = operationFact(write)
            return <TableRow key={`${write.kind}-${write.tableDisplay}-${index}`}>
              <TableCell>{kindLabels[write.kind] ?? '数据操作'}</TableCell>
              <TableCell><span className="block break-words">{write.tableDisplay}</span><span className="block whitespace-pre-wrap break-words text-muted">{compactRecordReference(write.recordDisplay)}</span></TableCell>
              <TableCell>
                <span className="block whitespace-pre-wrap break-words">{compactRecordReference(fact)}</span>
                {write.detail && write.detail !== fact ? <span className="mt-1 block whitespace-pre-wrap break-words text-muted">{compactRecordReference(write.detail)}</span> : null}
              </TableCell>
              <TableCell><span className="block whitespace-pre-wrap break-words">{write.nodeName || '未归属节点'}</span>{write.nodeName ? null : <span className="mt-1 block text-xs text-muted">运行事件未记录所属节点</span>}</TableCell>
              <TableCell><span className="block whitespace-pre-wrap break-words">{write.referenceDisplay ? compactRecordReference(write.referenceDisplay) : '—'}</span></TableCell>
              <TableCell><TableStatus tone={result.tone}>{result.label}</TableStatus></TableCell>
            </TableRow>
          })}
          {!writes && !loading ? <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted">{error ? '数据操作事实暂时不可用' : '项目数据操作尚未读取'}</TableCell></TableRow> : null}
          {writes?.length === 0 && !loading && !error ? <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted">本任务没有项目数据操作</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </TableScroll>
    {loading ? <p role="status" className="m-0 text-sm text-muted">正在读取项目数据操作…</p> : null}
  </section>
}
