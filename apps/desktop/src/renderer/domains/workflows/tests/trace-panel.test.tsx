import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { components } from '../../../shared/api/generated'
import { workflowApi } from '../api'
import { TracePanel } from '../components/TracePanel'

type Page = components['schemas']['StudioTracePage']
const page = (runId = 'run-a'): Page => ({
  runId, localOnly: true, runStatus: 'failed', status: 'partial', archiveId: 'zip-1', gaps: ['网页源码未单独采集'], total: 102, nextCursor: 100,
  events: [
    { id: 'a', snapshotMissing: false, truncated: false, kind: 'execution', timeMs: 100, timestamp: '2026-09-25T00:00:00Z', nodeId: 'open', executionId: 'exec-1', phase: 'execution:node_complete', pageId: 'p', snapshotId: 'shot-1' },
    { id: 'b', snapshotMissing: false, truncated: false, kind: 'execution', timeMs: 200, timestamp: '2026-09-25T00:00:01Z', nodeId: 'click', executionId: 'exec-2', phase: 'execution:node_complete', pageId: 'p', snapshotId: 'shot-2', success: false },
  ],
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('loads registered snapshots, compares the same page and downloads the chosen run archive', async () => {
  const list = vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: page() })
  const artifact = vi.spyOn(workflowApi, 'getRunArtifact').mockImplementation(async (_run, id) => ({ success: true, data: new Blob(['evidence'], { type: id.startsWith('shot') ? 'image/png' : 'application/zip' }) }))
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:trace')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  const download = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<TracePanel runId="run-a" />)
  await screen.findByAltText('该次执行结束时的页面快照')
  fireEvent.click(screen.getByRole('button', { name: /click · 失败/ }))
  await waitFor(() => expect(artifact).toHaveBeenCalledWith('run-a', 'shot-2'))
  fireEvent.click(screen.getByRole('button', { name: '对比上一张同页快照' }))
  await waitFor(() => expect(screen.getAllByAltText('该次执行结束时的页面快照')).toHaveLength(2))
  fireEvent.click(screen.getByRole('button', { name: '下载原始追踪' }))
  await waitFor(() => expect(download).toHaveBeenCalledOnce())
  expect(artifact).toHaveBeenCalledWith('run-a', 'zip-1')
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(list).toHaveBeenLastCalledWith('run-a', 100, ''))
})

it('does not label absent historical evidence as a successful capture', async () => {
  vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: { ...page(), status: 'unavailable', archiveId: null, events: [], gaps: [], total: 0, nextCursor: null } })
  render(<TracePanel runId="run-a" />)
  await screen.findByText(/本次运行没有可读取的 Trace/)
  expect((screen.getByRole('button', { name: '下载原始追踪' }) as HTMLButtonElement).disabled).toBe(true)
  expect(screen.queryByAltText('该次执行结束时的页面快照')).toBeNull()
})

it('drops late responses after switching runs and reports read errors', async () => {
  let resolve!: (value: Awaited<ReturnType<typeof workflowApi.getRunTrace>>) => void
  vi.spyOn(workflowApi, 'getRunTrace').mockImplementation(id => id === 'run-a' ? new Promise(done => { resolve = done }) : Promise.resolve({ success: false, error: '索引文件缺失' }))
  const { rerender } = render(<TracePanel runId="run-a" />)
  rerender(<TracePanel runId="run-b" />)
  await screen.findByText('索引文件缺失')
  await act(async () => resolve({ success: true, data: page('run-a') }))
  expect(screen.queryByText('open · 完成')).toBeNull()
  expect(screen.getByRole('alert').textContent).toContain('索引文件缺失')
})

it('assistant reads bounded evidence for an explicit run and omits raw content from summaries', async () => {
  const { executeClientAction } = await import('../api/aiAssistantSkills')
  const { useGlobalConfigStore } = await import('../hooks/stores/globalConfigStore')
  const original = useGlobalConfigStore.getState()
  const state = vi.spyOn(useGlobalConfigStore, 'getState').mockReturnValue({ ...original, config: { ...original.config, aiAssistant: { ...original.config.aiAssistant, enableTools: true, permissionMode: 'full' } } })
  try {
    const query = vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: page() })
    expect((await executeClientAction('get_trace_summary', {})).success).toBe(false)
    const summary = await executeClientAction('get_trace_summary', { runId: 'run-a' })
    expect(summary.data).toEqual({ runId: 'run-a', runStatus: 'failed', status: 'partial', gaps: ['网页源码未单独采集'], total: 102, traceId: undefined })
    await executeClientAction('query_trace_events', { runId: 'run-a', cursor: 100, executionId: 'exec-2' })
    expect(query).toHaveBeenLastCalledWith('run-a', 100, '', { limit: 20, executionId: 'exec-2', evidenceId: undefined })
    query.mockResolvedValue({ success: true, data: { ...page(), events: [] } })
    expect((await executeClientAction('read_trace_evidence', { runId: 'run-a', evidenceId: 'other' })).success).toBe(false)
  } finally { state.mockRestore() }
})
