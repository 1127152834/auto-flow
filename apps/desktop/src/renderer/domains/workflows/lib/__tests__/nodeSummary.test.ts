import { describe, expect, it } from 'vitest'
import type { ReferenceContext } from '../dataReferences'
import { INVALID_REFERENCE_LABEL } from '../dataReferences'
import { dataAccess, nodeDataTags, summarizeNode } from '../nodeSummary'

const context: ReferenceContext = {
  signature: { account: { label: '账号', fields: { email: { label: '邮箱' } } } },
  nodeOutputs: [{ nodeId: 'n_9f3a2b', key: 'text', name: '文本', label: '读取标题' }],
  variables: { 计数: {} },
}

describe('summarizeNode', () => {
  it('无引用时保持原摘要', () => {
    expect(summarizeNode({ moduleType: 'click_element', selector: '#submit' }, context).text).toBe('#submit')
    expect(summarizeNode({ moduleType: 'subflow', subflowName: '登录', url: 'x' }, context).text).toBe('登录')
    expect(summarizeNode({ moduleType: 'set_variable', variableName: 'a' }, context).text).toBe('→ a')
    expect(summarizeNode({ moduleType: 'x' }, context).text).toBe('')
  })

  it('覆盖两处旧实现各自的取值字段', () => {
    expect(summarizeNode({ logMessage: '开始' }, context).text).toBe('开始')
    expect(summarizeNode({ userPrompt: '请输入' }, context).text).toBe('请输入')
    expect(summarizeNode({ requestUrl: 'https://a.test' }, context).text).toBe('https://a.test')
    expect(summarizeNode({ filePath: 'C:/a.txt' }, context).text).toBe('C:/a.txt')
    expect(summarizeNode({ listVariable: '列表' }, context).text).toBe('列表')
    expect(summarizeNode({ text: '  ' }, context).text).toBe('')
  })

  it('引用显示成业务名，不含原始引用串或内部 id', () => {
    const summary = summarizeNode({ text: '登录 {input.account.email} 与 {node.n_9f3a2b.text}' }, context)
    expect(summary.text).toBe('登录 账号·邮箱 与 读取标题·文本')
    expect(summary.text).not.toMatch(/n_9f3a2b|[{}]/)
    expect(summary.parts.filter(part => part.type === 'ref')).toHaveLength(2)
  })

  it('失效引用显示为已失效的引用', () => {
    const summary = summarizeNode({ text: '{input.gone.x}' }, context)
    expect(summary.text).toBe(INVALID_REFERENCE_LABEL)
    expect(summary.parts[0]).toMatchObject({ type: 'ref', valid: false })
  })

  it('按显示文字截断，不切断引用', () => {
    const summary = summarizeNode({ text: '{input.account.email}'.repeat(20) }, context, 6)
    expect(summary.text.endsWith('…')).toBe(true)
    expect(summary.text).not.toContain('{')
    expect(summary.text.length).toBeLessThanOrEqual(7)
  })
})

describe('nodeDataTags', () => {
  it('收集配置里的引用，去重，跳过摘要里已显示的', () => {
    const data = { selector: '{input.account.email}', text: '{计数} {计数}', other: { deep: ['{node.n_9f3a2b.text}'] }, projectInputTypes: { "PROJECT_INPUTS['a']": 'string' } }
    const shown = summarizeNode(data, context)
    expect(nodeDataTags(data, context, shown).map(tag => tag.display)).toEqual(['计数', '读取标题·文本'])
    expect(nodeDataTags(data, context).map(tag => tag.display)).toEqual(['账号·邮箱', '计数', '读取标题·文本'])
  })

  it('不把代码里偶然的 {名字} 当作失效引用', () => {
    expect(nodeDataTags({ code: 'a{3} ${x}' }, context)).toEqual([])
    expect(nodeDataTags({ text: '{input.gone.x}' }, context).map(tag => tag.valid)).toEqual([false])
  })
})

describe('dataAccess', () => {
  it('含引用即读取', () => {
    expect(dataAccess({ moduleType: 'click_element', selector: '#a' }, [])).toEqual({ read: false, write: false })
    expect(dataAccess({ moduleType: 'click_element' }, [{}])).toEqual({ read: true, write: false })
  })

  it('project_data 按操作区分读与写，缺省为读取本次任务输入', () => {
    expect(dataAccess({ moduleType: 'project_data' }, [])).toEqual({ read: true, write: false })
    for (const operation of ['readRecord', 'queryRecords', 'queryTableSchema']) expect(dataAccess({ moduleType: 'project_data', operation }, [])).toEqual({ read: true, write: false })
    for (const operation of ['createRecord', 'updateRecord', 'setRecordStatus', 'deleteRecord']) expect(dataAccess({ moduleType: 'project_data', operation }, [])).toEqual({ read: false, write: true })
  })
})
