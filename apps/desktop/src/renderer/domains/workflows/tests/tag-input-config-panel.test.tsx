import { act, cleanup, render, waitFor } from '@testing-library/react'
import { EditorView } from '@codemirror/view'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key), clear: () => data.clear() })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { expandAdvanced } from './expand-advanced'
import { useWorkflowStore as store } from '../editor-store'
import type { ModuleType } from '../types/workflow'
Element.prototype.scrollIntoView = vi.fn()
beforeEach(() => {
  store.getState().clearWorkflow()
  localStorage.setItem('autoflow.flags.tagInput', 'true')
})
afterEach(() => {
  cleanup()
  localStorage.clear()
})

// Five typical nodes with the tag input on: typing writes the plain string into the node, undo restores it,
// and a reference typed into the field is kept as written.
it.each([
  { type: 'open_page', field: 'url', placeholder: 'https://example.com' },
  { type: 'input_text', field: 'text', placeholder: '要输入的文本内容' },
  { type: 'click_element', field: 'selector', placeholder: '例如: #button, .submit' },
  { type: 'wait_element', field: 'selector', placeholder: '例如: #element, .class' },
  { type: 'get_element_info', field: 'columnName', placeholder: '列名(可选)' },
])('$type / $field 在 tagInput 开启时写入原始字符串并可撤销', async ({ type, field, placeholder }) => {
  store.getState().addNode(type as ModuleType, { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  store.getState().updateNodeData(id, { [field]: '' })
  store.getState().markAsSaved()
  const { container } = render(<ConfigPanel selectedNodeId={id} />)
  expandAdvanced()
  const editor = await waitFor(() => {
    const found = [...container.querySelectorAll<HTMLElement>('.cm-editor')].find(element => element.querySelector('.cm-placeholder')?.textContent === placeholder)
    expect(found).toBeTruthy()
    return found!
  })
  const view = EditorView.findFromDOM(editor)!
  const value = '第一行 {列名} ${x}'
  act(() => { view.dispatch({ changes: { from: 0, insert: value }, userEvent: 'input.type' }) })
  expect(store.getState().nodes[0].data[field]).toBe(value)
  expect(store.getState().hasUnsavedChanges).toBe(true)
  act(() => store.getState().undo())
  expect(store.getState().nodes[0].data[field]).toBe('')
  expect(view.state.doc.toString()).toBe('')
})
