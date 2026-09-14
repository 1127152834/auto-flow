import { expect, it } from 'vitest'
import { applySchemaField, createSchemaDraft, schemaChanges } from './schema-draft'
import type { components } from '../../shared/api/generated'

const field: components['schemas']['DataFieldView'] = { ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: 'f' }, key: 'title', name: '标题', type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 2 }

it('keeps complete stable identities and revisions when a display name changes', () => {
  const original = createSchemaDraft('g', { tableRevision: 3, items: [field] })
  const changed = applySchemaField(original, 'f', { definition: { ...original.fields[0].definition, name: '文章标题' } })
  expect(original.fields[0].definition.name).toBe('标题')
  expect(changed.fields[0]).toMatchObject({ fieldId: 'f', expectedFieldRevision: 2, definition: { key: 'title', name: '文章标题' } })
  expect(schemaChanges(original, changed)).toEqual([{ id: 'f', name: '文章标题', key: 'title', summary: '显示名称："标题" → "文章标题"' }])
})

it('summarizes each actual property change and removed constraints without changing the candidate', () => {
  const original = createSchemaDraft('g', { tableRevision: 3, items: [{ ...field, type: 'date', validation: { pattern: '^old$', minimum: 0 } }] })
  const changed = applySchemaField(original, 'f', { definition: { key: 'title', name: '标题', type: 'string', required: true, validation: { minLength: 0, maxLength: 100, pattern: '^new$' } } })
  const snapshot = structuredClone(changed)
  const summary = schemaChanges(original, changed)[0].summary
  expect(summary.split('\n')).toEqual([
    '类型：日期 → 文本', '必填：否 → 是', '最长长度：未设置 → 100', '最短长度：未设置 → 0',
    '最小值：0 → 未设置', '正则表达式："^old$" → "^new$"',
  ])
  expect(summary).not.toContain('显示名称')
  expect(changed).toEqual(snapshot)
  expect(schemaChanges(original, original)).toEqual([])
})

it.each([
  [{}, '未设置'],
  [{ existingRecordDefault: null }, 'null（空值）'],
  [{ existingRecordDefault: false }, 'false'],
  [{ existingRecordDefault: 0 }, '0'],
  [{ existingRecordDefault: '' }, '""（空字符串）'],
  [{ existingRecordDefault: 'null' }, '"null"'],
  [{ existingRecordDefault: { kind: 'date' as const, precision: 'datetime' as const, value: '2026-09-14T12:30:45.123', offset: '+08:00' } }, '{"kind":"date","precision":"datetime","value":"2026-09-14T12:30:45.123","offset":"+08:00"}'],
])('shows a new field definition and its exact default presence: %j', (defaultValue, expected) => {
  const original = createSchemaDraft('g', { tableRevision: 1, items: [] })
  const changed = applySchemaField(original, null, { definition: { key: 'note', name: '摘要', type: 'string', required: false, validation: { maxLength: 100 } }, ...defaultValue }, 'new')
  expect(schemaChanges(original, changed)[0].summary.split('\n')).toEqual([
    '新增字段', '类型：文本', '必填：否', '最长长度：100', `现有记录默认值：${expected}`,
  ])
})

it('preserves unknown validation facts and distinguishes missing from explicit null', () => {
  const original = createSchemaDraft('g', { tableRevision: 3, items: [field] })
  const changed = applySchemaField(original, 'f', { definition: { ...original.fields[0].definition, validation: { custom: null, maximum: 0 } } })
  expect(schemaChanges(original, changed)[0].summary).toBe('校验规则 custom：未设置 → null（空值）\n最大值：未设置 → 0')
})

it('keeps missing and explicit null distinct for a new local field', () => {
  const original = createSchemaDraft('g', { tableRevision: 1, items: [] })
  const definition = { key: 'note', name: '摘要', type: 'string' as const, required: false, validation: {} }
  const added = applySchemaField(original, null, { definition }, 'client')
  expect(added.fields[0]).not.toHaveProperty('existingRecordDefault')
  const edited = applySchemaField(added, 'client', { definition, existingRecordDefault: null })
  expect(edited.fields[0]).toMatchObject({ kind: 'new', clientId: 'client', sourceColumnPolicy: 'localOnly', existingRecordDefault: null })
})

it('rejects duplicate keys and missing target without losing the draft', () => {
  const original = createSchemaDraft('g', { tableRevision: 3, items: [field] })
  expect(() => applySchemaField(original, null, { definition: original.fields[0].definition }, 'client')).toThrow('字段键')
  expect(() => applySchemaField(original, 'unknown', { definition: original.fields[0].definition })).toThrow('不存在')
  expect(original.fields).toHaveLength(1)
})
