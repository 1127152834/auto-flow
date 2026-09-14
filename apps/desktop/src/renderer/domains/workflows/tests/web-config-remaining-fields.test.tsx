import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'
import { configureStudioConnection } from '../api/config'
import { mockRequest } from '../api/mock-server'
Element.prototype.scrollIntoView = vi.fn()
let restore: (() => void) | undefined
beforeEach(() => store.getState().clearWorkflow())
afterEach(() => { cleanup(); restore?.(); restore = undefined })
async function reopen() {
  const saved = await mockRequest('http://autoflow-studio.mock/api/local-workflows/save-to-folder', { method: 'POST', body: JSON.stringify({ filename: 'remaining-fields', content: JSON.parse(store.getState().exportWorkflow()) }) })
  expect(saved.status).toBe(200)
  const loaded = await (await mockRequest('http://autoflow-studio.mock/api/local-workflows/load/remaining-fields.json')).json()
  act(() => { store.getState().clearWorkflow(); expect(store.getState().importWorkflow(loaded.content)).toBe(true) })
}
it.each([['0', 0, false], ['2.5', 2.5, false], ['{seconds}', '{seconds}', false], ['', '', false], ['-1', -1, true], ['Infinity', 'Infinity', true]] as const)('wait_element timeout %s preserves the editor contract, history and saved document', async (text, value, invalid) => {
  store.getState().addNode('wait_element', { x: 0, y: 0 })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)
  const input = screen.getByLabelText('超时时间(秒)') as HTMLInputElement
  expect(input.value).toBe('60')
  fireEvent.change(input, { target: { value: text } }); fireEvent.blur(input)
  expect(store.getState().nodes[0].data.waitTimeout).toBe(value)
  expect(input.getAttribute('aria-invalid') === 'true').toBe(invalid)
  act(() => store.getState().undo()); expect(input.value).toBe('60')
  act(() => { store.getState().redo(); store.getState().copyNodes([id]); store.getState().pasteNodes() })
  expect(store.getState().nodes[1].data.waitTimeout).toBe(value)
  await reopen()
  expect(store.getState().nodes[0].data.waitTimeout).toBe(value)
})
it('screenshot path tool reaches the system endpoint, writes one history change and survives save/reopen', async () => {
  const requests: unknown[] = []
  restore = configureStudioConnection('http://autoflow-studio.mock', async (input, init) => {
    if (String(input).endsWith('/api/system/select-file')) {
      requests.push(JSON.parse(String(init?.body)))
      return Response.json({ success: true, path: '/截图/{name}/页面.png' })
    }
    return mockRequest(input, init)
  })
  store.getState().addNode('screenshot', { x: 0, y: 0 }, { savePath: '/before.png' })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.click(screen.getByTitle('选择文件'))
  await waitFor(() => expect(store.getState().nodes[0].data.savePath).toBe('/截图/{name}/页面.png'))
  expect(requests).toEqual([{ title: '选择文件' }])
  act(() => store.getState().undo()); expect(store.getState().nodes[0].data.savePath).toBe('/before.png')
  act(() => { store.getState().redo(); store.getState().copyNodes([id]); store.getState().pasteNodes() })
  expect(store.getState().nodes[1].data.savePath).toBe('/截图/{name}/页面.png')
  await reopen(); expect(store.getState().nodes[0].data.savePath).toBe('/截图/{name}/页面.png')
})
it.each(['cancel', 'failure', 'switch-node', 'edit'] as const)('screenshot path %s preserves the correct node draft', async mode => {
  let reply!: (value: Response) => void
  restore = configureStudioConnection('http://autoflow-studio.mock', (input, init) => String(input).endsWith('/api/system/select-file') ? new Promise(resolve => { reply = resolve }) : mockRequest(input, init))
  store.getState().addNode('screenshot', { x: 0, y: 0 }, { savePath: '/first.png' })
  store.getState().addNode('screenshot', { x: 0, y: 200 }, { savePath: '/second.png' })
  const [first, second] = store.getState().nodes
  const view = render(<ConfigPanel selectedNodeId={first.id} />)
  fireEvent.click(screen.getByTitle('选择文件'))
  await waitFor(() => expect(reply).toBeTypeOf('function'))
  if (mode === 'switch-node') view.rerender(<ConfigPanel selectedNodeId={second.id} />)
  if (mode === 'edit') {
    const input = screen.getByDisplayValue('/first.png')
    fireEvent.change(input, { target: { value: '/manual.png' } }); fireEvent.blur(input)
  }
  await act(async () => reply(mode === 'failure' ? Response.json({ error: '权限不足' }, { status: 403 }) : Response.json(mode === 'cancel' ? { success: false, path: null, message: '用户取消选择' } : { success: true, path: '/late.png' })))
  if (mode === 'failure') expect((await screen.findByRole('alert')).textContent).toContain('权限不足')
  expect(store.getState().nodes[0].data.savePath).toBe(mode === 'edit' ? '/manual.png' : '/first.png')
  expect(store.getState().nodes[1].data.savePath).toBe('/second.png')
})
it('open_page URL suggestions deduplicate other pages and apply only to the selected node with history', async () => {
  store.getState().addNode('open_page', { x: 0, y: 0 }, { url: 'https://current.test' })
  const id = store.getState().nodes[0].id
  store.getState().addNode('open_page', { x: 0, y: 100 }, { url: 'https://other.test/{path}' })
  store.getState().addNode('open_page', { x: 0, y: 200 }, { url: 'https://other.test/{path}' })
  render(<ConfigPanel selectedNodeId={id} />)
  fireEvent.focus(screen.getByPlaceholderText('https://example.com'))
  expect(screen.getAllByTitle('https://other.test/{path}')).toHaveLength(1)
  expect(screen.queryByTitle('https://current.test')).toBeNull()
  fireEvent.click(screen.getByTitle('https://other.test/{path}'))
  expect(store.getState().nodes[0].data.url).toBe('https://other.test/{path}')
  expect(screen.queryByText('流程中的网址')).toBeNull()
  act(() => store.getState().undo()); expect(store.getState().nodes[0].data.url).toBe('https://current.test')
  act(() => store.getState().redo())
  await reopen(); expect(store.getState().nodes[0].data.url).toBe('https://other.test/{path}')
})
