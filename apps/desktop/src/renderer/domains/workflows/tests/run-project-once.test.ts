import { beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
const f = vi.hoisted(() => ({ state: {} as { automation: Record<string, string | number>; debug: { selectionStatus: string; selection: { input: { recordRef: { recordKey: { value: string } }; contentRevision: number } | null } }; epoch: number; task: { task: { batchId: string; status: string } } | null }, store: { id: 'w', setExecutionStatus: vi.fn(), setBottomPanelTab: vi.fn(), setCurrentExecutionRunId: vi.fn(), setCurrentExecutionWorkflowId: vi.fn(), clearLogs: vi.fn(), clearCollectedData: vi.fn(), addLogBatch: vi.fn() }, request: vi.fn(), api: { start: vi.fn(), resumeStart: vi.fn(), getBatch: vi.fn(), listTasks: vi.fn(), getTask: vi.fn(), stop: vi.fn() } }))
vi.mock('../api/config', () => ({ getStudioOpenContext: () => ({ automationId: 'a', projectId: 'p', workflowId: 'w' }), getStudioResourceScope: () => 'workspace-p' }))
vi.mock('../api/transport', () => ({ getStudioTransportRevision: () => 1 }))
vi.mock('../editor-store', () => ({ useWorkflowStore: { getState: () => f.store } }))
vi.mock('../events', () => ({ socketService: { bindExecutionDocument: vi.fn() } }))
vi.mock('../project-inputs', () => ({ projectRuns: () => f.api, projectRoot: () => '/projects/p', projectRequest: (...args: unknown[]) => f.request(...args), useProjectInputs: { getState: () => f.state, setState: (state: object) => Object.assign(f.state, state) } }))
import { runProjectOnce } from '../run-project-once'
beforeEach(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('sessionStorage', { getItem: (key: string) => storage.get(key) ?? null, setItem: (key: string, value: string) => storage.set(key, value), removeItem: (key: string) => storage.delete(key) })
  vi.clearAllMocks()
  f.state = { automation: { automationId: 'a', projectId: 'p', workflowId: 'w', managementRevision: 1 }, debug: { selectionStatus: 'ready', selection: { input: { recordRef: { recordKey: { value: 'third' } }, contentRevision: 1 } } }, epoch: 1, task: null }
  f.api.start.mockResolvedValue({ state: 'succeeded', batch: { batchId: 'b' } })
  f.api.resumeStart.mockResolvedValue({ state: 'succeeded', batch: { batchId: 'b' } })
  f.api.getBatch.mockResolvedValue({ batch: { batchId: 'b', status: 'completed' }, configurationSnapshot: { automation: { inputPlan: { inputs: [] }, parameterSchema: [] } } })
  f.request.mockResolvedValue({ items: [{ runId: 'r', eventId: 'e1', sequence: 1, kind: 'log', occurredAt: '2026-09-26T00:00:00Z', nodeId: 'n', payload: { level: 'info', message: '已写入第三条' } }], afterSequence: 1, lastSequence: 1, hasMore: false, terminal: true })
  f.api.listTasks.mockResolvedValue({ items: [{ taskId: 't' }] })
  f.api.getTask.mockResolvedValue({ task: { taskId: 't', batchId: 'b', runId: 'r', status: 'succeeded' }, run: { runId: 'r', terminal: true } })
})
it('recovers an uncertain start using exactly the original selection and key', async () => {
  f.api.start.mockRejectedValueOnce(new TypeError('response lost'))
  await expect(runProjectOnce()).rejects.toThrow('response lost')
  const [automation, body, key] = f.api.start.mock.calls[0]
  f.state.debug.selection = { input: null }
  await runProjectOnce()
  expect(f.api.start).toHaveBeenCalledTimes(1)
  expect(f.api.resumeStart.mock.calls[0].slice(0, 3)).toEqual([automation, body, key])
  expect(body).toMatchObject({ maxTasks: 1, concurrency: 1, debugSelection: { input: { recordRef: { recordKey: { value: 'third' } } } } })
})
it('recovers an accepted batch after polling fails without submitting another run', async () => {
  f.api.getBatch.mockRejectedValueOnce(new TypeError('offline'))
  await expect(runProjectOnce()).rejects.toThrow('offline')
  await runProjectOnce()
  expect(f.api.start).toHaveBeenCalledTimes(1)
  expect(f.api.resumeStart).not.toHaveBeenCalled()
  expect(f.store.setExecutionStatus).toHaveBeenLastCalledWith('completed')
})
it('keeps a rejected selection editable without silently running another record', async () => {
  f.api.start.mockRejectedValueOnce(new ApiClientError('已被占用', 409, 'DEBUG_INPUT_INVALID'))
  await expect(runProjectOnce()).rejects.toThrow('已被占用')
  expect(f.api.getBatch).not.toHaveBeenCalled()
  expect(f.state.debug.selection.input!.recordRef.recordKey.value).toBe('third')
})

it('hydrates persisted events even when the real task has finished before the first poll', async () => {
  await runProjectOnce()
  expect(f.request).toHaveBeenCalledWith('/projects/p/tasks/t/events?afterSequence=0')
  expect(f.store.addLogBatch).toHaveBeenCalledWith([expect.objectContaining({ id: 'e1', message: '已写入第三条' })])
  await runProjectOnce()
  expect(f.api.start).toHaveBeenCalledTimes(2)
  expect(f.store.clearLogs).toHaveBeenCalledTimes(2)
  expect(f.store.addLogBatch).toHaveBeenCalledTimes(2)
})

it('does not show a previous successful task as the result of a rejected claim', async () => {
  await runProjectOnce()
  f.api.start.mockResolvedValue({ state: 'succeeded', batch: { batchId: 'rejected' } })
  f.api.getBatch.mockResolvedValue({ batch: { batchId: 'rejected', status: 'completed', selectionOutcome: { message: '所选数据已变化' } }, configurationSnapshot: {} })
  f.api.listTasks.mockResolvedValue({ items: [] })
  await runProjectOnce()
  expect(f.store.setExecutionStatus).toHaveBeenLastCalledWith('failed')
  expect(f.state.task).toBeNull()
})
