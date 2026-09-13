import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { Toolbar } from '../components/Toolbar'
import { useWorkflowStore as store } from '../editor-store'
import { useDebugStore } from '../hooks/stores/debugStore'
import { workflowApi } from '../api'
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }
beforeEach(() => {
  store.getState().clearWorkflow()
  store.getState().addNode('open_page', { x: 0, y: 0 })
  useDebugStore.setState({ breakpoints: new Set(), stepMode: false })
  vi.spyOn(workflowApi, 'create').mockResolvedValue({ success: true, data: { id: 'start-fixture' } })
  vi.spyOn(workflowApi, 'execute').mockResolvedValue({ success: true })
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })
it.each(['completed', 'stopped', 'failed', 'pending'] as const)('does not replace confirmed %s state when the start HTTP response arrives', async status => {
  const response = deferred<Awaited<ReturnType<typeof workflowApi.execute>>>()
  vi.mocked(workflowApi.execute).mockReturnValue(response.promise)
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  act(() => store.getState().setExecutionStatus(status))
  await act(async () => response.resolve({ success: true }))
  expect(store.getState().executionStatus).toBe(status)
})
it('coalesces repeated starts during preparation and freezes debug options before awaiting', async () => {
  const response = deferred<Awaited<ReturnType<typeof workflowApi.create>>>()
  vi.mocked(workflowApi.create).mockReturnValue(response.promise)
  const nodeId = store.getState().nodes[0].id
  useDebugStore.setState({ breakpoints: new Set([nodeId]), stepMode: true })
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  fireEvent.keyDown(window, { key: 'F5' })
  expect(workflowApi.create).toHaveBeenCalledTimes(1)
  act(() => useDebugStore.setState({ breakpoints: new Set(), stepMode: false }))
  await act(async () => response.resolve({ success: true, data: { id: 'start-fixture' } }))
  expect(workflowApi.execute).toHaveBeenCalledTimes(1)
  expect(workflowApi.execute).toHaveBeenCalledWith('start-fixture', expect.objectContaining({ breakpoints: [nodeId], stepMode: true }))
})
it('releases preparation ownership after failure so an explicit retry can start', async () => {
  vi.mocked(workflowApi.create).mockResolvedValueOnce({ success: false, error: '准备失败' })
  render(<Toolbar />)
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(store.getState().logs.some(log => log.message.includes('准备失败'))).toBe(true))
  expect(workflowApi.execute).not.toHaveBeenCalled()
  fireEvent.keyDown(window, { key: 'F5' })
  await waitFor(() => expect(workflowApi.execute).toHaveBeenCalledTimes(1))
  expect(workflowApi.create).toHaveBeenCalledTimes(2)
})
it('does not start another request through run-from-node while a run is active', async () => {
  store.getState().setExecutionStatus('running')
  render(<Toolbar />)
  await act(async () => window.dispatchEvent(new CustomEvent('run-from-node', { detail: { nodeId: store.getState().nodes[0].id } })))
  expect(workflowApi.create).not.toHaveBeenCalled()
  expect(workflowApi.execute).not.toHaveBeenCalled()
  expect(store.getState().executionStatus).toBe('running')
})
