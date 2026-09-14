import type { components } from '../../../shared/api/generated'
import { useEffect, useMemo } from 'react'
import { Modal } from '../../../shared/components/Modal'
import { Button } from '../../../shared/components/ui/button'
import { Checkbox } from '../../../shared/components/ui/checkbox'
import { Select } from '../../../shared/components/ui/select'

type Field = components['schemas']['DataFieldView']
type Status = components['schemas']['DataStatusView']
export type ExcelExportOptions = { scope: 'all' | 'filter'; fieldIds: string[]; includeStatus: boolean }
export type ExcelExportDialogProps = {
  open: boolean; fields: Field[]; statuses: Status[]; scope: ExcelExportOptions['scope']; selectedFieldIds: string[]; includeStatus: boolean
  busy?: boolean; disabled?: boolean; onScopeChange(scope: ExcelExportOptions['scope']): void; onSelectedFieldIdsChange(ids: string[]): void
  error?: string | null; onIncludeStatusChange(value: boolean): void; onClose(): void; onChooseOutput(options: ExcelExportOptions): void
}

export function ExcelExportDialog({ open, fields, statuses, scope, selectedFieldIds, includeStatus, busy, disabled, error, onScopeChange, onSelectedFieldIdsChange, onIncludeStatusChange, onClose, onChooseOutput }: ExcelExportDialogProps) {
  const validIds = useMemo(() => { const available = new Set(fields.map(field => field.ref.fieldId)); return selectedFieldIds.filter(id => available.has(id)) }, [fields, selectedFieldIds])
  useEffect(() => { if (validIds.length !== selectedFieldIds.length) onSelectedFieldIdsChange(validIds) }, [fields, onSelectedFieldIdsChange, selectedFieldIds, validIds])
  const unavailable = disabled || busy, noColumns = validIds.length === 0
  const options = { scope, fieldIds: validIds, includeStatus }
  const toggle = (fieldId: string, checked: boolean) => onSelectedFieldIdsChange(checked ? [...validIds, fieldId] : validIds.filter(id => id !== fieldId))
  return <Modal open={open} onOpenChange={next => { if (!next) onClose() }} title="导出 Excel" description="确认导出范围与列，然后在系统窗口中创建新的 .xlsx 文件。" closeDisabled={busy} footer={<Button variant="primary" disabled={unavailable || noColumns} loading={busy} onClick={() => onChooseOutput(options)}>选择保存位置</Button>}>
    <div className="grid gap-5">
      <label className="grid gap-2 text-sm">导出范围<Select aria-label="导出范围" value={scope} clearable={false} disabled={unavailable} options={[{ value: 'all', label: '整张表' }, { value: 'filter', label: '当前筛选结果' }]} onValueChange={value => value && onScopeChange(value as ExcelExportOptions['scope'])} /></label>
      <fieldset className="grid gap-2"><legend className="font-medium">数据列</legend>{fields.map(field => <label className="flex min-w-0 items-center gap-2" key={field.ref.fieldId}><Checkbox aria-label={field.name} checked={validIds.includes(field.ref.fieldId)} disabled={unavailable} onCheckedChange={checked => toggle(field.ref.fieldId, checked === true)} /><span className="truncate" title={field.name}>{field.name}</span></label>)}</fieldset>
      <label className="flex items-center gap-2"><Checkbox aria-label="包含业务状态" checked={includeStatus} disabled={unavailable} onCheckedChange={checked => onIncludeStatusChange(checked === true)} />包含业务状态{statuses.length ? `（${statuses.length} 个状态）` : '（当前记录将导出为空状态）'}</label>
      {noColumns ? <p role="alert" className="text-sm text-danger">至少选择一列后才能导出。</p> : null}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </div>
  </Modal>
}
