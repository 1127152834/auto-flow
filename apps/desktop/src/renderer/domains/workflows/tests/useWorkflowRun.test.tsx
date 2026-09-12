import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import { useWorkflowRun } from '../hooks/useWorkflowRun'
import { runApi, runEvent, runRecord } from './run-fixtures'

afterEach(cleanup)

it('offers an explicit retry with the exact original run id and snapshot after a request never reaches the server', async () => {
  const api = runApi()
  vi.mocked(api.start).mockRejectedValueOnce(new TypeError('offline before send'))
  vi.mocked(api.get).mockRejectedValue(new ApiClientError('not found', 404))
  const view = renderHook(() => useWorkflowRun(api, true))
  await waitFor(() => expect(view.result.current.uncertain).toBe(false))
  const content = { document: runRecord().document, layout: runRecord().layout }
  await act(async () => view.result.current.start(content, 'profile-1'))
  expect(view.result.current.canRetryStart).toBe(true)
  expect(view.result.current.run).toBeNull()
  const submitted = structuredClone(vi.mocked(api.start).mock.calls[0][0])
  content.document.name = '启动后继续编辑'
  await act(async () => view.result.current.retryStart())
  expect(api.start).toHaveBeenCalledTimes(2)
  expect(vi.mocked(api.start).mock.calls[1][0]).toEqual(submitted)
  expect(view.result.current.run?.document.name).toBe('快照流程')
  expect(view.result.current.canRetryStart).toBe(false)
})

it('keeps validation node/path details without selecting or polling a nonexistent run', async () => {
  const api = runApi()
  const issues = [{ code: 'FORWARD_REFERENCE', nodeId: 'node-1', path: ['config', 'url'], message: '该变量尚未产生' }]
  vi.mocked(api.start).mockRejectedValue(new ApiClientError('无法运行', 422, 'WORKFLOW_INVALID', { issues }))
  const view = renderHook(() => useWorkflowRun(api, true))
  await waitFor(() => expect(view.result.current.uncertain).toBe(false))
  const record = runRecord()
  await act(async () => view.result.current.start(record, 'profile-1'))
  expect(view.result.current.validation).toEqual({ document: record.document, issues })
  expect(view.result.current.message).toBe('无法运行')
  expect(view.result.current.run).toBeNull()
  expect(api.get).not.toHaveBeenCalled()
  expect(view.result.current.uncertain).toBe(false)
})

it('keeps loaded older history pages when refreshing the active run state', async () => {
  const api = runApi()
  const recent = runRecord({ state: 'succeeded' })
  const older = runRecord({ runId: 'older', state: 'failed', startedAt: '2026-09-12T00:00:00Z' })
  vi.mocked(api.list).mockImplementation(async offset => ({ items: offset ? [older] : [recent], activeRunId: null, nextOffset: offset ? null : 20 }))
  const view = renderHook(() => useWorkflowRun(api, true))
  await waitFor(() => expect(view.result.current.history).toHaveLength(1))
  await act(async () => view.result.current.more())
  expect(view.result.current.history).toHaveLength(2)
  await act(async () => view.result.current.refresh())
  expect(view.result.current.history.map(item => item.runId)).toEqual(['run-1', 'older'])
  expect(view.result.current.nextOffset).toBeNull()
})

it('keeps run identity and logs across a replacement API client and deduplicates persisted replay', async () => {
  const record = runRecord()
  const first = runApi(record)
  const replacement = runApi(record)
  vi.mocked(replacement.events).mockResolvedValue({ items: [runEvent(1), runEvent(2), runEvent(2)], hasMore: false, nextSeq: 2 })
  const view = renderHook(({ api, connected }) => useWorkflowRun(api, connected), { initialProps: { api: first, connected: true } })
  await waitFor(() => expect(view.result.current.events).toHaveLength(1))
  view.rerender({ api: first, connected: false })
  expect(view.result.current.run?.runId).toBe('run-1')
  expect(view.result.current.events).toHaveLength(1)
  view.rerender({ api: replacement, connected: true })
  await waitFor(() => expect(view.result.current.events.map(event => event.seq)).toEqual([1, 2]))
  expect(replacement.events).toHaveBeenCalledWith('run-1', 1)
  expect(first.start).not.toHaveBeenCalled()
  expect(replacement.start).not.toHaveBeenCalled()
})

it('does not confirm cleanup when stop response is lost and the persisted state remains stopping', async () => {
  const api = runApi(runRecord())
  vi.mocked(api.stop).mockRejectedValue(new TypeError('connection lost'))
  const view = renderHook(() => useWorkflowRun(api, true))
  await waitFor(() => expect(view.result.current.active).not.toBeNull())
  vi.mocked(api.get).mockResolvedValue(runRecord({ state: 'stopping', latestSeq: 2 }))
  await act(async () => expect(await view.result.current.stop()).toBe(false))
  expect(view.result.current.active?.state).toBe('stopping')
  expect(view.result.current.uncertain).toBe(true)
})


it('does not let a delayed active check for the previous run clear a newer run', async () => {
  const first = runRecord()
  const api = runApi(first)
  const view = renderHook(() => useWorkflowRun(api, true))
  await waitFor(() => expect(api.watch).toHaveBeenCalled())
  let release!: (value: ReturnType<typeof runRecord>) => void
  vi.mocked(api.get).mockImplementationOnce(() => new Promise(resolve => { release = resolve }))
  let oldCheck!: Promise<boolean | null>
  act(() => { oldCheck = view.result.current.refresh() })
  await waitFor(() => expect(release).toBeDefined())
  const completed = runRecord({ state: 'succeeded', latestSeq: 2, finishedAt: '2026-09-13T00:00:01Z' })
  vi.mocked(api.get).mockResolvedValue(completed)
  await act(async () => vi.mocked(api.watch).mock.calls[0][3](runEvent(2, { type: 'succeeded' })))
  await waitFor(() => expect(view.result.current.active).toBeNull())
  await act(async () => view.result.current.start(first, 'profile-1'))
  const newId = view.result.current.active!.runId
  expect(newId).not.toBe(first.runId)
  await act(async () => { release(completed); await oldCheck })
  expect(view.result.current.active?.runId).toBe(newId)
  expect(view.result.current.uncertain).toBe(false)
})
