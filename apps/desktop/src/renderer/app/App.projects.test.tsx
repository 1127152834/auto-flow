import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import '@testing-library/jest-dom/vitest'
import type { ProjectPage, ProjectView } from '../domains/projects/types'
import { choiceTestEnvironment } from '../shared/testing/choice-user'
import type { StreamingApiClient } from '../shared/api/client'
import type { DesktopSession } from './useDesktopSession'
import { App } from './App'

const state = vi.hoisted(() => ({ session: null as DesktopSession | null, workspaceChanging: false }))
vi.mock('./useDesktopSession', () => ({ useDesktopSession: () => ({ ...state, status: 'connected', reconnect: vi.fn(), message: null }) }))
choiceTestEnvironment()
const project: ProjectView = {
  projectId: '00000000-0000-0000-0000-000000000001', name: '项目 A', description: '真实上下文',
  managementRevision: 1, lifecycleState: 'active', createdAt: '2026-09-13T00:00:00Z', updatedAt: '2026-09-13T00:00:00Z', lastOpenedAt: null,
  defaultResources: { profileId: null, proxy: { mode: 'sourceDefault' }, modelProviderId: null },
}
const availability = { automations: 'notImplemented', data: 'notImplemented', runs: 'notImplemented', environments: 'notImplemented', statistics: 'notImplemented', sync: 'notImplemented' } as const
const requests = vi.fn(async (path: string) => {
  if (path.includes('/tables?')) return { items: [], page: 1, pageSize: 50, total: 0, sort: '-updatedAt' }
  if (path.includes('/overview')) return { project, availability, counts: {}, activity: [], recent: [] }
  if (path === `/api/v1/projects/${project.projectId}`) return project
  if (path.startsWith('/api/v1/projects?')) return { items: [{ ...project, availability }], page: 1, pageSize: 50, total: 1, sort: '-lastOpenedAt' } satisfies ProjectPage
  if (path.endsWith('/open')) return { project }
  throw new Error(`Unexpected test request ${path}`)
})
function session(workspaceKey: string, instanceId: string): DesktopSession {
  return { workspaceKey, instanceId, apiVersion: 'v1', token: instanceId, baseUrl: 'http://127.0.0.1:1', client: { request: requests, health: vi.fn(), stream: vi.fn() } as StreamingApiClient }
}
beforeEach(() => {
  window.history.replaceState(null, '', '#/projects')
  sessionStorage.clear(); requests.mockClear()
  vi.stubGlobal('autoflow', {})
  state.session = session('workspace-a', 'instance-1'); state.workspaceChanging = false
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it('opens a real project context and the six approved tabs without fake controls', async () => {
  const user = userEvent.setup(); render(<App />)
  await user.click(await screen.findByText(project.name))
  await screen.findByRole('heading', { name: '项目资料' })
  expect(window.location.hash).toBe(`#/projects/${project.projectId}/overview`)
  for (const label of ['概览', '自动化', '运行记录', '统计', '数据', '环境']) expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '数据' }))
  expect(await screen.findByText('还没有数据表')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '新建数据表' })).toBeEnabled()
  expect(requests.mock.calls.some(([path]) => path.includes(`/projects/${project.projectId}/tables?`))).toBe(true)
  await user.click(screen.getByRole('button', { name: '返回项目目录' }))
  expect(await screen.findByRole('button', { name: '新建项目' })).toBeInTheDocument()
})

it('retains the dirty draft when global navigation and browser Back are cancelled', async () => {
  const user = userEvent.setup(); render(<App />)
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '保留草稿')
  // Hash entry models a desktop Back/Forward or an external deep link while a modal owns focus.
  act(() => { window.location.hash = '#/settings' })
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  expect(screen.getByLabelText('项目名称')).toHaveValue('保留草稿')
  await waitFor(() => expect(window.location.hash).toBe('#/projects'))
  fireEvent.click(screen.getByRole('button', { name: '设置', hidden: true }))
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  expect(screen.getByLabelText('项目名称')).toHaveValue('保留草稿')
  expect(window.location.hash).toBe('#/projects')
})

it('preserves a draft across service instances, blocks switching, and clears it in another workspace', async () => {
  const user = userEvent.setup(); const view = render(<App />)
  await user.click(await screen.findByRole('button', { name: '新建项目' }))
  await user.type(screen.getByLabelText('项目名称'), '保留草稿')
  state.session = session('workspace-a', 'instance-2'); view.rerender(<App />)
  expect(screen.getByLabelText('项目名称')).toHaveValue('保留草稿')
  state.workspaceChanging = true; view.rerender(<App />)
  expect(screen.getByRole('button', { name: '创建项目', hidden: true })).toBeDisabled()
  state.workspaceChanging = false; state.session = session('workspace-b', 'instance-3'); view.rerender(<App />)
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  expect(window.location.hash).toBe('#/projects')
  expect(sessionStorage.getItem('autoflow:projects-ui:workspace-a')).toBeNull()
})

it('shows an invalid project address with a working directory return', async () => {
  window.history.replaceState(null, '', '#/projects/not-a-project/data')
  const user = userEvent.setup(); render(<App />)
  expect(screen.getByText('项目地址无效，请从项目目录重新打开。')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: '返回项目目录' }))
  expect(await screen.findByRole('button', { name: '新建项目' })).toBeInTheDocument()
})


it('keeps the data route and draft when cancelling Back or global navigation', async () => {
  const user = userEvent.setup(); render(<App />)
  await user.click(await screen.findByText(project.name)); await screen.findByRole('heading', { name: '项目资料' })
  await user.click(screen.getByRole('button', { name: '数据' }))
  await user.click(await screen.findByRole('button', { name: '新建数据表' }))
  await user.type(screen.getByLabelText('数据表名称'), '数据草稿')
  act(() => { window.location.hash = '#/settings' })
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  await waitFor(() => expect(window.location.hash).toBe(`#/projects/${project.projectId}/data`))
  expect(screen.getByLabelText('数据表名称')).toHaveValue('数据草稿')
  fireEvent.click(screen.getByRole('button', { name: '设置', hidden: true }))
  await user.click(await screen.findByRole('button', { name: '继续编辑' }))
  expect(window.location.hash).toBe(`#/projects/${project.projectId}/data`)
  expect(screen.getByLabelText('数据表名称')).toHaveValue('数据草稿')
})
