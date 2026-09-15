import { useAiActionLogStore } from '../hooks/stores/aiActionLogStore'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
const confirm = vi.hoisted(() => vi.fn(async () => false))
vi.mock('../components/controls/confirm-dialog', async importOriginal => ({ ...(await importOriginal<typeof import('../components/controls/confirm-dialog')>()), useConfirm: () => ({ confirm, alert: vi.fn(), ConfirmDialog: () => null }) }))
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))
import { executeClientAction, emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
let saved: Record<string, unknown>[]
const isDocumentCreate = (input: RequestInfo | URL, init?: RequestInit) =>
  new URL(String(input)).pathname === '/api/workflows' && init?.method === 'POST'
beforeEach(() => {
  confirm.mockClear(); saved = []
  useAiActionLogStore.getState().clear()
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addVariable({ name: 'draft', value: 'keep', type: 'string', scope: 'global' })
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, workflow: { ...state.config.workflow, localFolder: 'mock://draft-tests', showOverwriteConfirm: false } } }))
  setStudioTransport(async (input, init) => {
    if (isDocumentCreate(input, init)) saved.push(JSON.parse(String(init?.body)))
    return mockRequest(input, init)
  })
})
afterEach(() => { cleanup(); setStudioTransport(mockRequest) })
it('saves a variable-only document without requiring a canvas node', async () => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(saved).toHaveLength(1))
  expect(saved[0]).toMatchObject({ nodes: [], variables: [{ name: 'draft', value: 'keep' }] })
  await waitFor(() => expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false))
})
it.each(['button', 'shortcut', 'assistant'])('protects a variable-only draft on new via %s', async mode => {
  render(<Toolbar />)
  await act(async () => {
    if (mode === 'button') fireEvent.click(screen.getByRole('button', { name: '新建' }))
    if (mode === 'shortcut') fireEvent.keyDown(window, { key: 'n', altKey: true })
    if (mode === 'assistant') emitAssistantUiEvent('new_workflow', {})
  })
  expect(screen.getByRole('dialog', { name: '保存当前工作流？' })).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})
it('does not acknowledge a document after the service rejects the write', async () => {
  const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (isDocumentCreate(input, init)) return Response.json({ error: 'fixture write failed' }, { status: 503 })
    return mockRequest(input, init)
  })
  setStudioTransport(transport)
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('fixture write failed'))).toBe(true))
  expect(transport.mock.calls.filter(([input, init]) => isDocumentCreate(input, init))).toHaveLength(1)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('keeps newer variable edits dirty while acknowledging only the submitted snapshot', async () => {
  let release!: (response: Response) => void
  let content: Record<string, unknown> | undefined
  setStudioTransport(async (input, init) => {
    if (isDocumentCreate(input, init)) {
      content = JSON.parse(String(init?.body))
      return new Promise<Response>(resolve => { release = resolve })
    }
    return mockRequest(input, init)
  })
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(content).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'newer'))
  await act(async () => release(Response.json({ ...content, revision: 1 }, { status: 201 })))
  expect(content).toMatchObject({ variables: [{ name: 'draft', value: 'keep' }] })
  expect(useWorkflowStore.getState().variables[0].value).toBe('newer')
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it.each(['保存后继续', '放弃修改'])('creates a new document only after choosing %s', async choice => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: choice }))
  await waitFor(() => expect(useWorkflowStore.getState().variables).toEqual([]))
  expect(saved).toHaveLength(choice === '保存后继续' ? 1 : 0)
  if (choice === '保存后继续') expect(saved[0]).toMatchObject({ variables: [{ name: 'draft', value: 'keep' }] })
})
it('keeps the draft when save before new fails', async () => {
  setStudioTransport(async (input, init) => isDocumentCreate(input, init)
    ? Response.json({ success: false, error: 'disk full' }, { status: 507 }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('disk full'))).toBe(true))
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('does not leave after saving an older snapshot while the user continues editing', async () => {
  let release!: (response: Response) => void
  setStudioTransport(async (input, init) => isDocumentCreate(input, init)
    ? new Promise<Response>(resolve => { release = resolve }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(release).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited during save'))
  const current = JSON.parse(useWorkflowStore.getState().exportWorkflow())
  await act(async () => release(Response.json({ ...current, revision: 1 }, { status: 201 })))
  expect(useWorkflowStore.getState().variables[0].value).toBe('edited during save')
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('does not leave when the revisioned save conflicts', async () => {
  setStudioTransport(async (input, init) => isDocumentCreate(input, init)
    ? Response.json({ error: { code: 'WORKFLOW_REVISION_CONFLICT', message: '并发冲突', details: { expectedRevision: 1, currentRevision: 2 } } }, { status: 409 }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('并发冲突'))).toBe(true))
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
  expect(confirm).not.toHaveBeenCalled()
})
it('one confirmation cannot release duplicate new-document requests', async () => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.keyDown(window, { key: 'n', altKey: true })
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改' }))
  await waitFor(() => expect(useWorkflowStore.getState().variables).toEqual([]))
  expect(useWorkflowStore.getState().logs.filter(log => log.message === '已创建新工作流')).toHaveLength(1)
})
it('an edit made while the decision is open invalidates discard consent', async () => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  await screen.findByRole('button', { name: '放弃修改' })
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited while deciding'))
  fireEvent.click(screen.getByRole('button', { name: '放弃修改' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('确认期间草稿已修改'))).toBe(true))
  expect(useWorkflowStore.getState().variables[0].value).toBe('edited while deciding')
})
it('protects a name-only edit even before the name input loses focus', async () => {
  useWorkflowStore.getState().clearWorkflow()
  render(<Toolbar />)
  fireEvent.focus(screen.getByPlaceholderText('工作流名称'))
  fireEvent.change(screen.getByPlaceholderText('工作流名称'), { target: { value: 'name-only draft' } })
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  fireEvent.keyDown(window, { key: 'n', altKey: true })
  fireEvent.click(await screen.findByRole('button', { name: '取消' }))
  expect(useWorkflowStore.getState().name).toBe('name-only draft')
})
it.each(['new_workflow', 'load_workflow_from_data'])('the actual AI %s command waits for and respects the draft decision', async action => {
  render(<Toolbar />)
  let resolved = false
  const result = executeClientAction(action, { nodes: [{ id: 'web', type: 'open_page' }], animate: false }).then(value => { resolved = true; return value })
  await screen.findByRole('button', { name: '取消' })
  expect(resolved).toBe(false)
  fireEvent.click(screen.getByRole('button', { name: '取消' }))
  expect((await result).success).toBe(false)
  expect(useAiActionLogStore.getState().entries).toEqual([])
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})
it('rejects direct AI document replacement without a mounted editor', async () => {
  expect((await executeClientAction('new_workflow')).success).toBe(false)
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})
it('AI file loading keeps all saved variables after an explicit discard decision', async () => {
  const content = { name: 'loaded variables', nodes: [], edges: [], variables: [{ name: 'restored', type: 'string', value: 'from file', scope: 'global' }] }
  setStudioTransport(async (input, init) => String(input).includes('/local-workflows/load/')
    ? Response.json({ success: true, content }) : mockRequest(input, init))
  render(<Toolbar />)
  const result = executeClientAction('load_workflow', { filename: 'target' })
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改' }))
  expect((await result).success).toBe(true)
  expect(useWorkflowStore.getState().variables).toEqual(content.variables)
  expect(useWorkflowStore.getState().name).toBe('loaded variables')
})
it('AI file loading cannot replace edits made during its request', async () => {
  let release!: (response: Response) => void
  setStudioTransport(async (input, init) => String(input).includes('/local-workflows/load/')
    ? new Promise<Response>(resolve => { release = resolve }) : mockRequest(input, init))
  render(<Toolbar />)
  const result = executeClientAction('load_workflow', { filename: 'target' })
  await waitFor(() => expect(release).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'changed during AI request'))
  await act(async () => release(Response.json({ success: true, content: { name: 'late', nodes: [], edges: [], variables: [] } })))
  expect((await result).success).toBe(false)
  expect(useWorkflowStore.getState().variables[0].value).toBe('changed during AI request')
  expect(screen.queryByRole('dialog', { name: '保存当前工作流？' })).toBeNull()
})
it('marks an AI-generated document dirty and preserves its declared variables', async () => {
  render(<Toolbar />)
  const variables = [{ name: 'generated', value: 'initial', type: 'string', scope: 'global' }]
  const result = executeClientAction('load_workflow_from_data', { name: 'AI generated', nodes: [{ id: 'web', type: 'open_page' }], variables, animate: false })
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改' }))
  expect((await result).success).toBe(true)
  expect(useWorkflowStore.getState().variables).toEqual(variables)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})

const importBundle = { type: 'webrpa-workflow-bundle', version: 1, name: 'bundle target', workflow: { nodes: [], edges: [], variables: [{ name: 'bundled', value: 'from file', type: 'string', scope: 'global' }] } }
function selectBundle(text: Promise<string> = Promise.resolve(JSON.stringify(importBundle))) {
  const inputs: HTMLInputElement[] = []
  const picker = vi.spyOn(HTMLInputElement.prototype, 'click').mockImplementation(function (this: HTMLInputElement) { inputs.push(this) })
  fireEvent.click(screen.getByRole('button', { name: '导入整包' }))
  picker.mockRestore()
  const file = new File(['fixture'], 'test.bundle.json', { type: 'application/json' })
  Object.defineProperty(file, 'text', { value: () => text })
  fireEvent.change(inputs[0], { target: { files: [file] } })
}
it('does not call bundle import when leaving the draft is cancelled', async () => {
  const request = vi.fn(mockRequest)
  setStudioTransport(request)
  render(<Toolbar />)
  selectBundle()
  fireEvent.click(await screen.findByRole('button', { name: '取消' }))
  expect(request.mock.calls.some(([input]) => String(input).endsWith('/workflow-bundle/import'))).toBe(false)
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})
it.each(['保存后继续', '放弃修改'])('imports a bundle after %s and keeps it dirty until saved', async choice => {
  render(<Toolbar />)
  selectBundle()
  fireEvent.click(await screen.findByRole('button', { name: choice }))
  await waitFor(() => expect(useWorkflowStore.getState().name).toBe('bundle target'))
  expect(useWorkflowStore.getState().variables).toEqual(importBundle.workflow.variables)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  expect(saved).toHaveLength(choice === '保存后继续' ? 1 : 0)
})
it.each(['save', 'import'])('keeps the document when bundle %s fails', async failure => {
  const request = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (failure === 'save' ? isDocumentCreate(input, init) : String(input).endsWith('/workflow-bundle/import')) return Response.json({ success: false, error: 'bundle fixture failure' }, { status: 507 })
    return mockRequest(input, init)
  })
  setStudioTransport(request)
  render(<Toolbar />)
  selectBundle()
  fireEvent.click(await screen.findByRole('button', { name: failure === 'save' ? '保存后继续' : '放弃修改' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('bundle fixture failure'))).toBe(true))
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
  if (failure === 'save') expect(request.mock.calls.some(([input]) => String(input).endsWith('/workflow-bundle/import'))).toBe(false)
})
it('does not import a bundle read for an older draft', async () => {
  let release!: (text: string) => void
  const text = new Promise<string>(resolve => { release = resolve })
  render(<Toolbar />)
  selectBundle(text)
  expect((screen.getByRole('button', { name: '导入整包' }) as HTMLButtonElement).disabled).toBe(true)
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited while reading'))
  await act(async () => release(JSON.stringify(importBundle)))
  expect(screen.queryByRole('dialog', { name: '保存当前工作流？' })).toBeNull()
  expect(useWorkflowStore.getState().variables[0].value).toBe('edited while reading')
})
it('retains edits made during bundle resource restoration', async () => {
  let release!: (response: Response) => void
  setStudioTransport(async (input, init) => String(input).endsWith('/workflow-bundle/import')
    ? new Promise<Response>(resolve => { release = resolve }) : mockRequest(input, init))
  render(<Toolbar />)
  selectBundle()
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改' }))
  await waitFor(() => expect(release).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited while restoring'))
  await act(async () => release(Response.json({ success: true, name: importBundle.name, workflow: importBundle.workflow })))
  expect(useWorkflowStore.getState().variables[0].value).toBe('edited while restoring')
  expect(useWorkflowStore.getState().logs.some(log => log.message.includes('资源已导入，但草稿'))).toBe(true)
})
it('does not report success for an invalid workflow returned by bundle import', async () => {
  setStudioTransport(async (input, init) => String(input).endsWith('/workflow-bundle/import')
    ? Response.json({ success: true, workflow: { nodes: null, edges: [] } }) : mockRequest(input, init))
  render(<Toolbar />)
  selectBundle()
  fireEvent.click(await screen.findByRole('button', { name: '放弃修改' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('整包中的工作流格式无效'))).toBe(true))
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})

it('successful AI edits record an independent complete before snapshot', async () => {
  const result = await executeClientAction('add_nodes', { nodes: [{ id: 'web', type: 'open_page' }] })
  expect(result.success).toBe(true)
  const entries = useAiActionLogStore.getState().entries
  expect(entries).toHaveLength(1)
  expect(entries[0].before.variables).toMatchObject([{ name: 'draft', value: 'keep' }])
  useWorkflowStore.getState().updateVariable('draft', 'later')
  expect(entries[0].before.variables?.[0].value).toBe('keep')
  useWorkflowStore.getState().restoreSnapshot(entries[0].before)
  expect(useWorkflowStore.getState().nodes).toEqual([])
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
  useWorkflowStore.getState().undo()
  expect(useWorkflowStore.getState().nodes[0].id).toBe('web')
  expect(useWorkflowStore.getState().variables[0].value).toBe('later')
})
it('does not acknowledge an old document response after the connection changes', async () => {
  let release!: (response: Response) => void
  let submitted: Record<string, unknown> = {}
  setStudioTransport(async (input, init) => isDocumentCreate(input, init) ? new Promise<Response>(resolve => { submitted = JSON.parse(String(init?.body)); release = resolve }) : mockRequest(input, init))
  render(<Toolbar />); fireEvent.click(screen.getByRole('button', { name: '保存' })); await waitFor(() => expect(release).toBeDefined())
  const next = vi.fn(mockRequest); act(() => { setStudioTransport(next) })
  await act(async () => release(Response.json({ ...submitted, revision: 1 }, { status: 201 })))
  expect(next.mock.calls.some(([input, init]) => isDocumentCreate(input, init))).toBe(false)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('does not acknowledge a saved document after connection replacement', async () => {
  let release!: (response: Response) => void
  let submitted: Record<string, unknown> = {}
  setStudioTransport(async (input, init) => isDocumentCreate(input, init) ? new Promise<Response>(resolve => { submitted = JSON.parse(String(init?.body)); release = resolve }) : mockRequest(input, init))
  render(<Toolbar />); fireEvent.click(screen.getByRole('button', { name: '保存' })); await waitFor(() => expect(release).toBeDefined())
  act(() => { setStudioTransport(mockRequest) })
  await act(async () => release(Response.json({ ...submitted, revision: 1 }, { status: 201 })))
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  expect(useWorkflowStore.getState().logs.some(log => log.message.includes('工作流已保存'))).toBe(false)
})
it.each(['保存后继续', '放弃修改'])('invalidates a leave decision %s after connection change', async choice => {
  render(<Toolbar />); fireEvent.click(screen.getByRole('button', { name: '新建' })); await screen.findByRole('dialog', { name: '保存当前工作流？' })
  const next = vi.fn(mockRequest); act(() => { setStudioTransport(next) })
  fireEvent.click(screen.getByRole('button', { name: choice }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '保存当前工作流？' })).toBeNull())
  expect(useWorkflowStore.getState().variables[0]?.value).toBe('keep')
  expect(next.mock.calls.some(([input, init]) => isDocumentCreate(input, init))).toBe(false)
})
it('serializes repeated save clicks', async () => {
  let release!: (response: Response) => void
  let submitted: Record<string, unknown> = {}
  const request = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => isDocumentCreate(input, init) ? new Promise<Response>(resolve => { submitted = JSON.parse(String(init?.body)); release = resolve }) : mockRequest(input, init))
  setStudioTransport(request); render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' })); fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(release).toBeDefined())
  expect(request.mock.calls.filter(([input, init]) => isDocumentCreate(input, init))).toHaveLength(1)
  await act(async () => release(Response.json({ ...submitted, revision: 1 }, { status: 201 })))
})
it.each([{ id: 1, revision: 1 }, { id: 'draft' }, { id: 'draft', revision: '1' }])('does not mark saved for malformed receipt %j', async receipt => {
  setStudioTransport(async (input, init) => isDocumentCreate(input, init) ? Response.json(receipt, { status: 201 }) : mockRequest(input, init))
  render(<Toolbar />); fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.level === 'error')).toBe(true))
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
