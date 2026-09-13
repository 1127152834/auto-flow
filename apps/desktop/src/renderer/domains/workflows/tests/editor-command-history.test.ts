import { beforeEach, expect, it, vi } from 'vitest'
vi.mock('../lib/elkLayout', () => ({ layoutGraph: vi.fn() }))
import { layoutGraph } from '../lib/elkLayout'
import { useWorkflowStore as store } from '../editor-store'
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('open_page', { x: 10, y: 20 }); store.getState().markAsSaved(); vi.clearAllMocks() })
it.each(['internal', 'system'])('marks %s clipboard paste dirty and undoes only the paste', mode => {
  const original = store.getState().nodes[0]
  if (mode === 'internal') { store.getState().copyNodes([original.id]); store.getState().pasteNodes() }
  else store.getState().pasteNodesFromClipboard([original], [])
  expect(store.getState().nodes).toHaveLength(2)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes.map(n => n.id)).toEqual([original.id])
  store.getState().redo()
  expect(store.getState().nodes).toHaveLength(2)
})
it('records disabling nodes as one reversible edit', () => {
  const original = store.getState().nodes[0]
  store.getState().toggleNodesDisabled([original.id])
  expect(store.getState().nodes[0].data.disabled).toBe(true)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes[0]).toMatchObject({ id: original.id, data: original.data })
  store.getState().redo()
  expect(store.getState().nodes[0].data.disabled).toBe(true)
})
it('does not mark a no-op disable request as an edit', () => {
  store.getState().toggleNodesDisabled(['missing'])
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
it.each(['edit', 'document'])('rejects late automatic layout after a %s change', async mode => {
  const original = store.getState().nodes[0]
  const pending = deferred<{ positions: Record<string, { x: number; y: number }> }>()
  vi.mocked(layoutGraph).mockReturnValueOnce(pending.promise)
  const operation = store.getState().autoLayoutNodes()
  if (mode === 'edit') store.getState().updateNodeData(original.id, { label: '计算时编辑' })
  else store.getState().clearWorkflow()
  const snapshot = store.getState().exportWorkflow()
  pending.resolve({ positions: { [original.id]: { x: 100, y: 200 } } })
  expect((await operation).ok).toBe(false)
  expect(JSON.parse(store.getState().exportWorkflow()).nodes).toEqual(JSON.parse(snapshot).nodes)
})
it('applies layout across selection changes and supports undo', async () => {
  const original = store.getState().nodes[0]
  const pending = deferred<{ positions: Record<string, { x: number; y: number }> }>()
  vi.mocked(layoutGraph).mockReturnValueOnce(pending.promise)
  const operation = store.getState().autoLayoutNodes()
  store.getState().onNodesChange([{ type: 'select', id: original.id, selected: true }])
  pending.resolve({ positions: { [original.id]: { x: 100, y: 200 } } })
  expect((await operation).ok).toBe(true)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  store.getState().undo()
  expect(store.getState().nodes[0].position).toEqual(original.position)
})
it('only accepts the most recent layout request even when an earlier request resolves first', async () => {
  const original = store.getState().nodes[0]
  const first = deferred<{ positions: Record<string, { x: number; y: number }> }>()
  const second = deferred<{ positions: Record<string, { x: number; y: number }> }>()
  vi.mocked(layoutGraph).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  const a = store.getState().autoLayoutNodes({ direction: 'DOWN' })
  const b = store.getState().autoLayoutNodes({ direction: 'RIGHT' })
  first.resolve({ positions: { [original.id]: { x: 100, y: 100 } } })
  expect((await a).ok).toBe(false)
  second.resolve({ positions: { [original.id]: { x: 200, y: 200 } } })
  expect((await b).ok).toBe(true)
  expect(store.getState().nodes[0].position).toEqual({ x: 200, y: 200 })
})
