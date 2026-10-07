import { describe, expect, it } from 'vitest'
import { findReferenceRanges } from './references'
import { buildTagSources, filterCandidates } from './sources'

const base = {
  signature: [{
    key: 'account', name: '账号', rest: {}, fields: [
      { key: 'email', name: '邮箱', type: 'string', required: true, sensitive: false, sample: 'a@b.com', rest: {} },
      { key: 'pwd', name: '密码', type: 'string', required: true, sensitive: true, sample: 'secret', rest: {} },
    ],
  }],
  nodeOutputs: [{ nodeId: 'n1', key: 'text', name: '文本', label: '读取页面', variable: 'page', reference: 'node.n1.text', required: false, sensitive: false, named: true }],
  variables: [{ name: 'token', type: 'string' }, { name: 'ERROR', type: 'object', builtin: true, description: '错误信息' }],
  projectRefs: [
    { name: 'input.account.email', label: '账号 → 邮箱', type: 'string' },
    { name: "PROJECT_PARAMETERS['p1']", label: '固定参数 → 折扣', type: 'number' },
  ],
  automationInputs: [],
}

describe('buildTagSources', () => {
  const sources = buildTagSources(base)

  it('候选分为输入字段、节点输出、全局变量三组，按该顺序，重复引用只留一个', () => {
    expect(sources.candidates.map(c => [c.group, c.raw])).toEqual([
      ['input', '{input.account.email}'], ['input', '{input.account.pwd}'], ['input', "{PROJECT_PARAMETERS['p1']}"],
      ['node', '{node.n1.text}'],
      ['variable', '{token}'], ['variable', '{ERROR}'],
    ])
  })

  it('候选显示中文名与类型；可能为空的节点输出给出提示', () => {
    const byRaw = Object.fromEntries(sources.candidates.map(c => [c.raw, c]))
    expect(byRaw['{input.account.email}']).toMatchObject({ label: '账号·邮箱', type: 'string' })
    expect(byRaw['{node.n1.text}']).toMatchObject({ label: '读取页面·文本' })
    expect(byRaw['{node.n1.text}'].hint).toContain('可能为空')
    expect(byRaw["{PROJECT_PARAMETERS['p1']}"].label).toBe('固定参数·折扣')
  })

  it('解析上下文能把候选引用显示为业务名，敏感样例打码', () => {
    const text = "{input.account.email}{input.account.pwd}{node.n1.text}{PROJECT_PARAMETERS['p1']}{token}"
    const ranges = findReferenceRanges(text, sources)
    expect(ranges.map(r => r.part.display)).toEqual(['账号·邮箱', '账号·密码', '读取页面·文本', '固定参数·折扣', 'token'])
    expect(ranges[0].part.sample).toBe('a@b.com')
    expect(ranges[1].part.sample).toBe('••••••')
  })

  it('只来自自动化绑定的 input.* 引用也能解析，不显示内部键', () => {
    const only = buildTagSources({ ...base, signature: [], projectRefs: [{ name: 'input.client.name', label: '客户 → 姓名', type: 'string' }] })
    const [range] = findReferenceRanges('{input.client.name}', only)
    expect(range.part).toMatchObject({ valid: true, display: '客户·姓名' })
  })
})

describe('filterCandidates', () => {
  const { candidates } = buildTagSources(base)

  it('空查询保持分组顺序', () => {
    expect(filterCandidates(candidates, '').map(c => c.raw)).toEqual(candidates.map(c => c.raw))
  })

  it('按中文名或原文匹配，名称前缀优先于包含', () => {
    const list = buildTagSources({ ...base, variables: [{ name: 'my_email', type: 'string' }, { name: 'email_list', type: 'array' }] }).candidates
    expect(filterCandidates(list, 'email').map(c => c.raw)).toEqual(['{email_list}', '{input.account.email}', '{my_email}'])
    expect(filterCandidates(list, '邮箱').map(c => c.raw)).toEqual(['{input.account.email}'])
  })

  it('同等相关度时分组顺序优先，无匹配返回空', () => {
    expect(filterCandidates(candidates, 'zzzz')).toEqual([])
  })
})
