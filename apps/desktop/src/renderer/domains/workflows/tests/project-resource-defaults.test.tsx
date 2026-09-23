import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const storage = vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  return { data }
})

import type { components } from '../../../shared/api/generated'
import { browserApi } from '../api'
import { configureStudioConnection } from '../api/config'
import type { StudioTransport } from '../api/transport'
import { AutoBrowserDialog } from '../components/AutoBrowserDialog'
import { BrowserProfileSelect } from '../components/BrowserProfileSelect'
import { TaskCreateDialog } from '../components/scheduled-tasks/TaskCreateDialog'
import { useGlobalConfigStore } from '../hooks/stores/globalConfigStore'

Element.prototype.scrollIntoView = vi.fn()
Element.prototype.hasPointerCapture = vi.fn(() => false)
Element.prototype.setPointerCapture = vi.fn()
Element.prototype.releasePointerCapture = vi.fn()

type Profile = components['schemas']['ProfileRead']

const profiles = [
  { id: '10000000-0000-4000-8000-000000000001', name: '全局列表第一项' },
  { id: '20000000-0000-4000-8000-000000000002', name: '项目 A 默认配置' },
  { id: '30000000-0000-4000-8000-000000000003', name: '项目 B 默认配置' },
] as Profile[]

const project = (projectId: string, profileId: string | null) => ({
  projectId,
  name: projectId,
  description: '',
  managementRevision: 1,
  lifecycleState: 'active',
  defaultResources: {
    profileId,
    proxy: { mode: 'none' },
    modelProviderId: null,
  },
  createdAt: '2026-09-23T00:00:00Z',
  updatedAt: '2026-09-23T00:00:00Z',
  lastOpenedAt: null,
  availability: {},
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(done => { resolve = done })
  return { promise, resolve }
}

function responseFor(
  projectDefaults: Record<string, string | null>,
  calls: string[],
): StudioTransport {
  return async input => {
    const url = new URL(String(input))
    calls.push(url.pathname)
    if (url.pathname === '/api/v1/profiles') {
      return Response.json({ items: profiles, total: profiles.length })
    }
    const match = url.pathname.match(/^\/api\/v1\/projects\/([^/]+)$/)
    if (match) {
      const projectId = decodeURIComponent(match[1])
      return Response.json(project(projectId, projectDefaults[projectId] ?? null))
    }
    return Response.json({ code: 'NOT_FOUND', message: 'unexpected request' }, { status: 404 })
  }
}

let restoreConnection: (() => void) | undefined

beforeEach(() => {
  window.history.replaceState({}, '', '/studio.html')
  useGlobalConfigStore.setState(state => ({
    config: { ...state.config, browserProfileId: '' },
    projectResources: { scope: null },
  }))
  storage.data.clear()
})

afterEach(() => {
  cleanup()
  restoreConnection?.()
  restoreConnection = undefined
  window.history.replaceState({}, '', '/studio.html')
  useGlobalConfigStore.setState(state => ({
    config: { ...state.config, browserProfileId: '' },
    projectResources: { scope: null },
  }))
  storage.data.clear()
})

describe('Studio project browser resource defaults', () => {
  it('selects the project default Profile instead of the first global Profile', async () => {
    const calls: string[] = []
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': profiles[1].id }, calls),
    )

    render(<BrowserProfileSelect />)

    await waitFor(() => {
      expect(screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' }).value).toBe(profiles[1].id)
    })
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[1].id },
    })
    expect(calls).toContain('/api/v1/projects/project-a')
  })

  it('keeps an explicit project-session override across a Profile refresh', async () => {
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': profiles[1].id }, []),
    )
    render(<BrowserProfileSelect />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[1].id))

    fireEvent.change(select, { target: { value: profiles[0].id } })
    expect(select.value).toBe(profiles[0].id)
    fireEvent.click(screen.getByRole('button', { name: '刷新配置' }))

    await waitFor(() => expect(select.value).toBe(profiles[0].id))
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[0].id },
    })
  })

  it('does not silently select the first global Profile when the project has no default', async () => {
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': null }, []),
    )

    render(<BrowserProfileSelect />)

    await screen.findByRole('option', { name: '全局列表第一项' })
    expect(screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' }).value).toBe('')
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: false,
      httpStatus: 422,
    })
  })

  it('keeps a deleted project default unavailable instead of falling back to the first Profile', async () => {
    const deletedProfileId = '40000000-0000-4000-8000-000000000004'
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': deletedProfileId }, []),
    )

    render(<BrowserProfileSelect />)

    expect((await screen.findByRole<HTMLOptionElement>('option', { name: '所选配置已不可用，请重新选择' })).value).toBe(deletedProfileId)
    expect(screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' }).value).toBe(deletedProfileId)
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: false,
      httpStatus: 404,
    })
  })

  it('does not start a browser when the project default resource request fails', async () => {
    const calls: string[] = []
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      async input => {
        const pathname = new URL(String(input)).pathname
        calls.push(pathname)
        if (pathname === '/api/v1/profiles') return Response.json({ items: profiles, total: profiles.length })
        if (pathname === '/api/v1/projects/project-a') {
          return Response.json({ code: 'PROJECT_UNAVAILABLE', message: '项目默认资源暂不可用' }, { status: 503 })
        }
        return Response.json({ code: 'NOT_FOUND', message: 'unexpected request' }, { status: 404 })
      },
    )

    render(<BrowserProfileSelect />)

    expect((await screen.findByRole('alert')).textContent).toContain('项目默认资源暂不可用')
    expect(screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' }).value).toBe('')
    await expect(browserApi.open('about:blank')).resolves.toMatchObject({
      success: false,
      httpStatus: 503,
    })
    expect(calls).not.toContain('/api/browser/open')
  })

  it('keeps an explicit project override out of global persisted configuration', async () => {
    useGlobalConfigStore.setState(state => ({
      config: { ...state.config, browserProfileId: profiles[2].id },
    }))
    const persistedBefore = storage.data.get('autoflow-studio-mock-global-config')
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': profiles[1].id }, []),
    )
    render(<BrowserProfileSelect />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[1].id))

    fireEvent.change(select, { target: { value: profiles[0].id } })

    expect(useGlobalConfigStore.getState().projectResources.profileId).toBe(profiles[0].id)
    expect(useGlobalConfigStore.getState().config.browserProfileId).toBe(profiles[2].id)
    expect(storage.data.get('autoflow-studio-mock-global-config')).toBe(persistedBefore)
  })

  it('keeps an explicit override across a transport reconnect in the same workspace and project', async () => {
    const projectUrl = '/studio.html?workspaceKey=workspace-a&projectId=project-a'
    window.history.replaceState({}, '', projectUrl)
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': profiles[1].id }, []),
    )
    render(<BrowserProfileSelect />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[1].id))
    fireEvent.change(select, { target: { value: profiles[0].id } })
    expect(select.value).toBe(profiles[0].id)

    restoreConnection()
    restoreConnection = configureStudioConnection(
      'http://project-resource-reconnected.test',
      responseFor({ 'project-a': profiles[1].id }, []),
    )

    await waitFor(() => expect(select.value).toBe(profiles[0].id))
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[0].id },
    })
  })

  it('preserves a saved scheduled-task Profile across project defaults and transport reconnects', async () => {
    const onChange = vi.fn()
    window.history.replaceState({}, '', '/studio.html?workspaceKey=workspace-a&projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({ 'project-a': profiles[1].id }, []),
    )
    render(<BrowserProfileSelect label="计划任务浏览器配置" value={profiles[2].id} onChange={onChange} />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '计划任务浏览器配置' })
    await screen.findByRole('option', { name: profiles[1].name })
    expect(select.value).toBe(profiles[2].id)
    expect(onChange).not.toHaveBeenCalled()

    restoreConnection()
    restoreConnection = configureStudioConnection(
      'http://project-resource-reconnected.test',
      responseFor({ 'project-a': profiles[0].id }, []),
    )

    await waitFor(() => expect(select.value).toBe(profiles[2].id))
    expect(onChange).not.toHaveBeenCalled()
  })

  it('creates a scheduled task from the project default and submits an explicit Profile override', async () => {
    const submitted: Array<Record<string, unknown>> = []
    useGlobalConfigStore.setState(state => ({
      config: { ...state.config, browserProfileId: profiles[2].id },
    }))
    window.history.replaceState({}, '', '/studio.html?workspaceKey=workspace-a&projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      async (input, init) => {
        const pathname = new URL(String(input)).pathname
        if (pathname === '/api/v1/profiles') return Response.json({ items: profiles, total: profiles.length })
        if (pathname === '/api/v1/projects/project-a') return Response.json(project('project-a', profiles[1].id))
        if (pathname === '/api/local-workflows/default-folder') return Response.json({ folder: '/tmp/workflows' })
        if (pathname === '/api/local-workflows/list') {
          return Response.json({ workflows: [{ filename: 'project-flow.json', name: '项目流程', size: 100, modifiedTime: '' }] })
        }
        if (pathname === '/api/local-workflows/self-heal/project-flow.json') {
          return Response.json({ success: true, enabled: false })
        }
        if (pathname === '/api/scheduled-tasks' && init?.method === 'POST') {
          const body = JSON.parse(String(init.body || '{}')) as Record<string, unknown>
          submitted.push(body)
          return Response.json({
            ...body,
            id: 'scheduled-project-profile',
            total_executions: 0,
            success_executions: 0,
            failed_executions: 0,
            created_at: '2026-09-23T00:00:00Z',
            updated_at: '2026-09-23T00:00:00Z',
          })
        }
        return Response.json({ code: 'NOT_FOUND', message: `unexpected request: ${pathname}` }, { status: 404 })
      },
    )
    const onClose = vi.fn()
    render(<TaskCreateDialog open onClose={onClose} />)
    const profileSelect = screen.getByRole<HTMLSelectElement>('combobox', { name: '运行浏览器配置 *' })

    await waitFor(() => expect(profileSelect.value).toBe(profiles[1].id))
    expect(profileSelect.value).not.toBe(profiles[2].id)
    fireEvent.change(profileSelect, { target: { value: profiles[0].id } })
    fireEvent.change(screen.getByLabelText('任务名称 *'), { target: { value: '项目计划任务' } })

    const workflowSelect = screen.getAllByRole('combobox').find(control => control.tagName === 'BUTTON')
    expect(workflowSelect).toBeDefined()
    fireEvent.keyDown(workflowSelect!, { key: 'ArrowDown' })
    fireEvent.click(await screen.findByRole('option', { name: '项目流程' }))
    fireEvent.click(screen.getByRole('button', { name: '创建任务' }))

    await waitFor(() => expect(submitted).toHaveLength(1))
    expect(submitted[0]).toMatchObject({
      name: '项目计划任务',
      workflow_id: 'project-flow.json',
      profile_id: profiles[0].id,
    })
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('opens the interactive browser with the project override selected in its own UI', async () => {
    const openBodies: Array<Record<string, unknown>> = []
    let browserOpen = false
    useGlobalConfigStore.setState(state => ({
      config: { ...state.config, browserProfileId: profiles[2].id },
    }))
    window.history.replaceState({}, '', '/studio.html?workspaceKey=workspace-a&projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      async (input, init) => {
        const pathname = new URL(String(input)).pathname
        if (pathname === '/api/v1/profiles') return Response.json({ items: profiles, total: profiles.length })
        if (pathname === '/api/v1/projects/project-a') return Response.json(project('project-a', profiles[1].id))
        if (pathname === '/api/browser/status') {
          return Response.json({ isOpen: browserOpen, pickerActive: false, ...(browserOpen ? { sessionId: 'browser-project' } : {}) })
        }
        if (pathname === '/api/browser/open') {
          openBodies.push(JSON.parse(String(init?.body || '{}')) as Record<string, unknown>)
          browserOpen = true
          return Response.json({ success: true })
        }
        return Response.json({ code: 'NOT_FOUND', message: 'unexpected request' }, { status: 404 })
      },
    )
    render(<AutoBrowserDialog isOpen onClose={vi.fn()} onLog={vi.fn()} />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[1].id))
    fireEvent.change(select, { target: { value: profiles[0].id } })

    fireEvent.click(screen.getByRole('button', { name: '打开浏览器' }))

    await waitFor(() => expect(openBodies).toHaveLength(1))
    expect(openBodies[0]).toMatchObject({ profileId: profiles[0].id })
  })

  it('clears the old project override and resolves the new project default', async () => {
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({
        'project-a': profiles[1].id,
        'project-b': profiles[2].id,
      }, []),
    )
    render(<BrowserProfileSelect />)
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[1].id))
    fireEvent.change(select, { target: { value: profiles[0].id } })
    expect(select.value).toBe(profiles[0].id)

    window.history.replaceState({}, '', '/studio.html?projectId=project-b')
    act(() => window.dispatchEvent(new Event('studio:transport-changed')))

    await waitFor(() => expect(select.value).toBe(profiles[2].id))
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[2].id },
    })
  })

  it('ignores a late project-A default after project B has become current', async () => {
    const projectA = deferred<Response>()
    window.history.replaceState({}, '', '/studio.html?projectId=project-a')
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      async input => {
        const pathname = new URL(String(input)).pathname
        if (pathname === '/api/v1/profiles') {
          return Response.json({ items: profiles, total: profiles.length })
        }
        if (pathname === '/api/v1/projects/project-a') return projectA.promise
        if (pathname === '/api/v1/projects/project-b') {
          return Response.json(project('project-b', profiles[2].id))
        }
        return Response.json({ code: 'NOT_FOUND' }, { status: 404 })
      },
    )
    render(<BrowserProfileSelect />)

    window.history.replaceState({}, '', '/studio.html?projectId=project-b')
    act(() => window.dispatchEvent(new Event('studio:transport-changed')))
    const select = screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' })
    await waitFor(() => expect(select.value).toBe(profiles[2].id))

    await act(async () => {
      projectA.resolve(Response.json(project('project-a', profiles[1].id)))
      await projectA.promise
    })
    expect(select.value).toBe(profiles[2].id)
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[2].id },
    })
  })

  it('keeps the existing first-Profile fallback outside a project Studio', async () => {
    const calls: string[] = []
    restoreConnection = configureStudioConnection(
      'http://project-resource.test',
      responseFor({}, calls),
    )

    render(<BrowserProfileSelect />)

    await waitFor(() => {
      expect(screen.getByRole<HTMLSelectElement>('combobox', { name: '浏览器配置' }).value).toBe(profiles[0].id)
    })
    await expect(browserApi.resolveProfile()).resolves.toMatchObject({
      success: true,
      data: { id: profiles[0].id },
    })
    expect(calls.some(path => path.startsWith('/api/v1/projects/'))).toBe(false)
  })
})
