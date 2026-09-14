import { expect, it } from 'vitest'
import type { components } from '../../shared/api/generated'
import { addDraftRow, draftHistory, gridValues, hasDraftValues, undoDraft, updateDraftCell } from './record-grid-draft'
import { scalarDraft } from './scalar-draft'

type Field = components['schemas']['DataFieldView']
const field = (id: string, extra: Partial<Field> = {}): Field => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: id }, key: id, name: id, type: 'string', required: false, validation: {}, writable: true, formula: false, fieldRevision: 1, ...extra })

it('ignores untouched rows but preserves null empty text false and zero', () => {
  const fields = [field('text'), field('number', { type: 'number' }), field('boolean', { type: 'boolean' })]
  let state = addDraftRow(draftHistory(), fields)
  expect(hasDraftValues(state.rows)).toBe(false)
  expect(gridValues(fields, state.rows).rows).toEqual([])
  state = updateDraftCell(state, state.rows[0].clientRowId, 'text', scalarDraft(''))
  state = updateDraftCell(state, state.rows[0].clientRowId, 'number', scalarDraft(0))
  state = updateDraftCell(state, state.rows[0].clientRowId, 'boolean', scalarDraft(false))
  expect(gridValues(fields, state.rows).rows[0].values.map(c => c.value)).toEqual(['', 0, false])
  state = updateDraftCell(state, state.rows[0].clientRowId, 'text', scalarDraft(null))
  expect(gridValues(fields, state.rows).rows[0].values[0].value).toBeNull()
})
it('returns every field error with stable client row identity and submits no rows', () => {
  const fields = [field('title', { required: true }), field('amount', { type: 'number', required: true })]
  let state = addDraftRow(draftHistory(), fields)
  state = updateDraftCell(state, state.rows[0].clientRowId, 'amount', scalarDraft('001'))
  const result = gridValues(fields, state.rows)
  expect(result.rows).toEqual([])
  expect(result.errors.map(e => e.fieldId)).toEqual(['title', 'amount'])
  expect(result.errors.every(e => e.clientRowId === state.rows[0].clientRowId)).toBe(true)
})
it('undo preserves row identity and bounds history', () => {
  const fields = [field('title')]
  let state = addDraftRow(draftHistory(), fields)
  const id = state.rows[0].clientRowId
  for (let i = 0; i < 60; i++) state = updateDraftCell(state, id, 'title', scalarDraft(String(i)))
  expect(state.past).toHaveLength(50)
  expect(undoDraft(state).rows[0]).toMatchObject({ clientRowId: id, cells: { title: { text: '58' } } })
})
