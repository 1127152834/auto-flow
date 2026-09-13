import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'
Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => store.getState().clearWorkflow())
afterEach(cleanup)
it.each([
  { type: 'open_page', field: 'url', placeholder: 'https://example.com', value: 'https://example.test/{路径}?q=${关键词}' },
  { type: 'open_page', field: 'url', placeholder: 'https://example.com', value: '' },
  { type: 'use_opened_page', field: 'pageIdentifier', placeholder: '页面标题或URL的部分内容', value: '{页面标题}' },
  { type: 'click_element', field: 'selector', placeholder: '例如: #button, .submit', value: '#target[data-id="中文"]' },
  { type: 'input_text', field: 'selector', placeholder: '例如: #input, .text-field', value: 'xpath=//input[@name="test"]' },
  { type: 'input_text', field: 'text', placeholder: '要输入的文本内容', value: '第一行\n第二行 {name} ${name}' },
  { type: 'input_text', field: 'text', placeholder: '要输入的文本内容', value: '' },
  { type: 'wait_element', field: 'selector', placeholder: '例如: #element, .class', value: '{selector}' },
  { type: 'get_element_info', field: 'columnName', placeholder: '列名(可选)', value: '{列名}' },
  { type: 'get_element_info', field: 'variableName', placeholder: '变量名', value: '结果_1' },
  { type: 'screenshot', field: 'variableName', placeholder: '保存文件路径的变量名', value: '截图路径' },
])('$type / $field preserves literal $value through form, undo, copy and reopen', ({ type, field, placeholder, value }) => {
  store.getState().addNode(type as ModuleType, { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { [field]: 'initial' })
  store.getState().markAsSaved()
  render(<ConfigPanel selectedNodeId={id} />)
  const input = screen.getByPlaceholderText(placeholder)
  fireEvent.change(input, { target: { value } })
  fireEvent.blur(input)
  expect(store.getState().nodes[0].data[field]).toBe(value)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe('initial')
  act(() => { store.getState().redo(); store.getState().copyNodes([id]); store.getState().pasteNodes() })
  expect(store.getState().nodes[1].data[field]).toBe(value)
  const document = store.getState().exportWorkflow()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(document)).toBe(true) })
  expect(store.getState().nodes[0].data[field]).toBe(value)
})
it.each([['fullpage', '整个页面'], ['viewport', '可视区域'], ['element', '指定元素']])('screenshot %s preserves the inactive selector and shows it only for element mode', (value, label) => {
  store.getState().addNode('screenshot', { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { screenshotType: value === 'element' ? 'fullpage' : 'element', selector: '#preserved' })
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.keyDown(screen.getByRole('combobox', { name: '截图类型' }), { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: label }))
  expect(screen.queryByPlaceholderText('#target') !== null).toBe(value === 'element')
  expect(store.getState().nodes[0].data).toMatchObject({ screenshotType: value, selector: '#preserved' })
  const document = store.getState().exportWorkflow()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(document)).toBe(true) })
  expect(store.getState().nodes[0].data).toMatchObject({ screenshotType: value, selector: '#preserved' })
})
