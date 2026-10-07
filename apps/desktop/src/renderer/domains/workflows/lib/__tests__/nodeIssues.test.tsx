import { cleanup, renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
})
const rules = vi.hoisted(() => ({ data: null as null | { schemaRevision: string; coveredModules: string[]; requiredFields: Record<string, string[]>; conditionalRequired: Record<string, never>; fieldLabels: Record<string, Record<string, string>> } }))
vi.mock('../requiredFields', async importOriginal => ({
  ...(await importOriginal<typeof import('../requiredFields')>()),
  useRequiredFields: () => ({ data: rules.data, loading: false, error: null, retry: () => {} }),
}))
import { useWorkflowStore as store } from '../../editor-store'
import { computeAllNodeIssues, computeNodeIssues, useNodeIssueMap, useNodeIssues } from '../nodeIssues'

const ctx = { requiredFields: { open_page: ['url'] } }
function add(type: string, data: Record<string, unknown> = {}) {
  store.getState().addNode(type as 'wait', { x: 0, y: 0 }, data)
  return store.getState().nodes.at(-1)!
}
const loaded = { schemaRevision: 'test', coveredModules: ['open_page'], requiredFields: { open_page: ['url'] }, conditionalRequired: {}, fieldLabels: { open_page: { url: '网址' } } }
beforeEach(() => {
  store.getState().clearWorkflow()
  rules.data = null
})
afterEach(cleanup)

describe('computeNodeIssues', () => {
  it('reports invalid numbers with field and guidance', () => {
    const n = add('wait', { duration: 'abc' })
    const [issue] = computeNodeIssues(n)
    expect(issue).toMatchObject({ nodeId: n.id, field: 'duration', code: 'invalid-number', severity: 'error' })
    expect(issue.message).toContain('请')
  })
  it('reports missing required fields', () => {
    const n = add('open_page', { url: '  ' })
    expect(computeNodeIssues(n, ctx).filter(i => i.code === 'required-missing')).toMatchObject([{ field: 'url' }])
  })
  it('uses the Chinese field label and honours conditional required fields', () => {
    const n = add('real_keyboard', { inputType: 'text', text: '' })
    const context = {
      requiredFields: { real_keyboard: ['inputType'] },
      conditionalRequired: { real_keyboard: { field: 'inputType', default: 'text', map: { text: ['text'], key: ['keyName'] } } },
      fieldLabels: { real_keyboard: { text: '要输入的文字', keyName: '按键名称' } },
    }
    const issues = computeNodeIssues(n, context).filter(i => i.code === 'required-missing')
    expect(issues).toMatchObject([{ field: 'text' }])
    expect(issues[0].message).toContain('要输入的文字')
    const switched = add('real_keyboard', { inputType: 'key', text: '' })
    expect(computeNodeIssues(switched, context).map(i => i.field)).toEqual(['keyName'])
  })
  it('returns nothing for a healthy node and for disabled nodes', () => {
    expect(computeNodeIssues(add('wait', { duration: 1 }))).toEqual([])
    expect(computeNodeIssues(add('wait', { duration: 'abc', disabled: true }))).toEqual([])
  })
})

describe('computeAllNodeIssues', () => {
  it('omits healthy nodes and reuses arrays for unchanged data', () => {
    const bad = add('wait', { duration: 'abc' })
    add('wait', { duration: 1 })
    const first = computeAllNodeIssues(store.getState().nodes)
    expect([...first.keys()]).toEqual([bad.id])
    store.setState(state => ({ nodes: state.nodes.map(n => n.id === bad.id ? { ...n, position: { x: 9, y: 9 } } : n) }))
    const second = computeAllNodeIssues(store.getState().nodes)
    expect(second.get(bad.id)).toBe(first.get(bad.id))
  })
  it('recomputes when node data changes', () => {
    const n = add('wait', { duration: 'abc' })
    expect(computeAllNodeIssues(store.getState().nodes).has(n.id)).toBe(true)
    store.getState().updateNodeData(n.id, { duration: 2 })
    expect(computeAllNodeIssues(store.getState().nodes).has(n.id)).toBe(false)
  })
})

describe('hooks', () => {
  it('useNodeIssues does not rerender when an unrelated node changes', () => {
    const a = add('wait', { duration: 'abc' })
    const b = add('wait', { duration: 1 })
    let renders = 0
    const { result } = renderHook(() => { renders++; return useNodeIssues(a.id) })
    expect(result.current).toHaveLength(1)
    const before = renders
    act(() => store.getState().updateNodeData(b.id, { duration: 5 }))
    expect(renders).toBe(before)
    act(() => store.getState().updateNodeData(a.id, { duration: 5 }))
    expect(result.current).toEqual([])
  })
  it('useNodeIssueMap reflects store changes', () => {
    const a = add('wait', { duration: 'abc' })
    const { result } = renderHook(() => useNodeIssueMap())
    expect(result.current.has(a.id)).toBe(true)
  })

  it('反映已加载的必填规则：先只报数字问题，加载后补报缺失字段并带中文标签', () => {
    const n = add('open_page', { url: '' })
    const { result, rerender } = renderHook(() => useNodeIssues(n.id))
    expect(result.current).toEqual([])
    rules.data = loaded
    rerender()
    expect(result.current).toMatchObject([{ field: 'url', code: 'required-missing' }])
    expect(result.current[0].message).toContain('网址')
  })

  it('同一节点的多个使用方在规则加载后得到同一个数组，不会互相顶掉缓存而无限重渲染', () => {
    const n = add('open_page', { url: '' })
    rules.data = loaded
    let renders = 0
    const { result } = renderHook(() => { renders++; return [useNodeIssues(n.id), useNodeIssues(n.id)] as const })
    expect(result.current[0]).toHaveLength(1)
    expect(result.current[0]).toBe(result.current[1])
    expect(renders).toBeLessThan(5)
  })
})
