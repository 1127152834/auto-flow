import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { ApiClientError } from '../../../shared/api/client'
import { DeviceConsole, type ConsoleProps } from '../components/DeviceConsole'
import type { FleetApi } from '../fleet-api'
import { devices, fixtureSession } from './prototype-fixtures'

afterEach(cleanup)

function props(api: Partial<FleetApi>): ConsoleProps {
  return {
    device: devices[0], session: fixtureSession(true), api: api as FleetApi, image: 'fixture.png',
    onBack: vi.fn(), onSession: vi.fn(), onOpen: vi.fn(), onManage: vi.fn(), onRefresh: vi.fn(),
  }
}

it.each([
  ['ANDROID_INSTALL_VERIFY_FAILED', 422, true],
  ['ANDROID_OPERATION_UNKNOWN', 503, false],
] as const)('unlocks APK installation only when verification conclusively failed: %s', async (code, status, unlocked) => {
  const api = {
    install: vi.fn().mockRejectedValue(new Error('response lost')),
    verifyApp: vi.fn().mockRejectedValue(new ApiClientError('核验结果', status, code)),
  }
  const view = render(<DeviceConsole {...props(api)} />)
  await userEvent.upload(view.container.querySelector<HTMLInputElement>('input[type=file]')!, new File(['APK'], 'test.apk'))
  expect(screen.getByRole('button', { name: '上传 APK' })).toBeDisabled()
  await userEvent.click(await screen.findByRole('button', { name: '按原请求核实' }))
  await screen.findByText('核验结果')
  expect(screen.getByRole('button', { name: '上传 APK' }).hasAttribute('disabled')).toBe(!unlocked)
  expect(api.install).toHaveBeenCalledTimes(1)
})

it('verifies an uncertain install with its original generation after the session changes', async () => {
  const api = { install: vi.fn().mockRejectedValue(new Error('response lost')), verifyApp: vi.fn().mockRejectedValue(new Error('still unknown')) }
  const initial = props(api)
  const view = render(<DeviceConsole {...initial} />)
  await userEvent.upload(view.container.querySelector<HTMLInputElement>('input[type=file]')!, new File(['APK'], 'test.apk'))
  await screen.findByRole('button', { name: '按原请求核实' })
  view.rerender(<DeviceConsole {...initial} session={{ ...initial.session!, generation: initial.session!.generation + 1 }} />)
  await userEvent.click(screen.getByRole('button', { name: '按原请求核实' }))
  expect(api.verifyApp).toHaveBeenCalledWith(expect.anything(), expect.any(String), initial.session!.generation)
})


it.each(['generation', 'closed', 'unmount'])('ignores an install verification response after the control changes: %s', async (change) => {
  let finish!: (session: ReturnType<typeof fixtureSession>) => void
  const api = { install: vi.fn().mockRejectedValue(new Error('lost')),
    verifyApp: vi.fn(() => new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finish = resolve })) }
  const initial = props(api)
  const view = render(<DeviceConsole {...initial} />)
  await userEvent.upload(view.container.querySelector<HTMLInputElement>('input[type=file]')!, new File(['APK'], 'test.apk'))
  await userEvent.click(await screen.findByRole('button', { name: '按原请求核实' }))
  if (change === 'unmount') view.unmount()
  else view.rerender(<DeviceConsole {...initial} session={change === 'closed' ? { ...initial.session!, state: 'closed' } : { ...initial.session!, generation: initial.session!.generation + 1 }} />)
  await act(async () => { finish(initial.session!) })
  expect(initial.onSession).not.toHaveBeenCalled()
})

it('ignores an APK installation response after the session closes', async () => {
  let finish!: (session: ReturnType<typeof fixtureSession>) => void
  const api = { install: vi.fn(() => new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finish = resolve })) }
  const initial = props(api)
  const view = render(<DeviceConsole {...initial} />)
  await userEvent.upload(view.container.querySelector<HTMLInputElement>('input[type=file]')!, new File(['APK'], 'test.apk'))
  view.rerender(<DeviceConsole {...initial} session={{ ...initial.session!, state: 'closed' }} />)
  await act(async () => { finish(initial.session!) })
  expect(initial.onSession).not.toHaveBeenCalled()
})

it('does not send queued text or publish an old input response after the session closes', async () => {
  let finish!: (session: ReturnType<typeof fixtureSession>) => void
  const first = new Promise<ReturnType<typeof fixtureSession>>((resolve) => { finish = resolve })
  const api = { input: vi.fn().mockReturnValueOnce(first).mockResolvedValue(fixtureSession(true)) }
  const initial = { ...props(api), initialText: '中文' }
  const view = render(<DeviceConsole {...initial} />)
  await userEvent.click(screen.getByRole('button', { name: '发送到设备' }))
  await waitFor(() => expect(api.input).toHaveBeenCalledTimes(1))
  await userEvent.click(screen.getByRole('button', { name: '发送到设备' }))
  view.rerender(<DeviceConsole {...initial} session={null} />)
  await act(async () => { finish(initial.session!); await first })
  expect(api.input).toHaveBeenCalledTimes(1)
  expect(initial.onSession).not.toHaveBeenCalled()
})

it('does not send old-generation input when opening a native window blurs the page', async () => {
  const next = { ...fixtureSession(true), endpoint: 'native' as const, generation: 2 }
  const api = {
    input: vi.fn().mockRejectedValue(new Error('控制权已变化，请刷新会话')),
    action: vi.fn(async () => {
      window.dispatchEvent(new Event('blur'))
      await Promise.resolve()
      return next
    }),
  }
  const initial = props(api)
  render(<DeviceConsole {...initial} />)
  await userEvent.click(screen.getByRole('button', { name: '更多设备操作' }))
  await userEvent.click(screen.getByRole('button', { name: '独立 Mac 窗口' }))
  await waitFor(() => expect(initial.onSession).toHaveBeenCalledWith(next))
  expect(api.input).not.toHaveBeenCalled()
  expect(screen.queryByText('控制权已变化，请刷新会话')).not.toBeInTheDocument()
})
