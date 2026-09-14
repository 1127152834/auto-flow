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
const cases = [
  { type: 'open_page', field: 'openMode', label: '打开方式', options: [['new_tab', '新标签页'], ['current_tab', '当前标签页']] },
  { type: 'open_page', field: 'waitUntil', label: '等待条件', options: [['load', '页面加载完成'], ['domcontentloaded', 'DOM加载完成'], ['networkidle', '网络空闲']] },
  { type: 'use_opened_page', field: 'matchMode', label: '匹配模式', options: [['title', '按标题匹配'], ['url', '按URL匹配']] },
  { type: 'click_element', field: 'clickType', label: '点击类型', options: [['single', '单击'], ['double', '双击'], ['right', '右键']] },
  { type: 'get_element_info', field: 'attribute', label: '获取属性', options: [['text', '文本内容'], ['innerHTML', 'HTML内容'], ['value', '输入框值'], ['href', '链接地址'], ['src', '图片地址'], ['attributes', '元素属性值（字典）']] },
  { type: 'wait_element', field: 'waitCondition', label: '等待条件', options: [['visible', '可见'], ['hidden', '隐藏'], ['attached', '已附加'], ['detached', '已分离']] },
  { type: 'wait', field: 'waitType', label: '等待类型', options: [['time', '等待时间'], ['selector', '等待元素'], ['navigation', '等待导航']] },
] as const
const roundtrip = (id: string, field: string, value: unknown) => {
  expect(store.getState().nodes.find(n => n.id === id)?.data[field]).toEqual(value)
  const document = store.getState().exportWorkflow()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(document)).toBe(true) })
  expect(store.getState().nodes.find(n => n.id === id)?.data[field]).toEqual(value)
}
it.each(cases.flatMap(row => row.options.map(([value, option]) => ({ ...row, value, option }))))('$type / $field / $value through real form, undo, copy and reopen', ({ type, field, label, options, value, option }) => {
  store.getState().addNode(type as ModuleType, { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  const old = options.find(([v]) => v !== value)![0]
  store.getState().updateNodeData(id, { [field]: old })
  store.getState().markAsSaved()
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.keyDown(screen.getByRole('combobox', { name: label }), { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: option }))
  expect(store.getState().nodes[0].data[field]).toBe(value)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  if (type === 'wait') {
    expect(screen.queryByPlaceholderText('例如: 1 或 2.5') !== null).toBe(value === 'time')
    expect(screen.queryByPlaceholderText('例如: #element, .class') !== null).toBe(value === 'selector')
  }
  if (field === 'openMode') expect(screen.getByText(value === 'current_tab' ? '在当前标签页打开，会关闭当前页面' : '在新标签页打开，保留当前页面')).toBeDefined()
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(old)
  act(() => { store.getState().redo(); store.getState().copyNodes([id]); store.getState().pasteNodes() })
  expect(store.getState().nodes[1].data[field]).toBe(value)
  roundtrip(id, field, value)
})
it.each([
  ['click_element', 'followNewTab', '点击后跟进新标签页', false],
  ['click_element', 'followNewTab', '点击后跟进新标签页', true],
  ['input_text', 'clearBefore', '输入前清空原有内容', false],
  ['input_text', 'clearBefore', '输入前清空原有内容', true],
] as const)('%s / %s / %s / %s checkbox survives undo and reopening', (type, field, label, value) => {
  store.getState().addNode(type, { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { [field]: !value })
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.click(screen.getByRole('checkbox', { name: label }))
  expect(store.getState().nodes[0].data[field]).toBe(value)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe(!value)
  act(() => { store.getState().redo(); store.getState().copyNodes([id]); store.getState().pasteNodes() })
  expect(store.getState().nodes[1].data[field]).toBe(value)
  roundtrip(id, field, value)
})
