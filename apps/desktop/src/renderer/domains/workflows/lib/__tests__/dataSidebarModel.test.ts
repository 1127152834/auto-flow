import { describe, expect, it } from 'vitest'
import { SENSITIVE_SAMPLE_MASK, parseReferences } from '../dataReferences'
import { buildDataSidebar, filterRows, nodesReferencing, referencesInNode } from '../dataSidebarModel'

const signature = [{
  key: '账号', name: '账号信息', rest: {},
  fields: [
    { key: 'phone', name: '手机号', type: 'string', required: true, sensitive: false, sample: '13800000000', rest: {} },
    { key: 'pwd', name: '密码', type: 'string', required: false, sensitive: true, rest: {} },
    { key: 'ok', name: '已启用', type: 'boolean', required: false, sensitive: false, sample: true, rest: {} },
  ],
}]
const node = (id: string, label: string, moduleType: string, extra: Record<string, unknown> = {}) => ({ id, data: { label, moduleType, ...extra } })
const nodes = [
  node('n1', '读取标题', 'get_element_info', { variableName: 'title' }),
  node('n2', '判断', 'condition'),
  node('n3', '读取标题', 'get_element_info', { variableName: 'title2' }),
  node('n4', '打印', 'print_log', { message: '{input.账号.phone} / {count} / {node.n1.variableName}' }),
]
const edges = [
  { source: 'n1', target: 'n2' },
  { source: 'n2', target: 'n3', sourceHandle: 'true' },
  { source: 'n2', target: 'n4', sourceHandle: 'false' },
  { source: 'n3', target: 'n4' },
]
const variables = [
  { name: 'count', value: 3, type: 'number' as const, scope: 'global' as const },
  { name: 'tmp', value: 'x', type: 'string' as const, scope: 'local' as const },
  { name: 'cfg', value: { a: 1 }, type: 'object' as const, scope: 'global' as const },
]
const model = () => buildDataSidebar({ signature, nodes, edges, variables, credentials: [{ name: '邮箱账号', description: '发信用' }] })

describe('dataSidebarModel', () => {
  it('输入字段：分组、必填、样例与引用串', () => {
    const rows = model().inputs
    expect(rows.map(r => r.title)).toEqual(['手机号', '密码', '已启用'])
    expect(rows[0]).toMatchObject({ subgroup: '账号信息', type: '文本', required: true, sample: '13800000000', copyText: '{input.账号.phone}' })
    expect(rows[2].sample).toBe('是')
    expect(parseReferences(rows[0].copyText, { signature: { 账号: { fields: { phone: {} } } } })[0]).toMatchObject({ valid: true })
  })

  it('敏感字段样例打码，不看字段名', () => {
    const [, pwd] = model().inputs
    expect(pwd.sensitive).toBe(true)
    expect(pwd.sample).toBe(SENSITIVE_SAMPLE_MASK)
    const other = buildDataSidebar({ signature: [{ ...signature[0], fields: [{ ...signature[0].fields[0], key: 'token', name: '令牌', sensitive: false, sample: 'abc' }] }], nodes: [], edges: [], variables: [], credentials: [] })
    expect(other.inputs[0].sample).toBe('abc')
  })

  it('节点输出：标题·输出名，同名节点加序号，必有与条件', () => {
    const rows = model().nodeOutputs
    expect(rows.map(r => r.title)).toEqual(['读取标题（第 1 个）·结果', '读取标题（第 2 个）·结果'])
    expect(rows[0].copyText).toBe('{node.n1.variableName}')
    expect(rows[0].availability).toBe('always')
    expect(rows[1].availability).toBe('conditional')
    expect(JSON.stringify(rows)).not.toContain('"title":"n1')
  })

  it('全局变量只含全局范围，带类型与初值摘要', () => {
    const rows = model().variables
    expect(rows.map(r => [r.title, r.type, r.sample, r.copyText])).toEqual([['count', '数字', '3', '{count}'], ['cfg', '对象', '{"a":1}', '{cfg}']])
  })

  it('凭据只有名称与说明，没有值和引用', () => {
    const [row] = model().credentials
    expect(row).toMatchObject({ title: '邮箱账号', description: '发信用' })
    expect(row.sample).toBeUndefined()
  })

  it('搜索按标题、分组、说明过滤', () => {
    const rows = model().inputs
    expect(filterRows(rows, '账号').length).toBe(3)
    expect(filterRows(rows, '手机').map(r => r.title)).toEqual(['手机号'])
    expect(filterRows(rows, '  ')).toBe(rows)
  })

  it('引用串查找：哪些节点引用了它、节点引用了哪些行', () => {
    expect(nodesReferencing(nodes, '{input.账号.phone}')).toEqual(['n4'])
    expect(nodesReferencing(nodes, '{count}')).toEqual(['n4'])
    expect(nodesReferencing(nodes, '{input.账号.pwd}')).toEqual([])
    const m = model()
    const all = [...m.inputs, ...m.nodeOutputs, ...m.variables]
    expect(referencesInNode(nodes[3], all).sort()).toEqual(['{count}', '{input.账号.phone}', '{node.n1.variableName}'])
  })
})
