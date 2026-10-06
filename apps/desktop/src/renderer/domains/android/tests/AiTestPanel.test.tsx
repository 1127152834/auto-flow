import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import type { AiTestApi, AiTestRun } from '../ai-test-api'
import { AiTestPanel } from '../components/AiTestPanel'
import { DeviceConsole } from '../components/DeviceConsole'
import { devices } from './prototype-fixtures'

afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })

const target = { deviceKind: 'managed' as const, deviceId: 'dev-1' }
const run = (patch: Partial<AiTestRun> = {}): AiTestRun => ({
  id: 'run-1', requestId: 'req-1', deviceKind: 'managed', deviceId: 'dev-1', state: 'succeeded', createdAt: '2026-10-05T00:00:00Z',
  startedAt: '2026-10-05T00:00:00Z', finishedAt: '2026-10-05T00:01:30Z', instruction: '打开设置', mode: 'flash', modelId: 'm1', modelKey: 'gpt-x',
  maxSteps: 30, timeoutSeconds: 600, steps: [], artifacts: [], ...patch,
})

function setup(over: Partial<Record<keyof AiTestApi, unknown>> = {}, props: { onTakeOver?: () => void } = {}) {
  const api = {
    tool: vi.fn().mockResolvedValue({ state: 'ready', version: '1' }),
    installTool: vi.fn().mockResolvedValue({ state: 'ready' }),
    externalDevices: vi.fn().mockResolvedValue([]),
    installHelper: vi.fn().mockResolvedValue({ installed: true }),
    start: vi.fn().mockResolvedValue(run({ state: 'running', finishedAt: null })),
    runs: vi.fn().mockResolvedValue({ items: [], nextCursor: null }),
    run: vi.fn().mockResolvedValue(run({ state: 'running', finishedAt: null })),
    cancel: vi.fn().mockResolvedValue(run({ state: 'cancelled' })),
    remove: vi.fn().mockResolvedValue(undefined),
    artifactUrl: vi.fn((id: string, name: string) => `/x/${id}/${name}`),
    artifactBlob: vi.fn().mockRejectedValue(new Error('no blob')),
    modelOptions: vi.fn().mockResolvedValue({ items: [{ id: 'm1', providerId: 'p', providerName: '供应商', modelKey: 'gpt-x', displayName: '示例模型', tagsJson: [] }], total: 1 }),
    ...over,
  } as unknown as AiTestApi
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AiTestPanel api={api} target={target} {...props} /></QueryClientProvider>)
  return api
}

const fill = async (text = '打开设置搜索 Wi-Fi') => userEvent.type(await screen.findByLabelText('测试指令'), text)

it('offers installation when the tool is missing and disables it for a missing prerequisite', async () => {
  const api = setup({ tool: vi.fn().mockResolvedValue({ state: 'not_installed' }) })
  await userEvent.click(await screen.findByRole('button', { name: '安装测试工具' }))
  expect(api.installTool).toHaveBeenCalledWith({ requestId: expect.any(String) })
  cleanup()
  setup({ tool: vi.fn().mockResolvedValue({ state: 'missing_prerequisite', message: '请先安装 Python 3.11' }) })
  expect(await screen.findByText('请先安装 Python 3.11')).toBeVisible()
  expect(screen.getByRole('button', { name: '安装测试工具' })).toBeDisabled()
})

it('disables submit for out-of-range steps and starts a run with the entered values', async () => {
  const api = setup()
  await fill()
  const submit = await screen.findByRole('button', { name: '开始测试' })
  await waitFor(() => expect(submit).toBeEnabled())
  const steps = screen.getByLabelText('步数上限')
  await userEvent.clear(steps); await userEvent.type(steps, '201')
  expect(submit).toBeDisabled()
  await userEvent.clear(steps); await userEvent.type(steps, '20')
  await userEvent.click(submit)
  expect(api.start).toHaveBeenCalledWith(expect.objectContaining({ instruction: '打开设置搜索 Wi-Fi', mode: 'flash', modelId: 'm1', maxSteps: 20, timeoutSeconds: 600, deviceKind: 'managed', deviceId: 'dev-1' }))
})

it('shows steps of a running test and can stop it', async () => {
  const api = setup({
    run: vi.fn().mockResolvedValue(run({ state: 'running', finishedAt: null, steps: [{ index: 1, summary: '点击设置图标' }] })),
  })
  await fill()
  await userEvent.click(await screen.findByRole('button', { name: '开始测试' }))
  expect(await screen.findByText('点击设置图标')).toBeVisible()
  expect(screen.getByText('运行中')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '停止' }))
  expect(api.cancel).toHaveBeenCalledWith('run-1')
})

it('asks before installing the helper, then installs it and retries with a new request id', async () => {
  const start = vi.fn()
    .mockRejectedValueOnce(new ApiClientError('需要辅助组件', 409, 'AI_TEST_HELPER_REQUIRED'))
    .mockResolvedValueOnce(run({ state: 'running', finishedAt: null }))
  const api = setup({ start })
  await fill()
  await userEvent.click(await screen.findByRole('button', { name: '开始测试' }))
  expect(await screen.findByText('需要在该设备安装测试辅助组件')).toBeVisible()
  expect(api.installHelper).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '安装并继续' }))
  await waitFor(() => expect(start).toHaveBeenCalledTimes(2))
  expect(api.installHelper).toHaveBeenCalledWith({ deviceKind: 'managed', deviceId: 'dev-1', serial: undefined })
  expect(start.mock.calls[1][0].requestId).not.toBe(start.mock.calls[0][0].requestId)
  expect(start.mock.calls[1][0].instruction).toBe(start.mock.calls[0][0].instruction)
})

it('shows the backend failure reason and plain wording for an interrupted run', async () => {
  setup({ runs: vi.fn().mockResolvedValue({ items: [
    run({ id: 'a', state: 'needs_verification', finishedAt: null }),
    run({ id: 'b', state: 'failed', errorMessage: '模型返回 401' }),
  ], nextCursor: null }) })
  expect(await screen.findByText('结果待核实：程序中断，无法确定测试是否完成')).toBeVisible()
  expect(screen.getByText('失败')).toBeVisible()
  expect(screen.getByText('模型返回 401')).toBeVisible()
  expect(document.body.textContent).not.toMatch(/requestId|trace|ai_test|needs_verification/i)
})

it('reruns with the same instruction and deletes only after confirmation', async () => {
  const api = setup({ runs: vi.fn().mockResolvedValue({ items: [run()], nextCursor: null }) })
  await userEvent.click(await screen.findByRole('button', { name: '用相同指令重跑' }))
  expect(api.start).toHaveBeenCalledWith(expect.objectContaining({ instruction: '打开设置', modelId: 'm1', requestId: expect.not.stringMatching(/^req-1$/) }))
  await userEvent.click(await screen.findByRole('button', { name: '删除' }))
  expect(api.remove).not.toHaveBeenCalled()
  await userEvent.click(await screen.findByRole('button', { name: '确认删除' }))
  expect(api.remove).toHaveBeenCalledWith('run-1')
})

it('takes over only after the run has ended', async () => {
  let release: (value: AiTestRun) => void = () => {}
  const cancel = vi.fn(() => new Promise<AiTestRun>((resolve) => { release = resolve }))
  const onTakeOver = vi.fn()
  setup({ cancel }, { onTakeOver })
  await fill()
  await userEvent.click(await screen.findByRole('button', { name: '开始测试' }))
  await userEvent.click(await screen.findByRole('button', { name: '停止并接管' }))
  expect(cancel).toHaveBeenCalledWith('run-1')
  expect(onTakeOver).not.toHaveBeenCalled()
  await act(async () => { release(run({ state: 'cancelled' })) })
  await waitFor(() => expect(onTakeOver).toHaveBeenCalledTimes(1))
})

it('pauses polling while the page is hidden', async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
  const api = setup()
  await fill()
  await userEvent.click(await screen.findByRole('button', { name: '开始测试' }))
  await screen.findByRole('button', { name: '停止' })
  visibility.mockReturnValue('hidden')
  act(() => { document.dispatchEvent(new Event('visibilitychange')) })
  const before = vi.mocked(api.run).mock.calls.length
  await act(async () => { await vi.advanceTimersByTimeAsync(6000) })
  expect(vi.mocked(api.run).mock.calls.length).toBe(before)
  visibility.mockReturnValue('visible')
  act(() => { document.dispatchEvent(new Event('visibilitychange')) })
  await act(async () => { await vi.advanceTimersByTimeAsync(2500) })
  expect(vi.mocked(api.run).mock.calls.length).toBeGreaterThan(before)
})

it('adds an AI test tab to the device console and opens manual control after taking over', async () => {
  const onOpen = vi.fn()
  const api = {
    tool: vi.fn().mockResolvedValue({ state: 'ready' }), modelOptions: vi.fn().mockResolvedValue({ items: [], total: 0 }),
    runs: vi.fn().mockResolvedValue({ items: [run({ state: 'running', finishedAt: null })], nextCursor: null }),
    run: vi.fn().mockResolvedValue(run({ state: 'running', finishedAt: null })), cancel: vi.fn().mockResolvedValue(run({ state: 'cancelled' })),
  } as unknown as AiTestApi
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <DeviceConsole device={devices[0]} session={null} aiTestApi={api} onBack={vi.fn()} onSession={vi.fn()} onOpen={onOpen} onManage={vi.fn()} onRefresh={vi.fn()} />
  </QueryClientProvider>)
  await userEvent.click(screen.getByRole('button', { name: 'AI 测试' }))
  await userEvent.click(await screen.findByRole('button', { name: '停止并接管' }))
  await waitFor(() => expect(onOpen).toHaveBeenCalledTimes(1))
  expect(screen.queryByRole('region', { name: 'AI 测试' })).toBeNull()
})
