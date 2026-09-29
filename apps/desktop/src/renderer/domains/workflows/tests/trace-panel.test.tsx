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
  await waitFor(() => expect(list).toHaveBeenLastCalledWith('run-a', 100, '', { traceId: undefined }))
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
    expect(summary.data).toEqual({ runId: 'run-a', runStatus: 'failed', status: 'partial', gaps: ['网页源码未单独采集'], total: 102, traceId: undefined, sessions: undefined })
    await executeClientAction('query_trace_events', { runId: 'run-a', cursor: 100, executionId: 'exec-2' })
    expect(query).toHaveBeenLastCalledWith('run-a', 100, '', { limit: 20, executionId: 'exec-2', evidenceId: undefined })
    const domPage = page(); domPage.events[0].domId = 'dom-1'
    query.mockResolvedValue({ success: true, data: domPage })
    const content = '<html>recorded DOM</html>'
    const file = vi.spyOn(workflowApi, 'getRunArtifact').mockResolvedValue({ success: true, data: new Blob([content], { type: 'text/html' }) })
    const dom = await executeClientAction('read_trace_evidence', { runId: 'run-a', evidenceId: 'a', part: 'dom', offset: 6, limit: 8 })
    expect(dom.data).toMatchObject({ text: 'recorded', nextOffset: 14, totalCharacters: content.length })
    expect(file).toHaveBeenCalledWith('run-a', 'dom-1')
    expect((await executeClientAction('read_trace_evidence', { runId: 'run-a', evidenceId: 'a', part: 'dom', limit: 8001 })).success).toBe(false)
    query.mockResolvedValue({ success: true, data: { ...page(), events: [] } })
    expect((await executeClientAction('read_trace_evidence', { runId: 'run-a', evidenceId: 'other' })).success).toBe(false)
  } finally { state.mockRestore() }
})

it('diagnostic node forms expose independent capture choices and exact marker references', async () => {
  const { DiagnosticConfig } = await import('../components/config-panels/DiagnosticConfig')
  const { getModuleConfigDefaults, getModuleAllDefaultVars } = await import('../lib/moduleDefaultVars')
  const { moduleTypeLabels } = await import('../editor-store')
  const change = vi.fn()
  for (const type of ['trace_mark', 'capture_diagnostics', 'save_trace_segment'] as const) {
    const defaults = getModuleConfigDefaults(type)
    expect(defaults.variableName).toBe(getModuleAllDefaultVars(type).variableName)
    const view = render(<DiagnosticConfig data={{ moduleType: type, label: moduleTypeLabels[type], ...defaults }} onChange={change} />)
    expect((screen.getByLabelText('诊断名称') as HTMLInputElement).value).toBeTruthy()
    if (type === 'capture_diagnostics') {
      fireEvent.click(screen.getByRole('checkbox', { name: '只读 DOM 文档' }))
      expect(change).toHaveBeenLastCalledWith('includeDom', false)
      expect(screen.getByText(/截图始终为标签页视口/)).toBeTruthy()
    }
    if (type === 'save_trace_segment') {
      fireEvent.change(screen.getByLabelText('起始标记 ID（可选）'), { target: { value: '{trace_marker[id]}' } })
      expect(change).toHaveBeenLastCalledWith('startMarker', '{trace_marker[id]}')
    }
    view.unmount()
  }
})


it('renders captured DOM as inert text rather than an executable page', async () => {
  const data = page(); data.events[0].domId = 'dom-1'
  vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data })
  vi.spyOn(workflowApi, 'getRunArtifact').mockResolvedValue({ success: true, data: new Blob(['<script>throw Error("untrusted")</script><h1>Recorded</h1>'], { type: 'text/html' }) })
  render(<TracePanel runId="run-a" />)
  fireEvent.click(await screen.findByRole('button', { name: '查看 DOM 原文' }))
  const preview = await screen.findByLabelText('只读 DOM 原文')
  expect(preview.textContent).toContain('<script>')
  expect(preview.querySelector('script')).toBeNull()
  expect(preview.querySelector('h1')).toBeNull()
})


it('separates identical page IDs across browser sessions and downloads the selected evidence archive', async () => {
  const multi = page()
  multi.archiveId = null
  multi.sessions = [
    { traceId: 'browser-a', archiveId: 'zip-a', status: 'saved', gaps: [], eventCount: 1 },
    { traceId: 'browser-b', archiveId: 'zip-b', status: 'saved', gaps: [], eventCount: 1 },
  ]
  multi.events[0].traceId = 'browser-a'; multi.events[1].traceId = 'browser-b'
  const list = vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: multi })
  const artifact = vi.spyOn(workflowApi, 'getRunArtifact').mockResolvedValue({ success: true, data: new Blob(['png'], { type: 'image/png' }) })
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:trace')
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<TracePanel runId="run-a" />)
  await screen.findByLabelText('浏览器会话')
  fireEvent.click(screen.getByRole('button', { name: /click · 失败/ }))
  expect((screen.getByRole('button', { name: '对比上一张同页快照' }) as HTMLButtonElement).disabled).toBe(true)
  fireEvent.click(screen.getByRole('button', { name: '下载原始追踪' }))
  await waitFor(() => expect(artifact).toHaveBeenCalledWith('run-a', 'zip-b'))
  Element.prototype.scrollIntoView = vi.fn()
  fireEvent.keyDown(screen.getByLabelText('浏览器会话'), { key: 'Enter' })
  fireEvent.click(await screen.findByRole('option', { name: '会话 2 · 1 条' }))
  await waitFor(() => expect(list).toHaveBeenLastCalledWith('run-a', 0, '', { traceId: 'browser-b' }))
})


it('persists trace mode with document history and rejects unknown imported modes', async () => {
  const { useWorkflowStore } = await import('../editor-store')
  const store = () => useWorkflowStore.getState()
  store().clearWorkflow()
  const original = JSON.parse(store().exportWorkflow())
  expect(original.traceMode).toBeUndefined()
  store().setTraceMode('enhanced')
  const captured = store().exportWorkflow()
  expect(JSON.parse(captured).traceMode).toBe('enhanced')
  store().setTraceMode('off')
  expect(JSON.parse(captured).traceMode).toBe('enhanced')
  store().undo(); expect(store().traceMode).toBe('enhanced')
  store().redo(); expect(store().traceMode).toBe('off')
  expect(store().importWorkflow(captured)).toBe(true)
  expect(store().traceMode).toBe('enhanced')
  expect(store().hasUnsavedChanges).toBe(false)
  expect(store().importWorkflow(JSON.stringify({ ...original, traceMode: 'invalid' }))).toBe(false)
  expect(store().traceMode).toBe('enhanced')
  store().clearWorkflow(); expect(store().traceMode).toBeUndefined()
})

it('shows JS as inert source and lets the assistant request bounded source text', async () => {
  const source = page()
  source.events = [{ ...source.events[0], kind: 'source', sourceId: 'js-1', url: '/actual.js' }]
  vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: source })
  const content = 'window.proof = 42;'
  vi.spyOn(workflowApi, 'getRunArtifact').mockResolvedValue({ success: true, data: new Blob([content], { type: 'text/javascript' }) })
  render(<TracePanel runId="run-a" />)
  expect((await screen.findByLabelText('只读 JS 原文')).textContent).toBe(content)
  expect((window as unknown as { proof?: number }).proof).toBeUndefined()
  const { executeClientAction } = await import('../api/aiAssistantSkills')
  const { useGlobalConfigStore } = await import('../hooks/stores/globalConfigStore')
  const original = useGlobalConfigStore.getState()
  vi.spyOn(useGlobalConfigStore, 'getState').mockReturnValue({ ...original, config: { ...original.config, aiAssistant: { ...original.config.aiAssistant, enableTools: true, permissionMode: 'full' } } })
  const result = await executeClientAction('read_trace_evidence', { runId: 'run-a', evidenceId: 'a', part: 'source', offset: 7, limit: 5 })
  expect(result.data).toMatchObject({ part: 'source', text: 'proof', nextOffset: 12 })
})

it('refreshes an active run after an earlier browser session has already archived', async () => {
  vi.useFakeTimers()
  try {
    const active = { ...page(), runStatus: 'running', events: [] }
    const query = vi.spyOn(workflowApi, 'getRunTrace').mockResolvedValue({ success: true, data: active })
    render(<TracePanel runId="run-a" />)
    await act(async () => { await Promise.resolve() })
    expect(query).toHaveBeenCalledTimes(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
    expect(query).toHaveBeenCalledTimes(2)
  } finally { cleanup(); vi.useRealTimers() }
})
