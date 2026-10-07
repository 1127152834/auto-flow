import { describe, expect, it } from 'vitest'
import { autoMatchBindings, normalizeFieldName, typeMismatch, typesCompatible } from './field-matching'

const ref = (fieldId: string) => ({ projectId: 'p', tableId: 't', datasetGeneration: 'g', fieldId })
const column = (fieldId: string, name: string, type: 'string' | 'number' | 'boolean' | 'date') => ({ ref: ref(fieldId), key: fieldId, name, type }) as never
const group = (fields: { key: string; name: string; type: 'string' | 'number' | 'boolean' | 'date' | 'any'; required?: boolean }[]) => ({ key: 'g', name: '组', fields: fields.map(field => ({ required: false, sensitive: false, ...field })) })

describe('normalizeFieldName', () => {
  it('ignores case, whitespace and full-width forms', () => {
    expect(normalizeFieldName(' Ｅmail　Address ')).toBe('emailaddress')
    expect(normalizeFieldName('用户 名')).toBe('用户名')
  })
})

describe('typesCompatible', () => {
  it('accepts equal types and any, rejects the rest', () => {
    expect(typesCompatible('string', 'string')).toBe(true)
    expect(typesCompatible('any', 'date')).toBe(true)
    expect(typesCompatible('number', 'string')).toBe(false)
    expect(typeMismatch('number', 'string')).toBe('流程需要数字，所选字段是文本')
    expect(typeMismatch('any', 'string')).toBeNull()
  })
})

describe('autoMatchBindings', () => {
  const fields = [column('f1', '标题', 'string'), column('f2', '页　数', 'number'), column('f3', 'Price', 'string')]
  it('binds by normalized name with compatible type only', () => {
    const result = autoMatchBindings(group([{ key: 'title', name: '标题', type: 'string' }, { key: 'pages', name: '页数', type: 'number' }, { key: 'price', name: 'price', type: 'number' }]), [], fields)
    expect(result.map(item => [item.signatureField, item.fieldRef.fieldId, item.inputFieldAlias])).toEqual([['title', 'f1', '标题'], ['pages', 'f2', '页数']])
  })
  it('never overrides an existing binding or reuses a bound table field', () => {
    const existing = [{ inputFieldId: 'b', inputFieldAlias: '我的', fieldRef: ref('f1'), signatureField: 'other' }, { inputFieldId: 'c', inputFieldAlias: '页数', fieldRef: ref('f9'), signatureField: 'pages' }]
    const result = autoMatchBindings(group([{ key: 'title', name: '标题', type: 'string' }, { key: 'pages', name: '页数', type: 'number' }]), existing, fields)
    expect(result).toEqual([])
  })
  it('matches the field key when the display name differs', () => {
    const result = autoMatchBindings(group([{ key: 'price', name: '价格', type: 'string' }]), [], fields)
    expect(result.map(item => item.fieldRef.fieldId)).toEqual(['f3'])
  })
})
