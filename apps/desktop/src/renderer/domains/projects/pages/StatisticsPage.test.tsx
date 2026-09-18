import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../../shared/api/client'
import { choiceTestEnvironment, chooseOption } from '../../../shared/testing/choice-user'
import { StatisticsPage } from './StatisticsPage'

choiceTestEnvironment()
// 浏览偏好按工作区存在 sessionStorage；每条用例从默认区间开始，避免上一条用例的选择污染下一条。
beforeEach(() => sessionStorage.clear())
afterEach(cleanup)

const sample = { succeeded: 2, failed: 1, cancelled: 0, timed_out: 0, interrupted: 0 }
const payload = {
  from: '2026-09-12T00:00:00Z',
  to: '2026-09-19T03:30:00Z',
  timezone: 'Asia/Shanghai',
  sample,
  successRate: 2 / 3,
  averageDurationMs: 36000,
  trend: [{ bucketStart: '2026-09-18T16:00:00Z', ...sample, averageDurationMs: 36000 }],
  failuresByAutomation: [
    { automationId: 'a', name: '链接采集', count: 1, reasonSummary: '页面读取超时' },
  ],
  resultSetId: 'rs1',
  calculatedAt: '2026-09-19T03:30:00Z',
  expiresAt: '2026-09-20T03:30:00Z',
}
const taskPage = {
  items: [
    {
      taskId: 't1',
      projectId: 'p',
      batchId: 'b',
      runId: 'r',
      runRequestId: 'q',
      status: 'failed',
      statusRevision: 1,
      inputSnapshotId: 's',
      taskOrdinal: 3,
      automationName: '链接采集',
      createdAt: '2026-09-19T03:00:00Z',
      completedAt: '2026-09-19T03:01:00Z',
    },
  ],
  page: 1,
  pageSize: 50,
  total: 1,
  sort: '-createdAt',
}
/** 测试替身只实现 request；泛型签名由 StreamingApiClient 在本处一次性收窄。 */
const apiFor = (request: unknown) => ({ request: request as StreamingApiClient['request'], stream: vi.fn(), health: vi.fn() })
const newClient = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
const props = { workspaceKey: 'ws', instanceId: 'i', projectId: 'p', disabled: false, onOpenRuns: vi.fn() }
const renderPage = (request: unknown, client = newClient()) =>
  render(
    <QueryClientProvider client={client}>
      <StatisticsPage {...props} client={apiFor(request)} />
    </QueryClientProvider>,
  )

/** Every request the page can make, routed by the shape of its path. */
const routes = (statistics: unknown, tasks: unknown = taskPage) =>
  vi.fn(async (path: string) => {
    if (path.includes('/statistics/')) return tasks
    if (path.includes('/statistics?')) return statistics
    if (path.includes('/automations')) return { items: [], total: 0 }
    throw new Error(`unexpected request: ${path}`)
  })

const spanInDays = (path: string) => {
  const params = new URL(String(path), 'http://localhost').searchParams
  return Math.round((Date.parse(params.get('to')!) - Date.parse(params.get('from')!)) / 86_400_000)
}
const range = (request: ReturnType<typeof routes>, days: number, nth = -1) => {
  const calls = request.mock.calls.map(([path]) => path).filter(path => path.includes('/statistics?'))
  const match = calls.filter(path => spanInDays(path) === days)
  return nth === -1 ? match[match.length - 1] : match[nth]
}

it('reports the real four measures, the real scale note and never invents resource usage', async () => {
  renderPage(routes(payload))
  expect(await screen.findByText('本期已结束任务')).toBeVisible()
  expect(screen.getByText('66.7%')).toBeVisible()
  expect(screen.getByText('36 秒')).toBeVisible()
  expect(screen.getByText('链接采集')).toBeVisible()
  expect(screen.getByText('页面读取超时')).toBeVisible()
  expect(screen.getByRole('button', { name: /查看记录/ })).toBeEnabled()
  expect(screen.getByText('资源使用')).toBeVisible()
  expect(screen.getByText('尚未采集')).toBeVisible()
  expect(screen.getByText(/成功率 = 成功/)).toBeVisible()
  expect(screen.getByText(/不计运行中与等待人工/)).toBeVisible()
  expect(screen.getByText(/任务数不等于数据新增量/)).toBeVisible()
})

it('shows no sample instead of zero or full success when the denominator is empty', async () => {
  const empty = {
    ...payload,
    sample: { succeeded: 0, failed: 0, cancelled: 1, timed_out: 1, interrupted: 0 },
    successRate: null,
    averageDurationMs: null,
    trend: [],
    failuresByAutomation: [],
  }
  renderPage(routes(empty))
  await screen.findByText('无有效样本')
  expect(screen.getAllByText('无样本')).toHaveLength(1)
  expect(screen.queryByText('0.0%')).not.toBeInTheDocument()
  expect(screen.queryByText('100.0%')).not.toBeInTheDocument()
  expect(screen.getByText(/无已结束任务/)).toBeVisible()
  expect(screen.getByText('本区间没有失败任务。')).toBeVisible()
})

it('drills into the frozen result set instead of re-running the current filter', async () => {
  const request = routes(payload)
  renderPage(request)
  await userEvent.click((await screen.findAllByRole('button', { name: /查看记录/ }))[0])
  expect(await screen.findByText('任务 3 · 链接采集')).toBeVisible()
  expect(request).toHaveBeenCalledWith(
    expect.stringContaining('/statistics/rs1/tasks?result=failed'),
    expect.anything(),
  )
  await userEvent.click(screen.getByRole('button', { name: '返回统计' }))
  expect(screen.queryByText('任务 3 · 链接采集')).not.toBeInTheDocument()
  expect(screen.getByText('66.7%')).toBeVisible()
})

it('tells the user the result set expired instead of showing stale numbers as fresh', async () => {
  const request = vi.fn().mockRejectedValue(new ApiClientError('expired', 410, 'STATISTICS_RESULT_EXPIRED'))
  renderPage(request)
  expect(await screen.findByRole('alert')).toHaveTextContent('统计结果已过期，请刷新后重试')
})

it('keeps the last recorded numbers and their time when a refresh fails', async () => {
  let fail = false
  const request = vi.fn(async (path: string) => {
    if (path.includes('/statistics/')) return taskPage
    if (path.includes('/statistics?')) {
      if (fail) throw new ApiClientError('boom', 500, 'INTERNAL')
      return payload
    }
    if (path.includes('/automations')) return { items: [], total: 0 }
    throw new Error(`unexpected request: ${path}`)
  })
  const client = newClient()
  renderPage(request, client)
  await screen.findByText('66.7%')
  fail = true
  await client
    .refetchQueries({ queryKey: ['ws', 'i', 'project-statistics'] })
    .catch(() => undefined)
  expect(await screen.findByText(/统计刷新失败/)).toBeVisible()
  expect(screen.getByText(/以下是/)).toBeVisible()
  expect(screen.getByText('66.7%')).toBeVisible()
  expect(screen.getByText('36 秒')).toBeVisible()
})

it('re-reads the whole group with the new window when the range changes', async () => {
  const request = routes(payload)
  renderPage(request)
  await screen.findByText('66.7%')
  expect(range(request, 7)).toBeDefined()
  await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '统计区间' }), '30d')
  await waitFor(() => expect(range(request, 30)).toBeDefined())
})

it('restores the recorded range and scroll position after returning to the page', async () => {
  const scrollTo = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  try {
    const first = routes(payload)
    const view = renderPage(first)
    await screen.findByText('66.7%')
    await chooseOption(userEvent.setup(), screen.getByRole('combobox', { name: '统计区间' }), '90d')
    await waitFor(() => expect(range(first, 90)).toBeDefined())
    view.unmount()

    const stored = JSON.parse(
      sessionStorage.getItem(`autoflow:statistics:${JSON.stringify(['ws', 'p'])}`)!,
    )
    expect(stored.range).toBe('90d')
    sessionStorage.setItem(
      `autoflow:statistics:${JSON.stringify(['ws', 'p'])}`,
      JSON.stringify({ ...stored, scroll: 240 }),
    )

    const second = routes(payload)
    renderPage(second)
    expect(await screen.findByText('66.7%')).toBeVisible()
    expect(range(second, 90)).toBeDefined()
    expect(screen.getByRole('combobox', { name: '统计区间' })).toHaveAttribute(
      'data-choice-value',
      '90d',
    )
    await waitFor(() => expect(scrollTo).toHaveBeenCalledWith(0, 240))
  } finally {
    scrollTo.mockRestore()
    sessionStorage.clear()
  }
})
