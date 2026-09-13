import { expect, it } from 'vitest'
import { findExcludedModuleType } from '../lib/moduleCatalog'

it('checks cyclic module references at most once without changing their stored content', () => {
  const modules = {
    a: [{ type: 'custom_module', data: { customModuleId: 'b' } }],
    b: [{ type: 'custom_module', data: { customModuleId: 'a' } }, { type: 'open_page' }],
  }
  const before = structuredClone(modules)
  const visits: string[] = []
  expect(findExcludedModuleType([{ type: 'custom_module', data: { customModuleId: 'a' } }], id => {
    visits.push(id)
    return modules[id as keyof typeof modules]
  })).toBeNull()
  expect(visits).toEqual(['a', 'b'])
  expect(modules).toEqual(before)
})
