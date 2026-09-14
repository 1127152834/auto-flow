import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import type { DesktopRuntimeContext } from '../../shared/runtime'
import { useDesktopSession } from './useDesktopSession'
import { useStudioIntegration } from '../domains/workflows/hooks/useStudioIntegration'
import { useWorkflowStore as store } from '../domains/workflows/editor-store'
import { configureStudioConnection } from '../domains/workflows/api/config'
import { configureMock, mockRequest, mockSnapshot } from '../domains/workflows/api/mock-server'
import { getDocumentLeaveResources } from '../domains/workflows/lib/documentLeave'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
let restore: (() => void) | undefined
afterEach(() => { cleanup(); restore?.(); store.getState().clearWorkflow(); vi.unstubAllGlobals() })

it('explicit host restart connects the replacement runtime while the mounted Studio draft survives without start replay', async () => {
  let instanceId = 'before-restart'
  const runtime = (): DesktopRuntimeContext => ({ workspaceKey: '/workspace-a', sidecar: { state: 'ready', apiVersion: 'v1', port: 43127, baseUrl: 'http://127.0.0.1:43127', token: instanceId, instanceId }, preferences: { zoom: 100, motion: 'system' }, operation: 'idle' })
  const restartSidecar = vi.fn(async () => { instanceId = 'after-restart'; return runtime().sidecar })
  vi.stubGlobal('autoflow', { getRuntimeContext: vi.fn(async () => runtime()), onRuntimeContextChanged: vi.fn(() => vi.fn()), restartSidecar })
  const healthTokens: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    expect(new URL(String(input)).pathname).toBe('/health')
    healthTokens.push(new Headers(init?.headers).get('x-autoflow-token')!)
    return Response.json({ status: 'ok', apiVersion: 'v1', instanceId })
  }))
  configureMock({ offline: false, disconnect: false })
  const requests: string[] = []
  restore = configureStudioConnection('http://autoflow-studio.mock', async (input, init) => {
    requests.push(new URL(input instanceof Request ? input.url : String(input)).pathname)
    return mockRequest(input, init)
  })
  store.getState().clearWorkflow()
  store.getState().addNode('js_script', { x: 40, y: 80 })
  store.getState().addVariable({ name: 'draft', type: 'string', value: 'keep after restart', scope: 'global' })
  const draft = { id: store.getState().id, nodes: store.getState().nodes, edges: store.getState().edges, variables: store.getState().variables }
  // Production keeps the main runtime and the standalone Mock Studio transport separate.
  // Mount both real hooks without inventing a sidecar-to-Studio transport adapter.
  const view = renderHook(() => { useStudioIntegration(); return useDesktopSession() })
  await waitFor(() => expect(view.result.current.status).toBe('connected'))
  await waitFor(() => expect(requests).toContain('/api/browser/status'))
  expect(getDocumentLeaveResources()).toHaveLength(0)
  const previousClient = view.result.current.session!.client
  await act(async () => { await view.result.current.reconnect(true) })
  expect(restartSidecar).toHaveBeenCalledOnce()
  expect(view.result.current.status).toBe('connected')
  expect(view.result.current.session).toMatchObject({ workspaceKey: '/workspace-a', instanceId: 'after-restart', token: 'after-restart' })
  expect(view.result.current.session!.client).not.toBe(previousClient)
  expect(healthTokens).toEqual(['before-restart', 'after-restart'])
  expect(store.getState()).toMatchObject({ ...draft, hasUnsavedChanges: true })
  expect(store.getState().nodes).toBe(draft.nodes)
  expect(store.getState().variables).toBe(draft.variables)
  expect(getDocumentLeaveResources()).toHaveLength(0)
  expect(mockSnapshot()).toMatchObject({ browser: false, picking: false, recording: false })
  expect(requests.filter(path => path === '/api/executor/execute' || /\/workflows\/[^/]+\/(run|execute|start)$|\/browser\/open$|\/element-picker\/start$|\/recorder\/start$/.test(path))).toEqual([])
})
