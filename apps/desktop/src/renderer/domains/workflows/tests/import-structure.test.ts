import { beforeEach, expect, it } from 'vitest'
import { useWorkflowStore as store } from '../editor-store'
const valid = () => ({ name: '导入测试', nodes: [{ id: 'a', type: 'open_page', position: { x: 0, y: 0 }, data: { url: '' } }, { id: 'b', type: 'click_element', position: { x: 30, y: 60 }, data: { selector: '' } }], edges: [{ id: 'e', source: 'a', target: 'b' }], variables: [] })
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('print_log', { x: 200, y: 300 }); store.getState().addVariable({ name: 'keep', value: 'draft', type: 'string', scope: 'global' }) })
const broken = [
  ['duplicate-node', () => { const d = valid(); d.nodes[1].id = 'a'; return d }],
  ['duplicate-edge', () => { const d = valid(); d.edges.push({ ...d.edges[0] }); return d }],
  ['dangling-edge', () => { const d = valid(); d.edges[0].target = 'missing'; return d }],
  ['blank-node-id', () => { const d = valid(); d.nodes[0].id = ''; return d }],
  ['blank-edge-id', () => { const d = valid(); d.edges[0].id = ''; return d }],
  ['nodes-object', () => ({ ...valid(), nodes: {} })],
  ['edges-object', () => ({ ...valid(), edges: {} })],
  ['variables-object', () => ({ ...valid(), variables: {} })],
] as const
it.each((['open', 'merge'] as const).flatMap(mode => broken.map(([reason, make]) => ({ mode, reason, make }))))('rejects corrupt $mode/$reason without changing the draft or history', ({ mode, reason, make }) => {
    const before = store.getState()
    const result = mode === 'open' ? store.getState().importWorkflow(JSON.stringify(make())) : store.getState().mergeWorkflow(JSON.stringify(make()))
    expect(result, reason).toBe(false)
    const after = store.getState()
    for (const key of ['id', 'nodes', 'edges', 'variables', 'history', 'historyIndex', 'hasUnsavedChanges'] as const) expect(after[key], `${reason}.${key}`).toEqual(before[key])
})
it.each(['open', 'merge'] as const)('preserves unfinished and unknown node data on valid %s', mode => {
  const d = valid(); d.nodes[1].type = 'unknown_legacy_node'
  const result = mode === 'open' ? store.getState().importWorkflow(JSON.stringify(d)) : store.getState().mergeWorkflow(JSON.stringify(d))
  expect(result).toBe(true)
  expect(store.getState().nodes.at(-1)?.data.moduleType).toBe('unknown_legacy_node')
  expect(store.getState().nodes.at(-2)?.data.url).toBe('')
})
it.each(['open', 'merge'] as const)('keeps the legacy coordinate and missing-edge-ID fallback for %s', mode => {
  const d = { nodes: [{ id: 'a', type: 'open_page' }, { id: 'b', type: 'click_element' }], edges: [{ source: 'a', target: 'b' }] }
  const result = mode === 'open' ? store.getState().importWorkflow(JSON.stringify(d)) : store.getState().mergeWorkflow(JSON.stringify(d))
  expect(result).toBe(true)
  for (const node of store.getState().nodes) { expect(Number.isFinite(node.position.x)).toBe(true); expect(Number.isFinite(node.position.y)).toBe(true) }
  expect(store.getState().edges.at(-1)?.id).toBeTruthy()
})
