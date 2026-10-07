import { describe, expect, it } from 'vitest'
import { coerceValue, conditionsFromFilter, filterFromConditions, recordFromRows, rowsFromRecord } from './projectDataForm'

describe('projectDataForm', () => {
  it('round-trips field values without changing them', () => {
    const record = { a: 'x', b: 3, c: true, d: '{var}' }
    expect(recordFromRows(rowsFromRecord(record))).toEqual(record)
  })
  it('drops rows without a field and coerces plain literals only', () => {
    expect(recordFromRows([{ fieldId: '', value: 'x' }, { fieldId: 'a', value: 1 }])).toEqual({ a: 1 })
    expect(coerceValue('number', '12')).toBe(12)
    expect(coerceValue('number', '{n}')).toBe('{n}')
    expect(coerceValue('boolean', 'true')).toBe(true)
    expect(coerceValue('string', '12')).toBe('12')
  })
  it('reads flat filters and builds the stored shape back', () => {
    const filter = { type: 'all', items: [{ type: 'compare', fieldId: 'a', operator: 'eq', value: 'x' }, { type: 'compare', fieldId: 'b', operator: 'isNull' }] }
    const conditions = conditionsFromFilter(filter)
    expect(conditions).toEqual([{ fieldId: 'a', operator: 'eq', value: 'x' }, { fieldId: 'b', operator: 'isNull' }])
    expect(filterFromConditions(conditions!)).toEqual(filter)
    expect(filterFromConditions([])).toBeNull()
  })
  it('refuses to flatten complex filters', () => {
    expect(conditionsFromFilter({ type: 'any', items: [] })).toBeNull()
    expect(conditionsFromFilter({ type: 'all', items: [{ type: 'status', operator: 'eq' }] })).toBeNull()
    expect(conditionsFromFilter(null)).toEqual([])
  })
})
