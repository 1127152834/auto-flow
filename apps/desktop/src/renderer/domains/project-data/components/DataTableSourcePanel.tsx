import { ArrowClockwise, Database, Folder, WarningCircle } from '@phosphor-icons/react'
import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableRow, TableScroll } from '../../../shared/components/ui/table'

type TableView = components['schemas']['DataTableView']
type TableSource = Pick<TableView, 'sourceKind' | 'source'> & Partial<Pick<TableView, 'recordCount'>>
const labels: Record<TableSource['sourceKind'], string> = { local: '手动维护', excel: 'Excel 文件', sheets: 'Google Sheets', unconfigured: '尚未配置' }
export type DataTableSourcePanelProps = { table: TableSource; readonly?: boolean; disabled?: boolean; onReimport?(): void }

export function DataTableSourcePanel({ table, readonly = false, disabled = false, onReimport }: DataTableSourcePanelProps) {
  const source = table.source
  const excel = table.sourceKind === 'excel'
  const local = table.sourceKind === 'local'
  const importedAt = source?.importedAt ? new Date(source.importedAt) : null
  const validImportDate = importedAt && Number.isFinite(importedAt.getTime())
  // File metadata is a display name, never an arbitrary local path.
  const filename = source?.filename?.split(/[\\/]/).pop()
  const hasFacts = excel || local || filename || source?.sheetName || source?.importedAt || table.recordCount !== undefined
  const locked = readonly || disabled
  const reimport = () => { if (!locked) onReimport?.() }

  return <section className="grid gap-4 rounded-control border border-line bg-surface p-5" aria-label="数据来源">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h3 className="text-xl font-semibold">{excel ? 'Excel 导入来源' : '数据来源'}</h3>
        <p className="mt-1 text-base text-muted">{labels[table.sourceKind]}</p>
      </div>
      {excel && onReimport ? <Button className="h-12 px-7 text-base" disabled={locked} onClick={reimport}><Folder size={22} aria-hidden="true" />更换文件</Button> : null}
    </header>
    {!source ? <p className="text-sm text-muted">这个数据表没有已保存的文件信息。</p> : null}
    {hasFacts ? <TableScroll label="来源事实" className="max-w-[58rem] rounded-control border border-line">
      <Table data-variant="facts" aria-label="来源事实">
        <TableBody className="[&_th]:w-1/3 sm:[&_th]:w-[12.5rem] [&_td]:break-words">
          {excel || filename ? <TableRow><TableHead scope="row" className="font-normal">来源文件</TableHead><TableCell className="break-all">{filename || '未记录'}</TableCell></TableRow> : null}
          {excel || source?.sheetName ? <TableRow><TableHead scope="row" className="font-normal">工作表</TableHead><TableCell className="break-all">{source?.sheetName || '未记录'}</TableCell></TableRow> : null}
          {excel || importedAt ? <TableRow><TableHead scope="row" className="font-normal">最近导入</TableHead><TableCell>{validImportDate ? <time dateTime={source!.importedAt!}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(importedAt)}</time> : importedAt ? '导入时间无法读取' : '未记录'}</TableCell></TableRow> : null}
          {table.recordCount !== undefined ? <TableRow><TableHead scope="row" className="font-normal">本地记录</TableHead><TableCell>{table.recordCount.toLocaleString()} 条</TableCell></TableRow> : null}
          {excel || local ? <TableRow><TableHead scope="row" className="font-normal">写入方式</TableHead><TableCell>{excel ? '只维护本地数据' : '项目内维护'}</TableCell></TableRow> : null}
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
}
