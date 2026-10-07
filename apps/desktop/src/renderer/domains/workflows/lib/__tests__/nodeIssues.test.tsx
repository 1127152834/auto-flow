import { cleanup, renderHook, act } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
})
vi.mock('../requiredFields', async importOriginal => ({
  ...(await importOriginal<typeof import('../requiredFields')>()),
  useRequiredFields: () => ({ data: null, loading: false, error: null, retry: () => {} }),
}))
import { useWorkflowStore as store } from '../../editor-store'
import { computeAllNodeIssues, computeNodeIssues, useNodeIssueMap, useNodeIssues } from '../nodeIssues'

const ctx = { requiredFields: { open_page: ['url'] } }
function add(type: string, data: Record<string, unknown> = {}) {
  store.getState().addNode(type as 'wait', { x: 0, y: 0 }, data)
  return store.getState().nodes.at(-1)!
}
beforeEach(() => store.getState().clearWorkflow())
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
})
