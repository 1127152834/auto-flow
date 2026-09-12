import { expect, it } from 'vitest'
import type { components } from '../../shared/api/generated'
import { createRecordDraft, recordValues, RecordDraftError } from './record-draft'
import { scalarDraft } from './scalar-draft'
type Schema = components['schemas']
const field = (id: string, extra: Partial<Schema['DataFieldView']> = {}): Schema['DataFieldView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: id }, key: id, name: id, type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1, ...extra })
const record = (values: Schema['DataCellView'][]): Schema['DataRecordView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', recordKey: { type: 'text', value: '001' } }, values, recordSlots: [], statusId: null, currentEnvironmentId: null, contentRevision: 4, statusRevision: 2, linkRevision: 1, deleted: false, createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z' })
const cell = (fieldId: string, value: Schema['DataCellView']['value'], readable = true): Schema['DataCellView'] => ({ fieldId, value, readable, source: 'local' })

it('keeps missing, null, empty and whitespace distinct in create values', () => {
  const fields = ['missing', 'null', 'empty', 'space'].map(id => field(id))
  const drafts = createRecordDraft(fields)
  drafts.null = scalarDraft(null); drafts.empty = scalarDraft(''); drafts.space = scalarDraft('  ')
  expect(recordValues(fields, drafts)).toEqual([{ fieldId: 'null', value: null }, { fieldId: 'empty', value: '' }, { fieldId: 'space', value: '  ' }])
  expect(recordValues([], {})).toEqual([])
})
it.each([undefined, null, ''])('rejects missing/null/empty required text with field identity', value => {
  const fields = [field('title', { required: true })]
  expect(() => recordValues(fields, { title: scalarDraft(value) })).toThrow(RecordDraftError)
  try { recordValues(fields, { title: scalarDraft(value) }) } catch (error) { expect(error).toHaveProperty('fieldId', 'title') }
  expect(recordValues(fields, { title: scalarDraft(' ') })).toEqual([{ fieldId: 'title', value: ' ' }])
})
it('counts Unicode code points and applies numerical boundaries without interpreting Python regex', () => {
  const fields = [field('text', { validation: { minLength: 2, maxLength: 2, pattern: '\\A..\\Z' } }), field('number', { type: 'number', validation: { minimum: 1, maximum: 3 } })]
  expect(recordValues(fields, { text: scalarDraft('😀中'), number: scalarDraft(3) })).toHaveLength(2)
  expect(() => recordValues(fields, { text: scalarDraft('😀'), number: scalarDraft(2) })).toThrow('长度')
  expect(() => recordValues(fields, { text: scalarDraft('😀中'), number: scalarDraft(4) })).toThrow('最大值')
  expect(() => recordValues(fields, { text: scalarDraft('😀中'), number: scalarDraft(Infinity) })).toThrow(RecordDraftError)
})
it('edits only changed fields, omits protected values, and never writes record metadata', () => {
  const fields = [field('identity'), field('same'), field('change'), field('formula', { formula: true }), field('locked', { writable: false }), field('secret')]
  const initial = record([cell('identity', '001'), cell('same', 'same'), cell('change', 'old'), cell('formula', 'calculated'), cell('locked', 'locked'), cell('secret', 'hidden', false)])
  const drafts = createRecordDraft(fields, initial)
  drafts.identity = scalarDraft('002'); drafts.formula = scalarDraft('wrong'); drafts.locked = scalarDraft('wrong'); drafts.secret = scalarDraft('wrong'); drafts.change = scalarDraft(null)
  expect(recordValues(fields, drafts, initial, 'identity')).toEqual([{ fieldId: 'change', value: null }])
  expect(createRecordDraft(fields, initial).secret.presence).toBe('missing')
})
it('preserves arbitrary date precision and only writes genuinely changed dates', () => {
  const fields = [field('date', { type: 'date' })]
  const value: Schema['DataDateScalar'] = { kind: 'date', precision: 'datetime', value: '2026-09-13T12:34:56.123456789123456789123456789', offset: '+08:00' }
  const initial = record([cell('date', value)]), drafts = createRecordDraft(fields, initial)
  expect(recordValues(fields, drafts, initial)).toEqual([])
  drafts.date.offset = ''
  expect(recordValues(fields, drafts, initial)).toEqual([{ fieldId: 'date', value: { ...value, offset: null } }])
})
it('does not reinterpret omitted edits as null or send unchanged empty strings', () => {
  const fields = [field('empty'), field('missing')], initial = record([cell('empty', '')])
  const drafts = createRecordDraft(fields, initial)
  expect(recordValues(fields, drafts, initial)).toEqual([])
  drafts.missing = scalarDraft(null)
  expect(recordValues(fields, drafts, initial)).toEqual([{ fieldId: 'missing', value: null }])
})
