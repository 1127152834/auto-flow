import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
let first: string, second: string
beforeEach(() => {
  store.getState().clearWorkflow()
  store.getState().addNode('get_element_info', { x: 0, y: 0 }); first = store.getState().nodes[0].id
  store.getState().updateNodeData(first, { variableName: 'alpha' })
  store.getState().addNode('get_element_info', { x: 0, y: 100 }); second = store.getState().nodes[1].id
  store.getState().updateNodeData(second, { variableName: 'beta' })
  store.getState().addNode('input_text', { x: 0, y: 200 })
  store.getState().updateNodeData(store.getState().nodes[2].id, { text: '{alpha}' })
  vi.useFakeTimers()
})
afterEach(() => { cleanup(); vi.useRealTimers() })
it('does not interpret switching to another output field as renaming the previous node variable', async () => {
  const view = render(<ConfigPanel selectedNodeId={first} />)
  view.rerender(<ConfigPanel selectedNodeId={second} />)
  fireEvent.blur(screen.getByPlaceholderText('变量名'))
  await act(async () => vi.advanceTimersByTimeAsync(200))
  expect(screen.queryByText('变量重命名')).toBeNull()
  expect(store.getState().nodes[2].data.text).toBe('{alpha}')
})
it.each(['pending-blur', 'open-dialog', 'document'])('discards old rename state after %s context changes', async mode => {
  const view = render(<ConfigPanel selectedNodeId={first} />)
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'gamma' } })
  fireEvent.blur(screen.getByPlaceholderText('变量名'))
  if (mode === 'open-dialog') { await act(async () => vi.advanceTimersByTimeAsync(200)); expect(screen.getByText('变量重命名')).toBeDefined() }
  if (mode === 'document') {
    const nodes = store.getState().nodes
    act(() => { store.getState().clearWorkflow(); store.setState({ nodes }) })
  } else view.rerender(<ConfigPanel selectedNodeId={second} />)
  await act(async () => vi.advanceTimersByTimeAsync(200))
  expect(screen.queryByText('变量重命名')).toBeNull()
  expect(store.getState().nodes[2].data.text).toBe('{alpha}')
})
it('does not rewrite references from a rename dialog after its output field changed again', async () => {
  render(<ConfigPanel selectedNodeId={first} />)
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'gamma' } })
  fireEvent.blur(screen.getByPlaceholderText('变量名'))
  await act(async () => vi.advanceTimersByTimeAsync(200))
  expect(screen.getByText('变量重命名')).toBeDefined()
  act(() => store.getState().updateNodeData(first, { variableName: 'delta' }))
  fireEvent.click(screen.getByRole('button', { name: '全部更新' }))
  expect(store.getState().nodes[2].data.text).toBe('{alpha}')
  expect(store.getState().nodes[0].data.variableName).toBe('delta')
})
it('cancels a delayed rename check when the field value changes before it runs', async () => {
  render(<ConfigPanel selectedNodeId={first} />)
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'gamma' } })
  fireEvent.blur(screen.getByPlaceholderText('变量名'))
  act(() => store.getState().updateNodeData(first, { variableName: 'delta' }))
  await act(async () => vi.advanceTimersByTimeAsync(200))
  expect(screen.queryByText('变量重命名')).toBeNull()
  expect(store.getState().nodes[2].data.text).toBe('{alpha}')
})
it.each(['全部更新', '仅改此处'])('keeps valid rename confirmation behavior for %s', async choice => {
  render(<ConfigPanel selectedNodeId={first} />)
  fireEvent.change(screen.getByPlaceholderText('变量名'), { target: { value: 'gamma' } })
  fireEvent.blur(screen.getByPlaceholderText('变量名'))
  await act(async () => vi.advanceTimersByTimeAsync(200))
  fireEvent.click(screen.getByRole('button', { name: choice }))
  expect(store.getState().nodes[0].data.variableName).toBe('gamma')
  expect(store.getState().nodes[2].data.text).toBe(choice === '全部更新' ? '{gamma}' : '{alpha}')
})
