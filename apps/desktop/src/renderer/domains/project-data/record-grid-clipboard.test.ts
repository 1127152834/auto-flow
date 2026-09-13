import { expect, it } from 'vitest'
import { parseGridClipboard, pasteGridCells } from './record-grid-clipboard'
import { addDraftRow, draftHistory, gridValues, undoDraft } from './record-grid-draft'
import type { components } from '../../shared/api/generated'
const field = (id: string, type: 'string' | 'boolean' | 'number' = 'string'): components['schemas']['DataFieldView'] => ({ ref: { projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId: id }, key: id, name: id, type, required: false, validation: {}, writable: true, formula: false, fieldRevision: 1 })
it('parses quoted tabs newlines escaped quotes and explicit empty strings', () => {
  expect(parseGridClipboard('001\t"green\thouse"\r\n""\t"line1\n""line2"""\n')).toEqual([
    [{ text: '001', quoted: false }, { text: 'green\thouse', quoted: true }],
    [{ text: '', quoted: true }, { text: 'line1\n"line2"', quoted: true }],
  ])
  expect(parseGridClipboard('a\n\nb')).toHaveLength(3)
})
it('pastes one undoable rectangle without coercing zero false or leading zeros', () => {
  const fields = [field('text'), field('flag', 'boolean'), field('num', 'number')]
  const original = addDraftRow(draftHistory(), fields)
  const pasted = pasteGridCells(original, fields, fields, 0, 0, '001\tfalse\t0\n=SUM(A1)\tTRUE\t2')
  expect(gridValues(fields, pasted.rows).rows.map(r => r.values.map(v => v.value))).toEqual([['001', false, 0], ['=SUM(A1)', true, 2]])
  expect(undoDraft(pasted).rows).toEqual(original.rows)
})
it('preserves invalid boolean text as a cell error instead of silently choosing false', () => {
  const fields = [field('flag', 'boolean')]
  const pasted = pasteGridCells(addDraftRow(draftHistory(), fields), fields, fields, 0, 0, 'maybe')
  expect(pasted.rows[0].cells.flag.text).toBe('maybe')
  expect(gridValues(fields, pasted.rows).errors[0].fieldId).toBe('flag')
})
it('rejects whole paste on overflow readonly malformed or oversize input', () => {
  const fields = [field('text')], state = addDraftRow(draftHistory(), fields)
  for (const value of ['a\tb', Array(101).fill('x').join('\n'), 'x'.repeat(1024 * 1024 + 1), '"unclosed']) {
    expect(() => pasteGridCells(state, fields, fields, 0, 0, value)).toThrow()
  }
  expect(() => pasteGridCells(state, fields, [{ ...fields[0], writable: false }], 0, 0, 'x')).toThrow()
  expect(state.rows[0].cells.text.presence).toBe('missing')
})
