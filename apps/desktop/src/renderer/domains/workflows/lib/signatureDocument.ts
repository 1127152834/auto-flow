// Studio-side model of `content.signature` (inputs a workflow needs). Mirrors the backend rules in
// domain/workflows/signature.py so problems surface before saving; the backend stays authoritative.

export type SignatureSample = string | number | boolean
export interface SignatureFieldDraft {
  key: string
  name: string
  type: string
  required: boolean
  sensitive: boolean
  sample?: SignatureSample
  /** The key was typed by hand, so it is never regenerated from the name. Draft-only; not written to the document. */
  keyEdited?: boolean
  /** Keys this editor does not know; written back untouched. */
  rest: Record<string, unknown>
}
export interface SignatureInputDraft {
  key: string
  name: string
  fields: SignatureFieldDraft[]
  /** Draft-only; see SignatureFieldDraft.keyEdited. */
  keyEdited?: boolean
  rest: Record<string, unknown>
}
export interface SignatureIssue { path: string; message: string }
export interface SignatureDocument { inputs: SignatureInputDraft[]; rest: Record<string, unknown>; issues: SignatureIssue[] }

export const SIGNATURE_FIELD_TYPES = ['string', 'number', 'boolean', 'date', 'any'] as const
const KEY = /^[A-Za-z_一-龥][A-Za-z0-9_一-龥]{0,63}$/
const KEY_HINT = '只能包含字母、数字、下划线或中文，且不能以数字开头'

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown) => typeof value === 'string' ? value.trim() : ''
const without = (source: Record<string, unknown>, known: string[]) => Object.fromEntries(Object.entries(source).filter(([key]) => !known.includes(key)))

export function parseSignatureDocument(raw: unknown): SignatureDocument {
  if (raw == null) return { inputs: [], rest: {}, issues: [] }
  if (!isRecord(raw) || (raw.inputs !== undefined && !Array.isArray(raw.inputs))) return { inputs: [], rest: {}, issues: [{ path: 'signature', message: '流程输入格式不正确' }] }
  const issues: SignatureIssue[] = []
  const inputs: SignatureInputDraft[] = []
  ;((raw.inputs as unknown[] | undefined) ?? []).forEach((item, index) => {
    if (!isRecord(item)) { issues.push({ path: `signature.inputs.${index}`, message: '流程输入格式不正确' }); return }
    const fields: SignatureFieldDraft[] = []
    for (const [fieldIndex, field] of (Array.isArray(item.fields) ? item.fields : []).entries()) {
      if (!isRecord(field)) { issues.push({ path: `signature.inputs.${index}.fields.${fieldIndex}`, message: '字段格式不正确' }); continue }
      const sample = field.sample
      fields.push({
        key: text(field.key), name: text(field.name) || text(field.key), type: typeof field.type === 'string' ? field.type : 'string',
        required: field.required === true, sensitive: field.sensitive === true,
        ...(sample !== undefined && sample !== null ? { sample: sample as SignatureSample } : {}),
        rest: without(field, ['key', 'name', 'type', 'required', 'sensitive', 'sample']),
      })
    }
    inputs.push({ key: text(item.key), name: text(item.name) || text(item.key), fields, rest: without(item, ['key', 'name', 'fields']) })
  })
  return { inputs, rest: without(raw, ['inputs']), issues: [...issues, ...validateSignature(inputs)] }
}

function sampleProblem(type: string, sample: SignatureSample): string | null {
  if (type === 'string') return typeof sample === 'string' ? null : '样例值需要是文本'
  if (type === 'number') return typeof sample === 'number' && Number.isFinite(sample) ? null : '样例值需要是数字'
  if (type === 'boolean') return typeof sample === 'boolean' ? null : '样例值需要是“是”或“否”'
  if (type === 'date') {
    const valid = typeof sample === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(sample) && !Number.isNaN(Date.parse(`${sample}T00:00:00Z`)) && new Date(`${sample}T00:00:00Z`).toISOString().startsWith(sample)
    return valid ? null : '样例值需要是 年-月-日 格式的日期'
  }
  return ['string', 'number', 'boolean'].includes(typeof sample) ? null : '样例值需要是文本、数字或“是/否”'
}

export function validateSignature(inputs: SignatureInputDraft[]): SignatureIssue[] {
  const issues: SignatureIssue[] = []
  inputs.forEach((input, index) => {
    const path = `signature.inputs.${index}`
    if (!KEY.test(input.key)) issues.push({ path: `${path}.key`, message: `流程输入标识${KEY_HINT}` })
    else if (inputs.findIndex(item => item.key === input.key) !== index) issues.push({ path: `${path}.key`, message: `流程输入标识「${input.key}」重复` })
    input.fields.forEach((field, fieldIndex) => {
      const fieldPath = `${path}.fields.${fieldIndex}`
      if (!KEY.test(field.key)) { issues.push({ path: `${fieldPath}.key`, message: `字段标识${KEY_HINT}` }); return }
      if (input.fields.findIndex(item => item.key === field.key) !== fieldIndex) { issues.push({ path: `${fieldPath}.key`, message: `字段标识「${field.key}」重复` }); return }
      if (!(SIGNATURE_FIELD_TYPES as readonly string[]).includes(field.type)) { issues.push({ path: `${fieldPath}.type`, message: '字段类型不受支持' }); return }
      if (field.sample === undefined) return
      const problem = field.sensitive ? '敏感字段不能保存样例值' : sampleProblem(field.type, field.sample)
      if (problem) issues.push({ path: `${fieldPath}.sample`, message: problem })
    })
  })
  return issues
}

export function serializeSignature(inputs: SignatureInputDraft[], rest: Record<string, unknown>): Record<string, unknown> {
  return {
    ...rest,
    inputs: inputs.map(input => ({
      ...input.rest, key: input.key, name: input.name,
      fields: input.fields.map(({ rest: extra, sample, keyEdited: _hand, ...field }) => ({ ...extra, ...field, ...(sample !== undefined ? { sample } : {}) })),
    })),
  }
}
