import { describe, expect, it } from 'vitest'
import { findReferenceRanges, referenceTooltip, type TagSources } from './references'

const sources: TagSources = {
  context: {
    signature: { account: { label: '账号', fields: { email: { label: '邮箱', type: 'string', sample: 'a@b.com' }, pwd: { label: '密码', type: 'string', sensitive: true, sample: 'secret' } } } },
    nodeOutputs: [{ nodeId: 'n1', key: 'text', name: '文本', label: '读取页面', type: 'string' }],
    variables: { token: { type: 'string' } },
    inputs: [{ inputId: 'in1', alias: '客户', fields: [{ fieldId: 'f1', alias: '姓名', type: 'string' }] }],
  },
  labels: { "PROJECT_PARAMETERS['p1']": '固定参数·折扣' },
  candidates: [],
}

describe('findReferenceRanges', () => {
  it('找出输入、节点输出、全局变量引用的原文范围与业务名', () => {
    const text = '你好 {input.account.email} / {node.n1.text} / {token}'
    const ranges = findReferenceRanges(text, sources)
    expect(ranges.map(r => text.slice(r.from, r.to))).toEqual(['{input.account.email}', '{node.n1.text}', '{token}'])
    expect(ranges.map(r => r.part.display)).toEqual(['账号·邮箱', '读取页面·文本', 'token'])
  })

  it('失效的稳定引用保留为红色失效范围，未知的 {变量名} 与 JSON 一样当普通文本', () => {
    const text = '{input.account.gone} {unknown} {"a":1}'
    const ranges = findReferenceRanges(text, sources)
    expect(ranges).toHaveLength(1)
    expect(ranges[0].part.valid).toBe(false)
    expect(text.slice(ranges[0].from, ranges[0].to)).toBe('{input.account.gone}')
  })

  it('旧式 PROJECT_INPUTS 引用连同外层花括号一起成为一个范围，且显示业务名', () => {
    const text = "x {PROJECT_INPUTS['in1']['values']['f1']} y"
    const [range] = findReferenceRanges(text, sources)
    expect(text.slice(range.from, range.to)).toBe("{PROJECT_INPUTS['in1']['values']['f1']}")
    expect(range.part.display).toBe('客户·姓名')
    expect(range.part.valid).toBe(true)
  })

  it('不带花括号的旧式引用只覆盖引用本身', () => {
    const text = "PROJECT_INPUTS['in1']"
    const [range] = findReferenceRanges(text, sources)
    expect([range.from, range.to]).toEqual([0, text.length])
    expect(range.part.display).toBe('客户')
  })

  it('labels 为固定参数等 {名称} 提供业务名，不泄漏内部 id', () => {
    const text = "{PROJECT_PARAMETERS['p1']}"
    const [range] = findReferenceRanges(text, sources)
    expect(range.part.display).toBe('固定参数·折扣')
    expect(range.part.valid).toBe(true)
  })

  it('转义花括号后的位置仍然准确', () => {
    const text = '\{ {token} \}{token}'
    const ranges = findReferenceRanges(text, sources)
    expect(ranges.map(r => text.slice(r.from, r.to))).toEqual(['{token}', '{token}'])
  })

  it('多行文本中的位置按整篇文本计算', () => {
    const text = 'a\n{token}\nb {token}'
    expect(findReferenceRanges(text, sources).map(r => r.from)).toEqual([2, 12])
  })
})

describe('referenceTooltip', () => {
  it('显示类型、来源、样例，敏感样例打码', () => {
    const [email, pwd] = findReferenceRanges('{input.account.email}{input.account.pwd}', sources)
    expect(referenceTooltip(email.part)).toBe('账号·邮箱\n类型：文本\n来源：流程输入\n样例：a@b.com')
    expect(referenceTooltip(pwd.part)).toContain('样例：••••••')
    expect(referenceTooltip(pwd.part)).not.toContain('secret')
  })

  it('失效引用提示重新选择', () => {
    const [range] = findReferenceRanges('{input.nope.x}', sources)
    expect(referenceTooltip(range.part)).toContain('已失效')
    expect(referenceTooltip(range.part)).toContain('重新选择')
  })
})
