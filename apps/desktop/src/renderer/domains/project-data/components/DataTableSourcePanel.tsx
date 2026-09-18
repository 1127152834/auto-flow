import { ArrowClockwise, Database, Folder, Table as TableIcon, WarningCircle } from '@phosphor-icons/react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'
import { safeProjectError } from '../../projects/presentation-error'
import type { SheetsApi, SheetsImpact } from '../sheets-api'
import { SheetsBindingWizard } from './SheetsBindingWizard'
import { SyncOperationPanel } from './SyncOperationPanel'

type Schema = components['schemas']
type TableView = Schema['DataTableView']
type TableSource = Pick<TableView, 'sourceKind' | 'source'> & Partial<Pick<TableView, 'recordCount'>>
const labels: Record<TableSource['sourceKind'], string> = { local: '手动维护', excel: 'Excel 文件', sheets: 'Google Sheets', unconfigured: '尚未配置' }

/** Everything the source tab needs to drive a real Sheets binding and its sync facts. */
export type SheetsSourceContext = {
  api: SheetsApi
  projectId: string
  scopeKey: string
  contextKey: string
  tableId: string
  tableName: string
  tableRevision: number
  datasetGeneration: string
  fields: Schema['DataFieldView'][]
  onChanged?(): void
}

export type DataTableSourcePanelProps = { table: TableSource; readonly?: boolean; disabled?: boolean; onReimport?(): void; sheets?: SheetsSourceContext }

export function DataTableSourcePanel({ table, readonly = false, disabled = false, onReimport, sheets }: DataTableSourcePanelProps) {
  const source = table.source
  const excel = table.sourceKind === 'excel'
  const sheetsBound = table.sourceKind === 'sheets'
  const local = table.sourceKind === 'local'
  const importedAt = source?.importedAt ? new Date(source.importedAt) : null
  const validImportDate = importedAt && Number.isFinite(importedAt.getTime())
  // File metadata is a display name, never an arbitrary local path.
  const filename = source?.filename?.split(/[\\/]/).pop()
  const hasFacts = excel || local || filename || source?.sheetName || source?.importedAt || table.recordCount !== undefined
  const locked = readonly || disabled
  const reimport = () => { if (!locked) onReimport?.() }

  return <div className="grid gap-5">
    <section className="grid gap-4 rounded-control border border-line bg-surface p-5" aria-label="数据来源">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-xl font-semibold">{excel ? 'Excel 导入来源' : sheetsBound ? 'Google Sheets 来源' : '数据来源'}</h3>
          <p className="mt-1 text-base text-muted">{labels[table.sourceKind]}</p>
        </div>
        {excel && onReimport ? <Button className="h-12 px-7 text-base" disabled={locked} onClick={reimport}><Folder size={22} aria-hidden="true" />更换文件</Button> : null}
      </header>
      {!source && !sheetsBound ? <p className="text-sm text-muted">这个数据表没有已保存的文件信息。</p> : null}
      {hasFacts || sheetsBound ? <TableScroll label="来源事实" className="max-w-[58rem] rounded-control border border-line">
        <Table data-variant="facts" aria-label="来源事实">
          <TableBody className="[&_th]:w-1/3 sm:[&_th]:w-[12.5rem] [&_td]:break-words">
            {excel || filename ? <TableRow><TableHead scope="row" className="font-normal">来源文件</TableHead><TableCell className="break-all">{filename || '未记录'}</TableCell></TableRow> : null}
            {excel || source?.sheetName ? <TableRow><TableHead scope="row" className="font-normal">工作表</TableHead><TableCell className="break-all">{source?.sheetName || '未记录'}</TableCell></TableRow> : null}
            {sheets && sheetsBound ? <SheetsFactRows context={sheets} /> : null}
            {excel || importedAt ? <TableRow><TableHead scope="row" className="font-normal">最近导入</TableHead><TableCell>{validImportDate ? <time dateTime={source!.importedAt!}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(importedAt)}</time> : importedAt ? '导入时间无法读取' : '未记录'}</TableCell></TableRow> : null}
            {table.recordCount !== undefined ? <TableRow><TableHead scope="row" className="font-normal">本地记录</TableHead><TableCell>{table.recordCount.toLocaleString()} 条</TableCell></TableRow> : null}
            {excel || local || sheetsBound ? <TableRow><TableHead scope="row" className="font-normal">写入方式</TableHead><TableCell>{sheetsBound ? '与来源工作表保持一致' : excel ? '只维护本地数据' : '项目内维护'}</TableCell></TableRow> : null}
          </TableBody>
        </Table>
      </TableScroll> : null}
      {local ? <p className="text-base text-muted">记录和字段直接在项目中维护。</p> : null}
      {excel ? <>
        <div className="flex items-center gap-5 rounded-control border border-success/20 bg-success/5 p-5 text-success">
          <Database size={36} weight="fill" className="shrink-0" aria-hidden="true" />
          <p className="text-base font-medium">{readonly ? '本地副本保存在项目中，当前为只读。' : '本地副本可维护，支持单条新增、编辑与删除。'}不会监听原文件，也不会回写原文件。</p>
        </div>
        <div className="flex items-start gap-5 rounded-control border border-warning/20 bg-warning/5 p-5">
          <WarningCircle size={32} weight="fill" className="shrink-0 text-warning" aria-hidden="true" />
          <div className="grid min-w-0 gap-3">
            <h4 className="text-lg font-semibold text-clay">重新导入前请确认</h4>
            <p className="text-base text-muted">重新导入会替换当前本地数据，旧版本数据与业务状态会按数据代次隔离，不是增量追加。原始 Excel 文件不会被回写。</p>
            <div className="flex flex-wrap items-center gap-5">
              {onReimport ? <Button variant="primary" className="h-12 px-6 text-base" disabled={locked} onClick={reimport}><ArrowClockwise size={22} aria-hidden="true" />重新导入…</Button> : null}
              <p className="text-base text-clay">先预览影响，再确认替换</p>
            </div>
          </div>
        </div>
      </> : null}
    </section>
    {sheets ? <SheetsSourceSection table={table} context={sheets} readonly={readonly} disabled={disabled} /> : null}
  </div>
}

/** A bound worksheet keeps its real names in the binding, never in the file source. */
function SheetsFactRows({ context }: { context: SheetsSourceContext }) {
  const query = useQuery({ queryKey: ['sheets-binding', context.scopeKey, context.tableId], queryFn: ({ signal }) => context.api.readBinding(context.tableId, signal), retry: false })
  const binding = query.data ?? null
  // An unread binding is not an empty one, so loading and failures say what they are.
  const unread = query.isPending ? '读取中…' : query.isError ? '暂时无法读取' : '未记录'
  return <>
    <TableRow><TableHead scope="row" className="font-normal">来源表格</TableHead><TableCell className="break-all">{binding ? binding.spreadsheetTitle || binding.spreadsheetId : unread}</TableCell></TableRow>
    <TableRow><TableHead scope="row" className="font-normal">工作表</TableHead><TableCell className="break-all">{binding ? binding.sheetName || `工作表 ${binding.sheetId}` : unread}</TableCell></TableRow>
  </>
}

function SheetsSourceSection({ table, context, readonly, disabled }: { table: TableSource; context: SheetsSourceContext; readonly: boolean; disabled: boolean }) {
  const queries = useQueryClient()
  const [wizard, setWizard] = useState(false)
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const [unbind, setUnbind] = useState<{ revision: number; impacts: SheetsImpact[] } | null>(null)
  const bindingQuery = useQuery({ queryKey: ['sheets-binding', context.scopeKey, context.tableId], queryFn: ({ signal }) => context.api.readBinding(context.tableId, signal), retry: false })
  const connections = useQuery({ queryKey: ['sheets-connections', context.scopeKey], queryFn: () => context.api.connections(), retry: false })
  const binding = table.sourceKind === 'sheets' || bindingQuery.data ? bindingQuery.data ?? null : null
  const account = binding ? connections.data?.items.find(item => item.connectionId === binding.connectionId)?.accountLabel : null
  const bound = Boolean(binding)

  /** Unbinding keeps every local record; the confirmation says so before it runs. */
  const previewUnbind = async () => {
    if (busy) return
    setBusy(true); setError(null); setUnbind(null)
    try {
      const report = await context.api.previewUnbind(context.tableId)
      if (report.blockers.length > 0) { setError(report.blockers.map(blocker => blocker.message).join(' ')); return }
      setUnbind({ revision: report.impactRevision, impacts: report.impacts })
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  const confirmUnbind = async () => {
    if (busy || !unbind) return
    setBusy(true); setError(null)
    try {
      const operation = await context.api.removeBinding(context.tableId, { impactRevision: unbind.revision, expectedTableRevision: context.tableRevision }, crypto.randomUUID(), () => true)
      if (operation.status === 'failed') { setError(safeProjectError(operation.error ?? new Error('解除绑定未完成'))); return }
      setUnbind(null); setWizard(false)
      await Promise.all([
        bindingQuery.refetch(),
        queries.invalidateQueries({ queryKey: ['data-table', context.scopeKey, context.tableId] }),
      ])
      context.onChanged?.()
    } catch (cause) { setError(safeProjectError(cause)) } finally { setBusy(false) }
  }

  return <section className="grid gap-4 rounded-control border border-line bg-surface p-5" aria-label="Google Sheets">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <TableIcon size={28} aria-hidden="true" />
        <div><h3 className="text-xl font-semibold">Google Sheets</h3><p className="mt-1 text-base text-muted">{bound ? '本地表与来源工作表已建立映射。' : '把这张表绑定到一张工作表，之后按需拉取与推送。'}</p></div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        {bound ? <Button variant="ghost" className="h-12 px-7 text-base" disabled={readonly || disabled || busy} onClick={() => void previewUnbind()}>解除绑定…</Button> : null}
        <Button variant={bound ? 'ghost' : 'primary'} className="h-12 px-7 text-base" disabled={readonly || disabled} onClick={() => setWizard(true)}>{bound ? '调整绑定…' : '绑定 Google Sheets…'}</Button>
      </div>
    </header>
    {error ? <p role="alert" className="m-0 text-sm text-danger">{error}</p> : null}
    {unbind ? <section className="grid gap-3 rounded-control border border-clay bg-surface p-4" aria-label="解除绑定的确认">
      <h5 className="m-0 text-sm font-semibold">确认解除绑定</h5>
      <ul className="m-0 grid gap-1 pl-5 text-sm text-muted">{unbind.impacts.map((impact, index) => <li key={`${impact.code}-${index}`}>{impact.message}</li>)}</ul>
      <div className="flex flex-wrap gap-3">
        <Button size="sm" variant="primary" disabled={busy} onClick={() => void confirmUnbind()}>解除绑定</Button>
        <Button size="sm" disabled={busy} onClick={() => setUnbind(null)}>取消</Button>
      </div>
    </section> : null}
    {bindingQuery.error ? <p role="alert" className="m-0 text-sm text-danger">绑定信息暂时无法读取。<Button size="sm" variant="ghost" onClick={() => void bindingQuery.refetch()}>重新载入</Button></p> : null}
    {bound && binding ? <TableScroll label="绑定" className="max-w-[58rem] rounded-control border border-line">
      <Table data-variant="facts" aria-label="绑定">
        <TableBody className="[&_th]:w-1/3 sm:[&_th]:w-[12.5rem] [&_td]:break-words">
          <TableRow><TableHead scope="row" className="font-normal">Google 账号</TableHead><TableCell>{account ?? '账号名称暂时无法读取'}</TableCell></TableRow>
          <TableRow><TableHead scope="row" className="font-normal">Spreadsheet</TableHead><TableCell className="break-all">{binding.spreadsheetTitle || binding.spreadsheetId}</TableCell></TableRow>
          <TableRow><TableHead scope="row" className="font-normal">工作表</TableHead><TableCell className="break-all">{binding.sheetName || `工作表 ${binding.sheetId}`}</TableCell></TableRow>
          <TableRow><TableHead scope="row" className="font-normal">映射字段</TableHead><TableCell>{binding.mapping.length} 个{binding.identityStrategy.kind === 'column' ? `，身份列 ${binding.identityStrategy.columnId}` : '，系统身份'}</TableCell></TableRow>
          <TableRow><TableHead scope="row" className="font-normal">调度</TableHead><TableCell>{binding.syncPaused ? '已暂停' : '正常'}</TableCell></TableRow>
        </TableBody>
      </Table>
    </TableScroll> : null}
    <SyncOperationPanel api={context.api} tableId={context.tableId} scopeKey={context.scopeKey} tableRevision={context.tableRevision} binding={binding} readonly={readonly} disabled={disabled} onChanged={context.onChanged} />
    <SheetsBindingWizard open={wizard} api={context.api} scopeKey={context.scopeKey} contextKey={context.contextKey} table={{ tableId: context.tableId, name: context.tableName, tableRevision: context.tableRevision, datasetGeneration: context.datasetGeneration }}
      fields={context.fields} connectionId={binding?.connectionId ?? null} readonly={readonly} disabled={disabled}
      onClose={() => setWizard(false)}
      onBound={() => { setWizard(false); void bindingQuery.refetch(); void connections.refetch(); context.onChanged?.() }} />
  </section>
}
