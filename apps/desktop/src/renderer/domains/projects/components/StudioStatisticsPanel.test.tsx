import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { StudioStatisticsPanel } from './StudioStatisticsPanel'

choiceTestEnvironment()
afterEach(cleanup)
const data = { projectId: 'p', from: '2026-09-20T00:00:00Z', to: '2026-09-23T00:00:00Z', calculatedAt: '2026-09-23T00:00:00Z', totalRuns: 60, byStatus: { completed: 3, failed: 1, stopped: 1 }, successRate: .75, averageDurationMs: 1200, nodeExecutionCount: 1000, extractionExecutionCount: 501, artifactCount: 100, diagnosticCount: 30, debugCount: 2, recordingCount: null, recordingUnavailableReason: '历史录制尚未保存项目归属', latestActivityAt: '2026-09-23T00:00:00Z', failuresByNode: [{ nodeId: 'bad-node', count: 1 }], runsByWorkflow: [{ workflowId: 'flow', name: '真实采集', count: 60 }], byTrigger: { unknown: 55, time: 5 }, items: [{ runId: 'run', workflowId: 'flow', workflowName: '真实采集', status: 'completed', mode: 'run', startedAt: '2026-09-23T00:00:00Z', finishedAt: '2026-09-23T00:00:02Z' }], nextCursor: 50 }
function mount(request: (path: string) => Promise<unknown>) {
  const client = { request: vi.fn(request) as StreamingApiClient['request'], stream: vi.fn(), health: vi.fn() }
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = (projectId: string) => <QueryClientProvider client={cache}><StudioStatisticsPanel workspaceKey="w" instanceId="i" projectId={projectId} client={client} disabled={false} /></QueryClientProvider>
  const view = render(tree('p'))
  return { client, ...view, changeProject: () => view.rerender(tree('other')) }
}
it('displays server metrics, scopes filters and pagination, then reads original logs and assets', async () => {
  const view = mount(async path => path.includes('/logs?') ? { items: [{ sequence: 1, message: '实际执行日志' }], total: 1, nextCursor: null } : path.includes('/run-assets?') ? { items: [], total: 0, nextCursor: null } : data)
  expect(await screen.findByText('75.0%')).toBeVisible()
  expect(screen.getByText('1,000')).toBeVisible()
  expect(screen.getByText(/历史录制尚未保存项目归属/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(view.client.request).toHaveBeenCalledWith(expect.stringContaining('cursor=50'), expect.anything()))
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: 'Studio 运行状态筛选' }), 'failed')
  await waitFor(() => expect(view.client.request).toHaveBeenCalledWith(expect.stringMatching(/status=failed.*cursor=0|cursor=0.*status=failed/), expect.anything()))
  await userEvent.click(screen.getByRole('button', { name: '查看运行 run' }))
  expect(await screen.findByText(/实际执行日志/)).toBeVisible()
  expect(view.client.request).toHaveBeenCalledWith('/api/workflow-runs/run/logs?projectId=p&cursor=0&limit=100', expect.anything())
  await userEvent.click(screen.getByText('本次运行的产物'))
  await waitFor(() => expect(view.client.request).toHaveBeenCalledWith(expect.stringMatching(/\/projects\/p\/run-assets\?.*runId=run/), expect.anything()))
})
it('does not display foreign statistics or retain an open run across project replacement', async () => {
  const view = mount(async path => path.includes('/logs?') ? { items: [], total: 0 } : data)
  await userEvent.click(await screen.findByRole('button', { name: '查看运行 run' }))
  view.changeProject()
  expect(screen.queryByRole('region', { name: '统计运行详情' })).not.toBeInTheDocument()
  expect(await screen.findByRole('alert')).toHaveTextContent('统计读取失败')
  expect(screen.queryByText('75.0%')).not.toBeInTheDocument()
})
it('shows empty metrics honestly and offers retry after service failure', async () => {
  let failure = true
  mount(async () => { if (failure) throw new Error('network down'); return { ...data, totalRuns: 0, items: [], nextCursor: null, successRate: null, averageDurationMs: null } })
  expect(await screen.findByRole('alert')).toHaveTextContent('统计读取失败')
  failure = false
  await userEvent.click(screen.getByRole('button', { name: '刷新 Studio 统计' }))
  expect(await screen.findByText('没有匹配的 Studio 运行')).toBeVisible()
  expect(screen.getAllByText('无样本')).toHaveLength(2)
})
