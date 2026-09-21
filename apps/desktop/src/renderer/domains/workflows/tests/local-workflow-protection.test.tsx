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
it('ignores a load from a replaced service connection', async () => {
  let release!: (value: Response) => void
  load = () => new Promise(resolve => { release = resolve })
  const beforeReplace = vi.fn(async () => true)
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={vi.fn()} beforeReplace={beforeReplace} />)
  fireEvent.click(await screen.findByText('destination')); await waitFor(() => expect(release).toBeDefined())
  act(() => { setStudioTransport(mockRequest) })
  await act(async () => release(Response.json({ success: true, content })))
  expect(beforeReplace).not.toHaveBeenCalled(); expect(useWorkflowStore.getState().variables[0]?.value).toBe('keep')
})
it('rechecks service identity after the leave decision', async () => {
  let leave!: (choice: boolean) => void
  const beforeReplace = vi.fn(() => new Promise<boolean>(resolve => { leave = resolve }))
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={vi.fn()} beforeReplace={beforeReplace} />)
  fireEvent.click(await screen.findByText('destination')); await waitFor(() => expect(leave).toBeDefined())
  act(() => { setStudioTransport(mockRequest) }); await act(async () => leave(true))
  expect(useWorkflowStore.getState().variables[0]?.value).toBe('keep')
})
it('clears old file rows after a connection change until explicitly refreshed', async () => {
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={vi.fn()} beforeReplace={vi.fn(async () => true)} />)
  await screen.findByText('destination')
  const next = vi.fn(mockRequest); act(() => { setStudioTransport(next) })
  expect(screen.queryByText('destination')).toBeNull(); await screen.findByRole('alert')
  expect(next.mock.calls.some(([input]) => String(input).includes('/load/'))).toBe(false)
})
it.each([{ workflows: null }, { workflows: [{}] }, { workflows: [{ filename: 'broken', name: 'broken', modifiedTime: '', size: -1 }] }])('shows invalid list %j as an error rather than crashing', async body => {
  setStudioTransport(async input => String(input).endsWith('/list') ? Response.json(body) : Response.json({ folder: 'mock://open-tests' }))
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={vi.fn()} beforeReplace={vi.fn(async () => true)} />)
  expect((await screen.findByRole('alert')).textContent).toContain('格式无效')
  expect(screen.queryByText('destination')).toBeNull()
})
it('allows explicit retry after a failed list response', async () => {
  let failed = true
  setStudioTransport(async input => String(input).endsWith('/list')
    ? failed ? Response.json({ error: '列表离线' }, { status: 503 }) : Response.json({ workflows: [{ filename: 'destination.json', name: 'destination', size: 100, modifiedTime: '' }] })
    : Response.json({ folder: 'mock://open-tests' }))
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={vi.fn()} beforeReplace={vi.fn(async () => true)} />)
  await screen.findByRole('alert'); failed = false; fireEvent.click(screen.getByRole('button', { name: '刷新' })); await screen.findByText('destination')
  expect(screen.queryByRole('alert')).toBeNull()
})
it('does not delete from another connection after a pending confirmation', async () => {
  const onLog = vi.fn()
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={onLog} beforeReplace={vi.fn(async () => true)} />)
  await screen.findByText('destination'); fireEvent.click(screen.getByTitle('删除工作流'))
  await screen.findByRole('dialog', { name: '删除工作流' })
  const next = vi.fn(mockRequest); act(() => { setStudioTransport(next) })
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  await waitFor(() => expect(screen.queryByRole('dialog', { name: '删除工作流' })).toBeNull())
  expect(next.mock.calls.some(([input]) => String(input).includes('/delete'))).toBe(false)
})
it('opens the resolved workflow folder through the desktop host', async () => {
  const runStudioPlatformAction = vi.fn(async () => ({ ok: true as const, value: {} }))
  window.autoflow = { ...window.autoflow, runStudioPlatformAction }
  setStudioTransport(async input => {
    const path = new URL(String(input)).pathname
    if (path.endsWith('/default-folder')) return Response.json({ folder: '/tmp/workflows' })
    if (path.endsWith('/list')) return Response.json({ workflows: [] })
    if (path.endsWith('/open-folder')) return Response.json({ success: true, folder: '/tmp/workflows' })
    throw new Error(`Unexpected request ${path}`)
  })
  const onLog = vi.fn()
  render(<LocalWorkflowDialog isOpen onClose={vi.fn()} onLog={onLog} beforeReplace={vi.fn(async () => true)} />)
  fireEvent.click(await screen.findByRole('button', { name: '打开位置' }))
  await waitFor(() => expect(runStudioPlatformAction).toHaveBeenCalledWith({ action: 'open_path', path: '/tmp/workflows' }))
  expect(onLog).toHaveBeenCalledWith('success', expect.stringContaining('/tmp/workflows'))
})
