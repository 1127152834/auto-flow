import { useId } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'

export type DataInputPreviewOutcome = 'ready' | 'noMatch' | 'temporarilyBusy' | 'configurationError'

export type DataInputPreviewItem = {
  alias: string
  tableDisplay: string
  recordDisplay: string | null
  values?: { label: string; value: string }[]
  outcome: DataInputPreviewOutcome
}

export type DataInputPreviewProps = {
  inputs: DataInputPreviewItem[]
  loading?: boolean
  title?: string
  description?: string
  tableLabel?: string
}

const outcomes: Record<DataInputPreviewOutcome, { label: string; tone: 'success' | 'warning' | 'danger' }> = {
  ready: { label: '可以使用', tone: 'success' },
  noMatch: { label: '没有匹配记录', tone: 'warning' },
  temporarilyBusy: { label: '记录暂时被占用', tone: 'warning' },
  configurationError: { label: '配置错误', tone: 'danger' },
}

export function DataInputPreview({ inputs, loading = false, title = '数据输入预览', description = '预览只反映当前候选，启动时仍会重新检查。', tableLabel = '数据输入预览表格' }: DataInputPreviewProps) {
  const titleId = useId()
  return <section aria-labelledby={titleId} className="grid min-w-0 gap-3 rounded-card border border-line bg-surface p-5">
    <div>
      <h3 id={titleId} className="m-0 text-xl font-semibold">{title}</h3>
      <p className="mb-0 mt-1 text-sm text-muted">{description}</p>
    </div>
    <TableScroll label={tableLabel} className="rounded-control border border-line">
      <Table aria-label="数据输入预览结果" aria-busy={loading} className="min-w-[36rem] table-fixed text-sm">
        <TableHeader><TableRow><TableHead className="w-[16%]">输入</TableHead><TableHead className="w-[16%]">数据表</TableHead><TableHead className="w-[22%]">匹配记录</TableHead><TableHead>冻结字段</TableHead><TableHead className="w-24">结果</TableHead></TableRow></TableHeader>
        <TableBody>
          {inputs.map((input, index) => {
            const result = outcomes[input.outcome]
            return <TableRow key={`${input.alias}-${index}`}>
              <TableCell><span className="block break-words">{input.alias}</span></TableCell>
              <TableCell><span className="block break-words">{input.tableDisplay}</span></TableCell>
              <TableCell aria-label={input.recordDisplay ? undefined : '没有可显示的匹配记录'}><span className="block whitespace-pre-wrap break-words">{input.recordDisplay || '—'}</span></TableCell>
              <TableCell><span className="block whitespace-pre-wrap break-words">{input.values?.length ? input.values.map(item => `${item.label}：${item.value}`).join('；') : '—'}</span></TableCell>
              <TableCell><TableStatus tone={result.tone}>{result.label}</TableStatus></TableCell>
            </TableRow>
          })}
          {!inputs.length && !loading ? <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted">没有已配置的数据输入</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </TableScroll>
    {loading ? <p role="status" className="m-0 text-sm text-muted">正在预览数据输入…</p> : null}
  </section>
}
