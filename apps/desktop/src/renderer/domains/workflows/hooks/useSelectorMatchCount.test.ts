import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { elementPickerApi } from '../api'
import { useSelectorMatchCount } from './useSelectorMatchCount'

const ok = (count: number) => ({ success: true, data: { success: true, matched: count > 0, count } }) as never
let spy: ReturnType<typeof vi.spyOn>
beforeEach(() => { vi.useFakeTimers(); spy = vi.spyOn(elementPickerApi, 'testSelector') })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks() })
const flush = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms) })

describe('useSelectorMatchCount', () => {
  it('防抖 500ms 后以 highlight=false 请求一次并给出匹配数', async () => {
    spy.mockResolvedValue(ok(3))
    const hints = { tag: 'a' }
    const { result, rerender } = renderHook(({ s }) => useSelectorMatchCount(s, hints, true), { initialProps: { s: '#a' } })
    expect(result.current.status).toBe('checking')
    await flush(300)
    rerender({ s: '#ab' })
    await flush(499)
    expect(spy).not.toHaveBeenCalled()
    await flush(1)
    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy).toHaveBeenCalledWith('#ab', hints, false)
    expect(result.current).toEqual({ status: 'ok', count: 3 })
  })

  it('单飞：旧请求晚到的结果被丢弃', async () => {
    const releases: Array<(v: never) => void> = []
    spy.mockImplementation(() => new Promise(r => { releases.push(r as never) }) as never)
    const { result, rerender } = renderHook(({ s }) => useSelectorMatchCount(s, undefined, true), { initialProps: { s: '#a' } })
    await flush(500)
    rerender({ s: '#b' })
    await flush(500)
    expect(releases).toHaveLength(2)
    await act(async () => releases[1](ok(2)))
    await act(async () => releases[0](ok(99)))
    expect(result.current).toEqual({ status: 'ok', count: 2 })
  })

  it('enabled=false 时 disabled 且不请求，恢复后重新检查', async () => {
    spy.mockResolvedValue(ok(1))
    const { result, rerender } = renderHook(({ e }) => useSelectorMatchCount('#a', undefined, e), { initialProps: { e: false } })
    await flush(1000)
    expect(result.current.status).toBe('disabled')
    expect(spy).not.toHaveBeenCalled()
    rerender({ e: true })
    await flush(500)
    expect(result.current).toEqual({ status: 'ok', count: 1 })
  })

  it('选择器为空时 idle 且不请求', async () => {
    const { result } = renderHook(() => useSelectorMatchCount('  ', undefined, true))
    await flush(1000)
    expect(result.current.status).toBe('idle')
    expect(spy).not.toHaveBeenCalled()
  })

  it('浏览器未打开返回 noBrowser，其他失败返回 error 与原因', async () => {
    spy.mockResolvedValueOnce({ success: false, error: '浏览器未打开，请先打开页面' } as never)
    const { result, rerender } = renderHook(({ s }) => useSelectorMatchCount(s, undefined, true), { initialProps: { s: '#a' } })
    await flush(500)
    expect(result.current.status).toBe('noBrowser')
    spy.mockResolvedValueOnce({ success: false, error: '选择器语法错误' } as never)
    rerender({ s: '#b' })
    await flush(500)
    expect(result.current).toEqual({ status: 'error', error: '选择器语法错误' })
  })

  it('同样的 hints 内容不会因对象引用变化重复请求', async () => {
    spy.mockResolvedValue(ok(1))
    const { rerender } = renderHook(() => useSelectorMatchCount('#a', { tag: 'a' }, true))
    await flush(500)
    rerender()
    await flush(1000)
    expect(spy).toHaveBeenCalledTimes(1)
  })
})
