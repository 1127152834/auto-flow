import type { components } from '../../../../shared/api/generated'
import type { InputDefinition, InputTableOption } from './types'

type Schema = components['schemas']
type Binding = InputDefinition['fieldBindings'][number]
type SignatureType = Schema['WorkflowSignatureField']['type']

const typeNames: Record<string, string> = { string: '文本', number: '数字', boolean: '是否', date: '日期', any: '任意类型' }
export const typeName = (type: string) => typeNames[type] ?? type

/** Names match when case, whitespace and full/half-width forms are ignored. */
export const normalizeFieldName = (name: string) => name.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
export const typesCompatible = (required: SignatureType, actual: string) => required === 'any' || required === actual
export const typeMismatch = (required: SignatureType, actual: string) => typesCompatible(required, actual) ? null : `流程需要${typeName(required)}，所选字段是${typeName(actual)}`

/** Proposes new bindings for unbound signature fields only; existing bindings are never changed. */
export function autoMatchBindings(group: Schema['WorkflowSignatureInput'], existing: Binding[], fields: InputTableOption['fields']): Binding[] {
  const used = new Set(existing.map(binding => binding.fieldRef.fieldId))
  const bound = new Set(existing.map(binding => binding.signatureField).filter(Boolean))
  const added: Binding[] = []
  for (const signatureField of group.fields) {
    if (bound.has(signatureField.key)) continue
    const names = [normalizeFieldName(signatureField.name), normalizeFieldName(signatureField.key)]
    const match = fields.find(field => !used.has(field.ref.fieldId) && typesCompatible(signatureField.type, field.type) && (names.includes(normalizeFieldName(field.name)) || names.includes(normalizeFieldName(field.key))))
    if (!match) continue
    used.add(match.ref.fieldId)
    added.push({ inputFieldId: crypto.randomUUID(), inputFieldAlias: signatureField.name, fieldRef: match.ref, signatureField: signatureField.key })
  }
  return added
}
