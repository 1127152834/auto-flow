import { describe, expect, it, vi } from 'vitest'
import type { StreamingApiClient } from '../../shared/api/client'
import { advanceRunEvent, type RunEventCursor, watchRunEvents } from './events'
const state = (): RunEventCursor => ({ runId: 'run', sequence: 0, terminal: false })
const event = (sequence: number, status = 'running') => ({ runId: 'run', sequence, eventId: `e${sequence}`, executionGeneration: 1, kind: 'runStatus' as const, payload: { status, statusRevision: sequence }, occurredAt: '2026-09-15T00:00:00Z' })
describe('persistent run event cursor', () => {
  it('ignores duplicates and refuses gaps before advancing', () => { const one = advanceRunEvent(state(), event(1)); expect(advanceRunEvent(one, event(1))).toBe(one); expect(() => advanceRunEvent(one, event(3))).toThrow('缺口'); expect(one.sequence).toBe(1) })
  it('rejects another run and prevents terminal regression', () => { expect(() => advanceRunEvent(state(), { ...event(1), runId: 'another' })).toThrow('身份'); const end = advanceRunEvent(state(), event(1, 'succeeded')); expect(() => advanceRunEvent(end, event(2))).toThrow('终态'); expect(advanceRunEvent(end, event(1))).toBe(end) })
  it('backfills persisted pages before opening the stream and stops at a persisted terminal fact', async () => {
    const request = vi.fn()
      .mockResolvedValueOnce({ items: [event(1)], afterSequence: 1, lastSequence: 2, hasMore: true, terminal: false })
      .mockResolvedValueOnce({ items: [event(2, 'succeeded')], afterSequence: 2, lastSequence: 2, hasMore: false, terminal: true })
    const stream = vi.fn()
    const changes = vi.fn()
    await watchRunEvents({ request, stream } as unknown as StreamingApiClient, { projectId: 'project', taskId: 'task', runId: 'run', signal: new AbortController().signal, onChange: changes })
    expect(request.mock.calls.map(call => call[0])).toEqual([
      '/api/v1/projects/project/tasks/task/events?afterSequence=0',
      '/api/v1/projects/project/tasks/task/events?afterSequence=1',
    ])
    expect(changes).toHaveBeenCalledTimes(2)
    expect(stream).not.toHaveBeenCalled()
  })
  it('does not silently accept a malformed persisted cursor', async () => {
    const controller = new AbortController()
    const onError = vi.fn(() => controller.abort())
    const client = { request: vi.fn().mockResolvedValue({ items: [event(1)], afterSequence: 0, lastSequence: 1, hasMore: false, terminal: false }), stream: vi.fn() } as unknown as StreamingApiClient
    await watchRunEvents(client, { projectId: 'project', taskId: 'task', runId: 'run', signal: controller.signal, onChange: vi.fn(), onError })
    expect(onError).toHaveBeenCalledWith('运行事件补读结果不连续')
    expect(client.stream).not.toHaveBeenCalled()
  })
  it('uses the query cursor without adding a non-simple Last-Event-ID request header', async () => {
    const controller = new AbortController()
    const client = {
      request: vi.fn().mockResolvedValue({ items: [], afterSequence: 0, lastSequence: 0, hasMore: false, terminal: false }),
      stream: vi.fn(async () => {
        controller.abort()
        return new Response('')
      }),
    } as unknown as StreamingApiClient
    await watchRunEvents(client, { projectId: 'project', taskId: 'task', runId: 'run', signal: controller.signal, onChange: vi.fn() })
    expect(client.stream).toHaveBeenCalledWith(
      '/api/v1/projects/project/tasks/task/events/stream?afterSequence=0',
      expect.objectContaining({ headers: { accept: 'text/event-stream' } }),
    )
  })
})
