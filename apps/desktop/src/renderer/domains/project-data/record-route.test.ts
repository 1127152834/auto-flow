import { describe, expect, it } from 'vitest'
import { decodeRecordKey, encodeRecordKey } from './record-route'

describe('record route identity', () => {
  it.each(['001', '1', '中文/📄?x=1', '\uFEFF记录', '\uFEFF', '文'.repeat(8000)])('round trips text without changing its identity', value => {
    expect(decodeRecordKey('text', encodeRecordKey({ type: 'text', value }))).toEqual({ type: 'text', value })
  })

  it.each(['0', '-1', String(Number.MAX_SAFE_INTEGER), String(Number.MIN_SAFE_INTEGER)])('round trips canonical safe integers', value => {
    expect(decodeRecordKey('integer', encodeRecordKey({ type: 'integer', value }))).toEqual({ type: 'integer', value })
  })

  it('round trips only lowercase standard UUID identities', () => {
    const value = '123e4567-e89b-12d3-a456-426614174000'
    expect(decodeRecordKey('uuid', encodeRecordKey({ type: 'uuid', value }))).toEqual({ type: 'uuid', value })
  })

  it('retains key type independently', () => {
    const value = encodeRecordKey({ type: 'text', value: '1' })
    expect(decodeRecordKey('text', value)).not.toEqual(decodeRecordKey('integer', value))
  })

  it.each([
    { type: 'text' as const, value: '' },
    { type: 'text' as const, value: '\ud800' },
    { type: 'text' as const, value: '文'.repeat(8001) },
    { type: 'integer' as const, value: '001' },
    { type: 'integer' as const, value: '+1' },
    { type: 'integer' as const, value: '-0' },
    { type: 'integer' as const, value: String(Number.MAX_SAFE_INTEGER + 1) },
    { type: 'integer' as const, value: String(Number.MIN_SAFE_INTEGER - 1) },
    { type: 'uuid' as const, value: '123E4567-E89B-12D3-A456-426614174000' },
  ])('rejects invalid record key $type:$value', key => {
    expect(() => encodeRecordKey(key)).toThrow()
  })

  it.each(['MQ==', 'M+', 'M/', 'M', '_w', '4A', 'Zh'])('rejects padding, alphabet errors, malformed bytes, bad UTF-8, and noncanonical trailing bits: %s', encoded => {
    expect(() => decodeRecordKey('text', encoded)).toThrow()
  })
})
