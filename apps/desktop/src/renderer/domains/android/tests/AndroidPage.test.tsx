import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import type { RunRead } from '../../workflows/run-types'
import { runRecord } from '../../workflows/tests/run-fixtures'
import type { WorkflowContent } from '../../workflows/types'

const mocks = vi.hoisted(() => ({
  client: { request: vi.fn(), stream: vi.fn() },
  run: { active: null as RunRead | null, run: null as RunRead | null, uncertain: false, busy: false, message: null, canRetryStart: false, start: vi.fn(), retryStart: vi.fn(), refresh: vi.fn(), stop: vi.fn() },
}))
vi.mock('../../../app/ApiProvider', () => ({ useApi: () => ({ client: mocks.client, instanceId: 'instance' }) }))
vi.mock('../../workflows/hooks/useWorkflowRun', () => ({ useWorkflowRun: () => mocks.run }))
import { AndroidPage } from '../pages/AndroidPage'

const device = { deviceId: 'device-1', name: '安卓测试', runtimeId: 'lima', ownerRunId: null, control: 'idle', generation: 1, width: 720, height: 1280, imageId: 'image', androidStatus: 'ready', lastError: null }
const handoff = { handoffId: 'handoff', nodeId: 'device-manual', state: 'waiting', prompt: '手动操作', deadlineAt: new Date(Date.now() + 3600000).toISOString(), nativeSessionId: null, error: null, receipts: {} }
const manualRun = (content: WorkflowContent) => runRecord({ ...content, runId: 'manual-run', workflowId: content.document.id, target: { kind: 'android', deviceId: device.deviceId }, state: 'waiting_manual', handoff })
function setup() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const page = () => <QueryClientProvider client={query}><AndroidPage /></QueryClientProvider>
  const result = render(page())
  return { ...result, update: () => result.rerender(page()) }
}
beforeEach(() => {
  vi.clearAllMocks()
  Object.assign(mocks.run, { active: null, run: null, uncertain: false, busy: false })
  mocks.client.request.mockImplementation(async (path: string) => path.endsWith('/environment') ? { available: true, message: '运行环境可用' } : path.endsWith('/devices') ? [device] : runRecord())
})
afterEach(cleanup)

it('one device button starts only a manual node and opens once after admission, never on a refresh', async () => {
  const page = setup()
  const button = await screen.findByRole('button', { name: '打开操作窗口' })
  await waitFor(() => expect(button).toBeEnabled())
  await userEvent.click(button)
  const [content, target] = mocks.run.start.mock.calls[0] as [WorkflowContent, unknown]
  expect(target).toEqual({ kind: 'android', deviceId: device.deviceId })
  expect(content.document.nodes.map(n => n.type)).toEqual(['android_manual'])
  mocks.run.active = manualRun(content)
  page.update()
  await waitFor(() => expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/workflows/runs/manual-run/handoffs/handoff/open', expect.objectContaining({ method: 'POST' })))
  mocks.run.active = { ...mocks.run.active, latestSeq: 5, handoff: { ...handoff, state: 'closed' } }
  page.update()
  expect(mocks.client.request.mock.calls.filter(([path]) => path.endsWith('/open'))).toHaveLength(1)
  expect(screen.getByRole('button', { name: '结束操作' })).toBeEnabled()
  await userEvent.click(screen.getByRole('button', { name: '结束操作' }))
  expect(mocks.client.request).toHaveBeenCalledWith('/api/v1/workflows/runs/manual-run/handoffs/handoff/continue', expect.objectContaining({ method: 'POST' }))
})

it('returning to an active manual session only displays it and does not create another window', async () => {
  mocks.run.active = manualRun({ document: { id: 'existing', name: '手动操作', schemaVersion: 1, nodes: [{ id: 'device-manual', label: 'manual', type: 'android_manual', config: {} }], edges: [], variables: [] }, layout: { nodes: {}, viewport: { x: 0, y: 0, zoom: 1 } } })
  setup()
  await screen.findByText('安卓测试')
  expect(mocks.run.start).not.toHaveBeenCalled()
  expect(mocks.client.request.mock.calls.some(([path]) => path.endsWith('/open'))).toBe(false)
  const buttons = screen.getAllByRole('button', { name: '打开操作窗口' })
  expect(buttons[0]).toBeDisabled()
  expect(buttons[1]).toBeEnabled()
})

it('unverified global run state prevents opening even when the device was idle', async () => {
  mocks.run.uncertain = true
  setup()
  expect(await screen.findByRole('button', { name: '打开操作窗口' })).toBeDisabled()
})
