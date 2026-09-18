import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { StatisticsPage } from './StatisticsPage'

afterEach(cleanup)

const sample = { succeeded: 2, failed: 1, cancelled: 0, timed_out: 0, interrupted: 0 }
const payload = { from: '2026-09-12T00:00:00Z', to: '2026-09-19T03:30:00Z', timezone: 'Asia/Shanghai', sample, successRate: 2 / 3, averageDurationMs: 36000, trend: [{ bucketStart: '2026-09-18T16:00:00Z', ...sample, averageDurationMs: 36000 }], failuresByAutomation: [{ automationId: 'a', name: '链接采集', count: 1, reasonSummary: '页面读取超时' }], resultSetId: 'rs1', calculatedAt: '2026-09-19T03:30:00Z', expiresAt: '2026-09-20T03:30:00Z' }
const taskPage = { items: [{ taskId: 't1', projectId: 'p', batchId: 'b', runId: 'r', runRequestId: 'q', status: 'failed', statusRevision: 1, inputSnapshotId: 's', taskOrdinal: 3, automationName: '链接采集', createdAt: '2026-09-19T03:00:00Z', completedAt: '2026-09-19T03:01:00Z' }], page: 1, pageSize: 50, total: 1, sort: '-createdAt' }
const client = (request: StreamingApiClient['request']) => ({ request, stream: vi.fn(), health: vi.fn() })
const props = { workspaceKey: 'ws', instanceId: 'i', projectId: 'p', disabled: false, onOpenRuns: vi.fn() }
const renderPage = (request: StreamingApiClient['request']) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><StatisticsPage {...props} client={client(request)}/></QueryClientProvider>)
const routes = (value: unknown) => vi.fn().mockImplementation((path: string) => Promise.resolve(path.includes('/tasks') ? value : payload))

it('reports the real four measures, the real scale note and never invents resource usage', async () => {
  renderPage(routes(taskPage))
  expect(await screen.findByText('本期已结束任务')).toBeVisible()
  expect(screen.getByText('66.7%')).toBeVisible()
  expect(screen.getByText('36 秒')).toBeVisible()
  expect(screen.getByText('链接采集')).toBeVisible()
  expect(screen.getByText('资源使用')).toBeVisible()
  expect(screen.getByText('尚未采集')).toBeVisible()
  expect(screen.getByText(/成功率 = 成功/)).toBeVisible()
})

it('shows no sample instead of zero or full success when the denominator is empty', async () => {
  const empty = { ...payload, sample: { succeeded: 0, failed: 0, cancelled: 1, timed_out: 1, interrupted: 0 }, successRate: null, averageDurationMs: null, trend: [], failuresByAutomation: [] }
  const request = vi.fn().mockImplementation((path: string) => Promise.resolve(path.includes('/tasks') ? taskPage : empty))
  renderPage(request)
  await screen.findAllByText('无样本')
  expect(screen.getAllByText('无样本')).toHaveLength(2)
  expect(screen.queryByText('0.0%')).not.toBeInTheDocument()
  expect(screen.queryByText('100.0%')).not.toBeInTheDocument()
  expect(screen.getByText(/无已结束任务/)).toBeVisible()
  expect(screen.getByText('本区间没有失败任务。')).toBeVisible()
})

it('drills into the frozen result set instead of re-running the current filter', async () => {
  const request = routes(taskPage)
  renderPage(request)
  await userEvent.click((await screen.findAllByRole('button', { name: /查看记录/ }))[0])
  expect(await screen.findByText('任务 3 · 链接采集')).toBeVisible()
  expect(request).toHaveBeenCalledWith(expect.stringContaining('/statistics/rs1/tasks?result=failed'), expect.anything())
})

it('tells the user the result set expired instead of showing stale numbers as fresh', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('expired', 410, 'STATISTICS_RESULT_EXPIRED'))
  renderPage(request)
  expect(await screen.findByRole('alert')).toHaveTextContent('统计结果已过期，请刷新后重试')
})
