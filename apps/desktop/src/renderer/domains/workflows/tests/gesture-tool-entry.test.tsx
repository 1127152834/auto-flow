import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => data.set(key, value),
    removeItem: (key: string) => data.delete(key),
  })
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
})

import { configureStudioConnection } from '../api/config'
import { ConfigPanel } from '../components/ConfigPanel'
import { useWorkflowStore as store } from '../editor-store'

type RequestRecord = { method: string; pathname: string; body?: Record<string, unknown> }
let requests: RequestRecord[]
let recordResponse: () => Response
let restoreConnection: () => void

beforeEach(() => {
  store.getState().clearWorkflow()
  requests = []
  recordResponse = () => Response.json({ success: true })
  restoreConnection = configureStudioConnection('http://gesture.test', async (input, init) => {
    const url = new URL(String(input))
    const method = init?.method ?? 'GET'
    requests.push({ method, pathname: url.pathname, body: init?.body ? JSON.parse(String(init.body)) : undefined })
    if (url.pathname === '/api/triggers/gesture/custom' && method === 'GET') {
      return Response.json({ success: true, gestures: [{ name: '挥手' }] })
    }
    if (url.pathname === '/api/triggers/gesture/status') {
      return Response.json({ success: true, status: { is_running: false, camera_index: 0 } })
    }
    if (url.pathname === '/api/triggers/gesture/record' && method === 'POST') return recordResponse()
    if (url.pathname === '/api/triggers/gesture/custom/%E6%8C%A5%E6%89%8B' && method === 'DELETE') {
      return Response.json({ success: true })
    }
    return new Response('not found', { status: 404 })
  })
})

afterEach(() => {
  cleanup()
  restoreConnection()
})

function renderGesture(data: Record<string, unknown> = {}) {
  store.getState().addNode('gesture_trigger', { x: 0, y: 0 }, { timeout: 60_000, ...data })
  const id = store.getState().nodes[0].id
  render(<ConfigPanel selectedNodeId={id} />)
  return id
}

it('TOOL.gesture-dialogs.record: InputDialog and AlertDialog confirm a service-backed recording before updating the document', async () => {
  const id = renderGesture({ gestureName: '' })
  await waitFor(() => expect(requests.map(request => request.pathname)).toEqual(expect.arrayContaining([
    '/api/triggers/gesture/custom',
    '/api/triggers/gesture/status',
  ])))
  fireEvent.click(screen.getByRole('button', { name: '📹 录制新手势' }))
  fireEvent.change(await screen.findByPlaceholderText('请输入手势名称'), { target: { value: ' 点赞 ' } })
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  expect(await screen.findByText('准备录制手势"点赞"')).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: '确定' }))

  await waitFor(() => expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe('点赞'))
  expect(requests.find(request => request.pathname.endsWith('/record'))).toEqual({
    method: 'POST',
    pathname: '/api/triggers/gesture/record',
    body: { gesture_name: '点赞', timeout: 30 },
  })
  expect(await screen.findByText('操作成功')).toBeDefined()

  act(() => store.getState().undo())
  expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe('')
  act(() => store.getState().redo())
  expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe('点赞')
})

it('TOOL.gesture-dialogs.delete: ConfirmDialog waits for deletion before clearing the configured gesture', async () => {
  const id = renderGesture({ gestureName: '挥手' })
  await waitFor(() => expect(requests.map(request => request.pathname)).toContain('/api/triggers/gesture/custom'))
  fireEvent.click(screen.getByRole('button', { name: '🗑️ 删除' }))
  expect(await screen.findByText('确认删除')).toBeDefined()
  fireEvent.click(screen.getByRole('button', { name: '删除' }))

  await waitFor(() => expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe(''))
  expect(requests).toContainEqual({ method: 'DELETE', pathname: '/api/triggers/gesture/custom/%E6%8C%A5%E6%89%8B', body: undefined })
  expect(await screen.findByText('删除成功')).toBeDefined()
  act(() => store.getState().undo())
  expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe('挥手')
})

it('TOOL.gesture-dialogs.error: service rejection is visible and leaves the draft unchanged', async () => {
  recordResponse = () => Response.json({ detail: '摄像头不可用' }, { status: 503 })
  const id = renderGesture({ gestureName: '' })
  await waitFor(() => expect(requests.map(request => request.pathname)).toContain('/api/triggers/gesture/custom'))
  fireEvent.click(screen.getByRole('button', { name: '📹 录制新手势' }))
  fireEvent.change(await screen.findByPlaceholderText('请输入手势名称'), { target: { value: '失败手势' } })
  fireEvent.click(screen.getByRole('button', { name: '确定' }))
  fireEvent.click(await screen.findByRole('button', { name: '确定' }))

  expect(await screen.findByText('操作失败')).toBeDefined()
  expect(screen.getByText(/摄像头不可用/)).toBeDefined()
  expect(store.getState().nodes.find(node => node.id === id)?.data.gestureName).toBe('')
})
