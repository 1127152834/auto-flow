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
it.each([
  ['stop', '失败即停（默认）'], ['continue', '跳过并继续'], ['retry-self', '原地重试当前模块'], ['retry-from', '回流到上层模块重试'],
])('ADV.mode.%s updates real panel, visibility, history and serialization', (mode, option) => {
  const previous: ErrorPolicy = { mode: mode === 'continue' ? 'retry-self' : 'continue', maxRetries: 3, interval: 2, onExhausted: 'stop' }
  store.getState().updateNodeData(id, { errorPolicy: previous }); store.getState().markAsSaved()
  render(<ConfigPanel selectedNodeId={id} />); choose('出错时', option)
  expect(screen.queryByText('间隔(秒)') !== null).toBe(mode.startsWith('retry-'))
  expect(screen.queryByText('回流目标模块') !== null).toBe(mode === 'retry-from')
  expect(screen.queryByText('重试用尽后') !== null).toBe(mode === 'retry-from')
  expect(store.getState().hasUnsavedChanges).toBe(true)
  history('errorPolicy', previous, mode === 'stop' ? undefined : { ...previous, mode })
})
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
it('ADV.target offers another module but not itself and preserves retry-from configuration', () => {
  store.getState().addNode('open_page', { x: 0, y: 100 }); const target = store.getState().nodes[1].id
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'retry-from', maxRetries: 1, interval: 0, onExhausted: 'stop' } })
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.keyDown(labelled('回流目标模块', 'combobox'), { key: 'ArrowDown' })
  expect(screen.queryByRole('option', { name: '关闭网页' })).toBeNull(); fireEvent.click(screen.getByRole('option', { name: '打开网页' }))
  choose('重试用尽后', '继续往下'); edit('间隔(秒)', '2.5')
  expect(data().errorPolicy).toMatchObject({ targetId: target, onExhausted: 'continue', interval: 2.5 })
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
it.each([['maxRetries', '重试次数', '4', 4], ['interval', '间隔(秒)', '0.5', 0.5]] as const)('ADV.policy-number.%s updates structured policy and survives undo/reopen', (field, label, value, expected) => {
  const previous: ErrorPolicy = { mode: 'retry-self', maxRetries: 1, interval: 0, onExhausted: 'stop' }
  store.getState().updateNodeData(id, { errorPolicy: previous }); render(<ConfigPanel selectedNodeId={id} />)
  edit(label, value); history('errorPolicy', previous, { ...previous, [field]: expected })
})
it('ADV.policy-exhausted stop and continue both preserve retry target', () => {
  const previous: ErrorPolicy = { mode: 'retry-from', targetId: 'upstream', maxRetries: 2, interval: 1, onExhausted: 'continue' }
  store.getState().updateNodeData(id, { errorPolicy: previous }); render(<ConfigPanel selectedNodeId={id} />)
  choose('重试用尽后', '停止流程'); history('errorPolicy', previous, { ...previous, onExhausted: 'stop' })
})
it.each([['maxRetries', '重试次数'], ['interval', '间隔(秒)']] as const)('ADV.policy-invalid.%s does not introduce a non-finite value into the document', (field, label) => {
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'retry-self', maxRetries: 1, interval: 0, onExhausted: 'stop' } }); render(<ConfigPanel selectedNodeId={id} />)
  edit(label, '1abc'); expect(data().errorPolicy?.[field]).toBe('1abc')
  expect(labelled(label, 'textbox').getAttribute('aria-invalid')).toBe('true')
})

it.each([['maxRetries', '重试次数'], ['interval', '间隔(秒)']] as const)('ADV.policy-reference.%s retains deferred variable source', (field, label) => {
  store.getState().updateNodeData(id, { errorPolicy: { mode: 'retry-self', maxRetries: 1, interval: 0, onExhausted: 'stop' } }); render(<ConfigPanel selectedNodeId={id} />)
  edit(label, '{retry_value}'); expect(data().errorPolicy?.[field]).toBe('{retry_value}')
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
