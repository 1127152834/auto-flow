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
import { featureFlags } from '../lib/featureFlags'
Element.prototype.scrollIntoView = vi.fn()
let id: string
// These controls stay in the code but are hidden until M2 implements them (remediation M1 R1-01).
beforeEach(() => { featureFlags.nodeRetryPolicy = true; store.getState().clearWorkflow(); store.getState().addNode('close_page', { x: 0, y: 0 }); id = store.getState().nodes[0].id })
afterEach(() => { cleanup(); featureFlags.nodeRetryPolicy = false })
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
it.each([['retry', '重试'], ['skip', '跳过该模块，继续执行'], ['stop', '停止工作流执行']])('ADV.timeoutAction.%s', (value, option) => {
  const previous = value === 'retry' ? 'skip' : 'retry'; store.getState().updateNodeData(id, { timeoutAction: previous })
  render(<ConfigPanel selectedNodeId={id} />); choose('运行超时后', option); history('timeoutAction', previous, value)
})
it.each([['stop', '停止工作流'], ['skip', '跳过该模块，继续执行']])('ADV.exhausted.%s', (value, option) => {
  const previous = value === 'stop' ? 'skip' : 'stop'; store.getState().updateNodeData(id, { retryCount: 2, retryExhaustedAction: previous })
  render(<ConfigPanel selectedNodeId={id} />); choose('重试耗尽后', option); history('retryExhaustedAction', previous, value)
})
it.each([['fixed', '固定间隔'], ['exponential', '指数退避（间隔翻倍）']])('ADV.backoff.%s', (value, option) => {
  const previous = value === 'fixed' ? 'exponential' : 'fixed'; store.getState().updateNodeData(id, { retryCount: 2, retryDelay: 1, retryBackoff: previous })
  render(<ConfigPanel selectedNodeId={id} />); choose('退避策略', option); history('retryBackoff', previous, value)
})
it('ADV.visibility preserves inactive delay/backoff and exposes them only with positive count/delay', () => {
  store.getState().updateNodeData(id, { retryCount: 0, retryDelay: 0, retryBackoff: 'exponential' }); render(<ConfigPanel selectedNodeId={id} />)
  expect(screen.queryByText('重试间隔（秒）')).toBeNull(); expect(screen.queryByText('退避策略')).toBeNull()
  edit('重试次数', '2'); expect(screen.getByText('重试间隔（秒）')).toBeDefined(); expect(screen.queryByText('退避策略')).toBeNull()
  edit('重试间隔（秒）', '1'); expect(screen.getByText('退避策略')).toBeDefined()
  edit('重试次数', '0'); expect(screen.queryByText('退避策略')).toBeNull(); expect(data()).toMatchObject({ retryDelay: 1, retryBackoff: 'exponential' })
})
it.each([['timeout', '超时时间 (秒)', '1abc'], ['timeout', '超时时间 (秒)', '-1'], ['retryCount', '重试次数', '11'], ['retryCount', '重试次数', 'Infinity'], ['retryDelay', '重试间隔（秒）', '1abc']])('ADV.numeric.%s.%s.%s retains invalid drafts under existing NumberInput contract', (field, label, value) => {
  store.getState().updateNodeData(id, { retryCount: 2, [field]: 3 }); render(<ConfigPanel selectedNodeId={id} />)
  edit(label, value); const expected = value === '-1' ? -1 : value === '11' ? 11 : value
  expect(labelled(label, 'textbox').getAttribute('aria-invalid')).toBe('true'); history(field, 3, expected)
})
it('ADV.policy-v2 shows an old error policy as a candidate and enabling it is undoable and saved', () => {
  // Remediation M2 R2-08/R2-12: the old shape is never executed until the person enables it.
  const previous: ErrorPolicy = { mode: 'retry-self', maxRetries: 2, interval: 1, onExhausted: 'stop' }
  store.getState().updateNodeData(id, { errorPolicy: previous }); store.getState().markAsSaved()
  render(<ConfigPanel selectedNodeId={id} />)
  expect(screen.getByRole('status', { name: '未生效的出错设置' })).toHaveTextContent('以前保存的设置“出错时重试 2 次”尚未生效')
  fireEvent.click(screen.getByRole('button', { name: '启用这项设置' }))
  history('errorPolicy', previous, { version: 2, onError: 'retry', maxRetries: 2, backoff: { kind: 'fixed', initialSeconds: 1, maxSeconds: 1, jitter: false }, retryOn: 'any', gotoNodeId: null, onExhausted: 'stop' })
})
it('ADV.context does not send detached old field blur into a newly selected node', () => {
  store.getState().addNode('close_page', { x: 0, y: 100 }); const second = store.getState().nodes[1].id
  const view = render(<ConfigPanel selectedNodeId={id} />); const old = labelled('超时时间 (秒)', 'textbox')
  fireEvent.change(old, { target: { value: '12' } }); view.rerender(<ConfigPanel selectedNodeId={second} />); fireEvent.blur(old)
  expect(store.getState().nodes.find(n => n.id === second)!.data.timeout).not.toBe(12); expect(data().timeout).toBe(12)
})
it('ADV.save persists shared fields through real mock save/load and re-render', async () => {
  render(<ConfigPanel selectedNodeId={id} />)
  edit('节点备注', '高级配置验收'); edit('超时时间 (秒)', '12.5'); edit('重试次数', '3'); edit('重试间隔（秒）', '2'); choose('退避策略', '指数退避（间隔翻倍）'); choose('出错时', '原地重试当前模块')
  const expected = { ...data() }; const content = JSON.parse(store.getState().exportWorkflow())
  const saved = await mockRequest('http://autoflow-studio.mock/api/local-workflows/save-to-folder', { method: 'POST', body: JSON.stringify({ filename: 'advanced-fields', content }) }); expect(saved.status).toBe(200)
  const loaded = await (await mockRequest('http://autoflow-studio.mock/api/local-workflows/load/advanced-fields.json')).json()
  cleanup(); act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(loaded.content)).toBe(true) }); render(<ConfigPanel selectedNodeId={id} />)
  expect(data()).toEqual(expected); expect((labelled('节点备注', 'textbox') as HTMLInputElement).value).toBe('高级配置验收')
})
it.each([['maxRetries', '出错处理重试次数'], ['interval', '出错处理间隔（秒）']] as const)('ADV.block.%s uses same draft-preserving numeric control', async (field, label) => {
  const { BlockFlowView } = await import('../components/BlockFlowView')
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'retry-self', maxRetries: 1, interval: 0, onExhausted: 'stop' } })
  render(<BlockFlowView />); fireEvent.click(screen.getByTitle('出错处理（原地重试 / 回流上层重试 / 跳过继续）'))
  const input = screen.getByRole('textbox', { name: label })
  fireEvent.change(input, { target: { value: '1abc' } }); fireEvent.blur(input)
  expect(data().errorPolicy?.[field]).toBe('1abc'); expect(input.getAttribute('aria-invalid')).toBe('true')
  fireEvent.change(input, { target: { value: '{retry_value}' } }); fireEvent.blur(input)
  expect(data().errorPolicy?.[field]).toBe('{retry_value}')
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
  store.getState().updateNodeData(id, { name: '原备注' }); render(<ConfigPanel selectedNodeId={id} />)
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
