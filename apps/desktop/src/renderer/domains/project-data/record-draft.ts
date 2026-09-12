import type { components } from '../../shared/api/generated'
import { parseScalarDraft, scalarDraft, type Scalar, type ScalarDraft } from './scalar-draft'

type Field = components['schemas']['DataFieldView']
type RecordView = components['schemas']['DataRecordView']
export type RecordDraft = Record<string, ScalarDraft>

export class RecordDraftError extends Error {
  constructor(readonly fieldId: string, message: string) { super(message); this.name = 'RecordDraftError' }
}

export function createRecordDraft(fields: Field[], record?: RecordView): RecordDraft {
  const cells = new Map(record?.values.map(cell => [cell.fieldId, cell]))
  return Object.fromEntries(fields.map(field => {
    const cell = cells.get(field.ref.fieldId)
    return [field.ref.fieldId, scalarDraft(cell?.readable ? cell.value : undefined)]
  }))
}

function checkValue(field: Field, value: Scalar | undefined): void {
  if (field.required && (value === undefined || value === null || value === '')) throw new Error('请填写必填字段')
  if (value === undefined || value === null) return
  const rules = field.validation
  if (typeof value === 'string') {
    const length = [...value].length
    if (typeof rules.minLength === 'number' && length < rules.minLength) throw new Error(`文本长度不能少于 ${rules.minLength} 个字符`)
    if (typeof rules.maxLength === 'number' && length > rules.maxLength) throw new Error(`文本长度不能超过 ${rules.maxLength} 个字符`)
    // Python regex semantics are validated by the server, never reinterpreted in JS.
  }
  if (typeof value === 'number') {
    if (typeof rules.minimum === 'number' && value < rules.minimum) throw new Error(`不能小于最小值 ${rules.minimum}`)
    if (typeof rules.maximum === 'number' && value > rules.maximum) throw new Error(`不能超过最大值 ${rules.maximum}`)
  }
}

const sameValue = (a: Scalar | undefined, b: Scalar | undefined): boolean => {
  if (a === b) return true
  return Boolean(a && b && typeof a === 'object' && typeof b === 'object' && a.kind === b.kind && a.precision === b.precision && a.value === b.value && a.offset === b.offset)
}

export function recordValues(fields: Field[], drafts: RecordDraft, record?: RecordView, identityFieldId?: string): components['schemas']['DataCellWrite'][] {
  const cells = new Map(record?.values.map(cell => [cell.fieldId, cell]))
  const values: components['schemas']['DataCellWrite'][] = []
  for (const field of fields) {
    const fieldId = field.ref.fieldId, cell = cells.get(fieldId)
    if (field.formula || !field.writable || cell?.readable === false || (record && fieldId === identityFieldId)) {
      if (!record && field.required) throw new RecordDraftError(fieldId, '此必填字段不可填写，当前表结构无法新增记录')
      continue
    }
    try {
      const value = parseScalarDraft(field.type, drafts[fieldId] ?? scalarDraft(undefined))
      // A PATCH omission leaves the existing value untouched; only explicit null clears it.
      if (record && (value === undefined || sameValue(value, cell?.value))) continue
      checkValue(field, value)
      if (value !== undefined) values.push({ fieldId, value })
    } catch (error) {
      throw new RecordDraftError(fieldId, error instanceof Error ? error.message : '字段值无效')
    }
  }
  return values
}
