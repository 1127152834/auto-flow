import { describe, expect, it } from 'vitest'
import { emptyFieldForm, fieldDefinition, fieldFormSchema } from './field-form-schema'

describe('field form schema', () => {
  it('trims names and keys by Unicode code points', () => {
    expect(fieldDefinition({ ...emptyFieldForm, key: ' key ', name: ' Name ' })).toMatchObject({ key: 'key', name: 'Name' })
    expect(fieldFormSchema.safeParse({ ...emptyFieldForm, key: 'x'.repeat(121), name: 'n' }).success).toBe(false)
  })
  it('rejects controls and inconsistent rules without interpreting Python regex', () => {
    expect(fieldFormSchema.safeParse({ ...emptyFieldForm, key: 'a\nb', name: 'n' }).success).toBe(false)
    expect(fieldFormSchema.safeParse({ ...emptyFieldForm, key: 'k', name: 'n', minLength: '3', maxLength: '2' }).success).toBe(false)
    expect(fieldDefinition({ ...emptyFieldForm, key: 'k', name: 'n', pattern: '(?P<python>.*)' }).validation.pattern).toBe('(?P<python>.*)')
  })
  it('drops rules from the previous type', () => {
    expect(fieldDefinition({ ...emptyFieldForm, key: 'k', name: 'n', type: 'number', minLength: '4', pattern: 'x', minimum: '1' }).validation).toEqual({ minimum: 1 })
    expect(fieldDefinition({ ...emptyFieldForm, key: 'k', name: 'n', type: 'boolean', minLength: '-', minimum: 'bad' }).validation).toEqual({})
  })
  it('rejects whitespace, non-finite values, and unsafe integer bounds', () => {
    for (const minimum of [' ', 'Infinity', '1e400', '9007199254740992']) {
      expect(fieldFormSchema.safeParse({ ...emptyFieldForm, key: 'k', name: 'n', type: 'number', minimum }).success).toBe(false)
    }
  })
})
