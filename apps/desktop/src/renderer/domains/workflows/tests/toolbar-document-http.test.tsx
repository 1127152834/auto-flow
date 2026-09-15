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
