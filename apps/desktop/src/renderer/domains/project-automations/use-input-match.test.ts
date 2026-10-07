import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { useInputMatch } from './use-input-match'

const plan = (alias: string) => ({ inputs: [{ inputId: 'i1', alias }] }) as never
const response = { inputs: [{ inputId: 'i1', alias: 'a', outcome: 'counted', matchedCount: 5, unprocessedCount: 2, sample: [] }] } as never
beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

it('debounces edits and sends only the latest draft', async () => {
  const fetcher = vi.fn().mockResolvedValue(response)
  const { result, rerender } = renderHook(({ value }) => useInputMatch({ fetcher, plan: value }), { initialProps: { value: plan('a') } })
  rerender({ value: plan('ab') }); rerender({ value: plan('abc') })
  await act(async () => { await vi.advanceTimersByTimeAsync(599) })
  expect(fetcher).not.toHaveBeenCalled()
  expect(result.current.status).toBe('loading')
  await act(async () => { await vi.advanceTimersByTimeAsync(1) })
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0][0]).toEqual(plan('abc'))
  expect(result.current.status).toBe('ready')
  expect(result.current.items.get('i1')?.matchedCount).toBe(5)
})

it('aborts the in-flight request and ignores its stale answer when the draft changes', async () => {
  const resolvers: ((value: unknown) => void)[] = [], signals: AbortSignal[] = []
  const fetcher = vi.fn((_plan: unknown, signal: AbortSignal) => { signals.push(signal); return new Promise(resolve => resolvers.push(resolve)) })
  const { result, rerender } = renderHook(({ value }) => useInputMatch({ fetcher: fetcher as never, plan: value }), { initialProps: { value: plan('a') } })
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  rerender({ value: plan('b') })
  expect(signals[0].aborted).toBe(true)
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  expect(fetcher).toHaveBeenCalledTimes(2)
  await act(async () => { resolvers[0]({ inputs: [{ ...(response as { inputs: object[] }).inputs[0], matchedCount: 99 }] }); resolvers[1](response) })
  expect(result.current.items.get('i1')?.matchedCount).toBe(5)
})

it('shows the failure reason, keeps the previous answer and retries on demand', async () => {
  const fetcher = vi.fn().mockResolvedValueOnce(response).mockRejectedValueOnce(new Error('服务暂不可用')).mockResolvedValue(response)
  const { result, rerender } = renderHook(({ value }) => useInputMatch({ fetcher, plan: value }), { initialProps: { value: plan('a') } })
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  rerender({ value: plan('b') })
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  expect(result.current.status).toBe('error')
  expect(result.current.error).toContain('服务暂不可用')
  expect(result.current.items.get('i1')?.matchedCount).toBe(5)
  act(() => result.current.retry())
  await act(async () => { await vi.advanceTimersByTimeAsync(0) })
  expect(result.current.status).toBe('ready')
  expect(result.current.error).toBeNull()
})

it('stays idle without a fetcher or without inputs', async () => {
  const fetcher = vi.fn()
  const none = renderHook(() => useInputMatch({ fetcher: undefined, plan: plan('a') }))
  const empty = renderHook(() => useInputMatch({ fetcher, plan: { inputs: [] } as never }))
  await act(async () => { await vi.advanceTimersByTimeAsync(2000) })
  expect(fetcher).not.toHaveBeenCalled()
  expect(none.result.current.status).toBe('idle'); expect(empty.result.current.status).toBe('idle')
})

it('marks a validation-class failure as quiet and keeps other failures loud', async () => {
  const fetcher = vi.fn().mockRejectedValueOnce(Object.assign(new Error('bad'), { code: 'VALIDATION_ERROR' })).mockRejectedValueOnce(new Error('超时'))
  const { result, rerender } = renderHook(({ value }) => useInputMatch({ fetcher, plan: value }), { initialProps: { value: plan('a') } })
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  expect(result.current.status).toBe('error'); expect(result.current.quiet).toBe(true)
  rerender({ value: plan('b') })
  await act(async () => { await vi.advanceTimersByTimeAsync(600) })
  expect(result.current.quiet).toBe(false); expect(result.current.error).toBe('超时')
})
