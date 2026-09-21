import '@testing-library/jest-dom/vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { RuntimeDiagnostics } from '../components/RuntimeDiagnostics'
import type { AndroidManagementApi } from '../management-api'

it('shows explicit unknown checks and disabled capability reasons', async () => {
  const api: AndroidManagementApi = {
    environment: vi.fn(async () => ({
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
    })),
    capabilities: vi.fn(async () => ({ management: false, control: false, images: 'unknown', bulk: false, backups: false, workflow: false, reasons: { workflow: '安卓管理不通过工作流执行入口' } })),
  }

  render(<QueryClientProvider client={new QueryClient()}><RuntimeDiagnostics api={api} /></QueryClientProvider>)

  expect(await screen.findByText('当前平台不支持安卓运行时')).toBeVisible()
  expect(screen.getByText('运行环境不可访问')).toBeVisible()
  expect(screen.getByText('安卓管理不通过工作流执行入口')).toBeVisible()
})
