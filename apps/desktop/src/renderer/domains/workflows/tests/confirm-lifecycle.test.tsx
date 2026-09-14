import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'
import { useConfirm } from '../components/controls/confirm-dialog'
afterEach(cleanup)
it.each(['confirm','alert'] as const)('%s resolves false when its owner unmounts', async mode => {
  const { result, unmount } = renderHook(() => useConfirm())
  let settled: boolean | undefined
  act(() => { void result.current[mode]('测试').then(value => { settled = value }) })
  unmount()
  await Promise.resolve()
  expect(settled).toBe(false)
})
it('replacing an open decision cancels the first pending request', async () => {
  const { result, unmount } = renderHook(() => useConfirm())
  let first: boolean | undefined
  let second: boolean | undefined
  act(() => { void result.current.confirm('第一条').then(value => { first = value }) })
  act(() => { void result.current.alert('第二条').then(value => { second = value }) })
  await Promise.resolve()
  expect(first).toBe(false)
  expect(second).toBeUndefined()
  unmount()
  await Promise.resolve()
  expect(second).toBe(false)
})
it('a late caller after unmount receives cancellation without a new dialog', async () => {
  const { result, unmount } = renderHook(() => useConfirm())
  const confirm = result.current.confirm
  unmount()
  let settled: boolean | undefined
  void confirm('过期请求').then(value => { settled = value })
  await Promise.resolve()
  expect(settled).toBe(false)
})
