import { useId } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'

export type TaskDataWriteOutcome = 'succeeded' | 'conflict' | 'unknown'

type TaskDataWriteBase = {
  tableDisplay: string
  recordDisplay: string
  outcome: TaskDataWriteOutcome
}

export type TaskDataWrite = TaskDataWriteBase & ({
  kind: 'statusChange'
  previousStatus: string | null
  nextStatus: string | null
} | {
  kind: 'recordCreated'
  referenceDisplay?: string | null
})

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

const compactRecordReference = (value: string) => value.replace(
  /(?:uuid\s*·\s*)?([0-9a-f]{8})-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{8}([0-9a-f]{4})/gi,
  '记录 · $1…$2',
)

export function TaskDataWrites({ writes, loading = false, error }: TaskDataWritesProps) {
  const titleId = useId()
  return <section aria-labelledby={titleId} className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-5">
    <div>
      <h3 id={titleId} className="m-0 text-xl font-semibold">任务数据写入</h3>
      <p className="mb-0 mt-1 text-sm text-muted">只列出工作流明确提交的项目数据变化。</p>
    </div>
    {error ? <p role="alert" className="m-0 break-words text-sm text-danger">任务数据写入读取失败：{error}</p> : null}
    <TableScroll label="任务数据写入表格" className="rounded-control border border-line">
      <Table aria-label="任务数据写入结果" aria-busy={loading} className="min-w-[36rem] table-fixed text-sm">
        <TableHeader><TableRow><TableHead className="w-24">操作</TableHead><TableHead className="w-[28%]">数据表与记录</TableHead><TableHead>写入事实</TableHead><TableHead className="w-24">结果</TableHead></TableRow></TableHeader>
        <TableBody>
          {writes?.map((write, index) => {
            const result = outcomes[write.outcome]
            return <TableRow key={`${write.kind}-${write.tableDisplay}-${index}`}>
              <TableCell>{write.kind === 'statusChange' ? '变更状态' : '新增记录'}</TableCell>
              <TableCell><span className="block break-words">{write.tableDisplay}</span><span className="block whitespace-pre-wrap break-words text-muted">{compactRecordReference(write.recordDisplay)}</span></TableCell>
              <TableCell>{write.kind === 'statusChange'
                ? <span className="block whitespace-pre-wrap break-words">{write.previousStatus ?? '未设置'} → {write.nextStatus ?? '已清空'}</span>
                : <span className="block whitespace-pre-wrap break-words">{write.referenceDisplay ? `稳定引用：${compactRecordReference(write.referenceDisplay)}` : '稳定引用待核对'}</span>}
              </TableCell>
              <TableCell><TableStatus tone={result.tone}>{result.label}</TableStatus></TableCell>
            </TableRow>
          })}
          {!writes && !loading ? <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted">{error ? '写入事实暂时不可用' : '任务数据写入尚未读取'}</TableCell></TableRow> : null}
          {writes?.length === 0 && !loading && !error ? <TableRow><TableCell colSpan={4} className="py-8 text-center text-muted">本任务没有显式数据写入</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </TableScroll>
    {loading ? <p role="status" className="m-0 text-sm text-muted">正在读取任务数据写入…</p> : null}
  </section>
}
