import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { parseAppLocation, projectHash, useGuardedHashNavigation } from './navigation'

beforeEach(() => { window.history.replaceState(null, '', '#/projects') })
afterEach(cleanup)

it('parses project context and rejects malformed or unsupported project addresses', () => {
  const id = '00000000-0000-0000-0000-000000000001'
  expect(parseAppLocation(projectHash({ projectId: id, tab: 'data' }))).toMatchObject({ section: 'projects', project: { projectId: id, tab: 'data' } })
  expect(parseAppLocation('#/projects')).toMatchObject({ section: 'projects', project: { tab: 'overview' } })
  expect(parseAppLocation(`#/projects/${id}/bogus`).error).toBeTruthy()
  expect(parseAppLocation('#/projects/not-an-id/overview').error).toBeTruthy()
  expect(parseAppLocation('#/profiles').section).toBe('profiles')
})

it('keeps the route and URL when a global navigation is declined', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  result.current.registerLeaveGuard(async () => false)
  await act(() => result.current.navigate('#/settings'))
  expect(result.current.hash).toBe('#/projects')
  expect(window.location.hash).toBe('#/projects')
})

it('guards back/forward and preserves the forward entry when back is cancelled', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  await act(() => result.current.navigate('#/models'))
  const guard = vi.fn(async () => false)
  result.current.registerLeaveGuard(guard)
  act(() => window.history.back())
  await waitFor(() => expect(guard).toHaveBeenCalledOnce())
  await waitFor(() => expect(window.location.hash).toBe('#/models'))
  expect(result.current.hash).toBe('#/models')
  guard.mockResolvedValue(true)
  act(() => window.history.back())
  await waitFor(() => expect(result.current.hash).toBe('#/projects'))
  act(() => window.history.forward())
  await waitFor(() => expect(result.current.hash).toBe('#/models'))
})

it('guards direct hash navigation and ignores additional requests during confirmation', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  let confirm!: (allowed: boolean) => void
  result.current.registerLeaveGuard(() => new Promise(resolve => { confirm = resolve }))
  act(() => { window.location.hash = '#/settings' })
  await waitFor(() => expect(confirm).toBeDefined())
  await act(() => result.current.navigate('#/profiles'))
  await act(async () => { confirm(false) })
  await waitFor(() => expect(window.location.hash).toBe('#/projects'))
  expect(result.current.hash).toBe('#/projects')
})

it('guards a new hash entry with null state after an indexed project visit', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  await act(() => result.current.navigate('#/projects/00000000-0000-0000-0000-000000000001/overview'))
  const guard = vi.fn(async () => false)
  result.current.registerLeaveGuard(guard)
  act(() => { window.location.hash = '#/settings' })
  await waitFor(() => expect(guard).toHaveBeenCalledOnce())
  expect(window.location.hash).toContain('/overview')
  guard.mockResolvedValue(true)
  await act(() => result.current.navigate('#/models'))
  expect(result.current.hash).toBe('#/models')
})

it('restores a Back event received while a global navigation confirmation is pending', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  const project = '#/projects/00000000-0000-0000-0000-000000000001/overview'
  await act(() => result.current.navigate(project))
  let confirm!: (allowed: boolean) => void
  result.current.registerLeaveGuard(() => new Promise(resolve => { confirm = resolve }))
  let navigation!: Promise<void>
  act(() => { navigation = result.current.navigate('#/settings') })
  act(() => window.history.back())
  await new Promise(resolve => setTimeout(resolve, 50))
  await act(async () => { confirm(false); await navigation })
  expect(result.current.hash).toBe(project)
  await waitFor(() => expect(window.location.hash).toBe(project))
})
