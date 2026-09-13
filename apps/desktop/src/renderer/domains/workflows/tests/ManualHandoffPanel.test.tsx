import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ManualHandoffPanel } from '../components/ManualHandoffPanel'
import { runApi, runRecord } from './run-fixtures'
import { DeviceSelect } from '../../android/components/DeviceControls'

afterEach(cleanup)
const handoff = { handoffId: 'h1', nodeId: 'n1', state: 'closed', prompt: '打开设置子页', deadlineAt: new Date(Date.now() + 600000).toISOString(), nativeSessionId: null, error: null, receipts: {} }

it('closing a native window leaves manual continuation explicit and sends one command', async () => {
  const api = runApi()
  let finish!: () => void
  api.handoff = vi.fn(() => new Promise<ReturnType<typeof runRecord>>(resolve => { finish = () => resolve(runRecord()) }))
  render(<ManualHandoffPanel run={runRecord({ state: 'waiting_manual', handoff })} api={api} connected onRefresh={vi.fn()} onStop={vi.fn()} />)
  expect(screen.getByText('窗口已关闭，工作流仍在等待。')).toBeVisible()
  expect(api.handoff).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('button', { name: '完成并继续' }))
  expect(screen.getByRole('button', { name: '完成并继续' })).toBeDisabled()
  expect(api.handoff).toHaveBeenCalledTimes(1)
  expect(api.handoff).toHaveBeenCalledWith('run-1', 'h1', 'continue', expect.any(String))
  finish()
  await waitFor(() => expect(screen.getByRole('button', { name: '完成并继续' })).toBeEnabled())
})

it('an uncertain response retries the same command ID rather than opening a second session', async () => {
  const api = runApi()
  vi.mocked(api.handoff).mockRejectedValueOnce(new Error('连接中断'))
  render(<ManualHandoffPanel run={runRecord({ state: 'waiting_manual', handoff })} api={api} connected onRefresh={vi.fn()} onStop={vi.fn()} />)
  await userEvent.click(screen.getByRole('button', { name: '打开操作窗口' }))
  await userEvent.click(await screen.findByRole('button', { name: '按原编号重试' }))
  expect(vi.mocked(api.handoff).mock.calls[0]).toEqual(vi.mocked(api.handoff).mock.calls[1])
})

it('an occupied or unverified device cannot be selected', () => {
  const base = { cpu: 1, memoryMb: 1536, dpi: 320, androidVersion: '13', architecture: 'arm64', dataRetained: false, deleted: false, deviceId: 'device', name: '安卓测试', runtimeId: 'lima', ownerRunId: 'run', control: 'manual', generation: 1, width: 720, height: 1280, imageId: 'image', androidStatus: 'ready', lastError: null }
  render(<DeviceSelect devices={[base, { ...base, deviceId: 'unknown', control: 'idle', androidStatus: 'unknown' }]} value="" disabled={false} onChange={vi.fn()} />)
  for (const option of screen.getAllByRole('option').slice(1)) expect(option).toBeDisabled()
})
