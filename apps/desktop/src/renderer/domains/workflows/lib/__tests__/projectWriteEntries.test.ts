import { describe, expect, it } from 'vitest'
import { moduleCategories, projectWriteDefaults, projectWriteEntries } from '../moduleCatalog'

describe('project write-back catalog entries', () => {
  it('offers the four entries as project_data operations', () => {
    expect(projectWriteEntries.map(entry => [entry.label, entry.operation])).toEqual([
      ['更新当前记录', 'updateRecord'], ['设置状态', 'setRecordStatus'], ['新增记录', 'createRecord'], ['查询记录', 'queryRecords'],
    ])
    expect(new Set(projectWriteEntries.map(entry => entry.id)).size).toBe(4)
  })
  it('presets operation, empty arguments and a result variable on the new node', () => {
    for (const entry of projectWriteEntries) expect(projectWriteDefaults(entry)).toEqual({ operation: entry.operation, arguments: {}, variableName: entry.variableName })
  })
  it('names the business scenarios they serve', () => {
    for (const entry of projectWriteEntries) expect(entry.description).toMatch(/批量录入|多账号运营|批量运行|账号/)
  })
  it('keeps the generic project_data module so old workflows still open', () => {
    expect(moduleCategories.some(category => category.modules.includes('project_data'))).toBe(true)
  })
})
