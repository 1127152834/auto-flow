import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { ProjectInteractionHost } from './ProjectInteractionHost'
import { runJsScript } from '../../workflows/lib/runJsScript'
import { socketService } from '../../workflows/events'
vi.mock('../../workflows/lib/runJsScript', () => ({ runJsScript: vi.fn() }))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers() })
const identity = { projectId: 'project', taskId: 'task', runId: 'run', executionGeneration: 1, requestId: 'req', type: 'execution:input_prompt', status: 'pending' }
const prompt = { ...identity, nodeId: 'node', executionId: 'visit', inputMode: 'single', variableName: 'answer', title: '项目需要输入', message: '请输入任务值', defaultValue: 'before' }
const client = (request: ReturnType<typeof vi.fn>) => ({ request }) as unknown as StreamingApiClient
it('uses the original input form through project transport without the Studio socket', async () => {
  const studio = vi.spyOn(socketService, 'sendInputResult')
  const request = vi.fn(async (path, init) => path === '/api/v1/project-run-interactions' ? [identity] : path.includes('/requests/') ? prompt : { commandId: init.body.commandId, requestId: 'req', status: 'applied' })
  render(<ProjectInteractionHost client={client(request)} connected />)
  fireEvent.change(await screen.findByDisplayValue('before'), { target: { value: 'project-value' } })
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  const [, call] = request.mock.calls.find(([, init]) => init?.method === 'POST')!
  expect(call.body).toMatchObject({ event: 'input_prompt_result', executionGeneration: 1, data: { requestId: 'req', value: 'project-value' } })
  expect(studio).not.toHaveBeenCalled()
})
it('restores a submitted input as a query of its original command, never a second submission', async () => {
  const request = vi.fn(async (path, _init?: { method?: string }) => path === '/api/v1/project-run-interactions' ? [{ ...identity, status: 'submitted' }] : path.includes('/requests/') ? { ...prompt, status: 'submitted', commandId: 'original' } : { commandId: 'original', requestId: 'req', status: 'applied' })
  render(<ProjectInteractionHost client={client(request)} connected />)
  fireEvent.click(await screen.findByRole('button', { name: '查询提交结果' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
  expect(request.mock.calls.some(([path]) => path.endsWith('/commands/original'))).toBe(true)
  expect(request.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false)
})
it('does not restart a running JS tool when the main window reconnects', async () => {
  const target = { ...identity, type: 'execution:js_script' }
  const request = vi.fn(async (path, init) => path === '/api/v1/project-run-interactions' ? [target] : path.includes('/requests/') ? { ...target, code: 'function main(vars){return 7}', variables: {}, nodeId: 'n', executionId: 'v' } : { commandId: init.body.commandId, requestId: 'req', status: 'applied' })
  let finish!: (value: { success: boolean; result: number; variables: Record<string, unknown> }) => void
  vi.mocked(runJsScript).mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const { rerender, unmount } = render(<ProjectInteractionHost client={client(request)} connected />)
  await waitFor(() => expect(runJsScript).toHaveBeenCalledTimes(1))
  rerender(<ProjectInteractionHost client={client(request)} connected={false} />)
  rerender(<ProjectInteractionHost client={client(request)} connected />)
  await act(async () => finish({ success: true, result: 7, variables: {} }))
  expect(runJsScript).toHaveBeenCalledTimes(1)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_result')).toHaveLength(1)
  unmount()
})

it('clears the transport notice after the next complete poll succeeds', async () => {
  vi.useFakeTimers()
  const request = vi.fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockResolvedValue([])
  render(<ProjectInteractionHost client={client(request)} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.queryByText(/项目交互连接中断/)).toBeNull()
})

it('retries a transient JS request read before claim and executes the script once', async () => {
  vi.useFakeTimers()
  const target = { ...identity, type: 'execution:js_script' }
  let scriptReads = 0
  const request = vi.fn(async (path, init) => {
    if (path === '/api/v1/project-run-interactions') return [target]
    if (path.includes('/requests/')) {
      if (scriptReads++ === 0) throw new TypeError('offline')
      return { ...target, code: 'function main(vars){return 7}', variables: {}, nodeId: 'n', executionId: 'v' }
    }
    return { commandId: init.body.commandId, requestId: 'req', status: 'applied' }
  })
  vi.mocked(runJsScript).mockReset().mockResolvedValue({ success: true, result: 7, variables: {} })
  render(<ProjectInteractionHost client={client(request)} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
  expect(runJsScript).not.toHaveBeenCalled()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.queryByText(/项目交互连接中断/)).toBeNull()
  expect(runJsScript).toHaveBeenCalledTimes(1)
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(runJsScript).toHaveBeenCalledTimes(1)
  expect(scriptReads).toBe(2)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_claim')).toHaveLength(1)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_result')).toHaveLength(1)
})

it('keeps polling other interactions while a transient claim recovers with its original command', async () => {
  vi.useFakeTimers()
  const target = { ...identity, type: 'execution:js_script' }
  const input = { ...identity, requestId: 'input' }
  const inputRequest = { ...prompt, ...input }
  let pendingCalls = 0
  let claimRecovered = false
  let claimCommandId = ''
  const request = vi.fn(async (path, init) => {
    if (path === '/api/v1/project-run-interactions') return pendingCalls++ === 0 ? [target] : [target, input]
    if (path.includes('/requests/input')) return inputRequest
    if (path.includes('/requests/req')) return { ...target, code: 'function main(vars){return 7}', variables: {}, nodeId: 'n', executionId: 'v' }
    if (init?.body?.event === 'js_script_claim') {
      claimCommandId = init.body.commandId
      throw new TypeError('claim submit offline')
    }
    if (path.includes('/commands/')) {
      if (!claimRecovered) throw new TypeError('claim query offline')
      return { commandId: claimCommandId, requestId: 'req', status: 'applied' }
    }
    return { commandId: init.body.commandId, requestId: 'req', status: 'applied' }
  })
  vi.mocked(runJsScript).mockReset().mockResolvedValue({ success: true, result: 7, variables: {} })
  render(<ProjectInteractionHost client={client(request)} connected />)

  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
  expect(runJsScript).not.toHaveBeenCalled()

  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(pendingCalls).toBeGreaterThanOrEqual(2)
  expect(screen.getByRole('dialog')).toBeDefined()
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
  expect(runJsScript).not.toHaveBeenCalled()

  claimRecovered = true
  await act(async () => { await vi.advanceTimersByTimeAsync(500) })
  expect(screen.queryByText(/项目交互连接中断/)).toBeNull()
  expect(runJsScript).toHaveBeenCalledTimes(1)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_claim')).toHaveLength(1)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_result')).toHaveLength(1)
  const claimQueries = request.mock.calls.filter(([path]) => path.includes('/commands/'))
  expect(claimQueries.length).toBeGreaterThan(1)
  expect(claimQueries.every(([path]) => path.endsWith(`/commands/${claimCommandId}`))).toBe(true)
})

it('aborts an unresolved claim across a connection revision without replaying it', async () => {
  vi.useFakeTimers()
  const target = { ...identity, type: 'execution:js_script' }
  let claimSignal: AbortSignal | undefined
  const request = vi.fn(async (path, init) => {
    if (path === '/api/v1/project-run-interactions') return [target]
    if (path.includes('/requests/')) return { ...target, code: 'function main(vars){return 7}', variables: {}, nodeId: 'n', executionId: 'v' }
    if (init?.body?.event === 'js_script_claim') throw new TypeError('claim submit offline')
    if (path.includes('/commands/')) {
      claimSignal = init.signal
      return new Promise((_, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason), { once: true }))
    }
    return { commandId: init.body.commandId, requestId: 'req', status: 'applied' }
  })
  vi.mocked(runJsScript).mockReset().mockResolvedValue({ success: true, result: 7, variables: {} })
  const api = client(request)
  const view = render(<ProjectInteractionHost client={api} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(claimSignal?.aborted).toBe(false)

  view.rerender(<ProjectInteractionHost client={api} connected={false} />)
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(claimSignal?.aborted).toBe(true)
  view.rerender(<ProjectInteractionHost client={api} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })

  expect(runJsScript).not.toHaveBeenCalled()
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_claim')).toHaveLength(1)
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_result')).toHaveLength(0)
})

it('keeps an actual script failure after later transport polls succeed', async () => {
  vi.useFakeTimers()
  const target = { ...identity, type: 'execution:js_script' }
  let pendingCalls = 0
  const request = vi.fn(async (path, init) => {
    if (path === '/api/v1/project-run-interactions') return pendingCalls++ === 0 ? [target] : []
    if (path.includes('/requests/')) return { ...target, code: 'function main(){throw new Error()}', variables: {}, nodeId: 'n', executionId: 'v' }
    return { commandId: init.body.commandId, requestId: 'req', status: 'applied' }
  })
  vi.mocked(runJsScript).mockRejectedValue(new Error('脚本执行失败'))
  render(<ProjectInteractionHost client={client(request)} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByText('脚本执行失败')).toBeDefined()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  expect(screen.getByText('脚本执行失败')).toBeDefined()
})

it('does not let a late successful poll from an invalidated connection clear its notice', async () => {
  vi.useFakeTimers()
  let resolveLate!: (value: unknown[]) => void
  const request = vi.fn()
    .mockRejectedValueOnce(new TypeError('offline'))
    .mockImplementationOnce(() => new Promise(resolve => { resolveLate = resolve }))
  const api = client(request)
  const view = render(<ProjectInteractionHost client={api} connected />)
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
  await act(async () => { await vi.advanceTimersByTimeAsync(1000) })
  view.rerender(<ProjectInteractionHost client={api} connected={false} />)
  await act(async () => { resolveLate([]); await Promise.resolve() })
  expect(screen.getByText(/项目交互连接中断/)).toBeDefined()
})

it('aborts the JS tool on window disposal and ignores its late result', async () => {
  const target = { ...identity, type: 'execution:js_script' }
  const request = vi.fn(async (path, init) => path === '/api/v1/project-run-interactions' ? [target] : path.includes('/requests/') ? { ...target, code: 'function main(vars){return 7}', variables: {}, nodeId: 'n', executionId: 'v' } : { commandId: init.body.commandId, requestId: 'req', status: 'applied' })
  let finish!: (value: Awaited<ReturnType<typeof runJsScript>>) => void
  vi.mocked(runJsScript).mockClear().mockImplementation(() => new Promise(resolve => { finish = resolve }))
  const { unmount } = render(<ProjectInteractionHost client={client(request)} connected />)
  await waitFor(() => expect(runJsScript).toHaveBeenCalledTimes(1))
  const signal = vi.mocked(runJsScript).mock.calls[0][2]
  unmount()
  expect(signal.aborted).toBe(true)
  await act(async () => finish({ success: true, result: 7, variables: {} }))
  expect(request.mock.calls.filter(([, init]) => init?.body?.event === 'js_script_result')).toHaveLength(0)
})
