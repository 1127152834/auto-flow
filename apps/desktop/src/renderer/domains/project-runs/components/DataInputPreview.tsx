import { useId } from 'react'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { TableStatus } from '../../../shared/components/ui/table-status'

export type DataInputPreviewOutcome = 'ready' | 'noMatch' | 'temporarilyBusy' | 'ambiguous' | 'configurationError' | 'scanBudgetExceeded' | 'notEvaluated'

export type DataInputPreviewItem = {
  alias: string
  tableDisplay: string
  recordDisplay: string | null
  values?: { label: string; value: string }[]
  outcome: DataInputPreviewOutcome
  required?: boolean
  scannedCount?: number
  detail?: string
}

export type DataInputPreviewProps = {
  inputs: DataInputPreviewItem[]
  loading?: boolean
  error?: string
  title?: string
  description?: string
  tableLabel?: string
}

type OutcomePresentation = { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger'; help?: string }

const outcomes: Record<DataInputPreviewOutcome, OutcomePresentation> = {
  ready: { label: '可以使用', tone: 'success' },
  noMatch: { label: '没有匹配记录', tone: 'warning' },
  temporarilyBusy: { label: '记录暂时被占用', tone: 'warning' },
  ambiguous: { label: '匹配结果不唯一', tone: 'danger' },
  configurationError: { label: '配置错误', tone: 'danger' },
  scanBudgetExceeded: { label: '扫描范围过大', tone: 'danger' },
  notEvaluated: { label: '尚未确定', tone: 'neutral' },
}

const presentOutcome = (input: DataInputPreviewItem): OutcomePresentation => input.outcome === 'noMatch' && input.required === false
  ? { label: '可选输入未找到', tone: 'neutral', help: '不会阻止本次启动' }
  : outcomes[input.outcome]

export function DataInputPreview({ inputs, loading = false, error, title = '数据输入预览', description = '预览只反映当前候选，启动时仍会重新检查。', tableLabel = '数据输入预览表格' }: DataInputPreviewProps) {
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
            const result = presentOutcome(input)
            return <TableRow key={`${input.alias}-${index}`}>
              <TableCell><span className="block break-words">{input.alias}</span></TableCell>
              <TableCell><span className="block break-words">{input.tableDisplay}</span></TableCell>
              <TableCell aria-label={input.recordDisplay ? undefined : '没有可显示的匹配记录'}><span className="block whitespace-pre-wrap break-words">{input.recordDisplay || '—'}</span></TableCell>
              <TableCell><span className="block whitespace-pre-wrap break-words">{input.values?.length ? input.values.map(item => `${item.label}：${item.value}`).join('；') : '—'}</span></TableCell>
              <TableCell>
                <TableStatus tone={result.tone}>{result.label}</TableStatus>
                {result.help ? <span className="mt-1 block text-xs text-muted">{result.help}</span> : null}
                {typeof input.scannedCount === 'number' ? <span className="mt-1 block text-xs text-muted">已扫描 {input.scannedCount} 条记录</span> : null}
                {input.detail ? <span className="mt-1 block whitespace-pre-wrap break-words text-xs text-muted">{input.detail}</span> : null}
              </TableCell>
            </TableRow>
          })}
          {!inputs.length && !loading && !error ? <TableRow><TableCell colSpan={5} className="py-8 text-center text-muted">没有已配置的数据输入</TableCell></TableRow> : null}
        </TableBody>
      </Table>
    </TableScroll>
    {loading ? <p role="status" className="m-0 text-sm text-muted">正在预览数据输入…</p> : null}
    {error ? <p role="alert" className="m-0 whitespace-pre-wrap break-words text-sm text-danger">数据输入预检失败：{error}</p> : null}
  </section>
}
