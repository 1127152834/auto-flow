import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
const services = vi.hoisted(() => ({
  register: vi.fn<(...args: [Record<string, string>]) => Promise<{ success: boolean; error?: string }>>(async () => ({ success: true })),
  images: vi.fn(async () => ({ success: true, data: [] })),
  connect: vi.fn(), disconnect: vi.fn(), run: vi.fn(),
}))
vi.mock('../api', () => ({ imageAssetApi: { list: services.images }, systemApi: { setCustomHotkeys: services.register } }))
vi.mock('../events', () => ({ socketService: { connect: services.connect, disconnect: services.disconnect } }))
vi.mock('../lib/customShortcuts', async importOriginal => ({
  ...await importOriginal<typeof import('../lib/customShortcuts')>(),
  SHORTCUT_ACTION_MAP: { run_workflow: { run: services.run } },
}))
import { useStudioIntegration } from '../hooks/useStudioIntegration'
import { useWorkflowStore } from '../editor-store'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'
beforeEach(() => {
  vi.clearAllMocks()
  services.register.mockReset().mockResolvedValue({ success: true })
  useWorkflowStore.setState({ logs: [] })
  useGlobalConfigStore.setState(state => ({ config: { ...state.config, shortcuts: { run_workflow: 'Alt+R' } } }))
})
afterEach(cleanup)
it('registers current shortcuts on mount, edits and reconnect, then removes event handlers', async () => {
  const { unmount } = renderHook(useStudioIntegration)
  await waitFor(() => expect(services.register).toHaveBeenCalledWith({ run_workflow: 'Alt+R' }))
  act(() => useGlobalConfigStore.getState().updateShortcuts({ run_workflow: 'Alt+T' }))
  expect(services.register).toHaveBeenLastCalledWith({ run_workflow: 'Alt+T' })
  window.dispatchEvent(new Event('socket:reconnected'))
  expect(services.register).toHaveBeenCalledTimes(3)
  unmount()
  window.dispatchEvent(new Event('socket:reconnected'))
  expect(services.register).toHaveBeenCalledTimes(3)
  expect(services.disconnect).toHaveBeenCalledOnce()
})
it('consumes a recognized service shortcut once and ignores invalid actions and unmounted listeners', () => {
  const { unmount } = renderHook(useStudioIntegration)
  for (const actionId of ['unknown', 'toString', null, {}]) {
    window.dispatchEvent(new CustomEvent('hotkey:custom_action', { detail: { actionId } }))
  }
  expect(services.run).not.toHaveBeenCalled()
  window.dispatchEvent(new CustomEvent('hotkey:custom_action', { detail: { actionId: 'run_workflow' } }))
  expect(services.run).toHaveBeenCalledOnce()
  unmount()
  window.dispatchEvent(new CustomEvent('hotkey:custom_action', { detail: { actionId: 'run_workflow' } }))
  expect(services.run).toHaveBeenCalledOnce()
})
it('does not run local shortcuts in editable descendants or during key repeat', () => {
  renderHook(useStudioIntegration)
  const editable = document.createElement('div')
  editable.setAttribute('contenteditable', 'true')
  const child = document.createElement('span')
  editable.append(child)
  document.body.append(editable)
  const key = (repeat = false) => new KeyboardEvent('keydown', { key: 'r', altKey: true, bubbles: true, cancelable: true, repeat })
  child.dispatchEvent(key())
  window.dispatchEvent(key(true))
  expect(services.run).not.toHaveBeenCalled()
  const event = key()
  window.dispatchEvent(event)
  expect(services.run).toHaveBeenCalledOnce()
  expect(event.defaultPrevented).toBe(true)
  editable.remove()
})

it.each(['rejected', 'exception'] as const)('reports %s registration and recovers on reconnect', async failure => {
  if (failure === 'rejected') services.register.mockResolvedValueOnce({ success: false, error: '权限不足' })
  else services.register.mockRejectedValueOnce(new Error('服务离线'))
  renderHook(useStudioIntegration)
  await waitFor(() => expect(useWorkflowStore.getState().logs).toEqual(expect.arrayContaining([
    expect.objectContaining({ level: 'error', message: expect.stringContaining('全局快捷键注册失败') }),
  ])))
  expect(useGlobalConfigStore.getState().config.shortcuts).toEqual({ run_workflow: 'Alt+R' })
  await act(async () => window.dispatchEvent(new Event('socket:reconnected')))
  expect(services.register).toHaveBeenLastCalledWith({ run_workflow: 'Alt+R' })
  expect(useWorkflowStore.getState().logs.at(-1)).toMatchObject({ level: 'info', message: '全局快捷键注册已恢复' })
})
it('suppresses repeated registration failures until recovery', async () => {
  services.register.mockResolvedValue({ success: false, error: '权限不足' })
  renderHook(useStudioIntegration)
  await act(async () => {})
  await act(async () => window.dispatchEvent(new Event('socket:reconnected')))
  expect(useWorkflowStore.getState().logs).toHaveLength(1)
  services.register.mockResolvedValue({ success: true })
  await act(async () => window.dispatchEvent(new Event('socket:reconnected')))
  services.register.mockResolvedValue({ success: false, error: '权限不足' })
  await act(async () => window.dispatchEvent(new Event('socket:reconnected')))
  expect(useWorkflowStore.getState().logs.map(log => log.level)).toEqual(['error', 'info', 'error'])
})
it.each(['edit', 'reconnect', 'unmount'] as const)('ignores obsolete registration feedback after %s', async action => {
  let reject!: (reason: Error) => void
  services.register.mockImplementationOnce(() => new Promise((_resolve, fail) => { reject = fail }))
  const view = renderHook(useStudioIntegration)
  await act(async () => {
    if (action === 'edit') useGlobalConfigStore.getState().updateShortcuts({ run_workflow: 'Alt+T' })
    else if (action === 'reconnect') window.dispatchEvent(new Event('socket:reconnected'))
    else view.unmount()
  })
  await act(async () => reject(new Error('过期注册失败')))
  expect(useWorkflowStore.getState().logs).toEqual([])
})
