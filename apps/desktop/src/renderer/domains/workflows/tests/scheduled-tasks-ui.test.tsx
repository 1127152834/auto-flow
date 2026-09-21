import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
vi.hoisted(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('localStorage', { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
})
import { ScheduledTasksDialog } from '../components/scheduled-tasks/ScheduledTasksDialog'
import { useScheduledTaskStore } from '../hooks/stores/scheduledTaskStore'
import { mockRequest, configureMock } from '../api/mock-server'
beforeEach(() => { configureMock({ offline: false }); localStorage.removeItem('autoflow:studio:mock:scheduled-tasks:v1'); useScheduledTaskStore.setState({ tasks: [], loading: false, error: null }) })
afterEach(cleanup)
it('shows a creation validation error without closing the form or creating a task', async () => {
  render(<ScheduledTasksDialog open onClose={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: '创建任务' }))
  fireEvent.click(screen.getAllByRole('button', { name: '创建任务' }).at(-1)!)
  expect(await screen.findByText('请输入任务名称')).toBeDefined()
  expect(screen.getByRole('heading', { name: '创建计划任务' })).toBeDefined()
  expect(useScheduledTaskStore.getState().tasks).toEqual([])
})
it('shows execution errors and retains the task instead of falsely reporting running', async () => {
  await mockRequest('http://autoflow-studio.mock/api/scheduled-tasks', { method: 'POST', body: JSON.stringify({ name: 'missing workflow', workflow_id: 'missing.json', enabled: true, trigger: { type: 'startup' } }) })
  render(<ScheduledTasksDialog open onClose={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: '执行' }))
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('工作流不存在'))
  expect(screen.getByRole('heading', { name: 'missing workflow' })).toBeDefined()
  expect(screen.queryByRole('button', { name: '停止' })).toBeNull()
})
it('documents the required AutoFlow token for webhook triggers', async () => {
  render(<ScheduledTasksDialog open onClose={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: '创建任务' }))
  fireEvent.click(screen.getByRole('button', { name: 'Webhook' }))
  expect(screen.getByText(/必须携带 x-autoflow-token 请求头/)).toBeDefined()
  expect(screen.getByText(/x-autoflow-token: <AutoFlow 运行令牌>/)).toBeDefined()
})
