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
const entries: Array<{ type: ModuleType; field: string; label: string; extra?: Record<string, unknown> }> = [
  { type: 'click_element', field: 'selector', label: '元素选择器' },
  { type: 'input_text', field: 'selector', label: '元素选择器' },
  { type: 'wait_element', field: 'selector', label: '元素选择器' },
  { type: 'wait', field: 'selector', label: '元素选择器' },
  { type: 'get_element_info', field: 'selector', label: '元素选择器' },
  { type: 'screenshot', field: 'selector', label: '元素选择器' },
  { type: 'select_dropdown', field: 'selector', label: '元素选择器' },
  { type: 'set_checkbox', field: 'selector', label: '元素选择器' },
  { type: 'hover_element', field: 'selector', label: '元素选择器' },
  { type: 'drag_element', field: 'sourceSelector', label: '源元素选择器' },
  { type: 'drag_element', field: 'targetSelector', label: '目标元素选择器' },
  { type: 'upload_file', field: 'selector', label: '上传按钮选择器' },
  { type: 'get_child_elements', field: 'parentSelector', label: '父元素选择器' },
  { type: 'get_sibling_elements', field: 'elementSelector', label: '元素选择器' },
  { type: 'element_exists', field: 'selector', label: '元素选择器' },
  { type: 'element_visible', field: 'selector', label: '元素选择器' },
  { type: 'extract_table_data', field: 'tableSelector', label: '表格选择器' },
  { type: 'save_image', field: 'selector', label: '图片元素选择器' },
  { type: 'download_file', field: 'triggerSelector', label: '触发元素选择器', extra: { downloadMode: 'click' } },
  { type: 'condition', field: 'leftValue', label: '元素选择器', extra: { conditionType: 'element_exists' } },
  { type: 'assert_checkpoint', field: 'selector', label: '元素选择器', extra: { checkType: 'element' } },
  { type: 'element_change_trigger', field: 'selector', label: '元素选择器' },
  { type: 'ai_vision', field: 'imageSelector', label: '图片元素选择器', extra: { imageSource: 'element' } },
  { type: 'ocr_captcha', field: 'imageSelector', label: '验证码图片选择器' },
  { type: 'slider_captcha', field: 'sliderSelector', label: '滑块选择器' },
  { type: 'slider_captcha', field: 'trackSelector', label: '滑轨选择器' },
]
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
it.each(entries)('SELECTOR.ENTRY.$type.$field actual field dispatches picker and applies only its result', async ({ type, field, label, extra }) => {
  store.getState().addNode('open_page', { x: 0, y: 0 }, { url: 'https://example.test/source' })
  store.getState().addNode(type, { x: 0, y: 100 }, { [field]: '#before', ...extra, ...(type === 'drag_element' ? { sourceSelector: '#source', targetSelector: '#target' } : {}) })
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
