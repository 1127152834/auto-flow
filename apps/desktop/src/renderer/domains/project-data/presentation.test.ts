import { expect, it } from 'vitest'
import type { components } from '../../shared/api/generated'
import { recordDisplayLabel } from './presentation'

type S = components['schemas']
const internal = '11111111-2222-4333-8444-555555555555'
const field = (fieldId: string): S['DataFieldView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId }, key: fieldId, name: fieldId, type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
const record = (values: S['DataCellView'][]): S['DataRecordView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'uuid', value: internal } }, values, recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 1, statusRevision: 1, linkRevision: 1, deleted: false, createdAt: '2026-09-15T04:41:00Z', updatedAt: '2026-09-15T04:41:00Z' })

it('hides system keys and uses the first readable business text', () => {
  expect(recordDisplayLabel({ mode: 'system' }, [field('title')], record([{ fieldId: 'title', value: '参数资料', readable: true, source: 'local' }]))).toBe('参数资料')
  expect(recordDisplayLabel({ mode: 'system' }, [], record([]))).toMatch(/^未命名记录 · /)
})

it('preserves a UUID supplied by the user as a field identity', () => {
  expect(recordDisplayLabel({ mode: 'field', fieldId: 'business-id' }, [field('business-id')], record([{ fieldId: 'business-id', value: internal, readable: true, source: 'local' }]))).toBe(internal)
  expect(recordDisplayLabel({ mode: 'field', fieldId: 'gone' }, [], record([]))).toBe('字段已失效')
})

it('does not promote a date scalar and preserves field identity whitespace', () => {
  const date = { ...field('when'), type: 'date' as const }
  const item = record([{ fieldId: 'when', value: '2026-09-15', readable: true, source: 'local' }, { fieldId: 'title', value: '业务标题', readable: true, source: 'local' }])
  expect(recordDisplayLabel({ mode: 'system' }, [date, field('title')], item)).toBe('业务标题')
  expect(recordDisplayLabel({ mode: 'field', fieldId: 'title' }, [field('title')], { ...item, ref: { ...item.ref, recordKey: { type: 'text', value: '  用户值  ' } } })).toBe('  用户值  ')
})
