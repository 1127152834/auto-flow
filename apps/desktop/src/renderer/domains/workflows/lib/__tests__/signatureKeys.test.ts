import { describe, expect, it } from 'vitest'
import { importCandidates, suggestKey } from '../signatureKeys'

describe('suggestKey', () => {
  it('turns a Chinese name into a pinyin key', () => {
    expect(suggestKey('账号', [])).toBe('zhanghao')
  })
  it('keeps letters and digits from mixed names', () => {
    expect(suggestKey('Email 地址', [])).toBe('emaildizhi')
  })
  it('falls back to a stable numbered key when nothing usable remains', () => {
    expect(suggestKey('！！', [])).toBe('field1')
    expect(suggestKey('', ['field1'])).toBe('field2')
  })
  it('never starts with a digit', () => {
    expect(suggestKey('123', [])).toBe('field123')
  })
  it('stays unique among taken keys', () => {
    expect(suggestKey('账号', ['zhanghao'])).toBe('zhanghao2')
    expect(suggestKey('账号', ['zhanghao', 'zhanghao2'])).toBe('zhanghao3')
  })
})

describe('importCandidates', () => {
  const fields = [
    { key: 'phone', name: '手机号', type: 'string', required: true },
    { key: '年龄', name: '年龄', type: 'number', required: false },
    { key: 'bad key!', name: '生日', type: 'date', required: false },
  ]
  it('maps table fields to signature fields and flags those already present', () => {
    const result = importCandidates(fields, ['phone'])
    expect(result.map(item => [item.name, item.exists])).toEqual([['手机号', true], ['年龄', false], ['生日', false]])
    expect(result[1]).toMatchObject({ key: '年龄', type: 'number', required: false })
  })
  it('derives a valid unique key when the table key is not usable', () => {
    expect(importCandidates(fields, [])[2].key).toBe('shengri')
  })
})

describe('suggestKey fallback prefix', () => {
  it('uses the given prefix for numbered keys', () => {
    expect(suggestKey('', ['group1'], 'group')).toBe('group2')
  })
})
