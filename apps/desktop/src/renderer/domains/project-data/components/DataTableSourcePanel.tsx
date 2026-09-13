import type { components } from '../../../shared/api/generated'

type TableSource = Pick<components['schemas']['DataTableView'], 'sourceKind' | 'source'>
const labels: Record<TableSource['sourceKind'], string> = { local: '手动维护', excel: 'Excel 文件', sheets: 'Google Sheets', unconfigured: '尚未配置' }

export function DataTableSourcePanel({ table }: { table: TableSource }) {
  const source = table.source
  return <section className="grid gap-3 rounded-control border border-line bg-surface p-4" aria-label="数据来源">
    <div><h3 className="font-medium">数据来源</h3><p className="text-sm text-muted">{labels[table.sourceKind]}</p></div>
    {source ? <dl className="grid gap-2 text-sm">
      {source.filename ? <div><dt className="text-muted">文件名</dt><dd className="break-all">{source.filename}</dd></div> : null}
      {source.sheetName ? <div><dt className="text-muted">工作表</dt><dd className="break-all">{source.sheetName}</dd></div> : null}
      {source.importedAt ? <div><dt className="text-muted">导入时间</dt><dd><time dateTime={source.importedAt}>{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(source.importedAt))}</time></dd></div> : null}
    </dl> : <p className="text-sm text-muted">这个数据表没有已保存的文件信息。</p>}
    {table.sourceKind === 'local' ? <p className="text-sm">记录和字段直接在项目中维护。</p> : null}
    {table.sourceKind === 'excel' ? <p className="text-sm">导入后保存为项目中的本地副本；不会监听原文件，也不会回写原文件。</p> : null}
  </section>
}
