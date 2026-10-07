import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ADVANCED_FIELDS, COMMON_ADVANCED, isAdvancedField, splitFields } from './configSections'

const panels = resolve(__dirname, '../components')
const read = (rel: string) => readFileSync(resolve(panels, rel), 'utf8')

describe('configSections', () => {
  it('未登记字段默认为基本，登记字段与通用高级项为高级', () => {
    expect(isAdvancedField('click_element', 'selector')).toBe(false)
    expect(isAdvancedField('click_element', 'followNewTab')).toBe(true)
    expect(isAdvancedField('input_text', 'followNewTab')).toBe(false)
    expect(isAdvancedField('anything', 'timeout')).toBe(true)
  })

  it('splitFields 保持原顺序分成基本与高级', () => {
    expect(splitFields('click_element', ['selector', 'followNewTab', 'clickType', 'timeout'])).toEqual({
      basic: ['selector', 'clickType'],
      advanced: ['followNewTab', 'timeout'],
    })
  })

  it('ADVANCED_FIELDS 的每个 key 真实出现在节点配置组件源码中', () => {
    const source = read('config-panels/BasicModuleConfigs.tsx')
    for (const [moduleType, keys] of Object.entries(ADVANCED_FIELDS)) {
      for (const key of keys) expect(source, `${moduleType}.${key}`).toContain(`'${key}'`)
    }
  })

  it('COMMON_ADVANCED 的每个 key 真实出现在 ConfigPanel 源码中', () => {
    const source = read('ConfigPanel.tsx')
    for (const key of COMMON_ADVANCED) expect(source, key).toMatch(new RegExp(`['.]${key}\\b`))
  })
})
