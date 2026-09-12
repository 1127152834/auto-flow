import { describe, expect, it } from 'vitest'
import { projectFormSchema, toProjectCreate, toProjectPatch } from './form-schema'

describe('projectFormSchema', () => {
  it('uses Python-style stripping and counts Unicode code points', () => {
    expect(projectFormSchema.parse({ name: `  ${'😀'.repeat(36)}  `, description: '' }).name).toBe('😀'.repeat(36))
    expect(projectFormSchema.safeParse({ name: '😀'.repeat(37), description: '' }).success).toBe(false)
    expect(projectFormSchema.safeParse({ name: '\u00a0\t', description: '' }).success).toBe(false)
  })

  it('limits descriptions to 120 Unicode code points', () => {
    expect(projectFormSchema.safeParse({ name: '项目', description: '😀'.repeat(120) }).success).toBe(true)
    expect(projectFormSchema.safeParse({ name: '项目', description: '😀'.repeat(121) }).success).toBe(false)
  })

  it('writes only editable fields and preserves the expected revision on patch', () => {
    const values = { name: '  项目  ', description: '说明' }
    expect(toProjectCreate(values)).toEqual({ name: '项目', description: '说明' })
    expect(toProjectPatch(values, 7)).toEqual({ name: '项目', description: '说明', expectedManagementRevision: 7 })
  })
})
