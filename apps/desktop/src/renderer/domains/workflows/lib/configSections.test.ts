import { readdirSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { ADVANCED_FIELDS, COMMON_ADVANCED, inSection, isAdvancedField, splitFields } from './configSections'

const panels = resolve(__dirname, '../components')
const PILOT_COMPONENTS: Record<string, string> = {
  open_page: 'OpenPageConfig',
  click_element: 'ClickElementConfig',
  input_text: 'InputTextConfig',
  get_element_info: 'GetElementInfoConfig',
  wait_element: 'WaitElementConfig',
  hover_element: 'HoverElementConfig',
}
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

  it('inSection 把字段分给且仅分给一个分段', () => {
    expect(inSection('click_element', 'followNewTab', 'advanced')).toBe(true)
    expect(inSection('click_element', 'followNewTab', 'basic')).toBe(false)
    expect(inSection('click_element', 'selector', 'basic')).toBe(true)
    expect(inSection('click_element', 'selector', 'advanced')).toBe(false)
    expect(inSection('click_element', 'followNewTab', 'all')).toBe(true)
  })

  it('ADVANCED_FIELDS 的每个 key 真实出现在对应节点的配置组件函数中（跨配置文件）', () => {
    const files = readdirSync(resolve(panels, 'config-panels')).filter(f => f.endsWith('.tsx') && !f.endsWith('.test.tsx'))
    const sources = files.map(f => read(`config-panels/${f}`)).join('\n')
    for (const [moduleType, keys] of Object.entries(ADVANCED_FIELDS)) {
      const name = PILOT_COMPONENTS[moduleType]
      expect(name, `${moduleType} 未登记配置组件`).toBeTruthy()
      const start = sources.indexOf(`export function ${name}(`)
      expect(start, `找不到 ${name}`).toBeGreaterThanOrEqual(0)
      const body = sources.slice(start, sources.indexOf('\n}\n', start))
      for (const key of keys) expect(body, `${moduleType}.${key}`).toContain(`show('${key}')`)
    }
  })

  it('每个登记了高级字段的节点都由配置面板派发到试点配置组件', () => {
    const panel = read('ConfigPanel.tsx')
    for (const moduleType of Object.keys(ADVANCED_FIELDS)) expect(panel, moduleType).toContain(`case '${moduleType}':`)
  })

  it('COMMON_ADVANCED 的每个 key 真实出现在 ConfigPanel 源码中', () => {
    const source = read('ConfigPanel.tsx')
    for (const key of COMMON_ADVANCED) expect(source, key).toMatch(new RegExp(`['.]${key}\\b`))
  })
})
