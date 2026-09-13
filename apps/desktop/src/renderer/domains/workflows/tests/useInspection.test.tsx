import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { useInspection } from '../hooks/useInspection'
import type { InspectionApi, InspectionSession } from '../inspection-api'

const ready: InspectionSession = { sessionId: 'session', profileId: 'profile', profileName: 'profile', state: 'ready', headless: false, pages: [], targetPageId: null, pick: null, error: null }
const api = (): InspectionApi => ({ current: vi.fn().mockResolvedValue(null), start: vi.fn(), close: vi.fn(), page: vi.fn(), pick: vi.fn(), getPick: vi.fn(), cancel: vi.fn(), test: vi.fn() })
afterEach(cleanup)

it('keeps an uncertain launch ID and blocks leaving until the original request is resolved', async () => {
  const server = api(), view = renderHook(() => useInspection(server, true))
  await waitFor(() => expect(server.current).toHaveBeenCalled())
  vi.mocked(server.start).mockRejectedValueOnce(new TypeError('response lost'))
  await act(async () => { expect(await view.result.current.start('profile')).toBe(false) })
  const id = vi.mocked(server.start).mock.calls[0][0]
  await act(async () => { expect(await view.result.current.verifyActive()).toBeNull() })
  vi.mocked(server.start).mockResolvedValue({ ...ready, sessionId: id })
  await act(async () => { expect(await view.result.current.start('profile')).toBe(true) })
  expect(vi.mocked(server.start).mock.calls.map(call => call[0])).toEqual([id, id])
})
it('keeps the same browser session while offline and on connection recovery', async () => {
  const server = api(); vi.mocked(server.current).mockResolvedValue(ready)
  const view = renderHook(({ connected }) => useInspection(server, connected), { initialProps: { connected: true } })
  await waitFor(() => expect(view.result.current.session?.sessionId).toBe('session'))
  view.rerender({ connected: false })
  await act(async () => { expect(await view.result.current.verifyActive()).toBeNull() })
  expect(view.result.current.session?.sessionId).toBe('session')
  view.rerender({ connected: true })
  await act(async () => { expect(await view.result.current.verifyActive()).toBe(true) })
  expect(server.start).not.toHaveBeenCalled()
})
it('retains active status when cleanup fails and retries the same session', async () => {
  const server = api(); vi.mocked(server.current).mockResolvedValue(ready)
  vi.mocked(server.close).mockRejectedValueOnce(new Error('清理失败')).mockResolvedValueOnce({ ...ready, state: 'closed' })
  const view = renderHook(() => useInspection(server, true))
  await waitFor(() => expect(view.result.current.active).toBe(true))
  await act(async () => { expect(await view.result.current.close()).toBe(false) })
  expect(view.result.current.active).toBe(true)
  await act(async () => { expect(await view.result.current.close()).toBe(true) })
  expect(vi.mocked(server.close).mock.calls).toEqual([['session'], ['session']])
})
