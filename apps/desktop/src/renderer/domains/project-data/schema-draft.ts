import type { components } from '../../shared/api/generated'
import type { SchemaFieldDraft } from './components/SchemaFieldDrawer'
import type { SchemaCandidate } from './schema-api'

export type SchemaField = SchemaCandidate['fields'][number]
export type SchemaChange = { id: string; name: string; key: string; summary: string }
export const schemaFieldId = (field: SchemaField) => field.kind === 'existing' ? field.fieldId : field.clientId
export const sameSchema = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b)
export function createSchemaDraft(generation: string, directory: components['schemas']['DataFieldDirectory']): SchemaCandidate {
  return { datasetGeneration: generation, expectedTableRevision: directory.tableRevision, fields: directory.items.map(field => ({
    kind: 'existing', fieldId: field.ref.fieldId, expectedFieldRevision: field.fieldRevision,
    definition: { key: field.key, name: field.name, type: field.type, required: field.required, validation: structuredClone(field.validation) },
  })) }
}

export function applySchemaField(candidate: SchemaCandidate, id: string | null, draft: SchemaFieldDraft, clientId: string = crypto.randomUUID()): SchemaCandidate {
  if (id !== null && !candidate.fields.some(field => schemaFieldId(field) === id)) throw new Error('该字段草稿已不存在')
  if (candidate.fields.some(field => schemaFieldId(field) !== id && field.definition.key === draft.definition.key)) throw new Error('字段键已存在，请使用不同的字段键')
  const next = structuredClone(candidate)
  if (id === null) next.fields.push({ kind: 'new', clientId, sourceColumnPolicy: 'localOnly', ...structuredClone(draft) })
  else next.fields = next.fields.map(field => {
    if (schemaFieldId(field) !== id) return field
    if (field.kind === 'existing') return { ...field, definition: structuredClone(draft.definition) }
    return { kind: 'new', clientId: field.clientId, sourceColumnPolicy: 'localOnly', ...structuredClone(draft) }
  })
  return next
}

export function schemaChanges(original: SchemaCandidate, candidate: SchemaCandidate): SchemaChange[] {
  const before = new Map(original.fields.map(field => [schemaFieldId(field), field]))
  return candidate.fields.filter(field => !sameSchema(before.get(schemaFieldId(field)), field)).map(field => ({
    id: schemaFieldId(field), name: field.definition.name, key: field.definition.key,
    summary: schemaChangeSummary(before.get(schemaFieldId(field)), field),
  }))
}

const typeNames = { string: '文本', number: '数字', boolean: '布尔', date: '日期' }
const ruleNames: Record<string, string> = { minLength: '最短长度', maxLength: '最长长度', pattern: '正则表达式', minimum: '最小值', maximum: '最大值' }
const summaryValue = (value: unknown): string => value === undefined ? '未设置' : value === null ? 'null（空值）' : value === '' ? '""（空字符串）' : JSON.stringify(value)

function schemaChangeSummary(before: SchemaField | undefined, field: SchemaField): string {
  const previous = before?.definition, next = field.definition
  const lines: string[] = []
  if (field.kind === 'new') {
    lines.push('新增字段', `类型：${typeNames[next.type]}`, `必填：${next.required ? '是' : '否'}`)
  } else if (previous) {
    for (const [key, label] of [['key', '字段键'], ['name', '显示名称'], ['type', '类型'], ['required', '必填']] as const) {
      if (previous[key] === next[key]) continue
      const format = (definition: SchemaField['definition']) => key === 'type' ? typeNames[definition.type] : key === 'required' ? (definition.required ? '是' : '否') : summaryValue(definition[key])
      lines.push(`${label}：${format(previous)} → ${format(next)}`)
    }
  }
  const previousRules = field.kind === 'new' ? {} : previous?.validation ?? {}
  for (const key of [...new Set([...Object.keys(previousRules), ...Object.keys(next.validation)])].sort()) {
    if (sameSchema(previousRules[key], next.validation[key])) continue
    const label = ruleNames[key] ?? `校验规则 ${key}`
    lines.push(`${label}：${field.kind === 'new' ? '' : `${summaryValue(previousRules[key])} → `}${summaryValue(next.validation[key])}`)
  }
  if (field.kind === 'new') lines.push(`现有记录默认值：${summaryValue(field.existingRecordDefault)}`)
  return lines.join('\n')
}
