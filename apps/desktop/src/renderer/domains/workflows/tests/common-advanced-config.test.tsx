import '@testing-library/jest-dom/vitest'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const values = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (k: string) => values.get(k) ?? null, setItem: (k: string, v: string) => values.set(k, v), removeItem: (k: string) => values.delete(k) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store, type ErrorPolicy } from '../editor-store'
import { mockRequest } from '../api/mock-server'
import { expandAdvanced } from './expand-advanced'
Element.prototype.scrollIntoView = vi.fn()
let id: string
beforeEach(() => { store.getState().clearWorkflow(); store.getState().addNode('close_page', { x: 0, y: 0 }); id = store.getState().nodes[0].id })
afterEach(cleanup)
const data = () => store.getState().nodes.find(n => n.id === id)!.data
function labelled(text: string, role: 'combobox' | 'textbox') {
  return within(screen.getAllByText(text, { exact: true }).find(e => e.tagName === 'LABEL')!.parentElement!).getByRole(role)
}
function choose(label: string, option: string) {
  fireEvent.keyDown(labelled(label, 'combobox'), { key: 'ArrowDown' })
  fireEvent.click(screen.getByRole('option', { name: option }))
}
function edit(label: string, value: string) { const input = labelled(label, 'textbox'); fireEvent.change(input, { target: { value } }); fireEvent.blur(input) }
function history(field: string, previous: unknown, next: unknown) {
  expect(data()[field]).toEqual(next)
  act(() => store.getState().undo()); expect(data()[field]).toEqual(previous)
  act(() => store.getState().redo()); expect(data()[field]).toEqual(next)
  const document = store.getState().exportWorkflow()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(document)).toBe(true) })
  expect(data()[field]).toEqual(next)
}
it.each([['timeout', '超时时间 (秒)', '1abc'], ['timeout', '超时时间 (秒)', '-1']])('ADV.numeric.%s.%s.%s retains invalid drafts under existing NumberInput contract', (field, label, value) => {
  store.getState().updateNodeData(id, { [field]: 3 }); render(<ConfigPanel selectedNodeId={id} />); expandAdvanced()
  edit(label, value); const expected = value === '-1' ? -1 : value
  expect(labelled(label, 'textbox').getAttribute('aria-invalid')).toBe('true'); history(field, 3, expected)
})
it('ADV.policy-v2 shows an old error policy as a candidate and enabling it is undoable and saved', () => {
  // Remediation M2 R2-08/R2-12: the old shape is never executed until the person enables it.
  const previous: ErrorPolicy = { mode: 'retry-self', maxRetries: 2, interval: 1, onExhausted: 'stop' }
  store.getState().updateNodeData(id, { errorPolicy: previous }); store.getState().markAsSaved()
  render(<ConfigPanel selectedNodeId={id} />); expandAdvanced()
  expect(screen.getByRole('status', { name: '未生效的出错设置' })).toHaveTextContent('以前保存的设置“出错时重试 2 次”尚未生效')
  fireEvent.click(screen.getByRole('button', { name: '启用这项设置' }))
  history('errorPolicy', previous, { version: 2, onError: 'retry', maxRetries: 2, backoff: { kind: 'fixed', initialSeconds: 1, maxSeconds: 1, jitter: false }, retryOn: 'any', gotoNodeId: null, onExhausted: 'stop' })
})
it('ADV.context does not send detached old field blur into a newly selected node', () => {
  store.getState().addNode('close_page', { x: 0, y: 100 }); const second = store.getState().nodes[1].id
  const view = render(<ConfigPanel selectedNodeId={id} />); expandAdvanced(); const old = labelled('超时时间 (秒)', 'textbox')
  fireEvent.change(old, { target: { value: '12' } }); view.rerender(<ConfigPanel selectedNodeId={second} />); fireEvent.blur(old)
  expect(store.getState().nodes.find(n => n.id === second)!.data.timeout).not.toBe(12); expect(data().timeout).toBe(12)
})
it('ADV.save persists shared fields through real mock save/load and re-render', async () => {
  render(<ConfigPanel selectedNodeId={id} />); expandAdvanced()
  edit('节点备注', '高级配置验收'); edit('超时时间 (秒)', '12.5'); choose('出错时', '原地重试当前模块')
  const expected = { ...data() }; const content = JSON.parse(store.getState().exportWorkflow())
  const saved = await mockRequest('http://autoflow-studio.mock/api/local-workflows/save-to-folder', { method: 'POST', body: JSON.stringify({ filename: 'advanced-fields', content }) }); expect(saved.status).toBe(200)
  const loaded = await (await mockRequest('http://autoflow-studio.mock/api/local-workflows/load/advanced-fields.json')).json()
  cleanup(); act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(loaded.content)).toBe(true) }); render(<ConfigPanel selectedNodeId={id} />); expandAdvanced()
  expect(data()).toEqual(expected); expect((labelled('节点备注', 'textbox') as HTMLInputElement).value).toBe('高级配置验收')
})
it.each([
  ['maxRetries', '1abc'], ['maxRetries', ''], ['maxRetries', 0], ['maxRetries', 1.5], ['interval', 'Infinity'], ['interval', -1],
] as const)('ADV.preflight.%s.%s rejects the specific nested field', async (field, value) => {
  const { staticNumberIssues } = await import('../lib/staticNumberPreflight')
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'retry-self', maxRetries: 1, interval: 0, [field]: value } })
  expect(staticNumberIssues(store.getState().nodes)).toContainEqual({ nodeId: id, path: `data.errorPolicy.${field}`, message: expect.any(String) })
  expect(data().errorPolicy?.[field]).toBe(value)
})
it.each(['stop', 'continue', 'retry-self', 'retry-from'] as const)('ADV.preflight-mode.%s respects inactive fields and deferred templates', async mode => {
  const { staticNumberIssues } = await import('../lib/staticNumberPreflight')
  store.getState().updateNodeData(id, { errorPolicy: { mode, maxRetries: mode.startsWith('retry-') ? '{count}' : 'invalid', interval: mode.startsWith('retry-') ? '${delay}' : -1 } })
  expect(staticNumberIssues(store.getState().nodes)).toEqual([])
})
it('ADV.name-history editing shared note participates in undo and reopen', () => {
  store.getState().updateNodeData(id, { name: '原备注' }); render(<ConfigPanel selectedNodeId={id} />); expandAdvanced()
  edit('节点备注', '新备注'); history('name', '原备注', '新备注')
})
it.each([
  ['switch_tab', 'tabIndex', 1.5], ['switch_tab', 'tabIndex', '1abc'], ['switch_iframe', 'iframeIndex', -1], ['switch_iframe', 'iframeIndex', 1.5], ['wait_element', 'waitTimeout', 'Infinity'], ['wait_element', 'waitTimeout', -1],
] as const)('ADV.web-preflight.%s.%s.%s rejects active malformed fields', async (type, field, value) => {
  const { staticNumberIssues } = await import('../lib/staticNumberPreflight')
  store.getState().clearWorkflow(); store.getState().addNode(type, { x: 0, y: 0 }, { [field]: value }); const node = store.getState().nodes[0]
  expect(staticNumberIssues(store.getState().nodes)).toContainEqual({ nodeId: node.id, path: `data.${field}`, message: expect.any(String) })
  expect(node.data[field]).toBe(value)
})
it.each([['switch_tab', { switchMode: 'title', tabIndex: 'bad' }], ['switch_iframe', { locateBy: 'name', iframeIndex: 'bad' }], ['switch_tab', { tabIndex: '{index}' }], ['switch_iframe', { iframeIndex: '${index}' }], ['wait_element', { waitTimeout: 0.5 }]] as const)('ADV.web-preflight-allowed.%s.%j respects inactive fields, templates and fractional timeout', async (type, values) => {
  const { staticNumberIssues } = await import('../lib/staticNumberPreflight')
  store.getState().clearWorkflow(); store.getState().addNode(type, { x: 0, y: 0 }, values)
  expect(staticNumberIssues(store.getState().nodes)).toEqual([])
})
it.each([0, 1, 2.5])('ADV.page-wait-min.%s matches the form minimum of one second', async timeout => {
  const { staticNumberIssues } = await import('../lib/staticNumberPreflight')
  store.getState().clearWorkflow(); store.getState().addNode('wait_page_load', { x: 0, y: 0 }, { timeout }); const node = store.getState().nodes[0]
  const issues = staticNumberIssues(store.getState().nodes)
  if (timeout === 0) expect(issues).toEqual([{ nodeId: node.id, path: 'data.timeout', message: '页面等待超时不能小于1' }])
  else expect(issues).toEqual([])
})
