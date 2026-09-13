import type { components } from '../../shared/api/generated'
import { parseScalarDraft, scalarDraft, ScalarDraftError, type Scalar, type ScalarDraft, type ScalarDraftControl } from './scalar-draft'

type Field = components['schemas']['DataFieldView']
type RecordView = components['schemas']['DataRecordView']
export type RecordDraft = Record<string, ScalarDraft>

export class RecordDraftError extends Error {
  constructor(readonly fieldId: string, message: string, readonly control: ScalarDraftControl = 'value') { super(message); this.name = 'RecordDraftError' }
}

export function createRecordDraft(fields: Field[], record?: RecordView, submittedValues?: components['schemas']['DataCellWrite'][]): RecordDraft {
  const cells = new Map(record?.values.map(cell => [cell.fieldId, cell]))
  const submitted = new Map(submittedValues?.map(value => [value.fieldId, value.value]))
  return Object.fromEntries(fields.map(field => {
    const fieldId=field.ref.fieldId,cell = cells.get(fieldId),mayOverride=!field.formula&&field.writable&&cell?.readable!==false&&submitted.has(fieldId)
    return [fieldId, scalarDraft(mayOverride?submitted.get(fieldId):cell?.readable ? cell.value : undefined)]
  }))
}

function checkValue(field: Field, value: Scalar | undefined): void {
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
      if (!record && field.required) throw new RecordDraftError(fieldId, '此必填字段不可填写，当前表结构无法新增记录', 'presence')
      continue
    }
    let value: Scalar | undefined
    try { value = parseScalarDraft(field.type, drafts[fieldId] ?? scalarDraft(undefined)) } catch (error) {
      throw new RecordDraftError(fieldId, error instanceof Error ? error.message : '字段值无效', error instanceof ScalarDraftError ? error.control : 'value')
    }
    // A PATCH omission leaves the existing value untouched; only explicit null clears it.
    if (record && (value === undefined || sameValue(value, cell?.value))) continue
    if (field.required && (value === undefined || value === null || value === '')) throw new RecordDraftError(fieldId, '请填写必填字段', value === '' ? 'value' : 'presence')
    try { checkValue(field, value) } catch (error) {
      throw new RecordDraftError(fieldId, error instanceof Error ? error.message : '字段值无效', 'value')
    }
    if (value !== undefined) values.push({ fieldId, value })
  }
  return values
}
