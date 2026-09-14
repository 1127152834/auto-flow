import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { LogPanel } from '../components/LogPanel'
import { useWorkflowStore } from '../editor-store'
import { seedMockRunHistory } from '../api/mock-server'
import { workflowApi } from '../api'

beforeEach(() => {
  const storage = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => storage.get(key) ?? null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
  })
  vi.stubGlobal('ResizeObserver', class { observe() {}; unobserve() {}; disconnect() {} })
  Element.prototype.scrollIntoView = vi.fn()
  useWorkflowStore.getState().clearWorkflow()
  useWorkflowStore.setState({
    bottomPanelTab: 'logs', maxLogCount: 100,
    currentExecutionWorkflowId: 'workflow-history', currentExecutionRunId: 'run-history',
    nodes: [
      { id: 'node-a', type: 'module', position: { x: 0, y: 0 }, data: { moduleType: 'open_page', label: '打开页面' } },
      { id: 'node-b', type: 'module', position: { x: 0, y: 100 }, data: { moduleType: 'click_element', label: '点击元素' } },
    ],
  })
  seedMockRunHistory({
    runId: 'run-history', workflowId: 'workflow-history', documentId: useWorkflowStore.getState().id,
    logs: Array.from({ length: 650 }, (_, index) => ({
      id: `history-${index + 1}`, timestamp: new Date(Date.UTC(2026, 8, 14, 0, 0, index)).toISOString(),
      level: index === 600 ? 'error' as const : 'info' as const,
      nodeId: index % 2 ? 'node-b' : 'node-a',
      message: index === 600 ? '故障-00601' : `调度-${String(index + 1).padStart(5, '0')}`,
    })),
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

it('queries the complete run on the service and prepends older pages', async () => {
  render(<LogPanel />)
  await screen.findByText('100/650')
  fireEvent.click(screen.getByRole('button', { name: '更早日志' }))
  await screen.findByText('200/650')
})

it('applies keyword, level and node filters to the service query', async () => {
  const query = vi.spyOn(workflowApi, 'getRunLogs')
  render(<LogPanel />)
  await screen.findByText('100/650')
  fireEvent.change(screen.getByPlaceholderText('搜索日志...'), { target: { value: '故障-00601' } })
  await screen.findByText('1/1')
  expect(screen.getByText('故障-00601')).toBeDefined()
  fireEvent.click(screen.getByRole('combobox', { name: '按节点筛选日志' }))
  fireEvent.click(await screen.findByRole('option', { name: '点击元素' }))
  await waitFor(() => expect(query).toHaveBeenLastCalledWith('run-history', expect.objectContaining({ query: '故障-00601', nodeId: 'node-b' })))
})

it('downloads the server export instead of the retained UI window', async () => {
  const createUrl = vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:history')
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<LogPanel />)
  await screen.findByText('100/650')
  await act(async () => { fireEvent.click(screen.getByRole('button', { name: '下载' })) })
  await waitFor(() => expect(createUrl).toHaveBeenCalled())
  expect((createUrl.mock.calls[0][0] as Blob).size).toBeGreaterThan(20_000)
  expect(click).toHaveBeenCalledOnce()
})

it('restores the latest persisted run when the live execution identity is absent', async () => {
  useWorkflowStore.setState({ currentExecutionWorkflowId: null, currentExecutionRunId: null, logs: [] })
  expect((await workflowApi.listRuns()).data?.items.map(item => item.runId)).toContain('run-history')
  const list = vi.spyOn(workflowApi, 'listRuns')
  render(<LogPanel />)
  const run = await screen.findByRole('combobox', { name: '运行日志记录' })
  await waitFor(() => expect(list).toHaveBeenCalled())
  await waitFor(() => expect(run.textContent).toContain('Mock 运行'))
  fireEvent.click(run)
  fireEvent.click(await screen.findByRole('option', { name: /Mock 运行/ }))
  await screen.findByText('100/650')
})
