import type { components } from '../../shared/api/generated'

type Schema = components['schemas']
export type TableIdentity = Schema['DataTableView']['identity']

const scalarText = (cell: Schema['DataCellView'] | undefined): string | null => {
  if (!cell?.readable || cell.error || typeof cell.value !== 'string') return null
  return cell.value.trim() || null
}

const recordTime = (record: Schema['DataRecordView']): string =>
  new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(record.updatedAt || record.createdAt))

/** A table shows its identity exactly once: the mapped field when it is on screen, otherwise a dedicated key column. */
export function showsDedicatedIdentityColumn(identity: TableIdentity, visibleFieldIds: readonly string[]): boolean {
  return identity.mode === 'system' || !visibleFieldIds.includes(identity.fieldId)
}

/** Converts only the table-owned record identity; user field values remain untouched. */
export function recordDisplayLabel(identity: TableIdentity, fields: readonly Schema['DataFieldView'][], record: Schema['DataRecordView']): string {
  if (identity.mode === 'field') {
    const field = fields.find(item => item.ref.fieldId === identity.fieldId)
    if (!field) return '字段已失效'
    return String(record.ref.recordKey.value)
  }
  for (const field of fields) {
    if (field.type !== 'string') continue
    const value = scalarText(record.values.find(cell => cell.fieldId === field.ref.fieldId))
    if (value) return value
  }
  return `未命名记录 · ${recordTime(record)}`
}
