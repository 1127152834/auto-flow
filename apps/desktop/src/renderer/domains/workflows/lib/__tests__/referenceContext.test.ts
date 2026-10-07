import { describe, expect, it } from 'vitest'
import { formatReference } from '../dataReferences'
import { buildReferenceContext, selectReferenceContext } from '../referenceContext'
import type { SignatureInputDraft } from '../signatureDocument'

const signature = [{ key: 'account', name: '账号', fields: [{ key: 'email', name: '邮箱', type: 'string', required: true, sensitive: false, rest: {} }, { key: 'pwd', name: '密码', type: 'string', required: true, sensitive: true, sample: 'x', rest: {} }], rest: {} }] as unknown as SignatureInputDraft[]
const nodes = [
  { id: 'n1', position: { x: 0, y: 0 }, data: { moduleType: 'ai_chat', label: '读取标题' } },
  { id: 'n2', position: { x: 0, y: 0 }, data: { moduleType: 'click_element', label: '点击' } },
]
const variables = [{ name: '计数', value: 1, type: 'number', scope: 'global' }]
const automation = { inputPlan: { inputs: [{ inputId: 'in_1', alias: '客户', fieldBindings: [{ inputFieldId: 'f_1', inputFieldAlias: '电话' }] }] } } as never

describe('buildReferenceContext', () => {
  const context = buildReferenceContext({ signature, nodes, variables, automation })

  it('签名、全局变量、旧式项目输入都能解析成业务名', () => {
    expect(formatReference('{input.account.email}', context)).toBe('账号·邮箱')
    expect(formatReference('{计数}', context)).toBe('计数')
    expect(formatReference("PROJECT_INPUTS['in_1']['values']['f_1']", context)).toBe('客户·电话')
  })

  it('敏感字段不带样例', () => {
    expect(context.signature?.account.fields?.pwd).toMatchObject({ sensitive: true, sample: undefined })
  })

  it('节点输出来自已声明的输出，显示为 节点·输出名', () => {
    const output = context.nodeOutputs?.[0]
    expect(output).toMatchObject({ nodeId: 'n1' })
    expect(formatReference(`{node.n1.${output!.key}}`, context)).toBe(`读取标题·${output!.name}`)
    expect(context.nodeOutputs?.every(item => item.nodeId === 'n1')).toBe(true)
  })

  it('没有自动化与签名时得到空上下文而不是报错', () => {
    expect(buildReferenceContext({ signature: [], nodes: [], variables: [], automation: null })).toEqual({ signature: {}, nodeOutputs: [], variables: {}, inputs: [] })
  })
})

describe('selectReferenceContext', () => {
  it('输入引用不变时复用同一个对象；内容不变时即使数组换了也复用', () => {
    const first = selectReferenceContext(nodes, variables, signature, null)
    expect(selectReferenceContext(nodes, variables, signature, null)).toBe(first)
    const moved = nodes.map(node => ({ ...node, position: { x: 50, y: 50 } }))
    expect(selectReferenceContext(moved, variables, signature, null)).toBe(first)
  })

  it('只有位置变化（节点对象换了、data 引用不变）时直接返回同一对象，不重建', () => {
    const first = selectReferenceContext(nodes, variables, signature, null)
    const many = Array.from({ length: 200 }, (_, i) => ({ id: `m${i}`, position: { x: 0, y: 0 }, data: { moduleType: 'ai_chat', label: `n${i}` } }))
    const base = selectReferenceContext(many, variables, signature, null)
    expect(base).not.toBe(first)
    const t0 = performance.now()
    let result = base
    for (let frame = 0; frame < 100; frame++) result = selectReferenceContext(many.map(node => ({ ...node, position: { x: frame, y: frame } })), variables, signature, null)
    const perFrame = (performance.now() - t0) / 100
    expect(result).toBe(base)
    expect(perFrame).toBeLessThan(5)
  })

  it('内容变了就给新对象', () => {
    const first = selectReferenceContext(nodes, variables, signature, null)
    const renamed = [{ ...nodes[0], data: { ...nodes[0].data, label: '改名了' } }, nodes[1]]
    expect(selectReferenceContext(renamed, variables, signature, null)).not.toBe(first)
  })
})
