import { beforeEach, describe, expect, it, vi } from 'vitest'
import { isPlatformActionRequest, runPlatformAction } from '../lib/runPlatformAction'

const request = {
  requestId: 'request-1',
  workflowId: 'flow-1',
  nodeId: 'node-1',
  action: 'clipboard_read_text' as const,
  payload: {},
}

describe('Studio platform action execution', () => {
  beforeEach(() => {
    window.autoflow = {
      ...window.autoflow,
      runStudioPlatformAction: vi.fn().mockResolvedValue({ ok: true, value: { value: '原文' } }),
    }
  })

  it('validates the backend envelope and returns the Electron result', async () => {
    expect(isPlatformActionRequest(request)).toBe(true)
    await expect(runPlatformAction(request, new AbortController().signal)).resolves.toEqual({
      success: true,
      value: '原文',
      error: null,
    })
    expect(window.autoflow.runStudioPlatformAction).toHaveBeenCalledWith({ action: 'clipboard_read_text' })
  })

  it('rejects malformed payloads without invoking Electron', async () => {
    const malformed = { ...request, action: 'beep' as const, payload: { count: '2', interval: 0 } }
    await expect(runPlatformAction(malformed, new AbortController().signal)).resolves.toMatchObject({
      success: false,
      error: '当前环境不支持平台操作',
    })
    expect(window.autoflow.runStudioPlatformAction).not.toHaveBeenCalled()
  })

  it('does not report a late IPC result after cancellation', async () => {
    let release!: (value: { ok: true; value: Record<string, never> }) => void
    window.autoflow.runStudioPlatformAction = vi.fn(() => new Promise<{ ok: true; value: Record<string, never> }>(resolve => { release = resolve }))
    const controller = new AbortController()
    const running = runPlatformAction(
      { ...request, action: 'clipboard_write_text', payload: { text: 'hello' } },
      controller.signal,
    )
    controller.abort()
    release({ ok: true, value: {} })
    await expect(running).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('stops repeated beeps between native calls', async () => {
    vi.useFakeTimers()
    const controller = new AbortController()
    const running = runPlatformAction(
      { ...request, action: 'beep', payload: { count: 3, interval: 1 } },
      controller.signal,
    )
    await vi.advanceTimersByTimeAsync(0)
    expect(window.autoflow.runStudioPlatformAction).toHaveBeenCalledTimes(1)
    controller.abort()
    await expect(running).rejects.toMatchObject({ name: 'AbortError' })
    expect(window.autoflow.runStudioPlatformAction).toHaveBeenCalledTimes(1)
    vi.useRealTimers()
  })

  it('passes validated system control requests to Electron', async () => {
    vi.mocked(window.autoflow!.runStudioPlatformAction!).mockResolvedValueOnce({ ok: true, value: {} })
    await expect(runPlatformAction(
      { ...request, action: 'system_control', payload: { operation: 'sleep', delay: 0, force: false } },
      new AbortController().signal,
    )).resolves.toEqual({ success: true, value: null, error: null })
    expect(window.autoflow.runStudioPlatformAction).toHaveBeenCalledWith({
      action: 'system_control', operation: 'sleep', delay: 0, force: false,
    })
  })
})
