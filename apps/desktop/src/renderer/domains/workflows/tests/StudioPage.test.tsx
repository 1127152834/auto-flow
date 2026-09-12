import '@testing-library/jest-dom/vitest'
import { act, cleanup, createEvent, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiProvider } from '../../../app/ApiProvider'
import { StudioPage } from '../pages/StudioPage'
import type { WorkflowCanvasProps } from '../components/WorkflowCanvas'
import type { NodeDefinition, WorkflowContent, WorkflowIssue, WorkflowRead } from '../types'
import { isRunActive, type RunRead } from '../run-types'
import { runEvent, runRecord } from './run-fixtures'

// Canvas geometry belongs to its component/Electron tests; document state and the
// inspector, variable editor, persistence hook and HTTP client remain real here.
vi.mock('../components/WorkflowCanvas', () => ({
  WorkflowCanvas: ({ content, disabled, runMarkers, locate, onSelect, onMove, onConnect, onEditStart, onEditEnd }: WorkflowCanvasProps) => <section aria-label="测试画布">
    <output data-testid="document">{JSON.stringify(content)}</output>
    <output data-testid="run-markers">{JSON.stringify(runMarkers ?? {})}</output>
    <output data-testid="run-locate">{JSON.stringify(locate ?? null)}</output>
    {content.document.nodes.map((node) => <button key={node.id} disabled={disabled} onClick={() => onSelect([node.id], [])}>选择节点 {node.type}</button>)}
    <button disabled={disabled} onClick={() => { onEditStart(); onMove(Object.fromEntries(content.document.nodes.map((node, index) => [node.id, { x: 300 + index * 100, y: 200 }]))); onEditEnd() }}>移动全部节点</button>
    <button disabled={disabled} onClick={() => content.document.nodes.slice(1).forEach((node, index) => onConnect(content.document.nodes[index].id, node.id))}>顺序连接节点</button>
  </section>,
}))

const text = { type: 'string' }
function definition(type: NodeDefinition['type'], title: string, defaults: Record<string, unknown>, properties: Record<string, unknown>, required: string[]): NodeDefinition {
  return { type, title, description: '', category: '浏览器', defaultConfig: { ...defaults, timeoutSeconds: 60 }, configSchema: { type: 'object', properties: { ...properties, timeoutSeconds: { type: 'number', exclusiveMinimum: 0 } }, required, additionalProperties: false }, inputPorts: ['in'], outputPorts: ['out'], runnable: true }
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

type Request = { path: string; method: string; body?: WorkflowContent & { expectedRevision?: number; runId?: string; profileId?: string }; headers: Headers }
function testServer(initial: WorkflowRead[] = [], initialRuns: RunRead[] = []) {
  const documents = new Map(initial.map((record) => [record.document.id, structuredClone(record)]))
  const runs = new Map(initialRuns.map(record => [record.runId, structuredClone(record)]))
  const requests: Request[] = []
  let writeError: string | null = null
  let readBarrier: Promise<void> | null = null
  let writeBarrier: Promise<void> | null = null
  let stopBarrier: Promise<void> | null = null
  let loseStartResponse = false
  let runIssue: WorkflowIssue | null = null
  const fetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = new URL(String(input)).pathname
    const method = init?.method ?? 'GET'
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) as Request['body'] : undefined
    requests.push({ path, method, body, headers: new Headers(init?.headers) })
    if (path === '/api/v1/profiles') return json({ items: [{ id: 'profile-1', name: '真实配置', headless: false }], total: 1 })
    if (path === '/api/v1/workflows/runs' && method === 'GET') return json({ items: [...runs.values()], activeRunId: [...runs.values()].find(isRunActive)?.runId ?? null, nextOffset: null })
    if (path === '/api/v1/workflows/runs' && method === 'POST' && body) {
      if (runIssue) return json({ error: { code: 'WORKFLOW_INVALID', message: '运行校验未通过', details: { issues: [runIssue] }, requestId: 'fixture' } }, 422)
      const record = runRecord({ document: body.document, layout: body.layout, runId: body.runId!, workflowId: body.document.id, name: body.document.name, nodeOrder: body.document.nodes.map(node => node.id), currentNodeId: body.document.nodes[0]?.id ?? null })
      runs.set(record.runId, structuredClone(record))
      if (loseStartResponse) throw new TypeError('connection lost after acceptance')
      return json(record, 201)
    }
    if (path.startsWith('/api/v1/workflows/runs/')) {
      const id = path.split('/')[5]
      const record = runs.get(id)
      if (!record) return json({ error: { code: 'RUN_NOT_FOUND', message: '运行不存在', details: {}, requestId: 'fixture' } }, 404)
      if (path.endsWith('/stop')) {
        if (stopBarrier) await stopBarrier
        const stopped = { ...record, state: 'cancelled' as const, finishedAt: time, latestSeq: 2 }
        runs.set(id, stopped)
        return json(stopped)
      }
      if (path.endsWith('/events')) return json({ items: [runEvent(1, { runId: id, nodeId: record.document.nodes[0]?.id ?? null, message: '真实节点开始执行' })], hasMore: false, nextSeq: 1 })
      if (path.endsWith('/stream')) return new Response(new ReadableStream({ start(controller) { init?.signal?.addEventListener('abort', () => controller.close(), { once: true }) } }), { headers: { 'content-type': 'text/event-stream' } })
      return json(record)
    }
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
  return { fetch, requests, documents, runs, setWriteError(message: string | null) { writeError = message }, pauseRead(barrier: Promise<void>) { readBarrier = barrier }, pauseWrite(barrier: Promise<void>) { writeBarrier = barrier }, pauseStop(barrier: Promise<void>) { stopBarrier = barrier }, loseStartResponse() { loseStartResponse = true }, setRunIssue(issue: WorkflowIssue) { runIssue = issue } }
}

type LeaveHandler = (reason: 'close' | 'quit' | 'workspace' | 'new' | 'open') => Promise<boolean>
function setup(initial: WorkflowRead[] = [], initialRuns: RunRead[] = []) {
  const server = testServer(initial, initialRuns)
  vi.stubGlobal('fetch', server.fetch)
  let leave: LeaveHandler | null = null
  const registerLeave = vi.fn((handler: LeaveHandler | null) => { leave = handler })
  const page = (connected = true, locked = false) => <ApiProvider baseUrl="http://127.0.0.1:43127" token="studio-test-token" instanceId="studio-test-instance"><StudioPage connected={connected} locked={locked} registerLeave={registerLeave} /></ApiProvider>
  const view = render(page())
  return { ...view, server, registerLeave, prepareLeave: (reason: Parameters<LeaveHandler>[0]) => leave!(reason), setConnection(connected: boolean, locked = false) { view.rerender(page(connected, locked)) } }
}

const content = () => JSON.parse(screen.getByTestId('document').textContent!) as WorkflowContent
const writes = (server: ReturnType<typeof testServer>) => server.requests.filter((request) => (request.method === 'POST' || request.method === 'PUT') && !request.path.includes('/runs'))
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

async function beginRun(view: ReturnType<typeof setup>) {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  await user.type(screen.getByLabelText('网页地址'), 'https://example.test')
  await user.selectOptions(screen.getByLabelText('浏览器配置'), 'profile-1')
  await waitFor(() => expect(screen.getByRole('button', { name: '运行当前草稿' })).toBeEnabled())
  await user.click(screen.getByRole('button', { name: '运行当前草稿' }))
  await waitFor(() => expect(view.server.runs.size).toBe(1))
  await screen.findByText('真实节点开始执行')
  return user
}

it('runs a still-focused rename in a cloned unsaved draft, without saving or adding undo history', async () => {
  const view = setup()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  await user.type(screen.getByLabelText('网页地址'), 'https://example.test')
  await user.selectOptions(screen.getByLabelText('浏览器配置'), 'profile-1')
  await user.click(screen.getByRole('tab', { name: /流程变量/ }))
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  await user.clear(screen.getByLabelText('变量名'))
  await user.type(screen.getByLabelText('变量名'), '新名称')
  expect(content().document.variables[0].name).toBe('variable_1')
  fireEvent.click(screen.getByRole('button', { name: '运行当前草稿' }))
  await waitFor(() => expect(view.server.runs.size).toBe(1))
  expect([...view.server.runs.values()][0].document.variables[0].name).toBe('新名称')
  expect(writes(view.server)).toHaveLength(0)
  expect(screen.getByText('有未保存修改')).toBeVisible()
  await user.click(screen.getByRole('button', { name: '撤销' }))
  expect(content().document.variables[0].name).toBe('variable_1')
  expect([...view.server.runs.values()][0].document.variables[0].name).toBe('新名称')
})

it('blocks an invalid uncommitted variable rename even after switching away from its tab', async () => {
  const user = userEvent.setup()
  const view = setup()
  await screen.findByRole('button', { name: '添加打开网页' })
  await user.selectOptions(screen.getByLabelText('浏览器配置'), 'profile-1')
  await user.click(screen.getByRole('tab', { name: /流程变量/ }))
  await user.click(screen.getByRole('button', { name: '添加变量' }))
  await user.clear(screen.getByLabelText('变量名'))
  await user.type(screen.getByLabelText('变量名'), '123 bad')
  await user.click(screen.getByRole('tab', { name: '节点属性' }))
  await user.click(screen.getByRole('button', { name: '运行当前草稿' }))
  expect(await screen.findByText('变量名称尚未成功修改，请修正后再运行')).toBeVisible()
  expect(view.server.runs.size).toBe(0)
})

it('recovers a lost start response by the same run id and never automatically submits another start', async () => {
  const view = setup()
  view.server.loseStartResponse()
  await beginRun(view)
  const starts = view.server.requests.filter(request => request.path === '/api/v1/workflows/runs' && request.method === 'POST')
  expect(starts).toHaveLength(1)
  expect(view.server.requests.some(request => request.path === `/api/v1/workflows/runs/${starts[0].body!.runId}` && request.method === 'GET')).toBe(true)
  expect(screen.getByRole('button', { name: '运行当前草稿' })).toBeDisabled()
})

it('keeps snapshot markers for layout changes, removes them on document changes, and restores them on undo', async () => {
  const view = setup()
  const user = await beginRun(view)
  await waitFor(() => expect(screen.getByTestId('run-markers')).toHaveTextContent('执行中'))
  await user.click(screen.getByRole('button', { name: '移动全部节点' }))
  expect(screen.getByTestId('run-markers')).toHaveTextContent('执行中')
  await user.type(screen.getByLabelText('网页地址'), '/edited')
  expect(screen.getByTestId('run-markers')).toHaveTextContent('{}')
  expect(screen.getByRole('button', { name: '打开网页' })).toBeDisabled()
  expect([...view.server.runs.values()][0].document.nodes[0].config.url).toBe('https://example.test')
  await user.click(screen.getByRole('button', { name: '撤销' }))
  expect(screen.getByTestId('run-markers')).toHaveTextContent('执行中')
  await user.click(screen.getByRole('button', { name: '打开网页' }))
  expect(screen.getByTestId('run-locate')).toHaveTextContent(content().document.nodes[0].id)
})

it('cancel and failed save keep a dirty run alive, then new waits for cleanup after save succeeds', async () => {
  const view = setup()
  const user = await beginRun(view)
  await user.click(screen.getByRole('button', { name: '新建' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '取消' }))
  expect(view.server.requests.filter(request => request.path.endsWith('/stop'))).toHaveLength(0)
  view.server.setWriteError('磁盘已满')
  await user.click(screen.getByRole('button', { name: '新建' }))
  await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '保存并停止' }))
  expect(await within(screen.getByRole('dialog')).findByRole('alert')).toHaveTextContent('磁盘已满')
  expect(view.server.requests.filter(request => request.path.endsWith('/stop'))).toHaveLength(0)
  view.server.setWriteError(null)
  let cleaned!: () => void
  view.server.pauseStop(new Promise(resolve => { cleaned = resolve }))
  const id = content().document.id
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '保存并停止' }))
  await waitFor(() => expect(view.server.requests.some(request => request.path.endsWith('/stop'))).toBe(true))
  expect(content().document.id).toBe(id)
  expect(screen.getByRole('dialog')).toBeVisible()
  await act(async () => cleaned())
  await waitFor(() => expect(content().document.id).not.toBe(id))
  expect(view.server.documents.get(id)?.document.nodes).toHaveLength(1)
})

it('prompts even for a clean active run and blocks leaving while the connection is unknown', async () => {
  const view = setup()
  const user = await beginRun(view)
  await user.click(screen.getByRole('button', { name: '保存' }))
  await screen.findByText('已保存')
  let leaving!: Promise<boolean>
  act(() => { leaving = view.prepareLeave('close') })
  expect(await screen.findByText('停止运行后离开？')).toBeVisible()
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '取消' }))
  expect(await leaving).toBe(false)
  view.setConnection(false)
  await act(async () => expect(await view.prepareLeave('workspace')).toBe(false))
  expect(view.server.requests.some(request => request.path.endsWith('/stop'))).toBe(false)
  expect(content().document.nodes).toHaveLength(1)
})

it('retains the displayed run and logs while offline, then deduplicates replayed logs on reconnect', async () => {
  const view = setup()
  await beginRun(view)
  const id = [...view.server.runs.keys()][0]
  view.setConnection(false)
  expect(screen.getByText('真实节点开始执行')).toBeVisible()
  view.setConnection(true)
  await waitFor(() => expect(view.server.requests.filter(request => request.path === `/api/v1/workflows/runs/${id}/events`).length).toBeGreaterThan(1))
  expect(screen.getAllByText('真实节点开始执行')).toHaveLength(1)
  expect(view.server.requests.filter(request => request.path === '/api/v1/workflows/runs' && request.method === 'POST')).toHaveLength(1)
})

it.each(['new', 'close'] as const)('still permits offline discard for %s after confirming there was no active run', async reason => {
  const view = setup()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  await waitFor(() => expect(screen.queryByText(/正在核实运行状态/)).not.toBeInTheDocument())
  const id = content().document.id
  view.setConnection(false)
  let leaving: Promise<boolean> | undefined
  if (reason === 'new') await user.click(screen.getByRole('button', { name: '新建' }))
  else act(() => { leaving = view.prepareLeave('close') })
  const dialog = await screen.findByRole('dialog')
  expect(within(dialog).getByRole('button', { name: '保存并继续' })).toBeDisabled()
  await user.click(within(dialog).getByRole('button', { name: '放弃修改' }))
  if (leaving) expect(await leaving).toBe(true)
  else await waitFor(() => expect(content().document.id).not.toBe(id))
  expect(view.server.requests.some(request => request.path.endsWith('/stop'))).toBe(false)
})

it('shows server validation paths and locates the rejected snapshot node only while its document still matches', async () => {
  const view = setup()
  const user = userEvent.setup()
  await user.click(await screen.findByRole('button', { name: '添加打开网页' }))
  const id = content().document.nodes[0].id
  view.server.setRunIssue({ code: 'FORWARD_REFERENCE', message: '引用的输出尚未产生', nodeId: id, path: ['config', 'url'] })
  await user.selectOptions(screen.getByLabelText('浏览器配置'), 'profile-1')
  await user.click(screen.getByRole('button', { name: '运行当前草稿' }))
  expect(await screen.findByLabelText('运行校验问题')).toHaveTextContent('config / url')
  await user.click(screen.getByRole('button', { name: '定位 打开网页' }))
  expect(screen.getByTestId('run-locate')).toHaveTextContent(id)
  expect(view.server.runs.size).toBe(0)
  await user.type(screen.getByLabelText('网页地址'), 'https://example.test')
  expect(screen.getByRole('button', { name: '定位 打开网页' })).toBeDisabled()
  expect(screen.getByTestId('run-locate')).toHaveTextContent('null')
})


it('marks the current node failed after worker loss without a node_failed event', async () => {
  const view = setup()
  await beginRun(view)
  const record = [...view.server.runs.values()][0]
  view.server.runs.set(record.runId, { ...record, state: 'failed', finishedAt: time, latestSeq: 2, error: { code: 'WORKFLOW_WORKER_EXITED', message: '运行进程异常退出', nodeId: null, path: [] } })
  await userEvent.setup().click(screen.getByRole('button', { name: '刷新运行状态' }))
  await waitFor(() => expect(JSON.parse(screen.getByTestId('run-markers').textContent!)).toEqual({ [record.currentNodeId!]: '失败' }))
  expect(screen.getByTestId('run-markers')).not.toHaveTextContent('执行中')
})
