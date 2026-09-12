import '@testing-library/jest-dom/vitest'
import { act, cleanup, createEvent, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../../app/ApiProvider'
import { StudioPage } from '../pages/StudioPage'
import type { WorkflowCanvasProps } from '../components/WorkflowCanvas'
import type { NodeDefinition, WorkflowContent, WorkflowRead } from '../types'

// Canvas geometry belongs to its component/Electron tests; document state and the
// inspector, variable editor, persistence hook and HTTP client remain real here.
vi.mock('../components/WorkflowCanvas', () => ({
  WorkflowCanvas: ({ content, disabled, onSelect, onMove, onConnect, onEditStart, onEditEnd }: WorkflowCanvasProps) => <section aria-label="测试画布">
    <output data-testid="document">{JSON.stringify(content)}</output>
    {content.document.nodes.map((node) => <button key={node.id} disabled={disabled} onClick={() => onSelect([node.id], [])}>选择节点 {node.type}</button>)}
    <button disabled={disabled} onClick={() => { onEditStart(); onMove(Object.fromEntries(content.document.nodes.map((node, index) => [node.id, { x: 300 + index * 100, y: 200 }]))); onEditEnd() }}>移动全部节点</button>
    <button disabled={disabled} onClick={() => content.document.nodes.slice(1).forEach((node, index) => onConnect(content.document.nodes[index].id, node.id))}>顺序连接节点</button>
  </section>,
}))

const text = { type: 'string' }
function definition(type: NodeDefinition['type'], title: string, defaults: Record<string, unknown>, properties: Record<string, unknown>, required: string[]): NodeDefinition {
  return { type, title, description: '', category: '浏览器', defaultConfig: { ...defaults, timeoutSeconds: 60 }, configSchema: { type: 'object', properties: { ...properties, timeoutSeconds: { type: 'number', exclusiveMinimum: 0 } }, required, additionalProperties: false }, inputPorts: ['in'], outputPorts: ['out'], runnable: false }
}
const catalog = [
  definition('open_page', '打开网页', { url: '', openMode: 'new_tab', waitUntil: 'load' }, { url: text, openMode: text, waitUntil: text }, ['url']),
  definition('click_element', '点击元素', { selector: '', clickType: 'single', followNewTab: false }, { selector: text, clickType: text, followNewTab: { type: 'boolean' } }, ['selector']),
  definition('input_text', '输入文本', { selector: '', text: '', clearBefore: true }, { selector: text, text, clearBefore: { type: 'boolean' } }, ['selector']),
  definition('wait_element', '等待元素', { selector: '', waitCondition: 'visible' }, { selector: text, waitCondition: text }, ['selector']),
  definition('get_element_info', '提取数据', { selector: '', attribute: 'text', variableName: 'element_value' }, { selector: text, attribute: text, variableName: text }, ['selector', 'variableName']),
  definition('screenshot', '网页截图', { screenshotType: 'fullpage', selector: '', savePath: '', variableName: 'screenshot_path' }, { screenshotType: text, selector: text, savePath: text, variableName: text }, ['variableName']),
]

const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } })
const time = '2026-09-13T00:00:00Z'
function savedFlow(id = 'saved-flow', name = '已保存的流程'): WorkflowRead {
  return {
    document: { id, name, schemaVersion: 1, nodes: [{ id: 'stored-node', type: 'input_text', label: '填写关键词', config: { selector: '#search', text: '${目标}', clearBefore: false, timeoutSeconds: 15 } }], edges: [], variables: [{ name: '目标', type: 'string', value: '保留的初值' }] },
    layout: { nodes: { 'stored-node': { x: 420, y: 180 } }, viewport: { x: 40, y: 20, zoom: 0.8 } },
    revision: 3, createdAt: time, updatedAt: time, issues: [],
  }
}

type Request = { path: string; method: string; body?: WorkflowContent & { expectedRevision?: number }; headers: Headers }
function testServer(initial: WorkflowRead[] = []) {
  const documents = new Map(initial.map((record) => [record.document.id, structuredClone(record)]))
  const requests: Request[] = []
  let writeError: string | null = null
  let readBarrier: Promise<void> | null = null
  let writeBarrier: Promise<void> | null = null
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) as Request['body'] : undefined
    requests.push({ path, method, body, headers: new Headers(init?.headers) })
    if (path === '/api/v1/workflows/node-catalog') return json({ items: catalog })
    if (path === '/api/v1/workflows' && method === 'GET') return json({ items: [...documents.values()].map((record) => ({ id: record.document.id, name: record.document.name, revision: record.revision, updatedAt: record.updatedAt })) })
    if (method === 'GET' && path.startsWith('/api/v1/workflows/')) {
      if (readBarrier) await readBarrier
      const record = documents.get(decodeURIComponent(path.split('/').at(-1)!))
      if (record) return json(record)
      return json({ error: { code: 'WORKFLOW_NOT_FOUND', message: '流程不存在', details: {}, requestId: 'fixture' } }, 404)
    }
    if ((method === 'POST' || method === 'PUT') && body) {
      if (writeBarrier) await writeBarrier
      if (writeError) return json({ error: { code: 'WORKFLOW_WRITE_FAILED', message: writeError, details: {}, requestId: 'fixture' } }, 503)
      const previous = documents.get(body.document.id)
      if (method === 'PUT' && body.expectedRevision !== previous?.revision) return json({ error: { code: 'WORKFLOW_CONFLICT', message: '流程已被其他窗口修改', details: {}, requestId: 'fixture' } }, 409)
      const record: WorkflowRead = { document: body.document, layout: body.layout, revision: (previous?.revision ?? 0) + 1, createdAt: previous?.createdAt ?? time, updatedAt: time, issues: [] }
      documents.set(record.document.id, record)
      return json(record, method === 'POST' ? 201 : 200)
    }
    throw new Error(`Unexpected request ${method} ${path}`)
  })
  return { fetch, requests, documents, setWriteError(message: string | null) { writeError = message }, pauseRead(barrier: Promise<void>) { readBarrier = barrier }, pauseWrite(barrier: Promise<void>) { writeBarrier = barrier } }
}

type LeaveHandler = (reason: 'close' | 'quit' | 'workspace' | 'new' | 'open') => Promise<boolean>
function setup(initial: WorkflowRead[] = []) {
  const server = testServer(initial)
  vi.stubGlobal('fetch', server.fetch)
  let leave: LeaveHandler | null = null
  const registerLeave = vi.fn((handler: LeaveHandler | null) => { leave = handler })
  const page = (connected = true, locked = false) => <ApiProvider baseUrl="http://127.0.0.1:43127" token="studio-test-token" instanceId="studio-test-instance"><StudioPage connected={connected} locked={locked} registerLeave={registerLeave} /></ApiProvider>
  const view = render(page())
  return { ...view, server, registerLeave, prepareLeave: (reason: Parameters<LeaveHandler>[0]) => leave!(reason), setConnection(connected: boolean, locked = false) { view.rerender(page(connected, locked)) } }
}

const content = () => JSON.parse(screen.getByTestId('document').textContent!) as WorkflowContent
const writes = (server: ReturnType<typeof testServer>) => server.requests.filter((request) => request.method === 'POST' || request.method === 'PUT')
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('creates all six nodes, sends an authenticated manual save, then updates with a revision through Ctrl+S', async () => {
  const user = userEvent.setup()
  const { server } = setup()
  await screen.findByRole('button', { name: '添加打开网页' })
  await user.clear(screen.getByLabelText('流程名称'))
  await user.type(screen.getByLabelText('流程名称'), '六步流程')
  for (const item of catalog) await user.click(screen.getByRole('button', { name: `添加${item.title}` }))
  await user.selectOptions(screen.getByLabelText('截图范围'), 'element')
  expect(screen.getByLabelText('元素选择器')).toHaveValue('')
  await user.click(screen.getByRole('button', { name: '移动全部节点' }))
  await user.click(screen.getByRole('button', { name: '顺序连接节点' }))
  expect(writes(server)).toHaveLength(0)
  const draft = structuredClone(content())
  await user.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('已保存')
  expect(writes(server)).toHaveLength(1)
  expect(writes(server)[0]).toMatchObject({ path: '/api/v1/workflows', method: 'POST', body: draft })
  expect(writes(server)[0].headers.get('x-autoflow-token')).toBe('studio-test-token')
  expect(writes(server)[0].headers.get('content-type')).toBe('application/json')
  expect(draft.document.nodes).toHaveLength(6)
  expect(draft.document.edges).toHaveLength(5)
  expect(draft.document.nodes.find((node) => node.type === 'input_text')?.config.text).toBe('')
  expect(draft.document.nodes.find((node) => node.type === 'screenshot')?.config.screenshotType).toBe('element')
  await user.click(screen.getByRole('button', { name: '选择节点 open_page' }))
  await user.type(screen.getByLabelText('网页地址'), 'https://example.test')
  fireEvent.keyDown(screen.getByLabelText('网页地址'), { key: 's', ctrlKey: true })
  await waitFor(() => expect(writes(server)).toHaveLength(2))
  expect(writes(server)[1]).toMatchObject({ method: 'PUT', path: `/api/v1/workflows/${draft.document.id}`, body: { expectedRevision: 1, document: { id: draft.document.id } } })
  expect(writes(server)[1].body?.document.nodes[0].config.url).toBe('https://example.test')
})

it('leaves text editing shortcuts alone while canvas copy, paste and undo operate on document nodes', async () => {
  const user = userEvent.setup()
  setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  const url = screen.getByLabelText('网页地址')
  await user.type(url, 'https://example.test')
  const before = structuredClone(content())
  for (const key of ['Backspace', 'Delete', 'z', 'c', 'x', 'v', 'a']) {
    const event = createEvent.keyDown(url, { key, ctrlKey: !['Backspace', 'Delete'].includes(key), bubbles: true, cancelable: true })
    fireEvent(url, event)
    expect(event.defaultPrevented).toBe(false)
    expect(content()).toEqual(before)
  }
  await user.click(screen.getByRole('button', { name: '选择节点 open_page' }))
  fireEvent.keyDown(document.body, { key: 'c', ctrlKey: true })
  fireEvent.keyDown(document.body, { key: 'v', ctrlKey: true })
  expect(content().document.nodes).toHaveLength(2)
  expect(new Set(content().document.nodes.map((node) => node.id)).size).toBe(2)
  fireEvent.keyDown(document.body, { key: 'z', ctrlKey: true })
  expect(content()).toEqual(before)
})

it('keeps a dirty flow when new is cancelled or saving fails, then saves before replacing it', async () => {
  const user = userEvent.setup()
  const { server } = setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  const draft = structuredClone(content())
  await user.click(screen.getByRole('button', { name: '新建' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '取消' }))
  expect(content()).toEqual(draft)
  server.setWriteError('磁盘写入失败，编辑内容已保留')
  await user.click(screen.getByRole('button', { name: '新建' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '保存并继续' }))
  expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('磁盘写入失败')
  expect(content()).toEqual(draft)
  expect(screen.getByRole('dialog')).toBeVisible()
  server.setWriteError(null)
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '保存并继续' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(content().document.nodes).toHaveLength(0)
  expect(content().document.id).not.toBe(draft.document.id)
  expect(server.documents.get(draft.document.id)?.document).toEqual(draft.document)
  expect(writes(server).map((request) => request.body?.document.id)).toEqual([draft.document.id, draft.document.id])
})

it('protects the current draft before opening, searches the server list and restores stored parameters and layout', async () => {
  const user = userEvent.setup()
  const stored = savedFlow()
  const { server } = setup([stored, savedFlow('other-flow', '另一个流程')])
  await user.click(await screen.findByRole('button', { name: '添加网页截图' }))
  const original = structuredClone(content())
  await user.click(screen.getByRole('button', { name: '打开' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '取消' }))
  expect(content()).toEqual(original)
  expect(server.requests.some((request) => request.path === '/api/v1/workflows')).toBe(false)
  await user.click(screen.getByRole('button', { name: '打开' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '放弃修改' }))
  await screen.findByRole('heading', { name: '打开工作流' })
  await user.type(screen.getByLabelText('搜索工作流'), '已保存')
  const dialog = within(screen.getByRole('dialog'))
  expect(dialog.queryByRole('button', { name: /另一个流程/ })).not.toBeInTheDocument()
  await user.click(await dialog.findByRole('button', { name: /已保存的流程/ }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(content()).toEqual({ document: stored.document, layout: stored.layout })
  expect(screen.getByLabelText('流程名称')).toHaveValue(stored.document.name)
  await user.click(screen.getByRole('button', { name: '选择节点 input_text' }))
  expect(screen.getByLabelText('输入文本')).toHaveValue('${目标}')
  expect(screen.getByLabelText('超时（秒）')).toHaveValue(15)
  expect(screen.getByRole('switch', { name: '输入前清空' })).not.toBeChecked()
  expect(server.requests.some((request) => request.path === '/api/v1/workflows/saved-flow' && request.method === 'GET')).toBe(true)
  expect(writes(server)).toHaveLength(0)
})

it('renames references atomically and confirms deleting a referenced variable without deleting its text', async () => {
  const user = userEvent.setup()
  setup()
  await user.click(await screen.findByRole('button', { name: '添加输入文本' }))
  fireEvent.change(screen.getByLabelText('输入文本'), { target: { value: '{variable_1} / ${variable_1}' } })
  await user.click(screen.getByRole('tab', { name: /流程变量/ }))
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  await user.clear(screen.getByLabelText('变量名'))
  await user.type(screen.getByLabelText('变量名'), '目标{Enter}')
  expect(content().document.variables[0].name).toBe('目标')
  expect(content().document.nodes[0].config.text).toBe('{目标} / ${目标}')
  await user.click(screen.getByRole('button', { name: '撤销' }))
  expect(content().document.variables[0].name).toBe('variable_1')
  expect(content().document.nodes[0].config.text).toBe('{variable_1} / ${variable_1}')
  await user.click(screen.getByRole('button', { name: '重做' }))
  await user.click(screen.getByRole('button', { name: '删除变量 目标' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '取消' }))
  expect(content().document.variables).toHaveLength(1)
  await user.click(screen.getByRole('button', { name: '删除变量 目标' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '删除变量' }))
  expect(content().document.variables).toEqual([])
  expect(content().document.nodes[0].config.text).toBe('{目标} / ${目标}')
  await user.click(screen.getByRole('tab', { name: '节点属性' }))
  expect(screen.getAllByText('变量 目标 尚未声明').length).toBeGreaterThan(0)
  await user.click(screen.getByRole('button', { name: '撤销' }))
  expect(content().document.variables[0].name).toBe('目标')
  expect(screen.queryByText('变量 目标 尚未声明')).not.toBeInTheDocument()
})

it.each(['close', 'quit', 'workspace'] as const)('uses the registered %s leave guard and preserves the draft when cancelled', async (reason) => {
  const user = userEvent.setup()
  const view = setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  const before = structuredClone(content())
  let leaving!: Promise<boolean>
  act(() => { leaving = view.prepareLeave(reason) })
  const dialog = await screen.findByRole('dialog')
  await user.click(within(dialog).getByRole('button', { name: '取消' }))
  expect(await leaving).toBe(false)
  expect(content()).toEqual(before)
  act(() => { leaving = view.prepareLeave(reason) })
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '放弃修改' }))
  expect(await leaving).toBe(true)
  expect(writes(view.server)).toHaveLength(0)
  view.unmount()
  expect(view.registerLeave).toHaveBeenLastCalledWith(null)
})

it('keeps editing available offline, locks it during a workspace switch, then saves the same draft after reconnecting', async () => {
  const user = userEvent.setup()
  const view = setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  view.setConnection(false)
  expect(screen.getByRole('button', { name: '保存' })).toBeDisabled()
  await user.type(screen.getByLabelText('网页地址'), 'https://offline-edit.test')
  const draft = structuredClone(content())
  view.setConnection(false, true)
  expect(screen.getByLabelText('网页地址')).toBeDisabled()
  expect(screen.getByLabelText('流程名称')).toBeDisabled()
  expect(screen.getByRole('button', { name: '添加打开网页' })).toBeDisabled()
  view.setConnection(true)
  expect(content()).toEqual(draft)
  await user.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('已保存')
  expect(writes(view.server)[0].body).toEqual(draft)
})

it('locks background edits and refuses window leave while a stored flow is still opening', async () => {
  const user = userEvent.setup()
  const stored = savedFlow()
  const view = setup([stored])
  let finish!: () => void
  view.server.pauseRead(new Promise<void>((resolve) => { finish = resolve }))
  await screen.findByRole('button', { name: '添加打开网页' })
  const initial = structuredClone(content())
  await user.click(screen.getByRole('button', { name: '打开' }))
  await user.click(await within(screen.getByRole('dialog')).findByRole('button', { name: /已保存的流程/ }))
  expect(screen.getByLabelText('流程名称')).toBeDisabled()
  expect(screen.getByText('正在打开…')).toBeVisible()
  expect(within(screen.getByRole('dialog')).getByRole('button', { name: '关闭' })).toBeDisabled()
  fireEvent.keyDown(document.body, { key: 'v', ctrlKey: true })
  expect(content()).toEqual(initial)
  expect(await view.prepareLeave('close')).toBe(false)
  await act(async () => { finish() })
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(content()).toEqual({ document: stored.document, layout: stored.layout })
  expect(screen.getByLabelText('流程名称')).toBeEnabled()
})

it.each(['shortcut', 'close'] as const)('commits a still-focused variable rename before %s checks or saves the document', async (trigger) => {
  const user = userEvent.setup()
  const view = setup()
  await screen.findByRole('button', { name: '添加打开网页' })
  await user.click(screen.getByRole('tab', { name: /流程变量/ }))
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  await user.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('已保存')
  await user.clear(screen.getByLabelText('变量名'))
  await user.type(screen.getByLabelText('变量名'), '聚焦的重命名')
  expect(content().document.variables[0].name).toBe('variable_1')
  if (trigger === 'shortcut') {
    fireEvent.keyDown(screen.getByLabelText('变量名'), { key: 's', ctrlKey: true })
    await waitFor(() => expect(writes(view.server)).toHaveLength(2))
  } else {
    let leaving!: Promise<boolean>
    act(() => { leaving = view.prepareLeave('close') })
    const dialog = await screen.findByRole('dialog')
    expect(content().document.variables[0].name).toBe('聚焦的重命名')
    await user.click(within(dialog).getByRole('button', { name: '保存并继续' }))
    expect(await leaving).toBe(true)
  }
  expect(writes(view.server)[1].body?.document.variables[0].name).toBe('聚焦的重命名')
  expect(content().document.variables[0].name).toBe('聚焦的重命名')
})

it('waits for an in-flight save before deciding whether an undo back to the old baseline can close', async () => {
  const user = userEvent.setup()
  const view = setup()
  let finish!: () => void
  view.server.pauseWrite(new Promise<void>((resolve) => { finish = resolve }))
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  await user.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('正在保存…')
  await user.click(screen.getByRole('button', { name: '撤销' }))
  expect(content().document.nodes).toHaveLength(0)
  let leaving!: Promise<boolean>
  let finished = false
  act(() => { leaving = view.prepareLeave('close'); void leaving.then(() => { finished = true }) })
  expect(finished).toBe(false)
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await act(async () => { finish() })
  const dialog = await screen.findByRole('dialog')
  expect(finished).toBe(false)
  expect(view.server.documents.get(content().document.id)?.document.nodes).toHaveLength(1)
  await user.click(within(dialog).getByRole('button', { name: '取消' }))
  expect(await leaving).toBe(false)
  expect(content().document.nodes).toHaveLength(0)
})
