import { act, cleanup, render, renderHook, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ApplicationHeader } from './ApplicationHeader'
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
  expect(parseAppLocation('#/lab').section).toBe('lab')
})

it('exposes the lab as a global navigation tab', () => {
  const onNavigate = vi.fn()
  render(<ApplicationHeader route="dashboard" onNavigate={onNavigate} status="connected" />)
  screen.getByRole('button', { name: '实验室' }).click()
  expect(onNavigate).toHaveBeenCalledWith('lab')
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

it('round trips all five real data table tabs and rejects malformed nested addresses', () => {
  const projectId = '00000000-0000-4000-8000-000000000001', tableId = '00000000-0000-4000-8000-000000000002'
  for (const dataTab of ['records', 'fields', 'statuses', 'source', 'settings'] as const) {
    const route = { projectId, tab: 'data' as const, tableId, dataTab }
    const hash = `#/projects/${projectId}/data/${tableId}/${dataTab}`
    expect(projectHash(route)).toBe(hash)
    expect(parseAppLocation(hash)).toEqual({ section: 'projects', project: route })
  }
  for (const hash of [`#/projects/${projectId}/data/no-id/records`, `#/projects/${projectId}/data/${tableId}/bogus`, `#/projects/${projectId}/runs/${tableId}/records`, `#/projects/${projectId}/data/${tableId}`]) expect(parseAppLocation(hash).error).toBeTruthy()
})

it('round trips create, detail, and edit record routes with typed identities', () => {
  const projectId='00000000-0000-4000-8000-000000000001',tableId='00000000-0000-4000-8000-000000000002',datasetGeneration='00000000-0000-4000-8000-000000000003'
  const routes = [
    { projectId, tab:'data' as const, tableId, dataTab:'records' as const, record:{mode:'create' as const} },
    { projectId, tab:'data' as const, tableId, dataTab:'records' as const, record:{mode:'detail' as const,datasetGeneration,recordKey:{type:'text' as const,value:'中文/📄?new/edit'}} },
    { projectId, tab:'data' as const, tableId, dataTab:'records' as const, record:{mode:'edit' as const,datasetGeneration,recordKey:{type:'integer' as const,value:'-1'}} },
  ]
  for (const route of routes) expect(parseAppLocation(projectHash(route))).toEqual({section:'projects',project:route})
  const other={...routes[1],projectId:'00000000-0000-4000-8000-000000000009'}
  expect(parseAppLocation(projectHash(other)).project).toEqual(other)
})

it.each([
  '#/projects/00000000-0000-4000-8000-000000000001/data/00000000-0000-4000-8000-000000000002/records/not-a-generation/text/MQ',
  '#/projects/00000000-0000-4000-8000-000000000001/data/00000000-0000-4000-8000-000000000002/records/00000000-0000-4000-8000-000000000003/integer/MDAx',
  '#/projects/00000000-0000-4000-8000-000000000001/data/00000000-0000-4000-8000-000000000002/records/00000000-0000-4000-8000-000000000003/text/MQ==',
  '#/projects/00000000-0000-4000-8000-000000000001/data/00000000-0000-4000-8000-000000000002/records/new/edit',
])('rejects malformed record address %s', hash => {
  expect(parseAppLocation(hash).error).toBeTruthy()
})
it('round-trips automation directory, creation and canonical detail identities', () => {
  const projectId = '11111111-1111-4111-8111-111111111111'
  const automationId = '22222222-2222-4222-8222-222222222222'
  for (const route of [
    { projectId, tab: 'automations' as const },
    { projectId, tab: 'automations' as const, automationCreate: true },
    { projectId, tab: 'automations' as const, automationId },
  ]) expect(parseAppLocation(projectHash(route))).toEqual({ section: 'projects', project: route })
  expect(parseAppLocation(`#/projects/${projectId}/automations/not-an-id`).error).toBeTruthy()
})

it('preserves the mounted project guard after replacing a newly created resource URL', async () => {
  const { result } = renderHook(() => useGuardedHashNavigation())
  const guard = vi.fn(async () => false)
  result.current.registerLeaveGuard(guard)
  act(() => result.current.replace('#/projects/p/automations/a', { preserveGuard: true }))
  await act(() => result.current.navigate('#/projects/p/automations'))
  expect(guard).toHaveBeenCalledOnce()
  expect(window.location.hash).toBe('#/projects/p/automations/a')
  // Forced workspace replacement must still discard the previous workspace guard.
  act(() => result.current.replace('#/projects'))
  await act(() => result.current.navigate('#/settings'))
  expect(guard).toHaveBeenCalledOnce()
  expect(window.location.hash).toBe('#/settings')
})

it('round trips run directories, batches and task evidence without losing scoped identities', () => {
  const projectId = '00000000-0000-4000-8000-000000000001', id = '00000000-0000-4000-8000-000000000002'
  const routes = [
    { projectId, tab: 'runs' as const, runView: 'tasks' as const },
    { projectId, tab: 'runs' as const, runView: 'batches' as const, batchId: id },
    { projectId, tab: 'runs' as const, runView: 'manual' as const },
    { projectId, tab: 'runs' as const, runView: 'manual' as const, manualItemId: id },
    ...(['logs', 'io', 'evidence'] as const).map(taskTab => ({ projectId, tab: 'runs' as const, taskId: id, taskTab })),
  ]
  for (const route of routes) expect(parseAppLocation(projectHash(route)).project).toEqual(route)
  for (const suffix of ['batches/invalid', `tasks/${id}/other`, `tasks/${id}/logs/extra`, `manual/${id}/extra`, 'manual/invalid']) expect(parseAppLocation(`#/projects/${projectId}/runs/${suffix}`).error).toBeTruthy()
  expect(projectHash({ projectId, tab: 'runs', manualItemId: id })).toBe(`#/projects/${projectId}/runs/manual/${id}`)
  expect(() => projectHash({ projectId, tab: 'runs', taskId: id, manualItemId: id })).toThrow()
  expect(() => projectHash({ projectId, tab: 'runs', runView: 'manual', manualItemId: 'not-an-id' })).toThrow()
})

it('keeps the frozen statistics drill-down as its own runs page', () => {
  const projectId = '00000000-0000-4000-8000-000000000001'
  const routes = [
    { projectId, tab: 'runs' as const, runFrozen: { resultSetId: 'rs-1', result: 'failed' as const } },
    { projectId, tab: 'runs' as const, runFrozen: { resultSetId: 'rs-1', result: 'failed' as const, intervalStart: '2026-09-18T16:00:00.000Z' } },
    { projectId, tab: 'runs' as const, runFrozen: { resultSetId: 'rs-1', result: 'timed_out' as const, intervalStart: '2026-09-18T16:00:00.000Z', automationId: '00000000-0000-4000-8000-000000000003' } },
  ]
  for (const route of routes) expect(parseAppLocation(projectHash(route))).toEqual({ section: 'projects', project: route })
  expect(() => projectHash({ projectId, tab: 'runs', runFrozen: { resultSetId: 'rs-1', result: 'failed' }, taskId: projectId })).toThrow()
  expect(() => projectHash({ projectId, tab: 'statistics', runFrozen: { resultSetId: 'rs-1', result: 'failed' } })).toThrow()
  // 真实冻结结果集是服务端签名令牌（约 500 字符），不能按短标识校验。
  const signed = "eyJhdXRvbWF0aW9uSWQiOm51bGwsImNhbGN1bGF0ZWRBdCI6IjIwMjYtMDktMTlUMDM6MzA6MDArMDA6MDAiLCJmcm9tIjoiMjAyNi0wOS0xMlQwMDowMDowMCswMDowMCIsImludGVydmFsIjoiZGF5IiwicHJvamVjdElkIjoiMDAwMDAwMDAtMDAwMC00MDAwLTgwMDAtMDAwMDAwMDAwMDAxIiwidGFibGVJZCI6bnVsbCwidGltZXpvbmUiOiJBc2lhL1NoYW5naGFpIiwidG8iOiIyMDI2LTA5LTE5VDAzOjMwOjAwKzAwOjAwIn0.c777fd12d025667e"
  const signedRoute = { projectId, tab: 'runs' as const, runFrozen: { resultSetId: signed, result: 'failed' as const, intervalStart: '2026-09-18T16:00:00.000Z' } }
  expect(parseAppLocation(projectHash(signedRoute))).toEqual({ section: 'projects', project: signedRoute })
})
