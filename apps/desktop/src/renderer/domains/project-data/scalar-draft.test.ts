import { expect, it } from 'vitest'
import { parseScalarDraft, scalarDraft } from './scalar-draft'

it('keeps missing, null, empty string, boolean, number and date distinct', () => {
  expect(scalarDraft(undefined).presence).toBe('missing')
  expect(scalarDraft(null).presence).toBe('null')
  expect(scalarDraft('').presence).toBe('value')
  expect(parseScalarDraft('string', scalarDraft(' 001 '))).toBe(' 001 ')
  expect(parseScalarDraft('boolean', scalarDraft(false))).toBe(false)
  expect(parseScalarDraft('number', scalarDraft(12.5))).toBe(12.5)
  const date = { kind: 'date' as const, precision: 'datetime' as const, value: '2024-02-29T23:59:59.1234567', offset: '+23:59' }
  expect(parseScalarDraft('date', scalarDraft(date))).toEqual(date)
})

it('returns undefined or null for their explicit presence', () => {
  expect(parseScalarDraft('string', { ...scalarDraft('x'), presence: 'missing' })).toBeUndefined()
  expect(parseScalarDraft('number', { ...scalarDraft(1), presence: 'null' })).toBeNull()
})

it('rejects unsafe or non-finite numeric text', () => {
  for (const text of ['', 'NaN', 'Infinity', '9007199254740992', '0x10']) {
    expect(() => parseScalarDraft('number', { ...scalarDraft(0), text })).toThrow(/数字/)
  }
})

it('validates calendar dates and timezone text without normalizing them', () => {
  const draft = { ...scalarDraft(null), presence: 'value' as const, precision: 'date' as const, text: '2024-02-29' }
  expect(parseScalarDraft('date', draft)).toEqual({ kind: 'date', precision: 'date', value: '2024-02-29', offset: null })
  expect(() => parseScalarDraft('date', { ...draft, text: '2023-02-29' })).toThrow(/日期/)
  const datetime = { ...draft, precision: 'datetime' as const, text: '2026-09-13T10:30:00.1234567', offset: 'Z' }
  expect(parseScalarDraft('date', datetime)).toEqual({ kind: 'date', precision: 'datetime', value: datetime.text, offset: 'Z' })
  for (const offset of ['+00:99', '-01:60', '+24:00']) expect(() => parseScalarDraft('date', { ...datetime, offset })).toThrow(/时区/)
  expect(() => parseScalarDraft('date', { ...datetime, text: `${datetime.text}Z` })).toThrow(/日期/)
})
