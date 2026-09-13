import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
import { LocalWorkflowDialog } from '../components/LocalWorkflowDialog'
import { useWorkflowStore } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
import { setStudioTransport } from '../api/transport'
import { mockRequest } from '../api/mock-server'

const content = { name: 'destination', nodes: [], edges: [], variables: [] }
let load: () => Promise<Response>
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} })
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addVariable({ name: 'draft', value: 'keep', type: 'string', scope: 'global' })
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, workflow: { ...state.config.workflow, localFolder: 'mock://open-tests' } } }))
  load = async () => Response.json({ success: true, content })
  setStudioTransport(async input => {
    const path = new URL(String(input)).pathname
    if (path.endsWith('/default-folder')) return Response.json({ folder: 'mock://open-tests' })
    if (path.endsWith('/list')) return Response.json({ workflows: [{ filename: 'destination.json', name: 'destination', size: 100, modifiedTime: '' }] })
    if (path.includes('/load/')) return load()
    throw new Error(`Unexpected request ${path}`)
  })
})
afterEach(() => { cleanup(); setStudioTransport(mockRequest) })
it.each([false, true])('respects the shared leave decision %s before replacing the document', async allowed => {
  const beforeReplace = vi.fn(async () => allowed)
  const onClose = vi.fn()
  render(<LocalWorkflowDialog isOpen onClose={onClose} onLog={vi.fn()} beforeReplace={beforeReplace} />)
  fireEvent.click(await screen.findByText('destination'))
  await waitFor(() => expect(beforeReplace).toHaveBeenCalledOnce())
  await waitFor(() => expect(useWorkflowStore.getState().variables).toHaveLength(allowed ? 0 : 1))
  expect(onClose).toHaveBeenCalledTimes(allowed ? 1 : 0)
})
it.each(['close', 'edit', 'unmount'])('ignores a delayed load after %s', async reason => {
  let release!: (value: Response) => void
  load = () => new Promise(resolve => { release = resolve })
  const beforeReplace = vi.fn(async () => true)
  const props = { onClose: vi.fn(), onLog: vi.fn(), beforeReplace }
  const view = render(<LocalWorkflowDialog isOpen {...props} />)
  fireEvent.click(await screen.findByText('destination'))
  await waitFor(() => expect(release).toBeDefined())
  if (reason === 'close') view.rerender(<LocalWorkflowDialog isOpen={false} {...props} />)
  if (reason === 'unmount') view.unmount()
  if (reason === 'edit') act(() => useWorkflowStore.getState().updateVariable('draft', 'newer'))
  await act(async () => release(Response.json({ success: true, content })))
  expect(beforeReplace).not.toHaveBeenCalled()
  expect(useWorkflowStore.getState().variables[0].value).toBe(reason === 'edit' ? 'newer' : 'keep')
})
it('does not replace or ask to discard after a rejected load', async () => {
  load = async () => Response.json({ success: false, error: 'file missing' }, { status: 404 })
  const beforeReplace = vi.fn(async () => true), onLog = vi.fn()
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={onLog} beforeReplace={beforeReplace} />)
  fireEvent.click(await screen.findByText('destination'))
  await waitFor(() => expect(onLog).toHaveBeenCalledWith('error', expect.stringContaining('file missing')))
  expect(beforeReplace).not.toHaveBeenCalled()
  expect(useWorkflowStore.getState().variables[0].value).toBe('keep')
})
