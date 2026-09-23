import { expect, it, vi } from 'vitest'
import { ApiClientError, type StreamingApiClient } from '../../shared/api/client'
import { createProjectInteractions, executeProjectScript, type InteractionIdentity } from './interactions'
import { runJsScript } from '../workflows/lib/runJsScript'
vi.mock('../workflows/lib/runJsScript', () => ({ runJsScript: vi.fn() }))
const target: InteractionIdentity = { projectId: 'p', taskId: 't', runId: 'r', executionGeneration: 1, requestId: 'req', type: 'execution:js_script', status: 'pending' }
const script = { ...target, nodeId: 'n', executionId: 'visit', code: 'function main(vars){return 7}', variables: { count: 1 } }
const client = (request: ReturnType<typeof vi.fn>) => ({ request }) as unknown as StreamingApiClient
it('claims once, runs the existing JS tool, and queries a lost result response without re-execution', async () => {
  const posts: string[] = []
  const request = vi.fn(async (path, init) => {
    if (path.includes('/requests/')) return script
    if (init?.method === 'POST') { posts.push(init.body.event); if (init.body.event === 'js_script_result') throw new TypeError('offline'); return { commandId: init.body.commandId, requestId: 'req', status: 'applied' } }
    return { commandId: path.split('/').at(-1), requestId: 'req', status: 'applied' }
  })
  vi.mocked(runJsScript).mockResolvedValue({ success: true, result: 7, variables: { count: 2 } })
  await executeProjectScript(createProjectInteractions(() => client(request)), target, new AbortController().signal)
  expect(posts).toEqual(['js_script_claim', 'js_script_result'])
  expect(runJsScript).toHaveBeenCalledExactlyOnceWith(script.code, script.variables, expect.any(AbortSignal))
})
it('does not execute a script already claimed by another renderer or a changed run', async () => {
  vi.mocked(runJsScript).mockClear()
  for (const change of [{ status: 'claimed', claimId: 'elsewhere' }, { runId: 'foreign' }]) {
    const request = vi.fn().mockResolvedValue({ ...script, ...change })
    await expect(executeProjectScript(createProjectInteractions(() => client(request)), target, new AbortController().signal)).rejects.toThrow()
    expect(request).toHaveBeenCalledTimes(1)
  }
  expect(runJsScript).not.toHaveBeenCalled()
})
it('does not send a script result after cancellation', async () => {
  const controller = new AbortController()
  const request = vi.fn(async (path, init) => path.includes('/requests/') ? script : { commandId: init.body.commandId, requestId: 'req', status: 'applied' })
  vi.mocked(runJsScript).mockImplementation(async () => { controller.abort(); return { success: true, result: 7, variables: {} } })
  await expect(executeProjectScript(createProjectInteractions(() => client(request)), target, controller.signal)).rejects.toThrow()
  expect(request).toHaveBeenCalledTimes(2)
})
it('queries uncertain input commands but never resends them on a missing receipt', async () => {
  const request = vi.fn().mockRejectedValueOnce(new TypeError('offline')).mockRejectedValueOnce(new ApiClientError('not found', 404))
  await expect(createProjectInteractions(() => client(request)).submit(target, 'command', 'input_prompt_result', { requestId: 'req', value: 'secret' })).rejects.toThrow()
  expect(request.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
})

it('rejects a mismatched claim receipt without polling forever or executing JS', async () => {
  vi.mocked(runJsScript).mockClear()
  const request = vi.fn(async (path) => path.includes('/requests/') ? script : { commandId: 'foreign', requestId: 'req', status: 'applied' })
  await expect(executeProjectScript(createProjectInteractions(() => client(request)), target, new AbortController().signal)).rejects.toThrow('回执')
  expect(runJsScript).not.toHaveBeenCalled()
})
