import type { components } from '../../../shared/api/generated'
import { Button } from '../../../shared/components/ui/button'
import { Select } from '../../../shared/components/ui/select'

type Inspection = components['schemas']['ExcelInspectionView']
type Sheet = components['schemas']['ExcelSheetInspection']
export type ExcelInspectionPanelProps = {
  inspection: Inspection | null; selectedSheetId: string | null; checking?: boolean; disabled?: boolean
  onChoose(): void; onSelectSheet(sheetId: string | null): void; onContinue(sheet: Sheet): void; now?: () => Date
}

const text = (value: Sheet['sample'][number][number]) => value === null ? '' : typeof value === 'object' ? value.value : String(value)

export function ExcelInspectionPanel({ inspection, selectedSheetId, checking = false, disabled, onChoose, onSelectSheet, onContinue, now = () => new Date() }: ExcelInspectionPanelProps) {
  const selected = inspection?.sheets.find(sheet => sheet.sheetId === selectedSheetId) ?? null
  const expired = Boolean(inspection && new Date(inspection.expiresAt).getTime() <= now().getTime())
  return <section className="grid min-w-0 gap-4" aria-label="Excel 检查结果">
    <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-medium">{inspection?.filename ?? '尚未选择 Excel 文件'}</h3><p className="text-xs text-muted">这里只显示有限样例；提交导入时会重新完整验证工作簿。</p></div><Button variant="ghost" onClick={onChoose} disabled={disabled || checking}>{inspection ? '重新选择文件' : '选择 Excel 文件'}</Button></div>
    {checking ? <p role="status">正在检查工作簿…</p> : null}
    {inspection?.issues.map((issue, index) => <p role="alert" key={index}>{issue}</p>)}
    {expired ? <p role="alert">检查结果已过期，请重新选择并检查文件。</p> : null}
    {inspection ? <Select aria-label="工作表" value={selectedSheetId} options={inspection.sheets.map(sheet => ({ value: sheet.sheetId, label: sheet.name, description: `${sheet.rowCount} 条数据` }))} onValueChange={onSelectSheet} disabled={disabled || checking || expired} clearable={false} /> : null}
    {selected ? <div className="grid min-w-0 gap-3">
      <p>{selected.rowCount} 条数据 · 忽略 {selected.ignoredEmptyRowCount} 个空行</p>
      {selected.identityCandidates.length ? <p className="text-sm">{selected.identityCandidates.map(index => `第 ${index + 1} 列可作为候选身份`).join('；')}。候选仅表示文件内初步检查通过，仍需完整验证。</p> : <p className="text-sm text-muted">没有列通过候选身份初检，可使用系统生成身份。</p>}
      {selected.issues.map((issue, index) => <p role="alert" key={index}>{issue}</p>)}
      <div className="max-w-full overflow-auto rounded-control border border-line"><table className="min-w-max text-sm"><thead><tr>{selected.headers.map((header, index) => <th className="max-w-64 truncate p-2 text-left" title={header} key={index}>{header || `第 ${index + 1} 列`}</th>)}</tr></thead><tbody>{selected.sample.slice(0, 10).map((row, rowIndex) => <tr key={rowIndex}>{selected.headers.map((_, columnIndex) => <td className="max-w-64 truncate p-2" title={text(row[columnIndex] ?? null)} key={columnIndex}>{text(row[columnIndex] ?? null)}</td>)}</tr>)}</tbody></table></div>
      {selected.formulaRowCount.some(count => count > 0) ? <p className="text-xs text-muted">公式单元格：{selected.formulaRowCount.map((count, index) => count > 0 ? `第 ${index + 1} 列 ${count} 行` : null).filter(Boolean).join('；')}</p> : null}
      <Button onClick={() => onContinue(selected)} disabled={disabled || checking || expired}>继续字段映射</Button>
    </div> : null}
  </section>
}
