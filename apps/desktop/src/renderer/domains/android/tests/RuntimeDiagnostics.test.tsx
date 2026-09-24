import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { RuntimeDiagnostics } from '../components/RuntimeDiagnostics'
import type { AndroidManagementApi, ManagementEnvironment } from '../management-api'

afterEach(cleanup)

it('shows explicit unknown checks and disabled capability reasons', async () => {
  const environment: ManagementEnvironment = {
      available: false,
      platformSupported: false,
      runtimeId: 'redroid',
      message: '平台不支持',
      images: [],
      cpuCount: 0,
      memoryMb: 0,
      checkedAt: '2026-09-22T00:00:00Z',
      checks: {
        platform: { status: 'unsupported', code: 'ANDROID_PLATFORM_UNSUPPORTED', message: '当前平台不支持安卓运行时', action: null },
        adb: { status: 'unknown', code: 'ANDROID_CHECK_UNAVAILABLE', message: '运行环境不可访问', action: null },
      },
      capabilities: { management: false, control: false, images: 'unknown', workflow: false },
    }
  const api: Pick<AndroidManagementApi, 'environment' | 'capabilities' | 'checkEnvironment'> = {
    environment: vi.fn(async () => environment),
    capabilities: vi.fn(async () => ({ management: false, control: false, images: 'unknown', bulk: false, backups: false, workflow: false, reasons: { workflow: '安卓管理不通过工作流执行入口' } })),
    checkEnvironment: vi.fn(),
  }

  render(<QueryClientProvider client={new QueryClient()}><RuntimeDiagnostics api={api} /></QueryClientProvider>)

  expect(await screen.findByText('当前平台不支持安卓运行时')).toBeVisible()
  expect(screen.getByText('运行环境不可访问')).toBeVisible()
  expect(screen.getByText('安卓管理不通过工作流执行入口')).toBeVisible()
})

it('starts an explicit check and retains the prior snapshot when it fails', async () => {
  const environment: ManagementEnvironment = { available: false, platformSupported: true, runtimeId: 'redroid', message: '旧诊断快照', images: [], cpuCount: 0, memoryMb: 0, checkedAt: '2026-09-22T00:00:00Z', checks: { adb: { status: 'fail', code: 'ADB_DOWN', message: 'ADB 不可用', action: '安装 platform-tools' } }, capabilities: { management: false, control: false, images: 'unknown', workflow: false } }
  const api = {
    environment: vi.fn(async () => environment),
    capabilities: vi.fn(async () => ({ management: false, control: false, images: 'unknown', bulk: false, backups: false, workflow: false, reasons: {} })),
    checkEnvironment: vi.fn().mockRejectedValueOnce(new Error('环境检查连接中断')),
    operationByRequest: vi.fn(async () => ({ operationId: 'check-op', requestId: 'r', targetId: 'environment', action: 'check', state: 'needs_verification', stageCode: 'verify', stageLabel: '待核实', attempt: 1, createdAt: '' })),
    verify: vi.fn(async () => ({ operationId: 'check-op', requestId: 'r', targetId: 'environment', action: 'check', state: 'succeeded', stageCode: 'verified', stageLabel: '已核实', attempt: 1, createdAt: '' })),
  }
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RuntimeDiagnostics api={api} /></QueryClientProvider>)
  expect(await screen.findByText(/安装 platform-tools/)).toBeVisible()
  expect(screen.getByText('2026-09-22T00:00:00Z')).toHaveAttribute('dateTime', '2026-09-22T00:00:00Z')
  await userEvent.click(screen.getByRole('button', { name: '重新检查' }))
  expect(api.checkEnvironment).toHaveBeenCalledWith({ requestId: expect.any(String) })
  expect(await screen.findByRole('alert')).toHaveTextContent('环境检查连接中断')
  expect(screen.getByText('ADB 不可用')).toBeVisible()
  expect(screen.getByText(/旧诊断快照/)).toBeVisible()
  expect(screen.getByText(/本次检查结果未知/)).toBeVisible()
  await userEvent.click(screen.getByRole('button', { name: '核实原检查请求' }))
  expect(api.verify).toHaveBeenCalledWith('check-op', { requestId: api.checkEnvironment.mock.calls[0][0].requestId })
  expect(api.checkEnvironment).toHaveBeenCalledTimes(1)
})


it.each([
  [1073741824, 2147483648, '1.00 GiB', '2.00 GiB'],
  [0, null, '0.00 GiB', '未知'],
  [undefined, undefined, '未知', '未知'],
])('separates host and VM disk availability including zero and unknown (%s, %s)', async (host, vm, hostText, vmText) => {
  const api = {
    environment: vi.fn(async () => ({ available: true, platformSupported: true, runtimeId: 'redroid', message: '可用', checkedAt: '2026-09-24T00:00:00Z', checks: {}, capabilities: {}, hostWorkspaceFreeBytes: host, vmDockerFreeBytes: vm })),
    capabilities: vi.fn(async () => ({ management: true, control: true, images: true, bulk: true, backups: true, workflow: false, reasons: {} })),
  } as unknown as AndroidManagementApi
  render(<QueryClientProvider client={new QueryClient()}><RuntimeDiagnostics api={api} /></QueryClientProvider>)
  const hostRegion = await screen.findByRole('group', { name: '宿主工作区可用空间' })
  const vmRegion = screen.getByRole('group', { name: 'Linux VM Docker 可用空间' })
  expect(within(hostRegion).getByText(hostText)).toBeVisible()
  expect(within(vmRegion).getByText(vmText)).toBeVisible()
})
