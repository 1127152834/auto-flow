import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore } from '../editor-store'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
vi.mock('../hooks/stores/aiPermissionStore', () => ({ actionNeedsApproval: () => false, requestApproval: async () => true }))

beforeEach(() => {
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addVariable({ name: 'draft', value: 'keep', type: 'string', scope: 'global' })
})

afterEach(() => {
  cleanup()
  setStudioTransport(mockRequest)
})

it('saves the current document through the revisioned workflow service', async () => {
  let request: Record<string, unknown> | undefined
  setStudioTransport(async (input, init) => {
    if (new URL(String(input)).pathname === '/api/workflows' && init?.method === 'POST') {
      request = JSON.parse(String(init.body))
      return Response.json({ ...request, revision: 1, createdAt: '2026-09-15T00:00:00Z', updatedAt: '2026-09-15T00:00:00Z' }, { status: 201 })
    }
    return mockRequest(input, init)
  })

  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))

  await waitFor(() => expect(request).toBeDefined())
  expect(request).toMatchObject({ id: useWorkflowStore.getState().id, name: '未命名工作流', variables: [{ name: 'draft', value: 'keep' }] })
  await waitFor(() => expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false))
})

it('keeps edits made while the document request is pending dirty', async () => {
  let release!: (response: Response) => void
  setStudioTransport(async (input, init) => {
    if (new URL(String(input)).pathname === '/api/workflows' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      return new Promise<Response>(resolve => { release = () => resolve(Response.json({ ...body, revision: 1 })) })
    }
    return mockRequest(input, init)
  })

  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(release).toBeDefined())
  act(() => useWorkflowStore.getState().updateVariable('draft', 'newer'))
  release(Response.json({}))

  await waitFor(() => expect(useWorkflowStore.getState().variables[0].value).toBe('newer'))
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
it('updates an opened document using its revision instead of trying to create its existing ID', async () => {
  const saved = { id: 'opened-current', name: '真实打开的流程', revision: 7, updatedAt: '2026-09-28T00:00:00Z', nodes: [], edges: [], variables: [] }
  const writes: { path: string; method: string; body: Record<string, unknown> }[] = []
  act(() => useWorkflowStore.getState().markAsSaved())
  setStudioTransport(async (input, init) => {
    const path = new URL(String(input)).pathname
    if (path.startsWith('/api/workflows') && ['POST', 'PUT'].includes(init?.method ?? '')) {
      const body = JSON.parse(String(init?.body))
      writes.push({ path, method: init!.method!, body })
      return init?.method === 'PUT'
        ? Response.json({ ...saved, ...body, revision: 8 })
        : Response.json({ error: { code: 'WORKFLOW_ID_CONFLICT', message: '工作流 ID 已存在', details: {}, requestId: 'save-conflict' } }, { status: 409 })
    }
    if (path === '/api/workflows') return Response.json([saved])
    if (path === `/api/workflows/${saved.id}`) return Response.json(saved)
    return mockRequest(input, init)
  })
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: /打开/ }))
  fireEvent.click(await screen.findByRole('button', { name: `打开工作流 ${saved.name}` }))
  await waitFor(() => expect(useWorkflowStore.getState().id).toBe(saved.id))
  act(() => useWorkflowStore.getState().setWorkflowName('编辑后名称'))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toMatchObject({ path: `/api/workflows/${saved.id}`, method: 'PUT', body: { id: saved.id, expectedRevision: 7, name: '编辑后名称' } })
  await waitFor(() => expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false))
})

it('shows save rejection independently of the selected run log and keeps the draft dirty', async () => {
  setStudioTransport(async (input, init) => new URL(String(input)).pathname === '/api/workflows' && init?.method === 'POST'
    ? Response.json({ error: { code: 'WORKFLOW_REVISION_CONFLICT', message: '流程已被其他窗口修改', details: {}, requestId: 'save-conflict' } }, { status: 409 })
    : mockRequest(input, init))
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  expect((await screen.findByRole('alert')).textContent).toContain('流程已被其他窗口修改')
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
})
