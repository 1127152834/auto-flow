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
import { emitAssistantUiEvent } from '../api/aiAssistantSkills'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
let saved: Record<string, unknown>[]
beforeEach(() => {
  confirm.mockClear(); saved = []
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addVariable({ name: 'draft', value: 'keep', type: 'string', scope: 'global' })
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, workflow: { ...state.config.workflow, localFolder: 'mock://draft-tests', showOverwriteConfirm: false } } }))
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/local-workflows/save-to-folder')) saved.push(JSON.parse(String(init?.body)))
    return mockRequest(input, init)
  })
})
afterEach(() => { cleanup(); setStudioTransport(mockRequest) })
it('saves a variable-only document without requiring a canvas node', async () => {
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(saved).toHaveLength(1))
  expect(saved[0].content).toMatchObject({ nodes: [], variables: [{ name: 'draft', value: 'keep' }] })
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
it('does not save after a failed existence check', async () => {
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, workflow: { ...state.config.workflow, showOverwriteConfirm: true } } }))
  const transport = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).endsWith('/check-exists')) return Response.json({ error: 'fixture check failed' }, { status: 503 })
    return mockRequest(input, init)
  })
  setStudioTransport(transport)
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(useWorkflowStore.getState().logs.some(log => log.message.includes('fixture check failed'))).toBe(true))
  expect(transport.mock.calls.some(([input]) => String(input).endsWith('/save-to-folder'))).toBe(false)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('keeps newer variable edits dirty while acknowledging only the submitted snapshot', async () => {
  let release!: (response: Response) => void
  let content: Record<string, unknown> | undefined
  setStudioTransport(async (input, init) => {
    if (String(input).endsWith('/save-to-folder')) {
      content = JSON.parse(String(init?.body)).content
      return new Promise<Response>(resolve => { release = resolve })
    }
    return mockRequest(input, init)
  })
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(content).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'newer'))
  await act(async () => release(Response.json({ success: true, filename: 'draft.json' })))
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
  if (choice === '保存后继续') expect(saved[0].content).toMatchObject({ variables: [{ name: 'draft', value: 'keep' }] })
})
it('keeps the draft when save before new fails', async () => {
  setStudioTransport(async (input, init) => String(input).endsWith('/save-to-folder')
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
  setStudioTransport(async (input, init) => String(input).endsWith('/save-to-folder')
    ? new Promise<Response>(resolve => { release = resolve }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(release).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited during save'))
  await act(async () => release(Response.json({ success: true, filename: 'saved.json' })))
  expect(useWorkflowStore.getState().variables[0].value).toBe('edited during save')
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('does not leave when overwrite confirmation is cancelled', async () => {
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, workflow: { ...state.config.workflow, showOverwriteConfirm: true } } }))
  setStudioTransport(async (input, init) => String(input).endsWith('/check-exists')
    ? Response.json({ exists: true, filename: 'existing.json' }) : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '新建' }))
  fireEvent.click(await screen.findByRole('button', { name: '保存后继续' }))
  await waitFor(() => expect(confirm).toHaveBeenCalledOnce())
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
  expect(saved).toEqual([])
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
