import { RecordFilterEditor } from '../../../project-data/components/RecordFilterEditor'
import type { FilterExpression, OrderBy, RecordQuery } from '../../../project-data/record-query'
import type { InputDefinition, InputTableOption } from './types'

export type InputConditionSectionProps = {
  input: InputDefinition
  table: InputTableOption
  resetKey: string
  draftPending: boolean
  disabled: boolean
  onDirtyChange(dirty: boolean): void
  onChange(next: InputDefinition): void
}

/** Filter and sort conditions of one input; only bound fields can be filtered or sorted on. */
export function InputConditionSection({ input, table, resetKey, draftPending, disabled, onDirtyChange, onChange }: InputConditionSectionProps) {
  const boundIds = new Set(input.fieldBindings.map(binding => binding.fieldRef.fieldId))
  const boundFields = table.fields.filter(field => boundIds.has(field.ref.fieldId))
  const applied = input.filter.type !== 'all' || (Array.isArray(input.filter.items) && input.filter.items.length > 0) || input.orderBy.length > 0
  return <details open={applied || undefined} className="rounded-control border border-line bg-surface-subtle">
    <summary className="cursor-pointer px-3 py-2 text-sm font-medium">筛选与排序 <span className="ml-2 font-normal text-muted">{applied ? '已设置条件' : '未设置条件'}</span></summary>
    <div className="border-t border-line p-3" tabIndex={draftPending ? -1 : undefined} aria-invalid={draftPending ? true : undefined}>
      {!boundFields.length ? <p className="mb-2 mt-0 text-sm text-warning">字段筛选和字段排序需要先添加字段映射；状态条件和系统字段排序仍可使用。</p> : null}
      {draftPending ? <p role="alert" className="mb-2 text-sm text-danger">筛选或排序有尚未应用的修改，请先应用或取消。</p> : null}
      <RecordFilterEditor key={`${resetKey}:${input.inputId}`} fields={boundFields} statuses={table.statuses} appliedQuery={{ filter: input.filter as unknown as FilterExpression, orderBy: input.orderBy as unknown as OrderBy[] }} disabled={disabled} onDirtyChange={onDirtyChange} onApply={(query: RecordQuery) => onChange({ ...input, filter: query.filter as unknown as InputDefinition['filter'], orderBy: query.orderBy as unknown as InputDefinition['orderBy'] })}/>
    </div>
  </details>
}
