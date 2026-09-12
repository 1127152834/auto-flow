import { expect, it } from 'vitest'
import { dataTableFormSchema } from './form-schema'

it('trims a Unicode table name and preserves the description', () => {
  expect(dataTableFormSchema.parse({ name: '  客户😀  ', description: '  说明  ' })).toEqual({ name: '客户😀', description: '  说明  ' })
})

it('counts Unicode code points and rejects values outside the contract', () => {
  expect(dataTableFormSchema.safeParse({ name: '😀'.repeat(120), description: 'x'.repeat(1000) }).success).toBe(true)
  expect(dataTableFormSchema.safeParse({ name: '😀'.repeat(121), description: '' }).success).toBe(false)
  expect(dataTableFormSchema.safeParse({ name: 'x', description: '😀'.repeat(1001) }).success).toBe(false)
})
