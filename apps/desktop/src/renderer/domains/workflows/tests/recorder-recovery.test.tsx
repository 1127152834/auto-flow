import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
})
const api = vi.hoisted(() => ({ start: vi.fn(), events: vi.fn(), stop: vi.fn() }))
vi.mock('../api', () => ({ recorderApi: api, browserApi: { getStatus: async () => ({ success: true, data: { isOpen: true } }) } }))
import { useWorkflowStore } from '../editor-store'
import { RecorderPanel } from '../components/RecorderPanel'
let sessionId: string
const batch = (events: unknown[], stop = false) => ({ success: true, data: { success: true, sessionId, nextSeq: events.length, data: stop ? { events } : events } })
beforeEach(() => {
  vi.useFakeTimers(); vi.clearAllMocks()
  api.start.mockImplementation(async (id: string) => { sessionId = id; return { success: true, data: { success: true, recording: true, sessionId: id } } })
  api.events.mockImplementation(async () => batch([]))
  api.stop.mockImplementation(async () => batch([], true))
})
afterEach(() => { cleanup(); vi.useRealTimers() })
async function start(onClose = vi.fn()) {
  render(<RecorderPanel open onClose={onClose} />)
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '开始录制' })) })
  expect(screen.getByRole('button', { name: '停止录制' })).toBeDefined()
}
it('keeps recording and the panel open after failed stop, then accepts the tail on retry', async () => {
  const close = vi.fn()
  await start(close)
  api.stop.mockResolvedValueOnce({ success: false, error: 'Stop failed' })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '关闭录制器' })) })
  expect(close).not.toHaveBeenCalled()
  expect(screen.getByRole('alert').textContent).toContain('Stop failed')
  expect(screen.getByRole('button', { name: '停止录制' })).toBeDefined()
  api.stop.mockImplementationOnce(async () => batch([{ sequence: 1, type: 'click', selector: '#tail' }], true))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '停止录制' })) })
  expect(screen.getByText(/共 1 步/)).toBeDefined()
  expect(screen.getByRole('button', { name: '开始录制' })).toBeDefined()
})
it('cancels a pending poll after stop and does not append its late duplicate', async () => {
  let resolvePoll!: (value: unknown) => void
  api.events.mockImplementationOnce(() => new Promise(resolve => { resolvePoll = resolve }))
  await start()
  await act(async () => { vi.advanceTimersByTime(700) })
  expect(api.events).toHaveBeenCalledWith(sessionId, 0, expect.any(AbortSignal))
  const events = [{ sequence: 1, type: 'click', selector: '#tail' }]
  api.stop.mockImplementationOnce(async () => batch(events, true))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '停止录制' })) })
  expect(api.events.mock.calls[0][2].aborted).toBe(true)
  await act(async () => { resolvePoll(batch(events)) })
  expect(screen.getByText(/共 1 步/)).toBeDefined()
})
it.each([
  [{ type: 'click', selector: '#same', _frame: { name: 'a' } }, { type: 'dblclick', selector: '#same', _frame: { name: 'b' } }],
  [{ type: 'scroll', selector: '#a', dy: 10 }, { type: 'scroll', selector: '#b', dy: 10 }],
  [{ type: 'navigate', url: 'https://example.test', _frame: { name: 'a' } }, { type: 'navigate', url: 'https://example.test', _frame: { name: 'b' } }],
])('keeps different frame or target operations separate: %j / %j', async (first, second) => {
  await start()
  api.stop.mockImplementationOnce(async () => batch([{ ...first, sequence: 1 }, { ...second, sequence: 2 }], true))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '停止录制' })) })
  expect(screen.getByText(/共 2 步/)).toBeDefined()
})

it('appends generated nodes as one undo operation without clearing logs or marking the draft saved', async () => {
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.getState().addNode('print_log', { x: 0, y: 0 })
  useWorkflowStore.getState().addLog({ level: 'info', message: 'existing diagnostic' })
  const original = structuredClone(useWorkflowStore.getState().nodes)
  await start()
  api.stop.mockImplementationOnce(async () => batch([{ sequence: 1, type: 'navigate', url: 'https://example.test/' }, { sequence: 2, type: 'click', selector: '#button' }], true))
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '停止录制' })) })
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '生成节点' })) })
  expect(useWorkflowStore.getState().nodes).toHaveLength(original.length + 2)
  expect(useWorkflowStore.getState().hasUnsavedChanges).toBe(true)
  expect(useWorkflowStore.getState().logs.some(log => log.message === 'existing diagnostic')).toBe(true)
  act(() => useWorkflowStore.getState().undo())
  expect(useWorkflowStore.getState().nodes).toEqual(original)
  act(() => useWorkflowStore.getState().redo())
  expect(useWorkflowStore.getState().nodes).toHaveLength(original.length + 2)
})
