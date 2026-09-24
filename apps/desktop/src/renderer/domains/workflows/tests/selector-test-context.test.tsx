import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { elementPickerApi } from '../api'
let nodeId: string
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('click_element', { x: 0, y: 0 }); nodeId = store.getState().nodes[0].id; store.getState().updateNodeData(nodeId, { selector: '#before' }); store.getState().markAsSaved() })
afterEach(() => { cleanup(); vi.restoreAllMocks() })
const button = () => screen.getByTitle('测试定位：在当前浏览器页面验证选择器是否命中并高亮')
it.each([0, 1, 4])('reports %i matches against the originating node without modifying the draft', async count => {
  vi.spyOn(elementPickerApi, 'testSelector').mockResolvedValue({ success: true, data: { success: true, matched: count > 0, count, isPrimary: true } })
  render(<ConfigPanel selectedNodeId={nodeId} />)
  fireEvent.click(button())
  await waitFor(() => expect(store.getState().logs).toHaveLength(1))
  expect(store.getState().logs[0]).toMatchObject({ nodeId, level: count ? 'success' : 'warning' })
  expect(store.getState().nodes[0].data.selector).toBe('#before')
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
it.each(['field', 'node', 'document', 'unmount'])('ignores a late successful test after changing %s', async change => {
  let release!: (value: Awaited<ReturnType<typeof elementPickerApi.testSelector>>) => void
  vi.spyOn(elementPickerApi, 'testSelector').mockImplementation(() => new Promise(resolve => { release = resolve }))
  const view = render(<ConfigPanel selectedNodeId={nodeId} />)
  fireEvent.click(button())
  if (change === 'field') fireEvent.change(screen.getByDisplayValue('#before'), { target: { value: '#after' } })
  if (change === 'node') {
    act(() => store.getState().addNode('click_element', { x: 10, y: 20 }))
    view.rerender(<ConfigPanel selectedNodeId={store.getState().nodes[1].id} />)
  }
  if (change === 'document') {
    const original = store.getState().nodes
    act(() => { store.getState().clearWorkflow(); store.setState({ nodes: original }) })
  }
  if (change === 'unmount') view.unmount()
  await act(async () => release({ success: true, data: { success: true, matched: true, count: 99, isPrimary: true } }))
  expect(store.getState().logs.some(log => log.message.includes('命中 99'))).toBe(false)
})
it('reports service rejection as an error attached to the target node', async () => {
  vi.spyOn(elementPickerApi, 'testSelector').mockResolvedValue({ success: false, error: '选择器语法错误' })
  render(<ConfigPanel selectedNodeId={nodeId} />)
  fireEvent.click(button())
  await waitFor(() => expect(store.getState().logs.at(-1)).toMatchObject({ nodeId, level: 'error' }))
  expect(store.getState().hasUnsavedChanges).toBe(false)
})
it('keeps selector testing disabled until picker cleanup is confirmed', async () => {
  vi.spyOn(elementPickerApi, 'start').mockImplementation(() => new Promise(() => {}))
  vi.spyOn(elementPickerApi, 'stop').mockResolvedValue({ success: true, data: { success: true, sessionId: 'picker', active: false, selected: false } })
  render(<ConfigPanel selectedNodeId={nodeId} />)
  fireEvent.click(screen.getByTitle('可视化选择元素'))
  fireEvent.click(screen.getByRole('button', { name: '启动选择器' }))
  expect((button() as HTMLButtonElement).disabled).toBe(true)
})
it('does not let an older response clear the newer node test spinner or replace its result', async () => {
  const releases: Array<(value: Awaited<ReturnType<typeof elementPickerApi.testSelector>>) => void> = []
  vi.spyOn(elementPickerApi, 'testSelector').mockImplementation(() => new Promise(resolve => { releases.push(resolve) }))
  const view = render(<ConfigPanel selectedNodeId={nodeId} />)
  fireEvent.click(button())
  let nextId = ''
  act(() => {
    store.getState().addNode('click_element', { x: 20, y: 20 })
    nextId = store.getState().nodes[1].id
    store.getState().updateNodeData(nextId, { selector: '#second' })
  })
  view.rerender(<ConfigPanel selectedNodeId={nextId} />)
  fireEvent.click(button())
  await act(async () => releases[0]({ success: true, data: { success: true, matched: true, count: 99 } }))
  expect((button() as HTMLButtonElement).disabled).toBe(true)
  await act(async () => releases[1]({ success: true, data: { success: true, matched: true, count: 2, isPrimary: true } }))
  expect((button() as HTMLButtonElement).disabled).toBe(false)
  expect(store.getState().logs.filter(log => log.level === 'success')).toMatchObject([{ nodeId: nextId, message: '命中 2 个元素，已在页面高亮' }])
})
