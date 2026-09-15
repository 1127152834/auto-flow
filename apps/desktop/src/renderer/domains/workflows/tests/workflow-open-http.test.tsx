import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { WorkflowOpenDialog } from '../components/WorkflowOpenDialog'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'
import { useWorkflowStore } from '../editor-store'

const saved = {
  id: 'saved-flow',
  name: '已保存流程',
  revision: 3,
  createdAt: '2026-09-15T00:00:00Z',
  updatedAt: '2026-09-15T01:00:00Z',
  nodes: [{ id: 'open', type: 'open_page', position: { x: 10, y: 20 }, data: { url: 'https://example.test' } }],
  edges: [],
  variables: [{ name: 'restored', value: 'yes', type: 'string', scope: 'global' }],
}

beforeEach(() => {
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addVariable({ name: 'draft', value: 'keep', type: 'string', scope: 'global' })
})

afterEach(() => { cleanup(); setStudioTransport(mockRequest) })

it('lists and opens revisioned documents without reading the local-file service', async () => {
  const requests: string[] = []
  setStudioTransport(async input => {
    const path = new URL(String(input)).pathname
    requests.push(path)
    if (path === '/api/workflows') return Response.json([saved])
    if (path === '/api/workflows/saved-flow') return Response.json(saved)
    return Response.json({ error: 'unexpected' }, { status: 500 })
  })
  const onOpened = vi.fn()
  render(<WorkflowOpenDialog isOpen beforeReplace={vi.fn(async () => true)} onClose={vi.fn()} onOpened={onOpened} onLog={vi.fn()} />)

  fireEvent.click(await screen.findByRole('button', { name: '打开工作流 已保存流程' }))

  await waitFor(() => expect(onOpened).toHaveBeenCalledWith('saved-flow'))
  expect(useWorkflowStore.getState().variables).toEqual(saved.variables)
  expect(useWorkflowStore.getState().nodes[0]).toMatchObject({ id: 'open', type: 'moduleNode', position: { x: 10, y: 20 } })
  expect(requests).toEqual(['/api/workflows', '/api/workflows/saved-flow'])
  expect(requests.some(path => path.includes('local-workflows'))).toBe(false)
})
