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
  const document = { id: 'opened-project-document', name: '项目文档', revision: 4, updatedAt: '2026-09-23T00:00:00Z', nodes: [], edges: [], variables: [{ name: 'draft', value: 'original', type: 'string', scope: 'global' }] }
  const writes: { path: string; method: string; body: Record<string, unknown> }[] = []
  setStudioTransport(async (input, init) => {
    const path = new URL(String(input)).pathname
    if (path === '/api/workflows' && (!init?.method || init.method === 'GET')) return Response.json([document])
    if (path === `/api/workflows/${document.id}` && (!init?.method || init.method === 'GET')) return Response.json(document)
    if (path.startsWith('/api/workflows') && ['POST', 'PUT'].includes(init?.method || '')) {
      const body = JSON.parse(String(init?.body))
      writes.push({ path, method: init!.method!, body })
      return init?.method === 'PUT' ? Response.json({ ...body, revision: 5 }) : Response.json({ error: '工作流 ID 已存在' }, { status: 409 })
    }
    return mockRequest(input, init)
  })
  useWorkflowStore.getState().markAsSaved()
  render(<Toolbar />)
  fireEvent.click(screen.getByRole('button', { name: '打开' }))
  fireEvent.click(await screen.findByRole('button', { name: '打开工作流 项目文档' }))
  await waitFor(() => expect(useWorkflowStore.getState().id).toBe(document.id))
  act(() => useWorkflowStore.getState().updateVariable('draft', 'edited'))
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() => expect(writes).toHaveLength(1))
  expect(writes[0]).toMatchObject({ path: `/api/workflows/${document.id}`, method: 'PUT', body: { id: document.id, expectedRevision: 4, variables: [{ name: 'draft', value: 'edited' }] } })
  await waitFor(() => expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(false))
})
