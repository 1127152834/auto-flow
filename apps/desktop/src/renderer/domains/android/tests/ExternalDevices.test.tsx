import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { AiTestApi } from '../ai-test-api'
import { ExternalDevices } from '../components/ExternalDevices'

afterEach(cleanup)

function setup(externalDevices: unknown) {
  const api = { externalDevices } as unknown as AiTestApi
  const onSelect = vi.fn()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ExternalDevices api={api} onSelect={onSelect} /></QueryClientProvider>)
  return { api, onSelect }
}

it('renders each state and only lets available devices be selected', async () => {
  const { onSelect } = setup(vi.fn().mockResolvedValue([
    { serial: 'emulator-5554', state: 'device', model: 'Pixel 8' },
    { serial: 'R58M', state: 'offline', model: null },
    { serial: 'ABC123', state: 'unauthorized', model: null },
    { serial: 'XYZ', state: 'recovery', model: null },
  ]))
  expect(await screen.findByText('Pixel 8')).toBeVisible()
  expect(screen.getByText('可用')).toBeVisible()
  expect(screen.getByText('离线')).toBeVisible()
  expect(screen.getByText('未授权')).toBeVisible()
  expect(screen.getByText('请在设备上允许 USB 调试')).toBeVisible()
  expect(screen.getByText('不可用（recovery）')).toBeVisible()
  expect(screen.getByText('外接设备可能同时被其他程序操作')).toBeVisible()
  const buttons = screen.getAllByRole('button', { name: /^选择/ })
  expect(buttons).toHaveLength(4)
  expect(buttons.filter((button) => (button as HTMLButtonElement).disabled)).toHaveLength(3)
  await userEvent.click(screen.getByRole('button', { name: '选择 emulator-5554' }))
  expect(onSelect).toHaveBeenCalledWith('emulator-5554')
})

it('shows the empty hint and refetches on refresh', async () => {
  const { api } = setup(vi.fn().mockResolvedValue([]))
  expect(await screen.findByText('启动模拟器或连接设备后点击刷新；由 AutoFlow 创建的设备不在此列出')).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '刷新' }))
  await waitFor(() => expect(api.externalDevices).toHaveBeenCalledTimes(2))
})

it('surfaces the backend error message', async () => {
  setup(vi.fn().mockRejectedValue(new Error('未找到 adb')))
  expect(await screen.findByText('未找到 adb')).toBeVisible()
})
