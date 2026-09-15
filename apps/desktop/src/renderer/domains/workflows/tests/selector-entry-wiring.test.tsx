import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { elementPickerApi, systemApi } from '../api'
import type { ModuleType } from '../types/workflow'
Element.prototype.scrollIntoView = vi.fn()
const entries = [
  ['click_element', 'selector', '元素选择器'], ['input_text', 'selector', '元素选择器'], ['wait_element', 'selector', '元素选择器'],
  ['wait', 'selector', '元素选择器'], ['get_element_info', 'selector', '元素选择器'], ['screenshot', 'selector', '元素选择器'],
  ['select_dropdown', 'selector', '元素选择器'], ['set_checkbox', 'selector', '元素选择器'], ['hover_element', 'selector', '元素选择器'],
  ['drag_element', 'sourceSelector', '源元素选择器'], ['drag_element', 'targetSelector', '目标元素选择器'],
] as const
beforeEach(() => {
  vi.useFakeTimers(); store.getState().clearWorkflow()
  vi.spyOn(elementPickerApi, 'start').mockResolvedValue({ success: true, data: { success: true, sessionId: 'entry-picker', active: true, selected: false } })
  vi.spyOn(elementPickerApi, 'stop').mockResolvedValue({ success: true, data: { success: true } })
  vi.spyOn(elementPickerApi, 'getSelected').mockResolvedValue({ success: true, data: { selected: true, element: { selector: '#picked', tagName: 'BUTTON', text: '确定', attributes: { id: 'picked' } } } })
  vi.spyOn(elementPickerApi, 'getSimilar').mockResolvedValue({ success: true, data: { selected: false } })
  vi.spyOn(systemApi, 'setClipboard').mockResolvedValue({ success: true })
})
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })
function select(label: string, option: string) { fireEvent.keyDown(screen.getByRole('combobox', { name: label }), { key: 'ArrowDown' }); fireEvent.click(screen.getByRole('option', { name: option })) }
it.each(entries)('SELECTOR.ENTRY.%s.%s actual field dispatches picker and applies only its result', async (type, field, label) => {
  store.getState().addNode('open_page', { x: 0, y: 0 }, { url: 'https://example.test/source' })
  store.getState().addNode(type as ModuleType, { x: 0, y: 100 }, { [field]: '#before', ...(type === 'drag_element' ? { sourceSelector: '#source', targetSelector: '#target' } : {}) })
  const id = store.getState().nodes[1].id; const original = { ...store.getState().nodes[1].data }
  render(<ConfigPanel selectedNodeId={id} />)
  if (type === 'wait') { expect(screen.queryByTitle('可视化选择元素')).toBeNull(); select('等待类型', '等待元素') }
  if (type === 'screenshot') { expect(screen.queryByTitle('可视化选择元素')).toBeNull(); select('截图类型', '指定元素') }
  const container = screen.getByText(label, { exact: true }).closest('.space-y-2') as HTMLElement
  fireEvent.click(within(container).getByTitle('可视化选择元素'))
  await act(async () => fireEvent.click(screen.getByText('启动选择器')))
  expect(elementPickerApi.start).toHaveBeenCalledExactlyOnceWith('https://example.test/source')
  await act(async () => vi.advanceTimersByTimeAsync(500))
  expect(elementPickerApi.getSelected).toHaveBeenCalledTimes(1)
  expect(store.getState().nodes[1].data[field]).toBe('#picked')
  expect(store.getState().nodes[0].data.url).toBe('https://example.test/source')
  if (type === 'drag_element') expect(store.getState().nodes[1].data[field === 'sourceSelector' ? 'targetSelector' : 'sourceSelector']).toBe(field === 'sourceSelector' ? '#target' : '#source')
  act(() => store.getState().undo()); expect(store.getState().nodes[1].data[field]).toBe(original[field])
  act(() => store.getState().redo()); expect(store.getState().nodes[1].data[field]).toBe('#picked')
  const exported = store.getState().exportWorkflow()
  cleanup(); act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(exported)).toBe(true) })
  expect(store.getState().nodes.find(node => node.id === id)!.data[field]).toBe('#picked')
})
