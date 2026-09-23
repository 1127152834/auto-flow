import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../../shared/api/client'
import { ProjectInteractionHost } from './ProjectInteractionHost'
import { runJsScript } from '../../workflows/lib/runJsScript'
import { socketService } from '../../workflows/events'
vi.mock('../../workflows/lib/runJsScript', () => ({ runJsScript: vi.fn() }))
afterEach(() => { cleanup(); vi.restoreAllMocks() })
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
